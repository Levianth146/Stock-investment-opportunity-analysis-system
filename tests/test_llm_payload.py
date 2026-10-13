"""US2: compact payload không chứa prices.rows; news từ M5; module_polarity."""
from __future__ import annotations

import json

from stockai.llm.payload import build_debate_payload, payload_for_llm
from tests.helpers_m7_debate import demo_snapshot, load_scoring_cfg, rich_upstream


def test_payload_excludes_prices_rows():
    snap = demo_snapshot()
    assert snap.get("prices") and snap["prices"].get("rows")
    payload = build_debate_payload(
        snap,
        rich_upstream(),
        load_scoring_cfg(),
        score=55.0,
        rating="Nắm giữ",
        scores={"F": 60, "T": 50, "V": 70, "S": 40, "R": 30},
    )
    blob = json.dumps(payload, ensure_ascii=False)
    assert "prices" not in payload
    assert "prices.rows" not in blob
    assert len(blob) < 50_000
    llm = payload_for_llm(payload)
    assert "news_ref_map" not in llm
    assert "metrics_allowed" in llm
    assert "module_polarity" in llm
    assert set(llm["module_polarity"]) == {"F", "T", "V", "S", "R"}


def test_news_from_m5_evidence_not_snapshot_head():
    snap = demo_snapshot()
    up = rich_upstream()
    payload = build_debate_payload(snap, up, load_scoring_cfg(), score=55.0, rating="Nắm giữ")
    # max 6; mọi id phải đến từ m5 evidence news_id
    m5_ids = {
        str(ev["news_id"])
        for ev in up["m5"]["evidence"]
        if isinstance(ev, dict) and ev.get("news_id")
    }
    assert payload["news"]
    assert len(payload["news"]) <= 6
    for n in payload["news"]:
        assert n["id"] in m5_ids
        assert n["ref"].startswith("n")
        assert n.get("label") in ("pos", "neg")
    # evidence_summaries ≤ 2 dòng / module → tối đa 10
    assert len(payload["evidence_summaries"]) <= 10
