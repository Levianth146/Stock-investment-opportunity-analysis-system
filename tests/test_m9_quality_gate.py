"""M9: PDF phản ánh quality gate (insufficient / limited); không crash khi score is None."""
from __future__ import annotations

import json
from pathlib import Path

import pymupdf
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


def _pages_text(path: str) -> list[str]:
    with pymupdf.open(path) as doc:
        return [p.get_text() for p in doc]


def test_m9_insufficient_pdf_not_ranked(tmp_path):
    snap = _snap(["quality_tier_insufficient", "quality_illiquid", "quality_prices_lt_750"])
    up = _upstream()
    up["m7"] = run_m7(snap, up, CFG)
    assert up["m7"]["score"] is None and up["m7"]["target"] is None
    up["m8"] = {"status": "pass", "checked": 1, "issues": []}
    out = run_m9(snap, up, {**CFG, "out_dir": str(tmp_path), "cover": False})
    assert out["ranked"] is False
    pages = _pages_text(out["pdf_path"])
    assert len(pages) == 1
    txt = pages[0]
    assert "Chưa đủ dữ liệu để xếp hạng" in txt or "chưa đủ dữ liệu để xếp hạng" in txt
    assert "thanh khoản quá thấp" in txt
    assert "điểm trên thang" not in txt and "Khuyến nghị" not in txt
    with pymupdf.open(out["pdf_path"]) as doc:
        assert "ranking_status=NOT RANKED" in (doc.metadata.get("keywords") or "")


def test_m9_limited_pdf_scored_with_limitations(tmp_path):
    snap = _snap(["quality_tier_limited", "quality_news_few", "quality_low_liquidity"])
    up = _upstream()
    up["m7"] = run_m7(snap, up, CFG)
    assert isinstance(up["m7"]["score"], (int, float))
    up["m8"] = {"status": "pass", "checked": 1, "issues": []}
    out = run_m9(snap, up, {**CFG, "out_dir": str(tmp_path)})
    assert out["ranked"] is True
    txt = "\n".join(_pages_text(out["pdf_path"]))
    assert "chấm điểm có giới hạn" in txt
    assert "quá ít tin tức" in txt
