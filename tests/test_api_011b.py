"""Feature 011b — harden API (proxy IP, daily budget, docs, size limits)."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from starlette.requests import Request

from stockai.api.app import create_app
from stockai.api.deps import client_ip
from stockai.api.ratelimit import DebateRateLimiter, SlidingWindowLimiter
from stockai.api.store import ResultStore
from stockai.m7_scoring import debate as debate_mod

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "fixtures" / "snapshot_DEMO.json"
ASOF = "2026-10-08"

TICKERS = [
    ("AAA", "Banks"),
    ("BBB", "Steel"),
    ("CCC", "Steel"),
    ("DDD", "Technology"),
    ("EEE", "Retail"),
    ("FFF", "Other"),
]


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
    return snap


def _make_env(tmp_path: Path, **cfg_extra):
    snap_dir = tmp_path / "snapshots"
    cache_dir = tmp_path / "api_cache"
    snap_dir.mkdir()
    cache_dir.mkdir()
    for t, sec in TICKERS:
        (snap_dir / f"{t}_{ASOF}.json").write_text(
            json.dumps(_clone(t, sec), ensure_ascii=False), encoding="utf-8"
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
        "debate_live_max_per_hour": 100,
        "debate_live_max_per_ip_per_hour": 3,
        "debate_live_max_per_day": 15,
        "cache_dir": str(cache_dir),
    }
    api_cfg.update(cfg_extra)
    store = ResultStore(
        api_cfg,
        snapshots_dir=snap_dir,
        cache_dir=cache_dir,
        asof=ASOF,
        root=ROOT,
    )
    for t, _ in TICKERS:
        store.get_bundle(t, "long_term", debate_mode="template")
    app = create_app(api_cfg=api_cfg, store=store)
    return {
        "client": TestClient(app),
        "app": app,
        "store": store,
        "api_cfg": api_cfg,
        "cache_dir": cache_dir,
    }


def _fake_scope(*, headers: list[tuple[bytes, bytes]] | None = None, client_host: str = "203.0.113.10"):
    return {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": "/",
        "raw_path": b"/",
        "query_string": b"",
        "headers": headers or [],
        "client": (client_host, 12345),
        "server": ("test", 80),
    }


# --- client_ip / proxy ---


def test_xff_ignored_when_trust_proxy_false(tmp_path, monkeypatch):
    env = _make_env(tmp_path, trust_proxy_headers=False, debate_live_max_per_ip_per_hour=3)
    app = env["app"]
    client = env["client"]
    monkeypatch.setattr("stockai.api.debate_service._quota_or_no_key", lambda: False)

    def fake_m7(snapshot, upstream, cfg):
        return {
            "ticker": snapshot["meta"]["ticker"],
            "score": 55.0,
            "rating": "Nắm giữ",
            "bull": [{"text": "b", "refs": ["m2.roe"]}],
            "bear": [{"text": "e", "refs": ["m6.beta"]}],
            "flags": ["m7_debate_llm_used"],
        }

    monkeypatch.setattr("stockai.api.debate_service.run_m7", fake_m7)
    debate_mod.set_generate_fn(lambda *a, **k: {"bull": [], "bear": []})

    # Limiter chặt theo IP
    tight = DebateRateLimiter(
        max_per_hour=100,
        max_per_ip_per_hour=3,
        max_per_day=100,
        budget_path=env["cache_dir"] / "_debate_budget.json",
    )
    app.state.limiter = tight
    app.state.debate_service.limiter = tight

    symbols = ["AAA", "BBB", "CCC", "DDD", "EEE"]
    bodies = []
    for i, sym in enumerate(symbols):
        ddir = Path(env["cache_dir"]) / "debate"
        for f in ddir.glob(f"{sym}*.json"):
            f.unlink()
        r = client.post(
            f"/api/tickers/{sym}/debate",
            params={"profile": "long_term"},
            headers={"X-Forwarded-For": f"198.51.100.{i + 1}"},
        )
        assert r.status_code == 200
        bodies.append(r.json())

    # 3 live OK, lần 4 bị chặn theo cùng IP (TestClient host) dù XFF khác nhau
    assert bodies[0]["source"] == "LLM"
    assert bodies[1]["source"] == "LLM"
    assert bodies[2]["source"] == "LLM"
    assert bodies[3]["source"] == "TEMPLATE"
    assert "rate_limit" in (bodies[3].get("reason") or "")
    assert bodies[4]["source"] == "TEMPLATE"
    debate_mod.set_generate_fn(None)


def test_cf_connecting_ip_splits_when_trust_true(tmp_path):
    env = _make_env(tmp_path, trust_proxy_headers=True)
    app = env["app"]

    req_a = Request(
        _fake_scope(
            headers=[(b"cf-connecting-ip", b"198.51.100.10")],
            client_host="203.0.113.10",
        )
    )
    req_a.scope["app"] = app
    req_b = Request(
        _fake_scope(
            headers=[(b"cf-connecting-ip", b"198.51.100.20")],
            client_host="203.0.113.10",
        )
    )
    req_b.scope["app"] = app

    assert client_ip(req_a) == "198.51.100.10"
    assert client_ip(req_b) == "198.51.100.20"

    # XFF: lấy phần tử CUỐI
    req_xff = Request(
        _fake_scope(
            headers=[(b"x-forwarded-for", b"1.1.1.1, 2.2.2.2, 198.51.100.99")],
            client_host="203.0.113.10",
        )
    )
    req_xff.scope["app"] = app
    assert client_ip(req_xff) == "198.51.100.99"


def test_bad_proxy_ip_falls_back_to_client_host(tmp_path):
    env = _make_env(tmp_path, trust_proxy_headers=True)
    app = env["app"]
    req = Request(
        _fake_scope(
            headers=[
                (b"cf-connecting-ip", b"not-an-ip"),
                (b"x-forwarded-for", b"also-bad, still-bad"),
            ],
            client_host="203.0.113.55",
        )
    )
    req.scope["app"] = app
    assert client_ip(req) == "203.0.113.55"


def test_trust_false_ignores_cf_header(tmp_path):
    env = _make_env(tmp_path, trust_proxy_headers=False)
    app = env["app"]
    req = Request(
        _fake_scope(
            headers=[(b"cf-connecting-ip", b"198.51.100.10")],
            client_host="203.0.113.10",
        )
    )
    req.scope["app"] = app
    assert client_ip(req) == "203.0.113.10"


# --- _by_ip cleanup ---


def test_by_ip_cleanup_removes_empty_and_evicts_oldest():
    lim = DebateRateLimiter(
        max_per_hour=100,
        max_per_ip_per_hour=5,
        max_per_day=100,
        window_sec=0.05,
        max_tracked_ips=3,
    )
    assert lim.try_acquire("10.0.0.1")[0]
    assert lim.try_acquire("10.0.0.2")[0]
    assert lim.try_acquire("10.0.0.3")[0]
    assert lim.tracked_ip_count() == 3

    # Thêm IP thứ 4 → đuổi IP cũ nhất
    assert lim.try_acquire("10.0.0.4")[0]
    assert lim.tracked_ip_count() == 3
    assert "10.0.0.1" not in lim._by_ip  # noqa: SLF001

    # Hết cửa sổ → cleanup xóa limiter rỗng
    import time

    time.sleep(0.08)
    lim.cleanup_by_ip()
    assert lim.tracked_ip_count() == 0


def test_sliding_window_is_empty_after_prune():
    sw = SlidingWindowLimiter(max_events=2, window_sec=0.05)
    assert sw.is_empty_after_prune()
    assert sw.allow()
    assert not sw.is_empty_after_prune()
    import time

    time.sleep(0.08)
    assert sw.is_empty_after_prune()


# --- daily ceiling ---


def test_daily_ceiling_persists_across_recreate(tmp_path):
    budget = tmp_path / "_debate_budget.json"
    lim1 = DebateRateLimiter(
        max_per_hour=100,
        max_per_ip_per_hour=100,
        max_per_day=2,
        budget_path=budget,
    )
    assert lim1.try_acquire("1.1.1.1")[0]
    assert lim1.try_acquire("1.1.1.1")[0]
    ok, reason = lim1.try_acquire("1.1.1.1")
    assert not ok
    assert reason == "rate_limit_daily"
    assert budget.is_file()

    lim2 = DebateRateLimiter(
        max_per_hour=100,
        max_per_ip_per_hour=100,
        max_per_day=2,
        budget_path=budget,
    )
    assert not lim2.budget_ok("9.9.9.9")
    ok2, reason2 = lim2.try_acquire("9.9.9.9")
    assert not ok2
    assert reason2 == "rate_limit_daily"


def test_daily_not_consumed_on_cache_hit(tmp_path, monkeypatch):
    env = _make_env(tmp_path, debate_live_max_per_day=2)
    client = env["client"]
    app = env["app"]
    monkeypatch.setattr("stockai.api.debate_service._quota_or_no_key", lambda: False)

    def fake_m7(snapshot, upstream, cfg):
        return {
            "ticker": snapshot["meta"]["ticker"],
            "score": 60.0,
            "rating": "Mua",
            "bull": [{"text": "b", "refs": ["m2.roe"]}],
            "bear": [{"text": "e", "refs": ["m6.beta"]}],
            "flags": ["m7_debate_llm_used"],
        }

    monkeypatch.setattr("stockai.api.debate_service.run_m7", fake_m7)
    debate_mod.set_generate_fn(lambda *a, **k: {"bull": [], "bear": []})

    r1 = client.post("/api/tickers/AAA/debate", params={"profile": "long_term"})
    assert r1.json()["source"] == "LLM"
    r2 = client.post("/api/tickers/AAA/debate", params={"profile": "long_term"})
    assert r2.json()["source"] == "CACHE"
    # Chỉ 1 lần mạng → vẫn còn 1 slot ngày
    assert app.state.limiter.budget_ok("testclient")
    debate_mod.set_generate_fn(None)


# --- docs / size limits ---


def test_docs_disabled_returns_404(tmp_path):
    env = _make_env(tmp_path, docs_enabled=False)
    client = env["client"]
    assert client.get("/docs").status_code == 404
    assert client.get("/redoc").status_code == 404
    assert client.get("/openapi.json").status_code == 404
    assert client.get("/api/health").status_code == 200


def test_oversized_q_and_symbols_return_400(tmp_path):
    env = _make_env(tmp_path)
    client = env["client"]
    long_q = "A" * 41
    rq = client.get("/api/rankings", params={"q": long_q})
    assert rq.status_code == 400
    assert "disclaimer" in rq.json()

    many = ",".join(f"T{i:02d}" for i in range(51))
    rs = client.get("/api/quotes", params={"symbols": many})
    assert rs.status_code == 400
    assert "disclaimer" in rs.json()
