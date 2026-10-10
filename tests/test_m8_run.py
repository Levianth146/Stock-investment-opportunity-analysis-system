import copy
import json
from pathlib import Path

from stockai.contracts.schemas import validate
from stockai.m7_scoring.run import run as run_m7
from stockai.m8_validate.run import run
from stockai.pipeline import load_cfg

SNAP = Path(__file__).resolve().parents[1] / "data" / "snapshots" / "HPG_2026-10-08.json"


def _setup():
    snap = json.loads(SNAP.read_text(encoding="utf-8"))
    cfg = load_cfg("long_term")
    up = {m: {"module": m, "status": "ok", "score": 60.0, "metrics": {}, "evidence": [], "flags": []} for m in ("m2", "m3", "m4", "m5", "m6")}
    up["m6"]["score"] = 30.0
    up["m7"] = run_m7(snap, up, cfg)
    return snap, up, cfg


def test_clean_run_passes_schema_and_status():
    snap, up, cfg = _setup()
    out = run(snap, up, cfg)
    assert validate(out, "validation") == [] and out["checked"] > 5
    assert not any(i["severity"] == "fatal" for i in out["issues"])


def test_tampered_score_and_rating_fail():
    snap, up, cfg = _setup()
    up["m7"]["score"] += 10
    out = run(snap, up, cfg)
    assert out["status"] == "fail" and any("không khớp công thức" in i["message"] for i in out["issues"])
    snap, up, cfg = _setup()
    up["m7"]["rating"] = "Mua mạnh" if up["m7"]["rating"] != "Mua mạnh" else "Bán"
    assert any("Khuyến nghị" in i["message"] for i in run(snap, up, cfg)["issues"])


def test_lookahead_and_foreign_target_are_fatal():
    snap, up, cfg = _setup()
    bad = copy.deepcopy(snap)
    bad["prices"]["rows"].append({**bad["prices"]["rows"][-1], "date": "2026-12-31"})
    assert run(bad, up, cfg)["status"] == "fail"
    up["m7"]["target"] = {"base": 1.0, "bull": 2.0, "bear": 0.5, "method": "x", "assumptions": []}
    assert any("giá mục tiêu" in i["message"].lower() for i in run(snap, up, cfg)["issues"])


def test_stub_modules_warn_not_fail():
    snap, up, cfg = _setup()
    up["m4"]["status"] = "stub"
    out = run(snap, up, cfg)
    assert out["status"] == "warn" and any("M4" in i["message"] for i in out["issues"])


def test_quality_gate_unscored_skips_formula_and_rating_checks():
    """FR-008: khi quality_gate.scored is False, không fail vì công thức điểm / ngưỡng khuyến nghị."""
    snap, up, cfg = _setup()
    flags = [f for f in snap["meta"].get("flags", []) if not str(f).startswith("quality_")]
    flags += ["quality_tier_insufficient", "quality_illiquid"]
    snap["meta"]["flags"] = flags
    up["m4"]["target"] = {"base": 99.0, "bull": 120.0, "bear": 80.0, "method": "x", "assumptions": []}
    up["m7"] = run_m7(snap, up, cfg)
    assert up["m7"]["score"] is None and up["m7"]["quality_gate"]["scored"] is False
    assert up["m7"]["target"] is None
    out = run(snap, up, cfg)
    assert validate(out, "validation") == []
    assert not any("không khớp công thức" in i["message"] for i in out["issues"])
    assert not any("Khuyến nghị" in i["message"] and "không khớp ngưỡng" in i["message"] for i in out["issues"])
    assert not any("giá mục tiêu" in i["message"].lower() for i in out["issues"])
    # kiểm tra khác vẫn chạy (vd. synthetic/stub không bắt buộc fatal)
    assert out["checked"] > 0


def test_quality_gate_unscored_skips_target_vs_m4_even_if_tampered():
    """Khi scored is False, M8 không so target với M4 (dù M4 có target)."""
    snap, up, cfg = _setup()
    flags = [f for f in snap["meta"].get("flags", []) if not str(f).startswith("quality_")]
    snap["meta"]["flags"] = flags + ["quality_tier_insufficient", "quality_illiquid"]
    up["m4"]["target"] = {"base": 1.0, "bull": 2.0, "bear": 0.5, "method": "x", "assumptions": []}
    up["m7"] = run_m7(snap, up, cfg)
    assert up["m7"]["target"] is None
    out = run(snap, up, cfg)
    assert not any(i.get("where") == "m7.target" and i["severity"] == "fatal" for i in out["issues"])
