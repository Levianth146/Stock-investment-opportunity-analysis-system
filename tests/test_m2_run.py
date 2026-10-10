import json
from pathlib import Path

from stockai.contracts.schemas import validate
from stockai.m2_fundamental.run import run

SNAP = Path(__file__).resolve().parents[1] / "data" / "snapshots"


def _load(t):
    return json.loads((SNAP / f"{t}_2026-10-08.json").read_text(encoding="utf-8"))


def test_m2_nonbank_real_snapshot():
    out = run(_load("HPG"), {}, {})
    assert validate(out, "module_out") == []
    assert out["status"] == "ok" and 0 <= out["score"] <= 100
    m = out["metrics"]
    assert abs(m["roe"]["value"] - 0.118) < 0.002 and m["interest_coverage"]["value"] > 5
    assert "debt_to_equity" in m and "cir" not in m


def test_m2_bank_uses_bank_criteria_and_flags_missing_npl_car():
    out = run(_load("VCB"), {}, {})
    assert validate(out, "module_out") == []
    m = out["metrics"]
    assert "cir" in m and "nim" in m and "loan_to_deposit" in m and "gross_margin" not in m and "debt_to_equity" not in m
    assert out["status"] == "partial" and {"m2_missing_npl_ratio", "m2_missing_car"} <= set(out["flags"])


def test_m2_no_financials_is_error_not_crash():
    s = _load("HPG")
    s["financials"]["annual"] = []
    out = run(s, {}, {})
    assert out["status"] == "error" and out["score"] is None and validate(out, "module_out") == []
