"""Frontend contract: snapshot dates, validation, CORS and static build delivery."""
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from stockai.api.app import create_app
from stockai.api.analysis import analyze_snapshot, financial_reports
from stockai.api.store import ResultStore


@pytest.fixture
def client(tmp_path):
    snapshots = tmp_path / "snapshots"
    snapshots.mkdir()
    root = Path(__file__).resolve().parents[1]
    snapshot = json.loads((root / "fixtures/snapshot_DEMO.json").read_text(encoding="utf-8"))
    snapshot["meta"]["ticker"] = "DEMO"
    snapshot["meta"]["as_of"] = "2026-10-08"
    (snapshots / "DEMO_2026-10-08.json").write_text(json.dumps(snapshot), encoding="utf-8")
    cfg = {"snapshots_dir": str(snapshots), "cache_dir": str(tmp_path / "cache"),
           "asof": "2026-10-08", "cors_origins": ["http://localhost:5173"]}
    return TestClient(create_app(api_cfg=cfg, store=ResultStore(cfg)))


def test_frontend_analysis_contract(client):
    response = client.post("/api/analyze", json={"ticker": " demo ", "profile": "swing"})
    assert response.status_code == 200
    data = response.json()
    assert data["ticker"] == "DEMO"
    assert data["as_of"] == data["asof"] == "2026-10-08"
    assert data["profile"] == "swing"
    assert data["data_source"] == "snapshot"
    assert isinstance(data["bull"], list)
    assert "score" in data and "target_price" in data and "disclaimer" in data
    assert data["report_url"] == "/api/report/DEMO.pdf?profile=swing"
    detail = client.get("/api/tickers/DEMO?profile=swing").json()
    assert data["score"] == detail["result"]["score"]
    assert data["recommendation"] == detail["result"]["rating"]


def test_news_endpoint_retains_legacy_items_and_adds_archive(client):
    result = client.get("/api/tickers/DEMO/news").json()
    assert isinstance(result["items"], list)
    assert isinstance(result["articles"], list)
    assert result["classification_method"] == "headline_lexicon"


@pytest.mark.parametrize("payload,status", [
    ({"ticker": "DEMO", "as_of": "2026-10-09"}, 409),
    ({"ticker": "DEMO", "as_of": "invalid"}, 422),
    ({"ticker": "DEMO", "profile": "invalid"}, 422),
    ({"ticker": "../x"}, 422),
    ({"ticker": "ZZZZ"}, 404),
    ({}, 422),
])
def test_invalid_requests(client, payload, status):
    assert client.post("/api/analyze", json=payload).status_code == status


def test_static_frontend_and_api_routes(client):
    response = client.get("/")
    assert response.status_code == 200
    assert 'id="root"' in response.text
    assert "/api-client.js" in response.text
    assert client.get("/api-client.js").status_code == 200
    assert "/assets/analysis-panels.js" in response.text
    assert client.get("/assets/analysis-panels.js").status_code == 200
    assert "/assets/ticker-picker.js" in response.text
    assert client.get("/assets/ticker-picker.js").status_code == 200
    assert client.get("/assets/index-CI87uAUB.js").status_code == 200
    assert client.get("/api/does-not-exist").status_code == 404
    assert client.get("/assets/does-not-exist.js").status_code == 404
    assert client.get("/docs").status_code == 200


def test_frontend_cors_preflight(client):
    headers = {"Origin": "http://localhost:5173", "Access-Control-Request-Method": "POST",
               "Access-Control-Request-Headers": "content-type"}
    response = client.options("/api/analyze", headers=headers)
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == headers["Origin"]
    headers["Origin"] = "http://untrusted.example"
    assert client.options("/api/analyze", headers=headers).status_code == 400


def test_analysis_includes_real_financial_reports(client):
    data = client.post("/api/analyze", json={"ticker": "DEMO"}).json()
    reports = data["financial_reports"]
    assert reports["unit"] == "VND"
    fixture = json.loads((Path(__file__).resolve().parents[1] / "fixtures/snapshot_DEMO.json").read_text(encoding="utf-8"))
    expected = sorted(fixture["financials"]["annual"], key=lambda row: row["period"])
    assert [row["period"] for row in reports["annual"]] == [row["period"] for row in expected]
    for actual, source in zip(reports["annual"], expected):
        for key in ("revenue", "total_assets", "total_equity", "cfo", "cfi", "cff", "eps"):
            assert actual["items"][key] == source["items"][key]


def test_financial_reports_filter_dates_and_preserve_missing_values():
    snapshot = {"financials": {"unit": "VND", "annual": [
        {"period": "2025", "published_at": "2026-03-31", "items": {"cfo": 0, "cfi": -2e9, "eps": 1500, "cash": None, "revenue": float("nan")}},
        {"period": "2024", "published_at": "2025-03-31", "items": {"total_assets": 1e9}},
        {"period": "2026", "published_at": "2027-03-31", "items": {"cfo": 9e9}},
        {"period": "2023", "items": {"cfo": 9e9}},
    ]}}
    reports = financial_reports(snapshot, "2026-10-08")
    assert [row["period"] for row in reports["annual"]] == ["2024", "2025"]
    assert reports["annual"][1]["items"] == {"cfo": 0, "cfi": -2e9, "eps": 1500, "cash": None, "revenue": None}
    empty = financial_reports({}, "2026-10-08")
    assert empty["unit"] is None
    assert empty["annual"] == empty["quarterly"] == []


def test_quarterly_reports_preserve_bank_items_and_publication_metadata():
    snapshot = {"company": {"is_bank": True}, "financials": {
        "unit": "VND", "published_at_note": "Estimated publication dates",
        "quarterly": [
            {"period": "2026Q3", "published_at": "2026-11-15", "items": {"net_income": 3e9}},
            {"period": "2026Q2", "published_at": "2026-08-14", "published_at_estimated": True,
             "source_id": "src_fin_quarter", "items": {"nim": 0.0288, "cir": 0.3204, "customer_loans": 10e9}},
            {"period": "2026Q1", "published_at": "2026-05-15", "items": {"net_income": 1e9}},
        ]}}
    reports = financial_reports(snapshot, "2026-10-08")
    assert reports["is_bank"] is True
    assert reports["published_at_note"] == "Estimated publication dates"
    assert [row["period"] for row in reports["quarterly"]] == ["2026Q1", "2026Q2"]
    assert reports["quarterly"][1]["items"]["nim"] == 0.0288
    assert reports["quarterly"][1]["source_id"] == "src_fin_quarter"
    assert reports["quarterly"][1]["published_at_estimated"] is True


def test_analysis_panels_use_each_tickers_pipeline_results(tmp_path):
    snapshots = tmp_path / "snapshots"
    snapshots.mkdir()
    root = Path(__file__).resolve().parents[1]
    original = json.loads((root / "fixtures/snapshot_DEMO.json").read_text(encoding="utf-8"))
    for symbol in ("AAA", "BBB"):
        snapshot = json.loads(json.dumps(original))
        snapshot["meta"].update(ticker=symbol, as_of="2026-10-08")
        if symbol == "BBB":
            for index, row in enumerate(snapshot["prices"]["rows"]):
                factor = 2 * (1.05 if index % 2 else 0.95)
                for key in ("open", "high", "low", "close"):
                    if row.get(key) is not None:
                        row[key] *= factor
        destination = snapshots if symbol == "AAA" else snapshots / "market"
        destination.mkdir(exist_ok=True)
        (destination / f"{symbol}_2026-10-08.json").write_text(json.dumps(snapshot), encoding="utf-8")
    cfg = {"snapshots_dir": str(snapshots), "cache_dir": str(tmp_path / "cache"), "asof": "2026-10-08"}
    store = ResultStore(cfg)
    client = TestClient(create_app(api_cfg=cfg, store=store))
    a = client.post("/api/analyze", json={"ticker": "AAA"}).json()
    b = client.post("/api/analyze", json={"ticker": "BBB"}).json()
    for key, metric in (("m3", "close"), ("m4", "pe"), ("m6", "annualized_volatility")):
        av = a["modules"][key]["metrics"][metric]["value"]
        bv = b["modules"][key]["metrics"][metric]["value"]
        assert av is not None and bv is not None and av != bv
    for symbol, data in (("AAA", a), ("BBB", b)):
        bundle = store.get_bundle(symbol, "long_term", debate_mode="template")
        assert data["validation"] == bundle["m8"]
        assert data["target"] == bundle["m7"].get("target")
        assert data["bull"] == bundle["m7"].get("bull", [])
        assert data["bear"] == bundle["m7"].get("bear", [])
        assert data["modules"]["m5"] == bundle["m5"]
        assert data["debate_source"] == "template"
        expected = sorted((row for row in store.load_snapshot(symbol)["prices"]["rows"]
                           if row["date"] <= store.asof), key=lambda row: row["date"])[-252:]
        assert len(data["price_history"]) == len(expected)
        assert data["price_history"][-1]["close"] == expected[-1]["close"]
        assert all(row["date"] <= data["as_of"] for row in data["price_history"])


def test_news_and_debate_share_canonical_refs_and_preserve_source_metadata():
    from types import SimpleNamespace

    snapshot = {"meta": {"ticker": "AAA", "as_of": "2026-10-08"}, "news": [
        {"id": "first-in-snapshot", "title": "Source title A", "published_at": "2026-10-06"},
        {"id": "first-in-debate", "title": "Source title B", "summary": "Original summary", "source": "Original source",
         "url": "https://example.com/b", "published_at": "2026-10-07"},
        {"id": "future", "title": "Future article", "published_at": "2026-10-09"},
    ]}
    bundle = {"m5": {"status": "ok", "score": 60, "evidence": [
        {"text": "tích cực | Source title B", "news_id": "first-in-debate"},
        {"text": "tiêu cực | Source title A", "news_id": "first-in-snapshot"},
        {"text": "tích cực | Future article", "news_id": "future"},
    ]}, "m7": {"bull": [{"text": "Backed by article B", "refs": ["n1"]}], "bear": []}}
    store = SimpleNamespace(asof="2026-10-08", get_bundle=lambda *args, **kwargs: bundle,
                            load_snapshot=lambda ticker: snapshot)
    data = analyze_snapshot(store, "AAA", "long_term")
    assert data["news_ref_map"]["n1"] == "first-in-debate"
    assert data["news_ref_map"]["n2"] == "first-in-snapshot"
    assert [item["id"] for item in data["news"]] == ["first-in-debate", "first-in-snapshot"]
    first = data["news"][0]
    assert first["label"] == "pos" and first["ref"] == "n1"
    assert first["source"] == "Original source"
    assert first["summary"] == "Original summary"
    assert first["url"] == "https://example.com/b"
    assert data["bull"][0]["refs"] == ["n1"]
    assert data["bear"] == []


def test_full_ticker_catalog_includes_nested_and_unranked_without_scoring(tmp_path, monkeypatch):
    snapshots = tmp_path / "snapshots"
    nested = snapshots / "market"
    nested.mkdir(parents=True)
    for index in range(515):
        ticker = f"T{index:03}"
        snapshot = {"meta": {"ticker": ticker, "data_status": {"financials": "missing"}},
                    "company": {"name": f"Company {ticker}", "exchange": "HNX"},
                    "prices": {"rows": [{"date": "2026-10-08", "close": 12000, "volume": 0},
                                         {"date": "2026-10-09", "close": 999999},
                                         {"date": "2026-10-07", "close": 10000}]}}
        (nested / f"{ticker}_2026-10-08.json").write_text(json.dumps(snapshot), encoding="utf-8")
    (snapshots / "T000_2026-10-08.json").write_text(json.dumps({"company": {"name": "Root company"}}), encoding="utf-8")
    (nested / "OLD_2026-10-07.json").write_text("{}", encoding="utf-8")
    (nested / "_manifest_2026-10-08.json").write_text("{}", encoding="utf-8")
    cfg = {"snapshots_dir": str(snapshots), "cache_dir": str(tmp_path / "cache"), "asof": "auto"}
    store = ResultStore(cfg)

    def no_scoring(*args, **kwargs):
        raise AssertionError("Catalog must not run pipeline or filter through rankings")

    monkeypatch.setattr(store, "get_bundle", no_scoring)
    client = TestClient(create_app(api_cfg=cfg, store=store))
    response = client.get("/api/tickers")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == len(data["items"]) == 515
    assert data["asof"] == "2026-10-08"
    assert data["items"][0]["name"] == "Root company"
    assert data["items"][-1]["symbol"] == "T514"
    sample = data["items"][1]
    assert sample["current_price"] == 12000
    assert sample["price_change_percent"] == 20
    assert sample["volume"] == 0
    assert sample["data_status"]["financials"] == "missing"
    assert store.snapshot_path("T000").parent == snapshots
    assert store.snapshot_path("T514").parent == nested
    # Newest-date discovery is recursive and does not mix snapshot dates.
    (nested / "NEW_2026-10-09.json").write_text("{}", encoding="utf-8")
    newer = ResultStore(cfg)
    assert newer.asof == "2026-10-09"
    assert newer.list_tickers() == ["NEW"]


@pytest.mark.parametrize("ticker", ["ABR", "AMC"])
def test_unranked_snapshot_keeps_prices_and_explains_skipped_collection(tmp_path, ticker):
    root = Path(__file__).resolve().parents[1]
    snapshot = json.loads((root / "fixtures/snapshot_DEMO.json").read_text(encoding="utf-8"))
    snapshot["meta"].update(ticker=ticker, as_of="2026-10-08",
                            flags=["quality_tier_insufficient", "quality_illiquid", "fetch_skipped_early"],
                            data_status={"prices": "ok", "financials": "missing", "news": "missing"})
    snapshot["financials"]["annual"] = []
    snapshot["financials"]["quarterly"] = []
    snapshot["news"] = []
    snapshots = tmp_path / "snapshots"
    snapshots.mkdir()
    (snapshots / f"{ticker}_2026-10-08.json").write_text(json.dumps(snapshot), encoding="utf-8")
    cfg = {"snapshots_dir": str(snapshots), "cache_dir": str(tmp_path / "cache"), "asof": "2026-10-08"}
    store = ResultStore(cfg)
    client = TestClient(create_app(api_cfg=cfg, store=store))
    response = client.post("/api/analyze", json={"ticker": ticker})
    assert response.status_code == 200
    body = response.json()
    assert body["ticker"] == ticker
    assert body["current_price"] is not None and body["price_history"]
    assert body["score"] is None and body["target_price"] is None
    assert all(value is None for value in body["scores"].values())
    assert body["quality_gate"]["scored"] is False
    assert body["data_availability"]["collection_incomplete"] is True
    assert body["data_availability"]["price_sessions"] > 0
    assert body["data_availability"]["annual_reports"] == 0
    assert body["data_availability"]["quarterly_reports"] == 0
    assert body["data_availability"]["news_articles"] == 0
    catalog = client.get("/api/tickers").json()["items"][0]
    assert catalog["quality_tier"] == "insufficient"
    assert catalog["quality_reasons"] == ["illiquid"]
    assert catalog["collection_incomplete"] is True


def test_analyze_ignores_invalid_latest_closes_and_preserves_snapshot_company():
    from types import SimpleNamespace

    snapshot = {"company": {"name": "Company ABR", "exchange": "HSX"}, "prices": {"rows": [
        {"date": "2026-10-05", "close": 10000},
        {"date": "2026-10-06", "close": 10350},
        {"date": "2026-10-07", "close": None},
        {"date": "2026-10-08", "close": float("nan")},
        {"date": "2026-10-08", "close": True},
        {"date": "2026-10-09", "close": 999999},
    ]}}
    store = SimpleNamespace(asof="2026-10-08", get_bundle=lambda *a, **kw: {"company": {"name": None}},
                            load_snapshot=lambda ticker: snapshot)
    body = analyze_snapshot(store, "ABR", "long_term")
    assert body["company"]["name"] == "Company ABR"
    assert body["current_price"] == 10350
    assert body["price_date"] == "2026-10-06"
    assert body["price_change"] == 350
    assert body["data_availability"]["price_sessions"] == 2


def test_store_rescans_new_snapshots_without_restart(tmp_path, monkeypatch):
    snaps = tmp_path / "s"
    snaps.mkdir()
    (snaps / "AAA_2026-10-08.json").write_text("{}", encoding="utf-8")
    store = ResultStore({"snapshots_dir": str(snaps), "cache_dir": str(tmp_path / "c"), "asof": "auto"})
    assert store.asof == "2026-10-08"
    assert store.list_tickers() == ["AAA"]
    (snaps / "AAA_2026-10-15.json").write_text("{}", encoding="utf-8")
    (snaps / "BBB_2026-10-15.json").write_text("{}", encoding="utf-8")
    store._last_scan -= ResultStore.RESCAN_SEC + 1  # giả lập hết chu kỳ quét
    assert store.asof == "2026-10-15"
    assert store.list_tickers() == ["AAA", "BBB"]
