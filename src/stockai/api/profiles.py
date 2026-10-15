"""Hồ sơ công ty (giới thiệu, niêm yết, sở hữu) từ data/company_profiles/profiles.json.

File sinh offline bằng scripts/build_company_profiles.py từ cache overview M1.
"""
from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any

_LOCK = threading.Lock()
_CACHE: dict[str, Any] = {"path": None, "mtime": None, "data": {}}


def _load(path: Path) -> dict[str, Any]:
    with _LOCK:
        try:
            mtime = path.stat().st_mtime_ns
        except OSError:
            return {}
        if _CACHE["path"] == str(path) and _CACHE["mtime"] == mtime:
            return _CACHE["data"]
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            data = {}
        _CACHE.update(path=str(path), mtime=mtime, data=data if isinstance(data, dict) else {})
        return _CACHE["data"]


def company_profile(root: Path, symbol: str) -> dict[str, Any]:
    """Trả {symbol, available, profile?}. Không có hồ sơ → available=false (UI nêu rõ)."""
    data = _load(root / "data" / "company_profiles" / "profiles.json")
    p = data.get(symbol)
    if not p:
        return {"symbol": symbol, "available": False, "profile": None}
    return {"symbol": symbol, "available": True, "profile": p}
