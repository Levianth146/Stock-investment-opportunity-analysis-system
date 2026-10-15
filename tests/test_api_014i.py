"""Feature 014i — budget chỉ trừ khi LLM thật; model thật; circuit_open sớm."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from stockai.api.app import create_app
from stockai.api.ratelimit import DebateRateLimiter
from stockai.api.store import ResultStore
from stockai.m7_scoring import debate as debate_mod

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "fixtures" / "snapshot_DEMO.json"
ASOF = "2026-10-08"


def _clone(ticker: str) -> dict:
    snap = json.loads(FIX.read_text(encoding="utf-8"))
    snap["meta"]["ticker"] = ticker
    snap["meta"]["as_of"] = ASOF
    snap["meta"]["synthetic"] = False
    flags = [f for f in (snap["meta"].get("flags") or []) if not str(f).startswith("quality_")]
    flags.append("quality_tier_full")
    snap["meta"]["flags"] = flags
    return snap


@pytest.fixture
def api_env(tmp_path):
    snap_dir = tmp_path / "snapshots"
    cache_dir = tmp_path / "api_cache"
    snap_dir.mkdir()
    cache_dir.mkdir()
    for t in ("AAA", "BBB"):
        (snap_dir / f"{t}_{ASOF}.json").write_text(
            json.dumps(_clone(t), ensure_ascii=False), encoding="utf-8"
        )
    api_cfg = {
        "snapshots_dir": str(snap_dir),
        "asof": ASOF,
        "default_profile": "long_term",
        "cors_origins": [],
        "docs_enabled": False,
        "trust_proxy_headers": False,
        "debate_live_max_per_hour": 20,
        "debate_live_max_per_ip_per_hour": 20,
        "debate_live_max_per_day": 15,
        "cache_dir": str(cache_dir),
    }
    store = ResultStore(
        api_cfg, snapshots_dir=snap_dir, cache_dir=cache_dir, asof=ASOF, root=ROOT
    )
    for t in ("AAA", "BBB"):
        store.get_bundle(t, "long_term", debate_mode="template")
    app = create_app(api_cfg=api_cfg, store=store)
    yield {"app": app, "cache_dir": cache_dir, "client": TestClient(app)}
    debate_mod.set_generate_fn(None)


@pytest.fixture
def client(api_env):
    return api_env["client"]


def test_budget_unchanged_when_llm_fails_five_times(client, api_env, monkeypatch):
    """Mock LLM fail 5 lần → daily/hour count không tăng (refund)."""
    monkeypatch.setattr("stockai.api.debate_service._quota_or_no_key", lambda: False)
    monkeypatch.setattr(
        "stockai.api.debate_service.llm_public_status",
        lambda: {
            "state": "ok",
            "provider": "gemini",
            "model": "gemini-3.6-flash",
            "key_configured": True,
            "blocked_until": None,
            "blocked_until_local": None,
        },
    )

    def fake_m7(snapshot, upstream, cfg):
        cfg["_debate_flags"] = ["debate_fallback_reason:all_providers_failed"]
        return {
            "ticker": snapshot["meta"]["ticker"],
            "score": 50.0,
            "rating": "Nắm giữ",
            "bull": [{"text": "t bull", "refs": ["m2.roe"]}],
            "bear": [{"text": "t bear", "refs": ["m6.beta"]}],
            "flags": ["debate_fallback_reason:all_providers_failed"],
        }

    monkeypatch.setattr("stockai.api.debate_service.run_m7", fake_m7)
    debate_mod.set_generate_fn(lambda *a, **k: {"bad": True})

    lim: DebateRateLimiter = api_env["app"].state.limiter
    before_day = lim.daily_count()
    before_hour = lim.global_limiter.event_count()

    for _ in range(5):
        r = client.post(
            "/api/tickers/AAA/debate",
            params={"profile": "long_term", "refresh": True},
        )
        assert r.status_code == 200
        body = r.json()
        assert body["source"] == "TEMPLATE"
        assert body.get("ai_attempt", {}).get("state") == "failed"

    assert lim.daily_count() == before_day
    assert lim.global_limiter.event_count() == before_hour


def test_real_model_persisted_on_llm_success(client, api_env, monkeypatch):
    """Response model = model provider thật (không phải model đầu config)."""
    ddir = Path(api_env["cache_dir"]) / "debate"
    for f in ddir.glob("AAA*.json"):
        f.unlink()

    monkeypatch.setattr("stockai.api.debate_service._quota_or_no_key", lambda: False)
    monkeypatch.setattr(
        "stockai.api.debate_service.llm_public_status",
        lambda: {
            "state": "ok",
            "provider": "gemini",
            "model": "gemini-3.8-flash",
            "key_configured": True,
            "blocked_until": None,
            "blocked_until_local": None,
        },
    )

    def fake_m7(snapshot, upstream, cfg):
        flags = ["m7_debate_llm_used"]
        cfg["_debate_flags"] = list(flags)
        cfg["_debate_provider"] = "glm"
        cfg["_debate_model"] = "glm-4.7-flash"
        return {
            "ticker": snapshot["meta"]["ticker"],
            "score": 62.0,
            "rating": "Mua",
            "bull": [{"text": "Bull", "refs": ["m2.roe"]}],
            "bear": [{"text": "Bear", "refs": ["m6.beta"]}],
            "flags": flags,
        }

    monkeypatch.setattr("stockai.api.debate_service.run_m7", fake_m7)
    debate_mod.set_generate_fn(lambda *a, **k: {"bull": [], "bear": []})

    r = client.post(
        "/api/tickers/AAA/debate",
        params={"profile": "long_term", "refresh": True},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["source"] == "LLM"
    assert body["model"] == "glm-4.7-flash"
    assert body.get("provider") == "glm"
    assert body.get("ai_attempt", {}).get("state") == "ok"

    cached = list(ddir.glob("AAA*.json"))
    assert cached
    disk = json.loads(cached[0].read_text(encoding="utf-8"))
    assert disk["model"] == "glm-4.7-flash"
    assert disk.get("provider") == "glm"


def test_circuit_open_skips_without_budget(client, api_env, monkeypatch):
    monkeypatch.setattr("stockai.api.debate_service._quota_or_no_key", lambda: False)
    monkeypatch.setattr(
        "stockai.api.debate_service.llm_public_status",
        lambda: {
            "state": "circuit_open",
            "provider": "gemini",
            "model": "gemini-3.6-flash",
            "key_configured": True,
            "blocked_until": None,
            "blocked_until_local": None,
            "retry_after": 120,
        },
    )
    lim: DebateRateLimiter = api_env["app"].state.limiter
    before = lim.daily_count()
    called = {"n": 0}

    def boom(*a, **k):
        called["n"] += 1
        raise AssertionError("không được gọi LLM khi circuit_open")

    monkeypatch.setattr("stockai.api.debate_service.run_m7", boom)
    r = client.post(
        "/api/tickers/AAA/debate",
        params={"profile": "long_term", "refresh": True},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["source"] == "TEMPLATE"
    assert body.get("reason") == "circuit_open"
    assert body.get("ai_attempt", {}).get("reason_code") == "circuit_open"
    assert body.get("ai_attempt", {}).get("retry_after") == 120
    assert called["n"] == 0
    assert lim.daily_count() == before
