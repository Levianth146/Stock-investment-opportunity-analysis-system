"""FR-008 / FR-009: M7 tiêu thụ quality_tier_* trên snapshot."""
import copy
import json
from pathlib import Path

import yaml

from stockai.contracts.schemas import validate
from stockai.m7_scoring.run import run

FIX = Path(__file__).resolve().parents[1] / "fixtures" / "snapshot_DEMO.json"
CFG = yaml.safe_load((Path(__file__).resolve().parents[1] / "config" / "scoring.yaml").read_text(encoding="utf-8"))
CFG = {**CFG, "profile": "long_term"}

TRADE = {"Mua mạnh", "Mua", "Nắm giữ", "Giảm tỷ trọng", "Bán"}


def _upstream():
    up = {
        m: {"module": m, "status": "ok", "score": 60.0, "metrics": {}, "evidence": [], "flags": []}
        for m in ("m2", "m3", "m4", "m5", "m6")
    }
    up["m6"]["score"] = 30.0
    return up


def _snap(extra_flags: list[str] | None = None) -> dict:
    snap = json.loads(FIX.read_text(encoding="utf-8"))
    flags = list(snap["meta"].get("flags") or [])
    flags = [f for f in flags if not str(f).startswith("quality_")]
    if extra_flags:
        flags.extend(extra_flags)
    snap["meta"]["flags"] = flags
    return snap


def test_insufficient_not_ranked():
    snap = _snap(["quality_tier_insufficient", "quality_illiquid", "quality_prices_lt_750"])
    out = run(snap, _upstream(), CFG)
    assert validate(out, "result") == []
    assert out["score"] is None
    assert out["rating"] == "Không xếp hạng"
    assert out["target"] is None
    assert out["quality_gate"]["scored"] is False
    assert out["quality_gate"]["tier"] == "insufficient"
    assert "illiquid" in out["quality_gate"]["reasons"]
    assert "quality_tier_insufficient" in out["flags"]
    assert "scoring_skipped_insufficient" in out["flags"]


def test_limited_scored_with_reasons():
    snap = _snap(["quality_tier_limited", "quality_news_few", "quality_low_liquidity"])
    out = run(snap, _upstream(), CFG)
    assert validate(out, "result") == []
    assert isinstance(out["score"], (int, float))
    assert out["rating"] in TRADE
    assert out["quality_gate"]["scored"] is True
    assert out["quality_gate"]["tier"] == "limited"
    assert "news_few" in out["quality_gate"]["reasons"]
    assert "quality_tier_limited" in out["flags"]
    assert "quality_news_few" in out["flags"]


def test_absent_tier_still_scores():
    snap = _snap([])
    out = run(snap, _upstream(), CFG)
    assert validate(out, "result") == []
    assert isinstance(out["score"], (int, float))
    assert out["rating"] in TRADE
    assert out["quality_gate"]["tier"] == "absent"
    assert out["quality_gate"]["scored"] is True
    assert "quality_tier_absent" in out["flags"]
