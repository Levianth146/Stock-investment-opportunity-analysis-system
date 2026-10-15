"""Lịch sử cổ tức từ data/dividends/dividends.json (scripts/fetch_dividends.py)."""
from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path
from typing import Any
from functools import lru_cache


@lru_cache(maxsize=4)
def _read_archive(path: str, mtime_ns: int) -> dict:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def dividends_for(root: Path, symbol: str, price: float | None = None, *, asof: str | None = None) -> dict[str, Any]:
    path = root / "data" / "dividends" / "dividends.json"
    try:
        data = _read_archive(str(path), path.stat().st_mtime_ns)
    except (OSError, ValueError):
        return {"symbol": symbol, "available": False, "reason": "no_file", "events": []}
    rec = data.get(symbol) if isinstance(data, dict) else None
    if not rec:
        return {"symbol": symbol, "available": False, "reason": "not_fetched", "events": []}
    anchor = date.fromisoformat(asof) if asof else date.today()
    events = [e for e in (rec.get("events") or []) if isinstance(e, dict)
              and isinstance(e.get("ex_date"), str) and e["ex_date"][:10] <= anchor.isoformat()]
    events.sort(key=lambda e: e["ex_date"], reverse=True)
    if not events:
        return {
            "symbol": symbol,
            "available": False,
            "reason": "no_events",
            "events": [],
            "source": rec.get("source"),
            "fetched_at": rec.get("fetched_at"),
        }
    cutoff = (anchor - timedelta(days=365)).isoformat()
    ttm = sum(
        float(e["dps_vnd"])
        for e in events
        if e.get("kind") == "cash" and e.get("dps_vnd") and str(e.get("ex_date") or "") >= cutoff
    )
    return {
        "symbol": symbol,
        "available": True,
        "events": events[:30],
        "dps_ttm_vnd": ttm or None,
        "source": rec.get("source"),
        "fetched_at": rec.get("fetched_at"),
        "asof": anchor.isoformat(),
    }
