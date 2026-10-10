"""M9: PDF phản ánh quality gate (insufficient / limited); không crash khi score is None."""
import json
from pathlib import Path

import yaml

from stockai.m7_scoring.run import run as run_m7
from stockai.m9_report.run import run as run_m9

FIX = Path(__file__).resolve().parents[1] / "fixtures" / "snapshot_DEMO.json"
CFG = yaml.safe_load((Path(__file__).resolve().parents[1] / "config" / "scoring.yaml").read_text(encoding="utf-8"))
CFG = {**CFG, "profile": "long_term"}


def _upstream():
    up = {
        m: {"module": m, "status": "ok", "score": 60.0, "metrics": {}, "evidence": [], "flags": []}
        for m in ("m2", "m3", "m4", "m5", "m6")
    }
    up["m6"]["score"] = 30.0
    up["m4"]["target"] = {"base": 10.0, "bull": 12.0, "bear": 8.0, "method": "stub", "assumptions": []}
    return up


def _snap(extra_flags: list[str]) -> dict:
    snap = json.loads(FIX.read_text(encoding="utf-8"))
    flags = [f for f in snap["meta"].get("flags", []) if not str(f).startswith("quality_")]
    snap["meta"]["flags"] = flags + extra_flags
    return snap


def _pdf_bytes(path: str) -> bytes:
    return Path(path).read_bytes()


def test_m9_insufficient_pdf_not_ranked(tmp_path):
    snap = _snap(["quality_tier_insufficient", "quality_illiquid", "quality_prices_lt_750"])
    up = _upstream()
    up["m7"] = run_m7(snap, up, CFG)
    assert up["m7"]["score"] is None and up["m7"]["target"] is None
    up["m8"] = {"status": "pass", "checked": 1, "issues": []}
    cfg = {**CFG, "out_dir": str(tmp_path)}
    out = run_m9(snap, up, cfg)
    raw = _pdf_bytes(out["pdf_path"])
    assert b"NOT RANKED" in raw
    assert b"illiquid" in raw or b"Exclusion reasons" in raw
    # ReportLab escapes parentheses in PDF strings: n/a \(not ranked\)
    assert b"n/a" in raw and b"not ranked" in raw


def test_m9_limited_pdf_scored_with_limitations(tmp_path):
    snap = _snap(["quality_tier_limited", "quality_news_few", "quality_low_liquidity"])
    up = _upstream()
    up["m7"] = run_m7(snap, up, CFG)
    assert isinstance(up["m7"]["score"], (int, float))
    up["m8"] = {"status": "pass", "checked": 1, "issues": []}
    cfg = {**CFG, "out_dir": str(tmp_path)}
    out = run_m9(snap, up, cfg)
    raw = _pdf_bytes(out["pdf_path"])
    assert b"scored with limitations" in raw
    assert b"news_few" in raw or b"Limitations" in raw
