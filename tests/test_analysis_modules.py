import json
from pathlib import Path

from stockai.contracts.schemas import validate
from stockai.m2_fundamental.run import run as run_m2
from stockai.m3_technical.run import run as run_m3
from stockai.m4_valuation.run import run as run_m4
from stockai.m5_sentiment.run import run as run_m5
from stockai.m6_risk.run import run as run_m6
from stockai.m7_scoring.debate import run_debate


FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "snapshot_DEMO.json"


def _snapshot():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_analysis_modules_calculate_from_normalized_snapshot():
    snapshot = _snapshot()
    outputs = {
        "m2": run_m2(snapshot, {}, {}),
        "m3": run_m3(snapshot, {}, {}),
        "m4": run_m4(snapshot, {}, {"m4": {
            "sector_stats_path": str(Path(__file__).parent / "fixtures/m4_sector_stats_mini.json"),
        }}),
        "m5": run_m5(snapshot, {}, {}),
        "m6": run_m6(snapshot, {}, {}),
    }

    for output in outputs.values():
        assert output["status"] in {"ok", "partial"}
        if output["score"] is not None:
            assert 0 <= output["score"] <= 100
        assert validate(output, "module_out") == []
    assert all(outputs[name]["score"] is not None for name in ("m2", "m3", "m4"))
    # DEMO is explicitly synthetic: M6 computes metrics but withholds a risk score.
    assert outputs["m6"]["score"] is None
    assert "m6_synthetic_data" in outputs["m6"]["flags"]
    assert outputs["m6"]["metrics"]["annualized_volatility"]["value"] is not None
    assert outputs["m4"]["target"]["base"] is not None
    # M2 on main exposes profitability as a ratio, rather than a percentage.
    assert outputs["m2"]["metrics"]["roe"]["unit"] == "ratio"
    assert outputs["m2"]["metrics"]["roe"]["value"] > 0

    bull, bear = run_debate(snapshot, outputs, {"debate": {"mode": "template"}})
    assert all(not claim["text"].startswith("[stub]") for claim in bull + bear)


def test_missing_inputs_are_reported_without_fabricated_scores():
    empty_snapshot = {
        "meta": {"ticker": "EMPTY", "as_of": "2026-10-09", "data_status": {}},
        "company": {"is_bank": False},
        "financials": {"annual": []},
        "prices": {"rows": []},
        "index": {"rows": []},
        "news": [],
        "peers": [],
    }

    outputs = (
        run_m2(empty_snapshot, {}, {}),
        run_m3(empty_snapshot, {}, {}),
        run_m4(empty_snapshot, {}, {}),
        run_m5(empty_snapshot, {}, {}),
        run_m6(empty_snapshot, {}, {}),
    )
    # M2 reports an error when no eligible annual statements exist.
    assert outputs[0]["status"] == "error"
    assert "m2_financials_unavailable" in outputs[0]["flags"]
    assert all(output["status"] == "partial" for output in outputs[1:])
    assert all(output["score"] is None for output in outputs)
    assert all(output["flags"] for output in outputs)


def test_neutral_news_does_not_create_a_neutral_sentiment_score():
    snapshot = {
        "meta": {"as_of": "2026-10-09"},
        "news": [
            {"id": f"n{i}", "title": f"Thông báo hoạt động thường kỳ {i}", "published_at": "2026-10-01"}
            for i in range(4)
        ],
    }

    output = run_m5(snapshot, {}, {})

    assert output["status"] == "partial"
    assert output["score"] is None
    assert output["metrics"]["news_directional_count"]["value"] == 0
