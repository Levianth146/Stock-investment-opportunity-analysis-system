"""Gemini generateContent qua requests REST (Q3:A — không SDK).

Theo docs ai.google.dev (generateContent + ThinkingConfig):
- ``generationConfig.maxOutputTokens`` — trần token đầu ra (cần đủ lớn; thinking
  cũng đếm vào ngân sách nếu không hạ thinkingLevel).
- ``generationConfig.thinkingConfig.thinkingLevel`` — MINIMAL (thấp nhất) hoặc
  LOW khi model (vd gemini-3.8-flash) không hỗ trợ MINIMAL.
- ``responseMimeType: application/json`` + ``responseSchema`` khi có schema_hint.

Empty content hoặc finishReason=MAX_TOKENS mà không có text → lỗi retryable
``llm_empty_output``; thử lại 1 lần với maxOutputTokens nhân đôi — KHÔNG coi là thành công.
"""
from __future__ import annotations

import json
import os
from typing import Any

import requests

DEFAULT_MODEL = "gemini-3.8-flash"
DEFAULT_MAX_OUTPUT_TOKENS = 2048
_API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"

# Model 3.x không liệt kê MINIMAL trong bảng Thinking levels → dùng LOW
_NO_MINIMAL_SUBSTRINGS = ("3.8-flash", "3.7-flash", "3.1-pro")


class GeminiRestError(RuntimeError):
    """Lỗi gọi Gemini REST."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        quota_exhausted: bool = False,
        empty_output: bool = False,
        body: str = "",
        finish_reason: str | None = None,
        retry_after: float | None = None,
    ):
        super().__init__(message)
        self.status_code = status_code
        self.quota_exhausted = quota_exhausted
        self.empty_output = empty_output
        self.body = body
        self.finish_reason = finish_reason
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
    key = os.environ.get("GEMINI_API_KEY")
    if key and str(key).strip():
        return str(key).strip()
    return None


def looks_like_quota_exhausted(status_code: int | None, body: str) -> bool:
    """Daily/quota hết — không backoff; failover ngay."""
    b = (body or "").lower()
    if "resource_exhausted" in b:
        return True
    if "insufficient" in b and ("quota" in b or "balance" in b or "credit" in b):
        return True
    if "quota" in b and any(x in b for x in ("exceed", "exhaust", "limit: 0", '"limit": 0', '"limit":0')):
        return True
    if "limit: 0" in b or '"limit": 0' in b or '"limit":0' in b:
        return True
    # Free tier daily (vd limit: 20) vẫn là quota — block persistent
    if status_code == 429 and (
        "quota" in b
        or "daily" in b
        or "per_day" in b
        or "perday" in b
        or "generate_content_free_tier" in b
        or "free_tier" in b
    ):
        return True
    return False


def thinking_level_for_model(model: str, preferred: str = "lowest") -> str:
    """Map 'lowest' → MINIMAL (hoặc LOW nếu model không hỗ trợ MINIMAL)."""
    pref = (preferred or "lowest").strip().lower()
    if pref in ("lowest", "minimal", "min"):
        for sub in _NO_MINIMAL_SUBSTRINGS:
            if sub in (model or ""):
                return "LOW"
        return "MINIMAL"
    if pref in ("low", "medium", "high", "minimal"):
        return pref.upper()
    return "MINIMAL"


def generate_content_json(
    prompt: str,
    *,
    model: str = DEFAULT_MODEL,
    temperature: float = 0.0,
    timeout_sec: float = 90.0,
    schema_hint: dict | None = None,
    max_output_tokens: int = DEFAULT_MAX_OUTPUT_TOKENS,
    thinking_level: str = "lowest",
) -> dict:
    """POST generateContent; trả dict JSON đã parse từ text response.

    Auth: header ``x-goog-api-key`` từ ``GEMINI_API_KEY``.
    Gắn ``_usage`` (token counts) nếu API trả usageMetadata — caller gỡ trước khi validate.
    Không in giá trị khóa.
    """
    key = _api_key()
    if not key:
        raise GeminiRestError("missing GEMINI_API_KEY")

    tokens = max(int(max_output_tokens or DEFAULT_MAX_OUTPUT_TOKENS), DEFAULT_MAX_OUTPUT_TOKENS)
    level = thinking_level_for_model(model, thinking_level)
    last_empty: GeminiRestError | None = None

    # 1 lần gọi + tối đa 1 retry khi empty / MAX_TOKENS không có text (nhân đôi tokens)
    for attempt in range(2):
        data = _post_generate(
            prompt,
            model=model,
            key=key,
            temperature=temperature,
            timeout_sec=timeout_sec,
            schema_hint=schema_hint,
            max_output_tokens=tokens,
            thinking_level=level,
        )
        text, finish_reason = _extract_text_and_finish(data)
        if not text:
            err = GeminiRestError(
                "llm_empty_output",
                empty_output=True,
                finish_reason=finish_reason,
                body=f"finishReason={finish_reason or 'none'}",
            )
            last_empty = err
            # Retry một lần với maxOutputTokens ×2 (kể cả khi finishReason khác MAX_TOKENS)
            if attempt == 0:
                tokens = tokens * 2
                continue
            raise err

        try:
            parsed = json.loads(text)
        except json.JSONDecodeError as e:
            # MAX_TOKENS cắt giữa JSON → cũng coi empty/truncated retryable lần đầu
            if attempt == 0 and (finish_reason or "").upper() == "MAX_TOKENS":
                tokens = tokens * 2
                last_empty = GeminiRestError(
                    "llm_empty_output",
                    empty_output=True,
                    finish_reason=finish_reason,
                    body="truncated_json_max_tokens",
                )
                continue
            raise GeminiRestError("parse_json_failed", finish_reason=finish_reason) from e
        if not isinstance(parsed, dict):
            raise GeminiRestError("json_not_object", finish_reason=finish_reason)
        usage = _extract_usage(data)
        if usage:
            parsed["_usage"] = usage
        if attempt > 0:
            parsed.setdefault("_meta_flags", [])
            if isinstance(parsed.get("_meta_flags"), list):
                parsed["_meta_flags"].append("llm_empty_output_retried")
        return parsed

    if last_empty:
        raise last_empty
    raise GeminiRestError("llm_empty_output", empty_output=True)


def _post_generate(
    prompt: str,
    *,
    model: str,
    key: str,
    temperature: float,
    timeout_sec: float,
    schema_hint: dict | None,
    max_output_tokens: int,
    thinking_level: str,
) -> dict:
    url = f"{_API_BASE}/{model}:generateContent"
    generation_config: dict[str, Any] = {
        "temperature": temperature,
        "responseMimeType": "application/json",
        "maxOutputTokens": int(max_output_tokens),
        "thinkingConfig": {
            "thinkingLevel": thinking_level,
            "includeThoughts": False,
        },
    }
    if schema_hint:
        generation_config["responseSchema"] = schema_hint

    body = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": generation_config,
    }
    headers = {
        "Content-Type": "application/json",
        "x-goog-api-key": key,
    }
    try:
        from stockai.llm.netcount import bump_network_call

        bump_network_call()
    except RuntimeError:
        raise
    try:
        resp = requests.post(url, headers=headers, json=body, timeout=timeout_sec)
    except requests.Timeout as e:
        raise GeminiRestError("timeout") from e
    except requests.RequestException as e:
        raise GeminiRestError(f"request_error: {type(e).__name__}") from e

    raw_body = ""
    try:
        raw_body = resp.text or ""
    except Exception:
        raw_body = ""

    if resp.status_code >= 400:
        quota = looks_like_quota_exhausted(resp.status_code, raw_body)
        if quota:
            raise GeminiRestError(
                "quota_exhausted",
                status_code=resp.status_code,
                quota_exhausted=True,
                body=raw_body[:800],
            )
        if resp.status_code == 429:
            raise GeminiRestError(
                "rate_limited",
                status_code=429,
                body=raw_body[:800],
                retry_after=_parse_retry_after(resp),
            )
        raise GeminiRestError(
            f"http_{resp.status_code}",
            status_code=resp.status_code,
            body=raw_body[:800],
        )

    try:
        data = resp.json()
    except ValueError as e:
        raise GeminiRestError("invalid_json_envelope") from e
    if not isinstance(data, dict):
        raise GeminiRestError("invalid_json_envelope")
    return data


def _extract_usage(data: dict) -> dict[str, int]:
    meta = data.get("usageMetadata") or {}
    if not isinstance(meta, dict):
        return {}
    out: dict[str, int] = {}
    pt = meta.get("promptTokenCount")
    ct = meta.get("candidatesTokenCount")
    tt = meta.get("thoughtsTokenCount")
    if isinstance(pt, int):
        out["input_tokens"] = pt
    if isinstance(ct, int):
        out["output_tokens"] = ct
    if isinstance(tt, int):
        out["thoughts_tokens"] = tt
    return out


def _extract_text_and_finish(data: dict) -> tuple[str, str | None]:
    cands = data.get("candidates") or []
    if not cands:
        return "", None
    cand0 = cands[0] or {}
    finish = cand0.get("finishReason")
    finish_s = str(finish) if finish is not None else None
    parts = (cand0.get("content") or {}).get("parts") or []
    chunks: list[str] = []
    for p in parts:
        if not isinstance(p, dict):
            continue
        # Bỏ thought parts nếu API vẫn trả (includeThoughts=false thường không có)
        if p.get("thought") is True:
            continue
        if isinstance(p.get("text"), str):
            chunks.append(p["text"])
    return "".join(chunks).strip(), finish_s


def _extract_text(data: dict) -> str:
    text, _ = _extract_text_and_finish(data)
    return text
