"""Disk cache cho generate_json / debate — ``data/llm_cache/<hash>.json``."""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any


def cache_key(
    *,
    ticker: str,
    as_of: str,
    model: str,
    prompt_version: str,
    payload_hash: str,
) -> str:
    raw = f"{ticker}|{as_of}|{model}|{prompt_version}|{payload_hash}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def cache_path(cache_dir: str | Path, key: str) -> Path:
    return Path(cache_dir) / f"{key}.json"


def read_cache(cache_dir: str | Path, key: str) -> tuple[dict | None, list[str]]:
    """Đọc cache. Trả (entry|None, flags). Corrupt → (None, ['debate_cache_ignored'])."""
    flags: list[str] = []
    path = cache_path(cache_dir, key)
    if not path.is_file():
        return None, flags
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        flags.append("debate_cache_ignored")
        return None, flags
    if not isinstance(data, dict):
        flags.append("debate_cache_ignored")
        return None, flags
    if "bull" not in data or "bear" not in data:
        flags.append("debate_cache_ignored")
        return None, flags
    return data, flags


def write_cache(
    cache_dir: str | Path,
    key: str,
    *,
    bull: list[dict],
    bear: list[dict],
    provider: str,
    model: str,
    flags: list[str] | None = None,
) -> None:
    """Ghi entry cache (tạo thư mục nếu thiếu)."""
    path = cache_path(cache_dir, key)
    path.parent.mkdir(parents=True, exist_ok=True)
    entry: dict[str, Any] = {
        "key": key,
        "bull": bull,
        "bear": bear,
        "provider": provider,
        "model": model,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "flags": list(flags or []),
    }
    path.write_text(json.dumps(entry, ensure_ascii=False, indent=2), encoding="utf-8")
