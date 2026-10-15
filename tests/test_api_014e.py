"""Feature 014e — /api/market, signals rankings, income bridge reconcile."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from stockai.api.app import create_app
from stockai.api.signals import build_signals_from_m3
from stockai.api.store import ResultStore
from stockai.api.waterfall import build_income_bridge, sum_items

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
    company["is_bank"] = False
    company["shares_outstanding"] = 1_000_000_000
    snap["company"] = company
    # Index giả lập dùng chung
    snap["index"] = {
        "symbol": "VNINDEX",
        "rows": [
            {"date": "2026-09-01", "close": 1700.0},
            {"date": "2026-10-07", "close": 1720.0},
            {"date": "2026-10-08", "close": 1730.0},
        ],
    }
    return snap


@pytest.fixture(scope="module")
def api_env(tmp_path_factory):
    base = tmp_path_factory.mktemp("api014e")
    snap_dir = base / "snapshots"
    cache_dir = base / "api_cache"
    web_dist = base / "web_dist"
    snap_dir.mkdir()
    cache_dir.mkdir()
    web_dist.mkdir()
    (web_dist / "index.html").write_text(
        "<!doctype html><html><body>SPA</body></html>", encoding="utf-8"
    )

    for t, sec in [("AAA", "Steel"), ("BBB", "Steel"), ("CCC", "Banks")]:
        (snap_dir / f"{t}_{ASOF}.json").write_text(
            json.dumps(_clone(t, sec), ensure_ascii=False), encoding="utf-8"
        )

    (base / "data").mkdir(exist_ok=True)
    (base / "data" / "valuation_sector_stats.json").write_text(
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
    for name in ("scoring.yaml", "valuation.yaml"):
        src = ROOT / "config" / name
        dst = base / "config" / name
        dst.parent.mkdir(exist_ok=True)
        if src.is_file():
            dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")

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
        api_cfg, snapshots_dir=snap_dir, cache_dir=cache_dir, asof=ASOF, root=base
    )
    for t in ("AAA", "BBB", "CCC"):
        store.get_bundle(t, "long_term", debate_mode="template")
    app = create_app(api_cfg=api_cfg, store=store)
    return {"client": TestClient(app), "store": store}


@pytest.fixture
def client(api_env):
    return api_env["client"]


def test_market_contract(client):
    r = client.get("/api/market")
    assert r.status_code == 200
    body = r.json()
    assert body["asof"] == ASOF
    assert "disclaimer" in body
    idx = body["index"]
    assert idx is not None
    assert idx["symbol"] == "VNINDEX"
    assert idx["close"] == 1730.0
    assert isinstance(idx["change_pct"], (int, float))
    assert abs(idx["change_pct"] - ((1730 - 1720) / 1720 * 100)) < 0.05
    assert isinstance(idx["series_30d"], list)
    assert len(idx["series_30d"]) >= 2
    assert idx["series_30d"][-1]["close"] == 1730.0


def test_rankings_signals_vs_m3(client, api_env):
    store = api_env["store"]
    bundle = store.get_bundle("AAA", "long_term", debate_mode="template")
    expected = build_signals_from_m3(bundle.get("m3"))
    r = client.get("/api/rankings", params={"profile": "long_term", "limit": 50})
    assert r.status_code == 200
    row = next(i for i in r.json()["items"] if i["ticker"] == "AAA")
    assert "signals" in row
    assert row["signals"]["above_ma50"] == expected["above_ma50"]
    assert row["signals"]["above_ma200"] == expected["above_ma200"]
    assert row["signals"]["rsi_zone"] == expected["rsi_zone"]
    assert row["signals"]["volume_up"] == expected["volume_up"]
    assert "market_cap" in row


def test_signals_unit_rsi_zones():
    assert build_signals_from_m3(
        {"metrics": {"close": {"value": 100}, "ma50": {"value": 90}, "ma200": {"value": 80}, "rsi14": {"value": 75}, "volume_ratio_20": {"value": 1.2}}}
    ) == {
        "above_ma50": True,
        "above_ma200": True,
        "rsi_zone": "overbought",
        "volume_up": True,
    }
    assert build_signals_from_m3(
        {"metrics": {"close": {"value": 70}, "ma50": {"value": 90}, "rsi14": {"value": 25}}}
    )["rsi_zone"] == "oversold"
    assert build_signals_from_m3(None)["rsi_zone"] is None


def test_income_bridge_reconcile():
    items = {
        "revenue": 1000.0,
        "gross_profit": 400.0,
        "selling_expense": 50.0,
        "admin_expense": 50.0,
        "ebit": 280.0,
        "interest_expense": 30.0,
        "pretax_profit": 240.0,
        "net_income_parent": 200.0,
    }
    bridge = build_income_bridge(items)
    assert bridge is not None
    assert bridge["reconcile_ok"] is True
    check = bridge["start"]
    for s in bridge["steps"][1:]:
        if s["kind"] == "delta":
            check += s["value"]
        else:
            assert abs(check - s["value"]) <= 1e-6
            check = s["value"]
    assert abs(check - bridge["end"]) <= 1e-6
    assert abs(bridge["end"] - 200.0) <= 1e-6


def test_income_bridge_missing_merges_khac():
    items = {
        "revenue": 500.0,
        "net_income_parent": 80.0,
        # thiếu gp/ebit/pretax → một bước Khác/thuế
    }
    bridge = build_income_bridge(items)
    assert bridge is not None
    assert bridge["reconcile_ok"] is True
    labels = [s["label"] for s in bridge["steps"]]
    assert "Doanh thu" in labels
    assert "LNST CĐCT mẹ" in labels
    deltas = sum(s["value"] for s in bridge["steps"] if s["kind"] == "delta")
    assert abs(bridge["start"] + deltas - bridge["end"]) <= 1e-6


def test_sum_items_ttm():
    periods = [
        {"items": {"revenue": 10.0, "net_income_parent": 1.0}},
        {"items": {"revenue": 20.0, "net_income_parent": 2.0}},
        {"items": {"revenue": 30.0}},
        {"items": {"revenue": 40.0, "net_income_parent": 4.0}},
    ]
    acc = sum_items(periods, ("revenue", "net_income_parent"))
    assert acc["revenue"] == 100.0
    assert acc["net_income_parent"] == 7.0
