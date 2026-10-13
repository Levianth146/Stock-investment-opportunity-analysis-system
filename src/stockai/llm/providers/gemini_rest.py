"""Gemini generateContent qua requests REST (Q3:A — không SDK)."""
from __future__ import annotations

import json
import os
from typing import Any

import requests

DEFAULT_MODEL = "gemini-3.8-flash"
_API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"


class GeminiRestError(RuntimeError):
    """Lỗi gọi Gemini REST."""

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
    # Một số gói free hết hạn mức ngày trả 429 kèm quota
    if status_code == 429 and ("quota" in b or "daily" in b or "per_day" in b or "perday" in b):
        return True
    return False


def generate_content_json(
    prompt: str,
    *,
    model: str = DEFAULT_MODEL,
    temperature: float = 0.0,
    timeout_sec: float = 45.0,
    schema_hint: dict | None = None,
) -> dict:
    """POST generateContent; trả dict JSON đã parse từ text response.

    Auth: header ``x-goog-api-key`` từ ``GEMINI_API_KEY``.
    Gắn ``_usage`` (token counts) nếu API trả usageMetadata — caller gỡ trước khi validate.
    Không in giá trị khóa.
    """
    key = _api_key()
    if not key:
        raise GeminiRestError("missing GEMINI_API_KEY")

    url = f"{_API_BASE}/{model}:generateContent"
    generation_config: dict[str, Any] = {
        "temperature": temperature,
        "responseMimeType": "application/json",
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
                body=raw_body[:500],
            )
        if resp.status_code == 429:
            raise GeminiRestError("rate_limited", status_code=429, body=raw_body[:500])
        raise GeminiRestError(
            f"http_{resp.status_code}",
            status_code=resp.status_code,
            body=raw_body[:500],
        )

    try:
        data = resp.json()
    except ValueError as e:
        raise GeminiRestError("invalid_json_envelope") from e

    text = _extract_text(data)
    if not text:
        raise GeminiRestError("empty_response")
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as e:
        raise GeminiRestError("parse_json_failed") from e
    if not isinstance(parsed, dict):
        raise GeminiRestError("json_not_object")
    usage = _extract_usage(data)
    if usage:
        parsed["_usage"] = usage
    return parsed


def _extract_usage(data: dict) -> dict[str, int]:
    meta = data.get("usageMetadata") or {}
    if not isinstance(meta, dict):
        return {}
    out: dict[str, int] = {}
    pt = meta.get("promptTokenCount")
    ct = meta.get("candidatesTokenCount")
    if isinstance(pt, int):
        out["input_tokens"] = pt
    if isinstance(ct, int):
        out["output_tokens"] = ct
    return out


def _extract_text(data: dict) -> str:
    cands = data.get("candidates") or []
    if not cands:
        return ""
    parts = ((cands[0] or {}).get("content") or {}).get("parts") or []
    chunks: list[str] = []
    for p in parts:
        if isinstance(p, dict) and isinstance(p.get("text"), str):
            chunks.append(p["text"])
    return "".join(chunks).strip()
