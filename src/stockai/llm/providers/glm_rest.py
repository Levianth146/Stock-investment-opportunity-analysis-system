"""GLM (Z.AI) chat/completions qua requests REST (Q3:A — không OpenAI SDK)."""
from __future__ import annotations

import json
import os
from typing import Any

import requests

DEFAULT_MODEL = "glm-4.7-flash"
DEFAULT_BASE_URL = "https://api.z.ai/api/paas/v4/"
DEFAULT_TIMEOUT_SEC = 120.0


class GlmRestError(RuntimeError):
    """Lỗi gọi GLM REST."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        quota_exhausted: bool = False,
        code_1113: bool = False,
        body: str = "",
        retry_after: float | None = None,
    ):
        super().__init__(message)
        self.status_code = status_code
        self.quota_exhausted = quota_exhausted
        self.code_1113 = code_1113
        self.body = body
        self.retry_after = retry_after


def _parse_retry_after(resp: Any) -> float | None:
    """Đọc header Retry-After (giây). Trả None nếu thiếu/không parse được."""
    try:
        headers = getattr(resp, "headers", None) or {}
        raw = headers.get("Retry-After") or headers.get("retry-after")
    except Exception:
        return None
    if raw is None:
        return None
    try:
        return float(str(raw).strip())
    except (TypeError, ValueError):
        return None


def _api_key() -> str | None:
    key = os.environ.get("ZAI_API_KEY")
    if key and str(key).strip():
        return str(key).strip()
    return None


def looks_like_code_1113(body: str) -> bool:
    """Z.AI code 1113 Insufficient balance — block paid model, không retry."""
    b = body or ""
    compact = b.replace(" ", "")
    if '"code":1113' in compact or "'code':1113" in compact:
        return True
    bl = b.lower()
    return "1113" in b and ("insufficient" in bl or "balance" in bl)


def looks_like_quota_exhausted(status_code: int | None, body: str) -> bool:
    """Hết hạn mức / số dư — không backoff; failover ngay."""
    if looks_like_code_1113(body):
        return True
    b = (body or "").lower()
    if "insufficient balance" in b or "insufficient_balance" in b:
        return True
    if "resource_exhausted" in b:
        return True
    if "quota" in b and any(x in b for x in ("exceed", "exhaust", "limit: 0", '"limit":0', '"limit": 0')):
        return True
    if status_code in (402, 403) and ("balance" in b or "quota" in b or "credit" in b):
        return True
    if status_code == 429 and ("quota" in b or "daily" in b or "balance" in b):
        return True
    return False


def chat_completions_json(
    prompt: str,
    *,
    model: str = DEFAULT_MODEL,
    base_url: str = DEFAULT_BASE_URL,
    temperature: float = 0.0,
    timeout_sec: float = DEFAULT_TIMEOUT_SEC,
) -> dict:
    """POST {base_url}/chat/completions; parse JSON object từ message content.

    Auth: Bearer ``ZAI_API_KEY``. ``response_format: json_object``.
    Gắn ``_usage`` nếu có. Không in giá trị khóa.
    """
    key = _api_key()
    if not key:
        raise GlmRestError("missing ZAI_API_KEY")

    base = base_url.rstrip("/") + "/"
    url = base + "chat/completions"
    body: dict[str, Any] = {
        "model": model,
        "messages": [
            {"role": "system", "content": "Trả về đúng một JSON object, không markdown."},
            {"role": "user", "content": prompt},
        ],
        "temperature": temperature,
        "response_format": {"type": "json_object"},
    }
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {key}",
    }
    try:
        from stockai.llm.netcount import bump_network_call

        bump_network_call()
    except RuntimeError:
        raise
    try:
        resp = requests.post(url, headers=headers, json=body, timeout=timeout_sec)
    except requests.Timeout as e:
        raise GlmRestError("timeout") from e
    except requests.RequestException as e:
        raise GlmRestError(f"request_error: {type(e).__name__}") from e

    raw_body = ""
    try:
        raw_body = resp.text or ""
    except Exception:
        raw_body = ""

    if resp.status_code >= 400:
        code_1113 = looks_like_code_1113(raw_body)
        quota = looks_like_quota_exhausted(resp.status_code, raw_body)
        if quota:
            raise GlmRestError(
                "quota_exhausted",
                status_code=resp.status_code,
                quota_exhausted=True,
                code_1113=code_1113,
                body=raw_body[:800],
            )
        if resp.status_code == 429:
            raise GlmRestError(
                "rate_limited",
                status_code=429,
                body=raw_body[:800],
                retry_after=_parse_retry_after(resp),
            )
        raise GlmRestError(
            f"http_{resp.status_code}",
            status_code=resp.status_code,
            body=raw_body[:800],
        )

    try:
        data = resp.json()
    except ValueError as e:
        raise GlmRestError("invalid_json_envelope") from e

    text = _extract_content(data)
    if not text:
        raise GlmRestError("empty_response")
    # Một số model bọc ```json
    text = text.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:].lstrip()
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as e:
        raise GlmRestError("parse_json_failed") from e
    if not isinstance(parsed, dict):
        raise GlmRestError("json_not_object")
    usage = _extract_usage(data)
    if usage:
        parsed["_usage"] = usage
    return parsed


def _extract_usage(data: dict) -> dict[str, int]:
    usage = data.get("usage") or {}
    if not isinstance(usage, dict):
        return {}
    out: dict[str, int] = {}
    pt = usage.get("prompt_tokens")
    ct = usage.get("completion_tokens")
    if isinstance(pt, int):
        out["input_tokens"] = pt
    if isinstance(ct, int):
        out["output_tokens"] = ct
    return out


def _extract_content(data: dict) -> str:
    choices = data.get("choices") or []
    if not choices:
        return ""
    msg = (choices[0] or {}).get("message") or {}
    content = msg.get("content")
    if isinstance(content, str):
        return content
    return ""
