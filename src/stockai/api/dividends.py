"""Lịch sử cổ tức từ data/dividends/dividends.json (scripts/fetch_dividends.py)."""
from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path
from typing import Any


def dividends_for(root: Path, symbol: str, price: float | None = None) -> dict[str, Any]:
    path = root / "data" / "dividends" / "dividends.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"symbol": symbol, "available": False, "reason": "no_file", "events": []}
    rec = data.get(symbol) if isinstance(data, dict) else None
    if not rec:
        return {"symbol": symbol, "available": False, "reason": "not_fetched", "events": []}
    events = rec.get("events") or []
    if not events:
        return {
            "symbol": symbol,
            "available": False,
            "reason": "no_events",
            "events": [],
            "source": rec.get("source"),
            "fetched_at": rec.get("fetched_at"),
        }
    cutoff = (date.today() - timedelta(days=365)).isoformat()
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
    }
