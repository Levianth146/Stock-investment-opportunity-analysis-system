"""M4 DCF (FCFF hai giai đoạn): số học đối chiếu độc lập, cổng dữ liệu, không lookahead, tích hợp vào giá mục tiêu."""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest

from stockai.contracts.schemas import validate
from stockai.m4_valuation.dcf import compute_dcf
from stockai.m4_valuation.multiples import derive_multiples
from stockai.m4_valuation.run import run as run_m4
from tests.helpers_m4_snapshots import _base

_STATS = Path(__file__).parent / "fixtures" / "m4_sector_stats_mini.json"
SHARES = 100_000_000.0


def _item(year: int, *, cfo=300e9, capex=100e9, interest=10e9, rev=2_000e9, dep=50e9, cash=0.0, debt=0.0):
    return {
        "period": str(year),
        "published_at": f"{year + 1}-03-31",
        "source_id": "src_fin",
        "items": {
            "cfo": cfo, "capex": capex, "interest_expense": interest, "revenue": rev, "depreciation": dep,
            "cash": cash, "short_term_debt": debt, "long_term_debt": 0.0, "total_equity": 2_000e9,
            "net_income": 200e9, "net_income_parent": 200e9, "eps": 2000.0,
        },
    }


def _snap(years=(2021, 2022, 2023, 2024, 2025), **kw) -> dict:
    s = _base("DCFX", sector="Technology", shares=SHARES)
    s["financials"]["annual"] = [_item(y, **kw) for y in years]
    return s


def _mi(snap):
    return derive_multiples(snap, stale_calendar_days=7, stale_financials_days=10_000)


def test_numbers_match_independent_calculation():
    """FCFF=300−100+10×0,8=208 tỷ/năm; doanh thu phẳng → g1 chặn ở 0; kiểm tra từng bước bằng công thức tay."""
    snap = _snap(cash=100e9, debt=200e9)
    r = compute_dcf(snap, _mi(snap), {"blend_weight": 0.3}, beta=1.0)
    assert r["status"] == "ok", r
    fcff = 300e9 - 100e9 + 10e9 * 0.8
    assert r["fcff_base"] == pytest.approx(fcff)
    ke = 0.035 + 1.0 * 0.085
    mcap = 20_000.0 * SHARES  # giá _base = 20.000
    kd = 10e9 / 200e9  # 5% (chạm sàn 5%)
    we = mcap / (mcap + 200e9)
    wacc = we * ke + (1 - we) * kd * 0.8
    assert r["wacc"] == pytest.approx(wacc)
    g_t, g1, years = 0.03, 0.0, 5
    pv, f = 0.0, fcff
    for t in range(1, years + 1):
        g = g1 + (g_t - g1) * (t - 1) / (years - 1)
        f *= 1 + g
        pv += f / (1 + wacc) ** t
    tv = f * (1 + g_t) / (wacc - g_t) / (1 + wacc) ** years
    expected = (pv + tv - 200e9 + 100e9) / SHARES
    assert r["per_share"] == pytest.approx(expected, rel=1e-9)
    assert r["bear"] < r["per_share"] < r["bull"]


def test_sensitivity_grid_is_monotonic():
    snap = _snap()
    r = compute_dcf(snap, _mi(snap), {}, beta=1.0)
    grid = r["sensitivity"]["per_share"]
    for row in grid:  # tăng trưởng dài hạn tăng → giá trị tăng
        assert row == sorted(row)
    for col in range(len(grid[0])):  # WACC tăng (hàng xuống) → giá trị giảm
        vals = [row[col] for row in grid]
        assert vals == sorted(vals, reverse=True)
    mid = grid[2][2]
    assert mid == pytest.approx(r["per_share"], abs=1.0)


def test_bank_and_financial_sectors_not_applicable():
    s = _snap()
    s["company"]["is_bank"] = True
    s["company"]["sector"] = "Banks"
    r = compute_dcf(s, _mi(s), {})
    assert r["status"] == "not_applicable" and not r["usable_for_target"]
    s2 = _snap()
    s2["company"]["sector"] = "Insurance"
    assert compute_dcf(s2, _mi(s2), {})["status"] == "not_applicable"


def test_no_lookahead_ignores_reports_published_after_as_of():
    s = _snap()
    s["financials"]["annual"][-1]["published_at"] = "2027-03-31"  # sau as_of 2026-10-08
    s["financials"]["annual"][-1]["items"]["cfo"] = 9e15  # nếu bị dùng sẽ làm kết quả phình ra
    clean = compute_dcf(_snap(years=(2021, 2022, 2023, 2024)), _mi(_snap(years=(2021, 2022, 2023, 2024))), {}, beta=1.0)
    r = compute_dcf(s, _mi(s), {}, beta=1.0)
    assert r["status"] == "ok"
    assert r["fcff_base"] == pytest.approx(clean["fcff_base"])


def test_short_history_and_stale_financials_have_reasons():
    s = _snap(years=(2024, 2025))
    r = compute_dcf(s, _mi(s), {})
    assert r["status"] == "insufficient" and "m4_dcf_short_history" in r["flags"]
    old = _snap(years=(2016, 2017, 2018, 2019, 2020))
    r2 = compute_dcf(old, _mi(old), {})
    assert r2["status"] == "insufficient" and "m4_dcf_stale_financials" in r2["flags"]


def test_negative_fcff_uses_proxy_without_stage_growth_or_fails():
    s = _snap(cfo=120e9, capex=400e9, dep=60e9, rev=2_000e9)  # FCFF âm, CFO−khấu hao dương
    r = compute_dcf(s, _mi(s), {}, beta=1.0)
    assert r["status"] == "ok" and "m4_dcf_maintenance_capex_proxy" in r["flags"]
    assert r["stage_growth_start"] == r["terminal_growth"]
    s2 = _snap(cfo=50e9, capex=400e9, dep=60e9)  # CFO < khấu hao: không cứu được
    r2 = compute_dcf(s2, _mi(s2), {}, beta=1.0)
    assert r2["status"] == "insufficient" and "m4_dcf_fcff_not_positive" in r2["flags"]


def test_negative_equity_after_debt_is_not_meaningful():
    s = _snap(debt=50_000e9)
    r = compute_dcf(s, _mi(s), {}, beta=1.0)
    assert r["status"] == "not_meaningful" and "m4_dcf_negative_equity" in r["flags"]


def test_implausible_result_is_shown_but_excluded_from_target():
    s = _snap(cfo=3_000e9, capex=100e9)  # FCFF rất lớn so với giá 20.000
    r = compute_dcf(s, _mi(s), {}, beta=1.0)
    assert r["status"] == "ok" and r["usable_for_target"] is False
    assert "m4_dcf_implausible" in r["flags"] and r["reason"]


def _run(snap, **m4):
    cfg = {"m4": {"sector_stats_path": str(_STATS), "min_sector_n": 5, "stale_calendar_days": 7, **m4}}
    out = run_m4(snap, {"m6": {"metrics": {"beta": {"value": 1.1, "unit": "ratio"}}}}, cfg)
    assert validate(out, "module_out") == []
    return out


def test_enable_dcf_blends_into_target_and_exposes_block():
    snap = _snap(cash=100e9, debt=200e9)
    off = _run(snap, enable_dcf=False)
    on = _run(snap, enable_dcf=True, dcf={"blend_weight": 0.3})
    assert "dcf" not in off and off["target"]["method"] == "relative_multiples_pe_pb"
    assert on["dcf"]["status"] == "ok" and on["dcf"]["beta"] == pytest.approx(1.1)
    if on["dcf"]["usable_for_target"]:
        assert on["target"]["method"] == "relative_multiples_pe_pb+dcf_fcff"
        rel, d = off["target"]["base"], on["dcf"]["per_share"]
        assert on["target"]["base"] == pytest.approx(0.7 * rel + 0.3 * d, abs=0.02)
    assert on["score"] == off["score"]  # DCF không đổi điểm V
    assert on["metrics"]["dcf_per_share"]["value"] == pytest.approx(on["dcf"]["per_share"])


def test_enable_dcf_does_not_force_partial_status():
    snap = _snap()
    assert _run(snap, enable_dcf=False)["status"] == _run(snap, enable_dcf=True)["status"]


def test_target_reliability_flags_far_from_price():
    from types import SimpleNamespace
    from stockai.m4_valuation.run import _target_reliability

    mi = SimpleNamespace(price_close=218000.0)
    low = _target_reliability({"base": 29088.0}, mi, {})
    assert low["level"] == "low" and "13%" in low["reason"]
    ok = _target_reliability({"base": 200000.0}, mi, {})
    assert ok["level"] == "normal" and ok["reason"] is None
    assert _target_reliability(None, mi, {}) is None
