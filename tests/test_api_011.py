"""Feature 011 — FastAPI layer (offline, TestClient, mock LLM)."""
from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from stockai.api.app import create_app
from stockai.api.ratelimit import DebateRateLimiter
from stockai.api.store import DISCLAIMER, ResultStore
from stockai.m7_scoring import debate as debate_mod

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "fixtures" / "snapshot_DEMO.json"
ASOF = "2026-10-08"

# ≥6 mã; ZZZ = unranked (insufficient)
TICKERS_SCORED = [
    ("AAA", "Banks"),
    ("BBB", "Steel"),
    ("CCC", "Steel"),
    ("DDD", "Technology"),
    ("EEE", "Retail"),
]
TICKER_UNRANKED = ("ZZZ", "Other")


def _clone_demo(ticker: str, sector: str, *, insufficient: bool = False) -> dict:
    snap = json.loads(FIX.read_text(encoding="utf-8"))
    snap["meta"]["ticker"] = ticker
    snap["meta"]["as_of"] = ASOF
    snap["meta"]["synthetic"] = False
    flags = [f for f in (snap["meta"].get("flags") or []) if not str(f).startswith("quality_")]
    if insufficient:
        flags.extend(
            [
                "quality_tier_insufficient",
                "quality_prices_lt_750",
                "quality_news_few",
            ]
        )
    else:
        flags.append("quality_tier_full")
    snap["meta"]["flags"] = flags
    company = dict(snap.get("company") or {})
    company["name"] = f"Cong ty {ticker}"
    company["sector"] = sector
    company["exchange"] = "HSX"
    snap["company"] = company
    return snap


@pytest.fixture(scope="module")
def api_env(tmp_path_factory):
    base = tmp_path_factory.mktemp("api011")
    snap_dir = base / "snapshots"
    cache_dir = base / "api_cache"
    snap_dir.mkdir()
    cache_dir.mkdir()
    for t, sec in TICKERS_SCORED:
        data = _clone_demo(t, sec, insufficient=False)
        (snap_dir / f"{t}_{ASOF}.json").write_text(
            json.dumps(data, ensure_ascii=False), encoding="utf-8"
        )
    t, sec = TICKER_UNRANKED
    data = _clone_demo(t, sec, insufficient=True)
    (snap_dir / f"{t}_{ASOF}.json").write_text(
        json.dumps(data, ensure_ascii=False), encoding="utf-8"
    )

    api_cfg = {
        "snapshots_dir": str(snap_dir),
        "asof": ASOF,
        "default_profile": "long_term",
        "host": "127.0.0.1",
        "port": 8000,
        "cors_origins": [],
        "docs_enabled": True,
        "trust_proxy_headers": False,
        "proxy_ip_header": "CF-Connecting-IP",
        "debate_live_max_per_hour": 10,
        "debate_live_max_per_ip_per_hour": 3,
        "debate_live_max_per_day": 15,
        "cache_dir": str(cache_dir),
    }
    store = ResultStore(
        api_cfg,
        snapshots_dir=snap_dir,
        cache_dir=cache_dir,
        asof=ASOF,
        root=ROOT,
    )
    # Warm cache (template) — một lần / module
    for t, _ in TICKERS_SCORED + [TICKER_UNRANKED]:
        store.get_bundle(t, "long_term", debate_mode="template")
    app = create_app(api_cfg=api_cfg, store=store)
    client = TestClient(app)
    return {"client": client, "store": store, "app": app, "api_cfg": api_cfg, "cache_dir": cache_dir}


@pytest.fixture
def client(api_env):
    return api_env["client"]


@pytest.fixture
def store(api_env):
    return api_env["store"]


def _assert_safe(body: dict | list | str) -> None:
    raw = body if isinstance(body, str) else json.dumps(body, ensure_ascii=False)
    assert "Traceback" not in raw
    assert "GEMINI_API_KEY" not in raw
    assert "ZAI_API_KEY" not in raw
    assert "disclaimer" in raw.lower()


# --- health / meta / sectors ---


def test_health_and_meta(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["asof"] == ASOF
    assert "disclaimer" in body
    _assert_safe(body)

    m = client.get("/api/meta").json()
    assert m["asof"] == ASOF
    assert "long_term" in m["profiles"]
    assert m["universe_count"] == 6
    assert m["scored_count"] == 5
    assert m["formula"] == "v2"
    assert "risk_reference" in m
    assert "llm" in m
    assert "key_configured" in m["llm"]
    assert "blocked_until" in m["llm"]
    _assert_safe(m)


def test_sectors(client):
    r = client.get("/api/sectors")
    assert r.status_code == 200
    body = r.json()
    assert body["asof"] == ASOF
    names = {i["sector"] for i in body["items"]}
    assert "Steel" in names
    _assert_safe(body)


# --- rankings ---


def test_rankings_default_excludes_unranked(client):
    r = client.get("/api/rankings", params={"profile": "long_term", "limit": 50})
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == 5
    tickers = [i["ticker"] for i in body["items"]]
    assert "ZZZ" not in tickers
    assert all(i.get("ranked") for i in body["items"])
    _assert_safe(body)


def test_rankings_include_unranked(client):
    r = client.get(
        "/api/rankings",
        params={"profile": "long_term", "include_unranked": True, "limit": 50},
    )
    body = r.json()
    assert body["total"] == 6
    assert any(i["ticker"] == "ZZZ" for i in body["items"])
    z = next(i for i in body["items"] if i["ticker"] == "ZZZ")
    assert z["rating"] == "Không xếp hạng"
    assert z["score"] is None


def test_rankings_filter_sector_and_q(client):
    r = client.get("/api/rankings", params={"sector": "Steel", "profile": "long_term"})
    body = r.json()
    assert body["total"] >= 1
    assert all(i["sector"] == "Steel" for i in body["items"])
    r2 = client.get("/api/rankings", params={"q": "AAA"})
    assert any(i["ticker"] == "AAA" for i in r2.json()["items"])


def test_rankings_sort_and_pagination(client):
    r = client.get(
        "/api/rankings",
        params={"sort": "score", "order": "desc", "limit": 2, "offset": 0},
    )
    body = r.json()
    assert len(body["items"]) == 2
    assert body["total"] == 5
    scores = [i["score"] for i in body["items"] if i["score"] is not None]
    assert scores == sorted(scores, reverse=True)

    r2 = client.get(
        "/api/rankings",
        params={"sort": "score", "order": "desc", "limit": 2, "offset": 2},
    )
    page2 = [i["ticker"] for i in r2.json()["items"]]
    page1 = [i["ticker"] for i in body["items"]]
    assert set(page1).isdisjoint(set(page2))

    for key in ("F", "T", "V", "S", "R"):
        rk = client.get("/api/rankings", params={"sort": key, "order": "asc", "limit": 3})
        assert rk.status_code == 200


# --- ticker detail / 404 ---


def test_ticker_detail_ok(client):
    r = client.get("/api/tickers/AAA", params={"profile": "long_term"})
    assert r.status_code == 200
    body = r.json()
    assert body["symbol"] == "AAA"
    assert "result" in body
    assert "modules" in body
    assert "validation" in body
    assert "quality_gate" in body
    assert "company" in body
    assert body["asof"] == ASOF
    _assert_safe(body)


def test_ticker_404_and_bad_symbol(client):
    assert client.get("/api/tickers/NOPE").status_code == 404
    assert client.get("/api/tickers/../etc").status_code == 404
    assert client.get("/api/tickers/toolongg").status_code == 404
    assert client.get("/api/tickers/aa").status_code == 404  # lowercase fail regex after upper? we upper — AA may 404 missing
    body = client.get("/api/tickers/NOPE").json()
    assert "Traceback" not in json.dumps(body)
    assert "disclaimer" in body


# --- prices / news ---


def test_prices_range(client):
    r = client.get("/api/tickers/AAA/prices", params={"range": "3m"})
    assert r.status_code == 200
    body = r.json()
    assert "ohlcv" in body
    assert len(body["ohlcv"]) > 0
    assert body["ohlcv"][0]["time"]
    assert "close" in body["ohlcv"][0]
    r_all = client.get("/api/tickers/AAA/prices", params={"range": "all"})
    assert len(r_all.json()["ohlcv"]) >= len(body["ohlcv"])
    assert client.get("/api/tickers/AAA/prices", params={"range": "99y"}).status_code == 400


def test_news_endpoint(client):
    r = client.get("/api/tickers/AAA/news")
    assert r.status_code == 200
    body = r.json()
    assert "items" in body
    assert body["asof"] == ASOF
    _assert_safe(body)


# --- quotes ---


def test_quotes(client):
    r = client.get("/api/quotes", params={"symbols": "AAA,BBB,NOPE"})
    assert r.status_code == 200
    body = r.json()
    syms = [i["symbol"] for i in body["items"]]
    assert "AAA" in syms and "BBB" in syms
    assert "NOPE" not in syms
    assert body["items"][0]["source"] == "snapshot"


# --- debate (mock) ---


def test_debate_llm_then_cache(client, store, monkeypatch, api_env):
    # xóa cache debate
    ddir = Path(api_env["cache_dir"]) / "debate"
    if ddir.is_dir():
        for f in ddir.glob("*.json"):
            f.unlink()

    monkeypatch.setattr("stockai.api.debate_service._quota_or_no_key", lambda: False)

    def fake_m7(snapshot, upstream, cfg):
        flags = ["m7_debate_llm_used", "debate_mock"]
        cfg["_debate_flags"] = list(flags)
        return {
            "ticker": snapshot["meta"]["ticker"],
            "as_of": snapshot["meta"]["as_of"],
            "profile": cfg.get("profile"),
            "score": 61.0,
            "rating": "Mua",
            "bull": [{"text": "Bull mock", "refs": ["m2.roe"]}],
            "bear": [{"text": "Bear mock", "refs": ["m6.beta"]}],
            "flags": flags,
            "scores": {"F": 60, "T": 60, "V": 60, "S": 60, "R": 40},
            "quality_gate": {"tier": "full", "scored": True, "reasons": []},
        }

    monkeypatch.setattr("stockai.api.debate_service.run_m7", fake_m7)
    # đánh dấu mock để nhánh key không chặn nếu quota patch lỗi
    debate_mod.set_generate_fn(lambda *a, **k: {"bull": [], "bear": []})

    r1 = client.post("/api/tickers/AAA/debate", params={"profile": "long_term"})
    assert r1.status_code == 200
    b1 = r1.json()
    assert b1["source"] == "LLM"
    assert b1["bull"]
    _assert_safe(b1)

    r2 = client.post("/api/tickers/AAA/debate", params={"profile": "long_term"})
    assert r2.status_code == 200
    b2 = r2.json()
    assert b2["source"] == "CACHE"
    _assert_safe(b2)
    debate_mod.set_generate_fn(None)


def test_debate_quota_template(client, monkeypatch, api_env):
    ddir = Path(api_env["cache_dir"]) / "debate"
    for f in ddir.glob("BBB*.json"):
        f.unlink()
    monkeypatch.setattr("stockai.api.debate_service._quota_or_no_key", lambda: True)
    debate_mod.set_generate_fn(None)
    r = client.post("/api/tickers/BBB/debate", params={"profile": "long_term"})
    assert r.status_code == 200
    body = r.json()
    assert body["source"] == "TEMPLATE"
    assert body.get("reason")
    _assert_safe(body)


def test_debate_rate_limit_template(client, monkeypatch, api_env):
    ddir = Path(api_env["cache_dir"]) / "debate"
    for f in ddir.glob("CCC*.json"):
        f.unlink()
    monkeypatch.setattr("stockai.api.debate_service._quota_or_no_key", lambda: False)
    debate_mod.set_generate_fn(lambda *a, **k: {"bull": [], "bear": []})

    # limiter chặt
    tight = DebateRateLimiter(max_per_hour=1, max_per_ip_per_hour=1)
    api_env["app"].state.limiter = tight
    api_env["app"].state.debate_service.limiter = tight

    def fake_m7(snapshot, upstream, cfg):
        flags = ["m7_debate_llm_used"]
        return {
            "ticker": snapshot["meta"]["ticker"],
            "score": 55.0,
            "rating": "Nắm giữ",
            "bull": [{"text": "b", "refs": ["m2.roe"]}],
            "bear": [{"text": "e", "refs": ["m6.beta"]}],
            "flags": flags,
        }

    monkeypatch.setattr("stockai.api.debate_service.run_m7", fake_m7)

    r1 = client.post("/api/tickers/CCC/debate", params={"profile": "long_term", "refresh": True})
    assert r1.status_code == 200
    # Xóa cache API để lần 2 không đi nhánh CACHE
    for f in ddir.glob("CCC*.json"):
        f.unlink()
    r2 = client.post("/api/tickers/CCC/debate", params={"profile": "long_term", "refresh": False})
    assert r2.status_code == 200
    body2 = r2.json()
    assert body2["source"] == "TEMPLATE"
    reason = body2.get("reason") or ""
    assert "rate_limit" in reason or "refresh_denied" in reason
    _assert_safe(body2)
    debate_mod.set_generate_fn(None)


def test_debate_bad_json_validator_template(client, monkeypatch, api_env):
    ddir = Path(api_env["cache_dir"]) / "debate"
    for f in ddir.glob("DDD*.json"):
        f.unlink()
    monkeypatch.setattr("stockai.api.debate_service._quota_or_no_key", lambda: False)
    # limiter rộng lại
    wide = DebateRateLimiter(max_per_hour=100, max_per_ip_per_hour=100)
    api_env["app"].state.limiter = wide
    api_env["app"].state.debate_service.limiter = wide

    def fake_m7(snapshot, upstream, cfg):
        # không gắn m7_debate_llm_used → nhánh TEMPLATE
        return {
            "ticker": snapshot["meta"]["ticker"],
            "score": 50.0,
            "rating": "Nắm giữ",
            "bull": [{"text": "template bull"}],
            "bear": [{"text": "template bear"}],
            "flags": ["debate_fallback_reason:invalid_json", "debate_fallback_template"],
        }

    monkeypatch.setattr("stockai.api.debate_service.run_m7", fake_m7)
    debate_mod.set_generate_fn(lambda *a, **k: {"not": "valid"})
    r = client.post("/api/tickers/DDD/debate", params={"profile": "long_term", "refresh": True})
    assert r.status_code == 200
    body = r.json()
    assert body["source"] == "TEMPLATE"
    _assert_safe(body)
    debate_mod.set_generate_fn(None)


def test_report_pdf_stub(client):
    r = client.get("/api/report/AAA.pdf", params={"profile": "long_term"})
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/pdf")
    assert r.content[:4] == b"%PDF"
