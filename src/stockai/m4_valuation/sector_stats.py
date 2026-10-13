"""IO sector stats JSON + winsorize-then-median + percentile từ phân phối lưu sẵn.

Runtime chỉ đọc cache; không tính median/percentile từ peers[] hay quét lại snapshots.
Sector nhỏ (n < min_sector_n) → dùng median/phân phối thị trường + m4_sector_fallback.
"""
from __future__ import annotations

import json
import math
import statistics
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


MARKET_KEY = "__market__"


def winsorize(values: list[float], low_pct: float = 0.05, high_pct: float = 0.95) -> list[float]:
    """Cắt phân vị low/high trên mẫu; trả list đã cắt (cùng độ dài nếu n>=2)."""
    if not values:
        return []
    xs = sorted(float(v) for v in values if math.isfinite(float(v)))
    n = len(xs)
    if n == 0:
        return []
    if n == 1:
        return xs
    lo = max(0.0, min(1.0, float(low_pct)))
    hi = max(0.0, min(1.0, float(high_pct)))
    if hi < lo:
        lo, hi = hi, lo
    i_lo = int(math.floor(lo * (n - 1)))
    i_hi = int(math.ceil(hi * (n - 1)))
    floor_v = xs[i_lo]
    ceil_v = xs[i_hi]
    return [min(max(v, floor_v), ceil_v) for v in xs]


def median_after_winsor(
    values: list[float],
    low_pct: float = 0.05,
    high_pct: float = 0.95,
) -> float | None:
    """Winsorize rồi median; None nếu mẫu rỗng."""
    w = winsorize(values, low_pct=low_pct, high_pct=high_pct)
    if not w:
        return None
    return float(statistics.median(w))


def percentile_rank(value: float, sorted_vals: list[float]) -> float | None:
    """Hạng phân vị midrank trong [0,1]; thấp = multiple thấp hơn phần lớn mẫu."""
    if not sorted_vals:
        return None
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(v):
        return None
    n = len(sorted_vals)
    less = 0
    equal = 0
    for x in sorted_vals:
        if x < v:
            less += 1
        elif x == v:
            equal += 1
    return (less + 0.5 * equal) / n


def cheapness_percentile_score(multiple: float, sorted_vals: list[float]) -> float | None:
    """Điểm chân 0–100: multiple thấp (rẻ) → điểm cao. score = 100*(1 - pct)."""
    pct = percentile_rank(multiple, sorted_vals)
    if pct is None:
        return None
    return round(100.0 * (1.0 - pct), 4)


def _as_float_list(raw: Any) -> list[float]:
    if not isinstance(raw, list):
        return []
    out: list[float] = []
    for x in raw:
        try:
            v = float(x)
        except (TypeError, ValueError):
            continue
        if math.isfinite(v) and v > 0:
            out.append(v)
    return sorted(out)


@dataclass
class SectorMedians:
    """Kết quả lookup median + phân phối ngành cho một mã."""

    sector: str | None
    median_pe: float | None = None
    median_pb: float | None = None
    pe_sorted: list[float] = field(default_factory=list)
    pb_sorted: list[float] = field(default_factory=list)
    n_pe: int = 0
    n_pb: int = 0
    version: int | None = None
    as_of: str | None = None
    used_fallback: bool = False
    flags: list[str] = field(default_factory=list)
    stats_loaded: bool = False


def load_sector_stats(path: Path | str) -> dict[str, Any] | None:
    """Đọc JSON sector stats; None nếu thiếu/lỗi."""
    p = Path(path)
    try:
        if not p.is_file():
            return None
        data = json.loads(p.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return None
        return data
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return None


def lookup_sector_medians(
    stats: dict[str, Any] | None,
    sector: str | None,
    *,
    min_sector_n: int = 5,
) -> SectorMedians:
    """Resolve median PE/PB + sorted distributions; fallback thị trường khi n < min_sector_n."""
    out = SectorMedians(sector=sector)
    if stats is None:
        out.flags.append("m4_sector_stats_missing")
        return out

    out.stats_loaded = True
    try:
        out.version = int(stats.get("version")) if stats.get("version") is not None else None
    except (TypeError, ValueError):
        out.version = None
    out.as_of = str(stats.get("as_of")) if stats.get("as_of") else None

    sectors = stats.get("sectors") if isinstance(stats.get("sectors"), dict) else {}
    min_n = int(min_sector_n)

    def _read_block(name: str | None) -> tuple[float | None, float | None, int, int, list[float], list[float]]:
        if not name or name not in sectors:
            return None, None, 0, 0, [], []
        block = sectors.get(name) or {}
        if not isinstance(block, dict):
            return None, None, 0, 0, [], []
        try:
            n_pe = int(block.get("n_pe") or 0)
        except (TypeError, ValueError):
            n_pe = 0
        try:
            n_pb = int(block.get("n_pb") or 0)
        except (TypeError, ValueError):
            n_pb = 0
        m_pe = block.get("median_pe")
        m_pb = block.get("median_pb")
        pe = float(m_pe) if isinstance(m_pe, (int, float)) and math.isfinite(float(m_pe)) else None
        pb = float(m_pb) if isinstance(m_pb, (int, float)) and math.isfinite(float(m_pb)) else None
        pe_s = _as_float_list(block.get("pe_sorted") or block.get("pe_values"))
        pb_s = _as_float_list(block.get("pb_sorted") or block.get("pb_values"))
        return pe, pb, n_pe, n_pb, pe_s, pb_s

    pe, pb, n_pe, n_pb, pe_s, pb_s = _read_block(sector)
    out.n_pe, out.n_pb = n_pe, n_pb

    use_pe = pe is not None and n_pe >= min_n
    use_pb = pb is not None and n_pb >= min_n

    if sector and sector not in sectors:
        out.flags.append("m4_sector_median_unavailable")
    elif sector and (n_pe < min_n and n_pb < min_n):
        out.flags.append("m4_peer_group_small")
        out.flags.append("m4_sector_median_unavailable")
    elif not use_pe and not use_pb and sector:
        out.flags.append("m4_sector_median_unavailable")

    # Fallback thị trường khi thiếu chân ngành
    m_pe, m_pb, mn_pe, mn_pb, m_pe_s, m_pb_s = _read_block(MARKET_KEY)
    need_fallback = False
    if not use_pe and m_pe is not None and mn_pe >= min_n:
        pe = m_pe
        n_pe = mn_pe
        pe_s = m_pe_s
        use_pe = True
        need_fallback = True
    if not use_pb and m_pb is not None and mn_pb >= min_n:
        pb = m_pb
        n_pb = mn_pb
        pb_s = m_pb_s
        use_pb = True
        need_fallback = True

    if need_fallback:
        out.used_fallback = True
        if "m4_sector_fallback" not in out.flags:
            out.flags.append("m4_sector_fallback")
        if "m4_peer_group_small" not in out.flags and sector:
            out.flags.append("m4_peer_group_small")
        # Fallback thị trường: chỉ giữ chân PE; PB bỏ (item 5)
        if "m4_pb_leg_dropped" not in out.flags:
            out.flags.append("m4_pb_leg_dropped")
        use_pb = False
        pb = None
        pb_s = []

    out.median_pe = pe if use_pe else None
    out.median_pb = pb if use_pb else None
    out.pe_sorted = pe_s if use_pe else []
    out.pb_sorted = pb_s if use_pb else []
    if use_pe:
        out.n_pe = n_pe
    if use_pb:
        out.n_pb = n_pb
    else:
        out.n_pb = 0

    if out.median_pe is None and out.median_pb is None:
        if "m4_sector_median_unavailable" not in out.flags:
            out.flags.append("m4_sector_median_unavailable")

    return out


def build_sectors_payload(
    per_ticker: list[dict[str, Any]],
    *,
    as_of: str,
    winsor_low: float,
    winsor_high: float,
    min_sector_n: int,
    pe_max_exclude: float | None = 100.0,
) -> dict[str, Any]:
    """Gom PE/PB theo sector + market; winsorize rồi median + lưu pe_sorted/pb_sorted.

    per_ticker: [{sector, pe, pb}, ...] — pe/pb có thể None.
    """
    by_sector: dict[str, dict[str, list[float]]] = {}
    market_pe: list[float] = []
    market_pb: list[float] = []

    for row in per_ticker:
        sector = row.get("sector")
        if not isinstance(sector, str) or not sector.strip():
            continue
        pe = row.get("pe")
        pb = row.get("pb")
        bucket = by_sector.setdefault(sector, {"pe": [], "pb": []})
        if isinstance(pe, (int, float)) and math.isfinite(float(pe)) and float(pe) > 0:
            if pe_max_exclude is not None and float(pe) > float(pe_max_exclude):
                pass
            else:
                bucket["pe"].append(float(pe))
                market_pe.append(float(pe))
        if isinstance(pb, (int, float)) and math.isfinite(float(pb)) and float(pb) > 0:
            bucket["pb"].append(float(pb))
            market_pb.append(float(pb))

    def _sector_block(pe_vals: list[float], pb_vals: list[float]) -> dict[str, Any]:
        flags: list[str] = []
        pe_w = winsorize(pe_vals, winsor_low, winsor_high) if pe_vals else []
        pb_w = winsorize(pb_vals, winsor_low, winsor_high) if pb_vals else []
        med_pe = float(statistics.median(pe_w)) if pe_w else None
        med_pb = float(statistics.median(pb_w)) if pb_w else None
        n_pe, n_pb = len(pe_vals), len(pb_vals)
        if n_pe < min_sector_n or n_pb < min_sector_n:
            flags.append("small_sample")
        return {
            "n_pe": n_pe,
            "n_pb": n_pb,
            "median_pe": med_pe,
            "median_pb": med_pb,
            # Phân phối đã winsorize — runtime percentile không quét lại snapshots
            "pe_sorted": sorted(pe_w),
            "pb_sorted": sorted(pb_w),
            "flags": flags,
        }

    sectors: dict[str, Any] = {}
    for name, vals in sorted(by_sector.items()):
        sectors[name] = _sector_block(vals["pe"], vals["pb"])
    sectors[MARKET_KEY] = _sector_block(market_pe, market_pb)

    return {
        "version": 2,
        "as_of": as_of,
        "universe": "full+limited",
        "winsor": {"low_pct": winsor_low, "high_pct": winsor_high},
        "min_sector_n": min_sector_n,
        "scoring": "percentile_inverted",
        "sectors": sectors,
    }
