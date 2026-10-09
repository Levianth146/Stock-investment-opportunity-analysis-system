from copy import deepcopy
from datetime import date, timedelta

from stockai.m3_technical.run import run


def _snapshot(count=205, as_of=None):
    start = date(2020, 1, 1)
    rows = []
    for index in range(count):
        rows.append({
            "date": (start + timedelta(days=index)).isoformat(),
            "close": 100 + index,
            "volume": 1000 + index,
        })
    return {
        "meta": {"as_of": as_of or rows[-1]["date"]},
        "prices": {"adjusted": True, "source_id": "prices-test", "rows": rows},
    }


def test_complete_output_and_source_evidence():
    snapshot = _snapshot()
    output = run(snapshot, {}, {})
    assert output["status"] == "ok"
    assert output["score"] == (
        output["metrics"]["trend_score"]["value"]
        + output["metrics"]["momentum_score"]["value"]
        + output["metrics"]["volume_score"]["value"]
    )
    assert output["metrics"]["technical_score"]["note"] == "Strong Bullish"
    assert all(item["source_id"] == "prices-test" for item in output["evidence"])


def test_partial_and_unadjusted_outputs():
    partial = run(_snapshot(10), {}, {})
    assert partial["status"] == "partial"
    assert partial["score"] is None
    assert "m3_insufficient_history_complete_score" in partial["flags"]

    unadjusted = _snapshot()
    unadjusted["prices"]["adjusted"] = False
    output = run(unadjusted, {}, {})
    assert output["status"] == "error"
    assert output["score"] is None
    assert output["metrics"] == {}
    assert "m3_unadjusted_prices" in output["flags"]


def test_future_rows_are_excluded_without_mutating_snapshot():
    snapshot = _snapshot(205)
    snapshot["meta"]["as_of"] = snapshot["prices"]["rows"][200]["date"]
    changed = deepcopy(snapshot)
    for row in changed["prices"]["rows"][201:]:
        row["close"] = -999999
        row["volume"] = 1
    before = deepcopy(snapshot)
    first = run(snapshot, {}, {})
    second = run(changed, {}, {})
    assert first == second
    assert snapshot == before
    assert "m3_lookahead_rows_excluded" in first["flags"]
