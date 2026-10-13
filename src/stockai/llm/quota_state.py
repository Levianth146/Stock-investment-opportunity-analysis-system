"""Trạng thái quota LLM bền vững trên đĩa (bỏ qua model đã hết hạn mức).

File mặc định: ``data/llm_cache/_quota_state.json``
Hình dạng: ``{"provider/model": "ISO8601 blocked_until", ...}``
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_PATH = _REPO_ROOT / "data" / "llm_cache" / "_quota_state.json"

# "retry in 7h34m" / "RetryDelay": "7h34m52s" / "retryDelay": "45s"
_RETRY_IN_RE = re.compile(
    r"retry\s*(?:in|delay)?\s*[:=]?\s*[\"']?(?:([\d.]+)\s*h)?\s*(?:([\d.]+)\s*m)?\s*(?:([\d.]+)\s*s)?",
    re.IGNORECASE,
)
_RETRY_DELAY_JSON_RE = re.compile(
    r'"retryDelay"\s*:\s*"((?:\d+\s*h)?(?:\d+\s*m)?(?:\d+\s*s)?)"',
    re.IGNORECASE,
)


def default_quota_path(cache_dir: str | Path | None = None) -> Path:
    if cache_dir:
        return Path(cache_dir) / "_quota_state.json"
    return _DEFAULT_PATH


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _parse_iso(s: str) -> datetime | None:
    try:
        dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def parse_retry_delay_seconds(body: str) -> float | None:
    """Trích số giây từ body lỗi Gemini/GLM (retry in XhYm / retryDelay)."""
    if not body:
        return None
    m = _RETRY_DELAY_JSON_RE.search(body)
    if m:
        return _hms_to_seconds(m.group(1))
    m = _RETRY_IN_RE.search(body)
    if not m:
        return None
    h, mi, s = m.group(1), m.group(2), m.group(3)
    if h is None and mi is None and s is None:
        return None
    return _hms_to_seconds_parts(h, mi, s)


def _hms_to_seconds(blob: str) -> float | None:
    m = re.match(
        r"(?:([\d.]+)\s*h)?\s*(?:([\d.]+)\s*m)?\s*(?:([\d.]+)\s*s)?$",
        blob.strip(),
        re.IGNORECASE,
    )
    if not m:
        return None
    return _hms_to_seconds_parts(m.group(1), m.group(2), m.group(3))


def _hms_to_seconds_parts(h: str | None, mi: str | None, s: str | None) -> float | None:
    total = 0.0
    if h:
        total += float(h) * 3600.0
    if mi:
        total += float(mi) * 60.0
    if s:
        total += float(s)
    return total if total > 0 else None


def state_key(provider: str, model: str) -> str:
    return f"{provider}/{model}"


def load_quota_state(path: str | Path | None = None) -> dict[str, str]:
    p = Path(path) if path else _DEFAULT_PATH
    if not p.is_file():
        return {}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if not isinstance(data, dict):
        return {}
    out: dict[str, str] = {}
    for k, v in data.items():
        if isinstance(k, str) and isinstance(v, str):
            out[k] = v
    return out


def save_quota_state(state: dict[str, str], path: str | Path | None = None) -> None:
    p = Path(path) if path else _DEFAULT_PATH
    p.parent.mkdir(parents=True, exist_ok=True)
    # Gỡ mục đã hết hạn để file gọn
    cleaned = dict(state)
    now = _now_utc()
    for k, v in list(cleaned.items()):
        dt = _parse_iso(v)
        if dt is not None and dt <= now:
            cleaned.pop(k, None)
    p.write_text(json.dumps(cleaned, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def is_blocked(
    provider: str,
    model: str,
    *,
    path: str | Path | None = None,
    state: dict[str, str] | None = None,
) -> tuple[bool, datetime | None]:
    """Trả (blocked?, blocked_until)."""
    st = state if state is not None else load_quota_state(path)
    key = state_key(provider, model)
    raw = st.get(key)
    if not raw:
        return False, None
    until = _parse_iso(raw)
    if until is None:
        return False, None
    if until <= _now_utc():
        return False, until
    return True, until


def mark_blocked(
    provider: str,
    model: str,
    *,
    body: str = "",
    code_1113: bool = False,
    default_hours: float = 6.0,
    path: str | Path | None = None,
) -> datetime:
    """Ghi blocked_until; 1113 → 6h; còn lại parse retry Delay hoặc default_hours."""
    p = Path(path) if path else _DEFAULT_PATH
    st = load_quota_state(p)
    if code_1113:
        sec = default_hours * 3600.0
    else:
        parsed = parse_retry_delay_seconds(body)
        sec = parsed if parsed is not None else default_hours * 3600.0
    until = _now_utc() + timedelta(seconds=sec)
    st[state_key(provider, model)] = until.isoformat()
    save_quota_state(st, p)
    return until


def format_blocked_until(until: datetime) -> str:
    local = until.astimezone()
    return local.strftime("%Y-%m-%d %H:%M:%S %Z")


def looks_like_code_1113(body: str) -> bool:
    b = body or ""
    if "1113" not in b:
        return False
    compact = b.replace(" ", "")
    if '"code":1113' in compact or "'code':1113" in compact:
        return True
    return "insufficient" in b.lower() and "balance" in b.lower()
