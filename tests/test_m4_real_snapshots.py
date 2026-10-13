"""5 mã thật VCB/FPT/HPG/VIC/SSI — skip nếu thiếu file snapshots_ext."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from stockai.contracts.schemas import validate
from stockai.m4_valuation.run import run as run_m4

_ROOT = Path(__file__).resolve().parents[1]
_SNAPS = _ROOT / "data" / "snapshots_ext"
_STATS = _ROOT / "data" / "valuation_sector_stats.json"
_TICKERS = ("VCB", "FPT", "HPG", "VIC", "SSI")
_AS_OF = "2026-10-08"


def _snap_path(ticker: str) -> Path | None:
    p = _SNAPS / f"{ticker}_{_AS_OF}.json"
    return p if p.is_file() else None


@pytest.mark.parametrize("ticker", _TICKERS)
def test_real5_no_crash(ticker: str):
    path = _snap_path(ticker)
    if path is None:
        pytest.skip(f"missing {_SNAPS / f'{ticker}_{_AS_OF}.json'}")
    if not _STATS.is_file():
        pytest.skip(f"missing {_STATS} — chạy build_m4_sector_stats trước")

    snap = json.loads(path.read_text(encoding="utf-8"))
    out = run_m4(
        snap,
        {},
        {"m4": {"sector_stats_path": str(_STATS)}},
    )
    errs = validate(out, "module_out")
    assert errs == [], errs
    assert out["module"] == "m4"
    assert out["status"] in ("ok", "partial", "error")
    # score null hoặc [0,100] — không ép 50 khi insufficient
    if out["score"] is not None:
        assert 0 <= out["score"] <= 100

    is_bank = bool((snap.get("company") or {}).get("is_bank"))
    if ticker == "VCB":
        assert is_bank
        if out["score"] is not None:
            assert "m4_bank_primary_pb" in (out.get("flags") or [])

    # VIC đủ PE/PB: chỉ minority flag → status ok (không ép partial)
    if ticker == "VIC" and out["score"] is not None:
        flags = out.get("flags") or []
        if flags == ["m4_pb_uses_total_equity"] or set(flags) <= {
            "m4_pb_uses_total_equity",
        }:
            assert out["status"] == "ok"

    m = out.get("metrics") or {}
    if out["score"] is not None:
        assert m.get("pe", {}).get("value") is not None or m.get("pb", {}).get("value") is not None
