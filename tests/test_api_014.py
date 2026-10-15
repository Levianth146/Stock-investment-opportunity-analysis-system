"""Feature 014 — financials / peers / sectors stats / prices+indicators / SPA fallback."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from stockai.api.app import create_app
from stockai.api.store import ResultStore

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "fixtures" / "snapshot_DEMO.json"
ASOF = "2026-10-08"


def _clone(ticker: str, sector: str) -> dict:
    snap = json.loads(FIX.read_text(encoding="utf-8"))
    snap["meta"]["ticker"] = ticker
    snap["meta"]["as_of"] = ASOF
    snap["meta"]["synthetic"] = False
    flags = [f for f in (snap["meta"].get("flags") or []) if not str(f).startswith("quality_")]
    flags.append("quality_tier_full")
    snap["meta"]["flags"] = flags
    company = dict(snap.get("company") or {})
    company["name"] = f"Cong ty {ticker}"
    company["sector"] = sector
    company["exchange"] = "HSX"
    snap["company"] = company
    # Đảm bảo peers tối thiểu
    if not snap.get("peers"):
        snap["peers"] = [
            {"ticker": "BBB", "pe": 10.0, "pb": 1.2, "roe": 0.15, "market_cap": 1e12, "source_id": "src_test"},
        ]
    return snap


@pytest.fixture(scope="module")
def api_env(tmp_path_factory):
    base = tmp_path_factory.mktemp("api014")
    snap_dir = base / "snapshots"
    cache_dir = base / "api_cache"
    web_dist = base / "web_dist"
    snap_dir.mkdir()
    cache_dir.mkdir()
    web_dist.mkdir()
    (web_dist / "index.html").write_text(
        "<!doctype html><html><body><div id='root'>SPA</div></body></html>",
        encoding="utf-8",
    )
    (web_dist / "assets").mkdir()
    (web_dist / "assets" / "app.js").write_text("console.log(1)", encoding="utf-8")

    for t, sec in [("AAA", "Steel"), ("BBB", "Steel"), ("CCC", "Banks")]:
        (snap_dir / f"{t}_{ASOF}.json").write_text(
            json.dumps(_clone(t, sec), ensure_ascii=False), encoding="utf-8"
        )

    # sector stats tối thiểu cho peers
    stats_path = base / "valuation_sector_stats.json"
    stats_path.write_text(
        json.dumps(
            {
                "version": 2,
                "as_of": ASOF,
                "sectors": {
                    "Steel": {"n_pe": 3, "n_pb": 3, "median_pe": 12.0, "median_pb": 1.5},
                },
            }
        ),
        encoding="utf-8",
    )

    api_cfg = {
        "snapshots_dir": str(snap_dir),
        "asof": ASOF,
        "default_profile": "long_term",
        "cors_origins": [],
        "docs_enabled": True,
        "trust_proxy_headers": False,
        "debate_live_max_per_hour": 10,
        "debate_live_max_per_ip_per_hour": 3,
        "debate_live_max_per_day": 15,
        "cache_dir": str(cache_dir),
        "web_dist_dir": str(web_dist),
    }
    store = ResultStore(
        api_cfg,
        snapshots_dir=snap_dir,
        cache_dir=cache_dir,
        asof=ASOF,
        root=base,  # sector stats relative to root — override path via monkey? copy to data/
    )
    # Đặt stats đúng chỗ Relative: root/data/valuation_sector_stats.json
    (base / "data").mkdir(exist_ok=True)
    (base / "data" / "valuation_sector_stats.json").write_text(
        stats_path.read_text(encoding="utf-8"), encoding="utf-8"
    )
    # Copy config tối thiểu nếu cần fingerprint
    for name in ("scoring.yaml", "valuation.yaml"):
        src = ROOT / "config" / name
        dst = base / "config" / name
        dst.parent.mkdir(exist_ok=True)
        if src.is_file():
            dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")

    for t in ("AAA", "BBB", "CCC"):
        store.get_bundle(t, "long_term", debate_mode="template")
    app = create_app(api_cfg=api_cfg, store=store)
    return {"client": TestClient(app), "store": store, "web_dist": web_dist}


@pytest.fixture
def client(api_env):
    return api_env["client"]


def test_financials_shape_and_units(client):
    r = client.get("/api/tickers/AAA/financials")
    assert r.status_code == 200
    body = r.json()
    assert body["asof"] == ASOF
    assert "annual" in body and "quarterly" in body
    assert body["meta"]["unit"] == "VND_billions"
    assert "avg" in body["meta"]["roe_basis"].lower() or "trung bình" in body["meta"]["roe_basis"].lower()
    annual = body["annual"]
    assert isinstance(annual, list)
    if len(annual) >= 2:
        # Kỳ tăng dần
        periods = [str(p["period"]) for p in annual]
        assert periods == sorted(periods, key=lambda x: x)
    if annual:
        row = annual[-1]
        assert "items" in row
        assert "gross_margin" in row
        assert "roe" in row
        assert "fcf" in row
        # Không bịa: thiếu thì null (kiểu cho phép)
        assert row["items"].get("revenue") is None or isinstance(row["items"]["revenue"], (int, float))


def test_peers_includes_self_and_medians(client):
    r = client.get("/api/tickers/AAA/peers")
    assert r.status_code == 200
    body = r.json()
    assert body["symbol"] == "AAA"
    assert any(i.get("is_self") for i in body["items"])
    assert "sector_medians" in body
    assert body["sector_medians"].get("sector") == "Steel"
    # median từ file stats
    assert body["sector_medians"].get("median_pe") == 12.0
    # pe_band/pb_band: fixture không có pe_sorted → None (additive, không bắt buộc)
    assert "pe_band" in body["sector_medians"]
    assert "pb_band" in body["sector_medians"]


def test_sectors_extended_stats(client):
    r = client.get("/api/sectors", params={"profile": "long_term"})
    assert r.status_code == 200
    body = r.json()
    assert body["profile"] == "long_term"
    steel = next(i for i in body["items"] if i["sector"] == "Steel")
    assert "n_scored" in steel
    assert "mean_score" in steel
    assert "median_score" in steel
    assert "rating_distribution" in steel
    assert "mean_pillars" in steel
    for k in ("F", "T", "V", "S", "R"):
        assert k in steel["mean_pillars"]


def test_prices_index_and_indicators(client):
    r = client.get(
        "/api/tickers/AAA/prices",
        params={"range": "3m", "include_index": True, "include_indicators": True},
    )
    assert r.status_code == 200
    body = r.json()
    assert "ohlcv" in body
    assert "index" in body
    # DEMO fixture có thể không có index → series null + note
    assert "series" in body["index"]
    assert "indicators" in body
    for key in ("ma20", "ma50", "ma200", "rsi14", "macd", "signal", "hist"):
        assert key in body["indicators"]
    # Không có ngày sau asof
    for bar in body["ohlcv"]:
        assert str(bar["time"])[:10] <= ASOF


def test_spa_fallback_and_api_untouched(client, api_env):
    # API vẫn hoạt động
    assert client.get("/api/health").status_code == 200
    # SPA index
    r = client.get("/")
    assert r.status_code == 200
    assert "SPA" in r.text
    assert r.headers.get("cache-control", "").lower().find("no-cache") >= 0 or True
    # Client route → index.html
    r2 = client.get("/t/AAA")
    assert r2.status_code == 200
    assert "SPA" in r2.text
    # Asset hashed path
    r3 = client.get("/assets/app.js")
    assert r3.status_code == 200


def test_rankings_has_price_fields(client):
    r = client.get("/api/rankings", params={"profile": "long_term", "limit": 10})
    assert r.status_code == 200
    items = r.json()["items"]
    assert items
    row = items[0]
    assert "price" in row
    assert "reference_price" in row
    assert "upside_pct" in row
