"""Fail-first / offline tests cho M6 risk (R score, Q1:B polarity)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from helpers_m3_m6_snapshots import (
    snapshot_high_vol_deep_dd,
    snapshot_identical_stock_index,
    snapshot_m6_misaligned_dates,
    snapshot_shared_holiday_gap,
    snapshot_short_history,
    snapshot_stable,
    snapshot_stock_suspended_vs_index,
    snapshot_synthetic,
    snapshot_unadjusted,
)
from stockai.contracts.schemas import validate
from stockai.m6_risk.run import run as run_m6

ROOT = Path(__file__).resolve().parents[1]
SNAP_EXT = ROOT / "data" / "snapshots_ext"
SNAP_EXT_NONEWS = ROOT / "data" / "snapshots_ext_nonews"


def test_helpers_importable_m6():
    assert callable(snapshot_identical_stock_index)


def test_eligible_path_numeric_r_and_metrics():
    snap = snapshot_identical_stock_index(n=200)
    out = run_m6(snap, {}, {})
    assert validate(out, "module_out") == []
    assert out["status"] == "ok"
    assert out["score"] is not None
    assert 0 <= float(out["score"]) <= 100
    m = out["metrics"]
    for key in (
        "beta",
        "annualized_volatility",
        "max_drawdown",
        "historical_var_95",
        "historical_cvar_95",
    ):
        assert key in m
        assert m[key]["value"] is not None


def test_insufficient_aligned_returns_null_score():
    # Ít phiên → không đủ aligned observations
    snap = snapshot_short_history(n=40)
    out = run_m6(snap, {}, {})
    assert validate(out, "module_out") == []
    assert out["score"] is None
    flags = set(out["flags"])
    assert (
        "m6_insufficient_aligned_returns" in flags
        or "m6_not_ready_for_risk_score" in flags
        or "m6_insufficient_stock_prices" in flags
    )
    assert out["status"] != "ok"


def test_date_alignment_intersection_no_forward_fill():
    snap = snapshot_m6_misaligned_dates(n=180)
    out = run_m6(snap, {}, {})
    assert validate(out, "module_out") == []
    # Không crash; observations aligned <= số ngày giao
    n = out["metrics"].get("aligned_observations", {}).get("value")
    assert n is not None
    stock_dates = {r["date"] for r in snap["prices"]["rows"]}
    idx_dates = {r["date"] for r in snap["index"]["rows"]}
    common = len(stock_dates & idx_dates)
    # aligned returns ≈ common-1 (trừ gap), không thể > common
    assert n <= common


def test_identical_series_beta_approx_one():
    snap = snapshot_identical_stock_index(n=200)
    out = run_m6(snap, {}, {})
    assert validate(out, "module_out") == []
    beta = out["metrics"]["beta"]["value"]
    assert beta is not None
    assert abs(float(beta) - 1.0) < 1e-6


def test_unadjusted_and_synthetic_not_eligible():
    u = run_m6(snapshot_unadjusted(n=200), {}, {})
    s = run_m6(snapshot_synthetic(n=200), {}, {})
    assert validate(u, "module_out") == []
    assert validate(s, "module_out") == []
    assert u["score"] is None
    assert s["score"] is None
    assert "m6_unadjusted_stock_prices" in u["flags"]
    assert "m6_synthetic_data" in s["flags"]
    # Không hard-code luôn partial trên mọi case: eligible path khác phải ok
    ok = run_m6(snapshot_identical_stock_index(n=200), {}, {})
    assert ok["status"] == "ok"
    assert u["status"] != "ok" or u["score"] is None
    assert s["status"] != "ok" or s["score"] is None


def test_polarity_high_vol_scores_higher_than_stable():
    high = run_m6(snapshot_high_vol_deep_dd(n=200), {}, {})
    stable = run_m6(snapshot_stable(n=200), {}, {})
    assert validate(high, "module_out") == []
    assert validate(stable, "module_out") == []
    assert high["score"] is not None and stable["score"] is not None
    assert float(high["score"]) > float(stable["score"])


def test_polarity_lock_against_stockai_safety_as_r():
    """Khóa cực tính: nếu dùng lại safety-as-R (StockAI), thứ tự sẽ đảo và fail."""
    high = run_m6(snapshot_high_vol_deep_dd(n=200), {}, {})
    stable = run_m6(snapshot_stable(n=200), {}, {})
    assert high["score"] is not None and stable["score"] is not None
    r_high = float(high["score"])
    r_stable = float(stable["score"])
    # CONTRACTS: high risk → higher R
    assert r_high > r_stable
    # StockAI safety ≈ 100 - R; safety-as-R sẽ cho high < stable
    safety_as_r_high = 100.0 - r_high
    safety_as_r_stable = 100.0 - r_stable
    assert safety_as_r_high < safety_as_r_stable


def test_shared_holiday_gap_no_flag_keeps_returns():
    """Nghỉ chung ~9 ngày lịch với chỉ số → không flag; đủ quan sát."""
    snap = snapshot_shared_holiday_gap(n=200, holiday_calendar_days=9)
    out = run_m6(snap, {}, {})
    assert validate(out, "module_out") == []
    flags = set(out["flags"])
    assert "m6_long_market_gaps_excluded" not in flags
    n = out["metrics"]["aligned_observations"]["value"]
    assert n is not None and float(n) >= 120
    assert out["metrics"]["gap_returns_excluded"]["value"] == 0.0
    assert out["status"] == "ok"
    assert out["score"] is not None


def test_stock_suspended_missed_index_sessions_flagged():
    """Stock treo 12 phiên chỉ số → flag + loại return bắc cầu qua khoảng treo."""
    snap = snapshot_stock_suspended_vs_index(n=200, suspend_sessions=12)
    out = run_m6(snap, {}, {})
    assert validate(out, "module_out") == []
    flags = set(out["flags"])
    assert "m6_long_market_gaps_excluded" in flags
    gap_ex = out["metrics"]["gap_returns_excluded"]["value"]
    assert gap_ex is not None and float(gap_ex) >= 1.0
    # Vẫn đủ quan sát quanh khoảng treo (200 - 12 - 1 ≈ đủ)
    n = out["metrics"]["aligned_observations"]["value"]
    assert n is not None and float(n) >= 120


@pytest.mark.parametrize("base", [SNAP_EXT, SNAP_EXT_NONEWS])
def test_optional_real_snapshot_m6(base: Path):
    if not base.is_dir():
        pytest.skip(f"missing {base}")
    cands = sorted(base.glob("HPG_*.json"))
    if not cands:
        pytest.skip("no HPG snapshot")
    snap = json.loads(cands[-1].read_text(encoding="utf-8"))
    out = run_m6(snap, {}, {})
    assert validate(out, "module_out") == []
    assert out["status"] in ("ok", "partial")
    if out["score"] is not None:
        assert 0 <= float(out["score"]) <= 100
        assert out["status"] == "ok"
