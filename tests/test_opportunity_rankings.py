from stockai.api.store import ResultStore
from stockai.api.opportunity_data import recent_closes


def test_price_trend_uses_twenty_sorted_sessions_without_future_or_invalid_closes():
    rows = [{"date": f"2026-09-{i:02d}", "close": i} for i in range(1, 29)]
    rows += [{"date": "2027-01-01", "close": 999}, {"date": "2026-09-29", "close": float("nan")}, {"date": "2026-09-30", "close": 0}, None]
    result = recent_closes({"prices": {"rows": list(reversed(rows))}}, "2026-10-08")
    assert len(result) == 20
    assert result[0] == {"date": "2026-09-09", "close": 9}
    assert result[-1] == {"date": "2026-09-28", "close": 28}


def test_ranking_never_promotes_raw_target_or_target_blocked_by_gate():
    base = {"ticker": "ABC", "company": {}, "m4": {"metrics": {"price_close": {"value": 100}}, "target": {"base": 999}}, "m7": {"score": 70, "quality_gate": {"scored": True}}}
    store = object.__new__(ResultStore)
    assert store.ranking_row(base)["reference_price"] is None
    base["m7"]["target"] = {"base": 120}
    assert store.ranking_row(base)["reference_price"] == 120
    assert store.ranking_row(base)["upside_pct"] == 20
    base["m7"]["quality_gate"]["scored"] = False
    assert store.ranking_row(base)["reference_price"] is None
    assert store.ranking_row(base)["upside_pct"] is None
