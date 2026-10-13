"""US3: M8 warn debate_ungrounded."""
from __future__ import annotations

import copy

from stockai.m7_scoring.run import run as run_m7
from stockai.m8_validate.run import run as run_m8
from stockai.pipeline import load_cfg
from tests.helpers_m7_debate import demo_snapshot, rich_upstream


def _base():
    snap = demo_snapshot()
    # bỏ quality flags để scored
    flags = [f for f in (snap["meta"].get("flags") or []) if not str(f).startswith("quality_")]
    snap = copy.deepcopy(snap)
    snap["meta"]["flags"] = flags
    cfg = load_cfg("long_term")
    up = rich_upstream()
    up["m7"] = run_m7(snap, up, cfg)
    return snap, up, cfg


def test_ungrounded_refs_warn():
    snap, up, cfg = _base()
    up["m7"] = copy.deepcopy(up["m7"])
    up["m7"]["bull"] = [{"text": "bịa số", "refs": ["not_a_ref"]}]
    up["m7"]["bear"] = [{"text": "thiếu", "refs": []}]
    out = run_m8(snap, up, cfg)
    msgs = [i["message"] for i in out["issues"] if "debate_ungrounded" in i["message"]]
    assert msgs
    assert any(i["severity"] == "warn" and i.get("where", "").startswith("m7.bull") for i in out["issues"])
    # không biến thành fatal chỉ vì refs
    assert not any(i["severity"] == "fatal" and "debate_ungrounded" in i["message"] for i in out["issues"])


def test_grounded_no_ungrounded_warn():
    snap, up, cfg = _base()
    up["m7"] = copy.deepcopy(up["m7"])
    up["m7"]["bull"] = [
        {"text": "ROE ổn.", "refs": ["m2.roe"]},
        {"text": "PE hợp lý.", "refs": ["m4.pe", "n1"]},
    ]
    up["m7"]["bear"] = [
        {"text": "Beta cao.", "refs": ["m6.beta"]},
        {"text": "Vol.", "refs": ["m6.vol_20d"]},
    ]
    out = run_m8(snap, up, cfg)
    assert not any("debate_ungrounded" in i["message"] for i in out["issues"])


def test_quality_gate_unscored_skips_refs_warn():
    snap = demo_snapshot()
    flags = [f for f in (snap["meta"].get("flags") or []) if not str(f).startswith("quality_")]
    snap = copy.deepcopy(snap)
    snap["meta"]["flags"] = flags + ["quality_tier_insufficient", "quality_illiquid"]
    cfg = load_cfg("long_term")
    up = rich_upstream()
    up["m7"] = run_m7(snap, up, cfg)
    assert up["m7"]["quality_gate"]["scored"] is False
    # quality_gate bull không có refs — không được warn debate_ungrounded
    out = run_m8(snap, up, cfg)
    assert not any("debate_ungrounded" in i["message"] for i in out["issues"])
