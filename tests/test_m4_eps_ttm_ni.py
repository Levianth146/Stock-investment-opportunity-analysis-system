"""Regression EPS TTM = sum(NI 4Q)/shares — không cộng items.eps quý."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from stockai.contracts.schemas import validate
from stockai.m4_valuation.multiples import derive_multiples
from stockai.m4_valuation.run import run as run_m4
from tests.helpers_m4_snapshots import (
    snap_eps_zero_quarterly_annual_ok,
    snap_hpg_like_eps_misleading,
    snap_quarter_gap,
)

_ROOT = Path(__file__).resolve().parents[1]
_SNAPS = _ROOT / "data" / "snapshots_ext"
_STATS = _ROOT / "data" / "valuation_sector_stats.json"
_FIXTURE_STATS = Path(__file__).parent / "fixtures" / "m4_sector_stats_mini.json"
_AS_OF = "2026-10-08"
_CROSS_TICKERS = (
    "HPG",
    "ACB",
    "FPT",
    "VCB",
    "SSI",
    "VIC",
    "VHM",
    "MWG",
    "MSN",
    "VNM",
    "GAS",
    "PLX",
    "REE",
    "PNJ",
    "DIG",
    "DXG",
    "HDB",
    "TCB",
    "MBB",
    "CTG",
)


def _cfg(**extra) -> dict:
    m4 = {"sector_stats_path": str(_FIXTURE_STATS), "min_sector_n": 5}
    m4.update(extra)
    return {"m4": m4}


def test_hand_fixture_ignores_misleading_quarterly_eps():
    """eps=[1781,0,1973,0] không được cộng; TTM từ NI ≈ 2750."""
    snap = snap_hpg_like_eps_misleading()
    mi = derive_multiples(snap)
    assert mi.eps_source == "ttm_ni"
    assert mi.eps_used is not None
    assert abs(mi.eps_used - 2750.0) / 2750.0 <= 0.02
    # sum(eps) = 3754 — tuyệt đối không dùng
    assert abs(mi.eps_used - 3754.0) / 3754.0 > 0.15
    assert mi.pe is not None
    assert abs(mi.pe - 7.3) / 7.3 <= 0.05


def test_fallback_annual_when_no_quarterly_ni():
    out = run_m4(snap_eps_zero_quarterly_annual_ok(), {}, _cfg())
    assert validate(out, "module_out") == []
    assert "m4_eps_ttm_fallback_annual" in (out.get("flags") or [])
    assert (out.get("metrics") or {}).get("eps_used", {}).get("value") == 1500.0
    assert (out.get("metrics") or {}).get("eps_used", {}).get("note") == "annual"


def test_quarter_gap_flags_and_annual_fallback():
    out = run_m4(snap_quarter_gap(), {}, _cfg())
    assert validate(out, "module_out") == []
    flags = out.get("flags") or []
    assert "m4_eps_quarter_gap" in flags
    assert "m4_eps_ttm_fallback_annual" in flags
    assert (out.get("metrics") or {}).get("eps_used", {}).get("value") == 1800.0


def test_real_hpg_eps_ttm_and_pe():
    path = _SNAPS / f"HPG_{_AS_OF}.json"
    if not path.is_file():
        pytest.skip(f"missing {path}")
    snap = json.loads(path.read_text(encoding="utf-8"))
    mi = derive_multiples(snap)
    assert mi.eps_source == "ttm_ni"
    assert mi.eps_used is not None
    assert abs(mi.eps_used - 2750.0) / 2750.0 <= 0.02
    assert mi.pe is not None
    assert abs(mi.pe - 7.3) / 7.3 <= 0.05


def test_real_acb_eps_ttm():
    path = _SNAPS / f"ACB_{_AS_OF}.json"
    if not path.is_file():
        pytest.skip(f"missing {path}")
    snap = json.loads(path.read_text(encoding="utf-8"))
    mi = derive_multiples(snap)
    assert mi.eps_source == "ttm_ni"
    assert mi.eps_used is not None
    assert abs(mi.eps_used - 2701.0) / 2701.0 <= 0.02


def _ni_ttm_reference(snap: dict) -> float | None:
    """Công thức tham chiếu độc lập: sum(NI 4Q mới nhất liên tiếp)/shares."""
    from datetime import date

    from stockai.m4_valuation.multiples import (
        parse_quarter_period,
        pick_net_income,
        quarter_index,
        quarters_are_consecutive,
    )

    def _d(v):
        try:
            return date.fromisoformat(str(v)[:10])
        except (TypeError, ValueError):
            return None

    as_of = _d((snap.get("meta") or {}).get("as_of"))
    try:
        shares = float((snap.get("company") or {}).get("shares_outstanding"))
    except (TypeError, ValueError):
        shares = None
    if as_of is None or shares is None or shares <= 0:
        return None
    fins = snap.get("financials") or {}
    quarterly = fins.get("quarterly") if isinstance(fins.get("quarterly"), list) else []
    by_period: dict = {}
    for p in quarterly:
        if not isinstance(p, dict):
            continue
        pub = _d(p.get("published_at"))
        if pub is None or pub > as_of:
            continue
        parsed = parse_quarter_period(p.get("period"))
        if parsed is None:
            continue
        items = p.get("items") if isinstance(p.get("items"), dict) else {}
        ni = pick_net_income(items)
        prev = by_period.get(parsed)
        if prev is None or pub > prev[0] or (pub == prev[0] and ni is not None and prev[1] is None):
            by_period[parsed] = (pub, ni)
    if len(by_period) < 4:
        return None
    keys = sorted(by_period.keys(), key=lambda t: quarter_index(t[0], t[1]), reverse=True)[:4]
    if not quarters_are_consecutive(keys):
        return None
    nis = []
    for k in keys:
        ni = by_period[k][1]
        if ni is None:
            return None
        nis.append(ni)
    return sum(nis) / shares


@pytest.mark.parametrize("ticker", _CROSS_TICKERS)
def test_crosscheck_eps_ttm_vs_ni_sum(ticker: str):
    path = _SNAPS / f"{ticker}_{_AS_OF}.json"
    if not path.is_file():
        pytest.skip(f"missing {path}")
    snap = json.loads(path.read_text(encoding="utf-8"))
    mi = derive_multiples(snap)
    ref = _ni_ttm_reference(snap)
    if ref is None or ref <= 0:
        pytest.skip(f"{ticker}: không đủ 4Q NI liên tiếp để cross-check")
    assert mi.eps_source == "ttm_ni"
    assert mi.eps_used is not None
    assert abs(mi.eps_used - ref) / abs(ref) <= 0.03


def test_sector_fallback_drops_pb_leg():
    """TinySector n<5 → market fallback; chỉ PE; m4_pb_leg_dropped."""
    from tests.helpers_m4_snapshots import snap_tiny_sector

    out = run_m4(snap_tiny_sector(), {}, _cfg())
    assert validate(out, "module_out") == []
    flags = out.get("flags") or []
    assert "m4_sector_fallback" in flags
    assert "m4_pb_leg_dropped" in flags
    # Có PE → vẫn chấm
    assert out["score"] is not None
