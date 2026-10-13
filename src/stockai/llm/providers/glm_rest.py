"""GLM (Z.AI) chat/completions qua requests REST (Q3:A — không OpenAI SDK)."""
from __future__ import annotations

import json
import os
from typing import Any

import requests

DEFAULT_MODEL = "glm-5.3-flash"
DEFAULT_BASE_URL = "https://api.z.ai/api/paas/v4/"


class GlmRestError(RuntimeError):
    """Lỗi gọi GLM REST."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        quota_exhausted: bool = False,
        body: str = "",
    ):
        super().__init__(message)
        self.status_code = status_code
        self.quota_exhausted = quota_exhausted
        self.body = body


def _api_key() -> str | None:
    key = os.environ.get("ZAI_API_KEY")
    if key and str(key).strip():
        return str(key).strip()
    return None


def looks_like_quota_exhausted(status_code: int | None, body: str) -> bool:
    """Hết hạn mức / số dư — không backoff; failover ngay."""
    b = (body or "").lower()
    if "insufficient balance" in b or "insufficient_balance" in b:
        return True
    if "1113" in b and ("balance" in b or "insufficient" in b or "code" in b):
        return True
    if '"code":1113' in b.replace(" ", "") or '"code": 1113' in b:
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
    timeout_sec: float = 45.0,
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
        quota = looks_like_quota_exhausted(resp.status_code, raw_body)
        if quota:
            raise GlmRestError(
                "quota_exhausted",
                status_code=resp.status_code,
                quota_exhausted=True,
                body=raw_body[:500],
            )
        if resp.status_code == 429:
            raise GlmRestError("rate_limited", status_code=429, body=raw_body[:500])
        raise GlmRestError(
            f"http_{resp.status_code}",
            status_code=resp.status_code,
            body=raw_body[:500],
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
