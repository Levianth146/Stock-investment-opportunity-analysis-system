"""Phân vị và dải p25–p75 ngành — dùng cùng hàm M4 (sector_stats), không viết lại."""
from __future__ import annotations

import math
from pathlib import Path
from typing import Any

from stockai.m4_valuation.sector_stats import (
    load_sector_stats,
    lookup_sector_medians,
    percentile_rank,
)
from stockai.m9_report.theme import ROOT


def _quantile(sorted_vals: list[float], q: float) -> float | None:
    """Phân vị tuyến tính trên mẫu đã sắp (q trong [0, 1])."""
    if not sorted_vals:
        return None
    xs = sorted_vals
    n = len(xs)
    if n == 1:
        return float(xs[0])
    q = max(0.0, min(1.0, float(q)))
    idx = q * (n - 1)
    lo = int(math.floor(idx))
    hi = int(math.ceil(idx))
    if lo == hi:
        return float(xs[lo])
    w = idx - lo
    return float(xs[lo]) * (1.0 - w) + float(xs[hi]) * w


def resolve_sector_band(
    sector: str | None,
    *,
    pe: float | None = None,
    pb: float | None = None,
    stats_path: str | Path | None = None,
    min_sector_n: int = 5,
) -> dict[str, Any]:
    """Trả p25/p75/percentile (0–100) và cờ fallback thị trường cho P/E và P/B.

    ``percentile`` = ``percentile_rank`` của M4 × 100 (không phải điểm chân inverted).
    """
    path = Path(stats_path) if stats_path else ROOT / "data" / "valuation_sector_stats.json"
    stats = load_sector_stats(path)
    med = lookup_sector_medians(stats, sector, min_sector_n=min_sector_n)
    out: dict[str, Any] = {
        "used_fallback": bool(med.used_fallback),
        "n_pe": med.n_pe,
        "n_pb": med.n_pb,
        "pe": {},
        "pb": {},
    }
    for kind, value, sorted_vals, n in (
        ("pe", pe, med.pe_sorted, med.n_pe),
        ("pb", pb, med.pb_sorted, med.n_pb),
    ):
        block: dict[str, Any] = {
            "p25": _quantile(sorted_vals, 0.25) if sorted_vals else None,
            "p75": _quantile(sorted_vals, 0.75) if sorted_vals else None,
            "percentile": None,
            "n": n,
            "market_wide": bool(med.used_fallback) or n < min_sector_n,
        }
        if value is not None and sorted_vals:
            pct = percentile_rank(float(value), sorted_vals)
            if pct is not None:
                block["percentile"] = round(100.0 * pct, 2)
        out[kind] = block
    return out
