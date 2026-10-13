"""Helpers fixture cho tests debate / llm (offline)."""
from __future__ import annotations

import copy
import json
from pathlib import Path

import yaml

FIX = Path(__file__).resolve().parents[1] / "fixtures" / "snapshot_DEMO.json"
SCORING = Path(__file__).resolve().parents[1] / "config" / "scoring.yaml"
LLM = Path(__file__).resolve().parents[1] / "config" / "llm.yaml"


def load_scoring_cfg(profile: str = "long_term") -> dict:
    cfg = yaml.safe_load(SCORING.read_text(encoding="utf-8"))
    llm = yaml.safe_load(LLM.read_text(encoding="utf-8")) if LLM.is_file() else {}
    out = {**cfg, "profile": profile}
    if isinstance(llm, dict):
        out["llm"] = llm
        if isinstance(llm.get("debate"), dict):
            out["debate"] = llm["debate"]
    return out


def demo_snapshot() -> dict:
    return json.loads(FIX.read_text(encoding="utf-8"))


def rich_upstream() -> dict:
    """Upstream m2–m6 với metrics + evidence M5 (news_id) đủ để refs grounded.

    Điểm: F/T/V/S > 50 (Bull), R > 50 (Bear qua d_R < 0).
    """
    up = {
        m: {
            "module": m,
            "status": "ok",
            "score": 60.0,
            "metrics": {},
            "evidence": [{"text": f"evidence {m}", "source_id": None}],
            "flags": [],
        }
        for m in ("m2", "m3", "m4", "m5", "m6")
    }
    up["m2"]["metrics"] = {"roe": {"value": 18.0, "unit": "%"}, "roa": {"value": 1.4}}
    up["m2"]["evidence"] = [
        {"text": "ROE 18,0% và ROA ổn định trong kỳ báo cáo.", "source_id": None}
    ]
    up["m3"]["metrics"] = {"rsi_14": {"value": 55.0}}
    up["m4"]["metrics"] = {"pe": {"value": 12.5}, "pb": {"value": 1.9}}
    up["m4"]["evidence"] = [
        {"text": "P/E = 12,5x so median ngành hợp lý.", "source_id": None}
    ]
    up["m4"]["target"] = {
        "base": 30.0,
        "bull": 36.0,
        "bear": 24.0,
        "method": "test",
        "assumptions": [],
    }
    up["m5"]["metrics"] = {"sentiment": {"value": 0.2}, "sentiment_polarity": {"value": 0.2}}
    # news_id khớp fixtures/snapshot_DEMO.json
    up["m5"]["evidence"] = [
        {"text": "Sentiment theo tiêu đề; tổng hợp.", "source_id": None},
        {"text": "tích cực | DEMO công bố lợi nhuận quý 2 tăng 18%", "news_id": "n0"},
        {"text": "tích cực | DEMO mở rộng nhà máy mới", "news_id": "n1"},
        {"text": "tiêu cực | DEMO bị điều tra chống bán phá giá", "news_id": "n3"},
        {"text": "tiêu cực | Khối ngoại bán ròng DEMO tuần qua", "news_id": "n4"},
    ]
    up["m6"]["metrics"] = {"beta": {"value": 1.1}, "vol_20d": {"value": 0.025}}
    up["m6"]["score"] = 70.0  # R cao → d_R < 0 → Bear
    up["m6"]["evidence"] = [
        {"text": "Beta 1,10 phản ánh rủi ro thị trường cao hơn trung bình.", "source_id": None}
    ]
    return up


def valid_llm_json() -> dict:
    return {
        "bull": [
            {"text": "ROE cao hỗ trợ luận điểm tăng trưởng.", "refs": ["m2.roe"]},
            {"text": "Định giá P/E hợp lý trong kỳ.", "refs": ["m4.pe", "n1"]},
        ],
        "bear": [
            {"text": "Beta phản ánh rủi ro thị trường.", "refs": ["m6.beta"]},
            {"text": "Biến động ngắn hạn cần theo dõi.", "refs": ["m6.vol_20d", "n3"]},
        ],
    }


def snap_with_quality(extra_flags: list[str] | None = None) -> dict:
    snap = demo_snapshot()
    flags = [f for f in (snap["meta"].get("flags") or []) if not str(f).startswith("quality_")]
    if extra_flags:
        flags.extend(extra_flags)
    snap = copy.deepcopy(snap)
    snap["meta"]["flags"] = flags
    return snap
