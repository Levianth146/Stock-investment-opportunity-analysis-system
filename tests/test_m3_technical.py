"""Fail-first / offline tests cho M3 technical (T score)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from helpers_m3_m6_snapshots import (
    snapshot_bad_ohlc,
    snapshot_empty_prices,
    snapshot_enough_history,
    snapshot_short_history,
    snapshot_stale,
    snapshot_with_future_rows,
)
from stockai.contracts.schemas import validate
from stockai.m3_technical.run import run as run_m3

ROOT = Path(__file__).resolve().parents[1]
SNAP_EXT = ROOT / "data" / "snapshots_ext"
SNAP_EXT_NONEWS = ROOT / "data" / "snapshots_ext_nonews"


def test_helpers_importable():
    assert callable(snapshot_enough_history)


def test_enough_history_score_and_metrics():
    snap = snapshot_enough_history()
    out = run_m3(snap, {}, {})
    assert validate(out, "module_out") == []
    assert out["status"] in ("ok", "partial")
    assert out["status"] != "stub"
    assert out["score"] is not None
    assert 0 <= float(out["score"]) <= 100
    m = out["metrics"]
    for key in (
        "ma20",
        "ma50",
        "ma200",
        "rsi14",
        "macd",
        "macd_signal",
        "macd_histogram",
        "volume_ratio_20",
        "atr14",
    ):
        assert key in m
        assert m[key]["value"] is not None


def test_short_history_score_none():
    snap = snapshot_short_history(n=100)
    out = run_m3(snap, {}, {})
    assert validate(out, "module_out") == []
    assert out["score"] is None
    assert "m3_insufficient_history_ma200" in out["flags"]
    assert out["status"] == "partial"


def test_future_rows_unused_in_indicators():
    snap = snapshot_with_future_rows()
    out = run_m3(snap, {}, {})
    assert validate(out, "module_out") == []
    assert out["score"] is not None
    close = out["metrics"]["close"]["value"]
    assert close is not None
    assert close < 500_000  # không lấy close 999999 của phiên tương lai
    # evidence/metrics không được phản ánh ngày sau as_of
    as_of = snap["meta"]["as_of"]
    for ev in out.get("evidence") or []:
        text = str(ev.get("text") or "")
        assert "999999" not in text
        assert "2026-10-09" not in text or as_of >= "2026-10-09"


def test_bad_ohlc_excluded_with_count_flag():
    snap = snapshot_bad_ohlc()
    out = run_m3(snap, {}, {})
    assert validate(out, "module_out") == []
    assert "m3_invalid_price_rows_excluded" in out["flags"]
    assert "invalid_price_rows" in out["metrics"]
    assert out["metrics"]["invalid_price_rows"]["value"] >= 1


def test_stale_last_session_flag():
    snap = snapshot_stale()
    out = run_m3(snap, {}, {})
    assert validate(out, "module_out") == []
    assert "m3_stale_price_data" in out["flags"]


def test_empty_prices_no_crash():
    snap = snapshot_empty_prices()
    out = run_m3(snap, {}, {})
    assert validate(out, "module_out") == []
    assert out["score"] is None
    assert out["status"] == "partial"
    assert "m3_no_valid_price_rows" in out["flags"] or "m3_insufficient_history_ma200" in out["flags"]


@pytest.mark.parametrize("base", [SNAP_EXT, SNAP_EXT_NONEWS])
def test_optional_real_snapshot_m3(base: Path):
    if not base.is_dir():
        pytest.skip(f"missing {base}")
    cands = sorted(base.glob("HPG_*.json"))
    if not cands:
        pytest.skip("no HPG snapshot")
    snap = json.loads(cands[-1].read_text(encoding="utf-8"))
    out = run_m3(snap, {}, {})
    assert validate(out, "module_out") == []
    assert out["status"] in ("ok", "partial")
    if out["score"] is not None:
        assert 0 <= float(out["score"]) <= 100
