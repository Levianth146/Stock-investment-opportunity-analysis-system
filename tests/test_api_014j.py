"""Feature 014j — job debate bất đồng bộ, timeout failover, quota 503, validator, cổ tức."""
from __future__ import annotations

import json
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from stockai.api.app import create_app
from stockai.api.financials import build_financials_payload, dividends_implausible
from stockai.api.store import ResultStore
from stockai.llm import generate as gen_mod
from stockai.llm.providers import gemini_rest
from stockai.llm.quota_state import load_quota_state
from stockai.m7_scoring import debate as debate_mod
from stockai.m7_scoring.debate_validate import (
    repair_debate_sides,
    validate_debate_sides,
    valuation_gap_ok,
)

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
        "debate_job_max_workers": 2,
        "cache_dir": str(cache_dir),
    }
    store = ResultStore(
        api_cfg, snapshots_dir=snap_dir, cache_dir=cache_dir, asof=ASOF, root=ROOT
    )
    for t in ("AAA", "BBB"):
        store.get_bundle(t, "long_term", debate_mode="template")
    app = create_app(api_cfg=api_cfg, store=store)
    yield {"app": app, "cache_dir": cache_dir, "client": TestClient(app), "tmp": tmp_path}
    debate_mod.set_generate_fn(None)


def test_debate_job_idempotent_per_ticker(api_env, monkeypatch):
    """Cùng mã đang chạy → POST jobs trả cùng job_id."""
    client = api_env["client"]
    gate = {"go": False}

    def slow_run(symbol, *, profile, refresh=False, client_ip="unknown"):
        while not gate["go"]:
            time.sleep(0.02)
        return {
            "asof": ASOF,
            "symbol": symbol,
            "profile": profile,
            "source": "LLM",
            "model": "mock",
            "bull": [{"text": "ok", "refs": ["m2.roe"]}],
            "bear": [{"text": "ok", "refs": ["m6.beta"]}],
            "ai_attempt": {"state": "ok"},
        }

    monkeypatch.setattr(api_env["app"].state.debate_service, "run", slow_run)
    r1 = client.post("/api/tickers/AAA/debate/jobs", params={"profile": "long_term"})
    assert r1.status_code == 200
    j1 = r1.json()["job_id"]
    assert r1.json()["state"] in ("queued", "running")
    r2 = client.post("/api/tickers/AAA/debate/jobs", params={"profile": "long_term"})
    assert r2.status_code == 200
    assert r2.json()["job_id"] == j1
    gate["go"] = True
    # chờ xong
    for _ in range(100):
        st = client.get(f"/api/tickers/AAA/debate/jobs/{j1}", params={"profile": "long_term"})
        assert st.status_code == 200
        if st.json()["state"] in ("ok", "failed"):
            assert st.json()["state"] == "ok"
            return
        time.sleep(0.05)
    pytest.fail("job không hoàn thành")


def test_http_503_does_not_write_quota(tmp_path, monkeypatch):
    """503 tạm thời → circuit, không ghi _quota_state.json."""
    qpath = tmp_path / "_quota_state.json"
    gen_mod.reset_circuit_state()
    monkeypatch.setenv("GEMINI_API_KEY", "test-key-not-real")
    monkeypatch.delenv("ZAI_API_KEY", raising=False)

    def boom(*a, **k):
        raise gemini_rest.GeminiRestError("http_503", status_code=503, body="unavailable")

    monkeypatch.setattr(gen_mod.gemini_rest, "generate_content_json", boom)
    debate = {
        "providers": ["gemini"],
        "timeout_sec": 1,
        "max_retries_per_call": 2,
        "cache_dir": str(tmp_path),
        "gemini": {"models": ["m1"], "timeout_sec": 1},
        "circuit_breaker": {"consecutive_failures": 1, "cooldown_minutes": 15},
    }
    with pytest.raises(RuntimeError, match="all_providers_failed"):
        gen_mod.generate_json(
            "hi",
            cfg={"debate": debate},
            use_cache=False,
        )
    assert not qpath.is_file() or load_quota_state(qpath) == {}


def test_timeout_triggers_failover(tmp_path, monkeypatch):
    """Timeout 30s class → thử model tiếp theo."""
    gen_mod.reset_circuit_state()
    monkeypatch.setenv("GEMINI_API_KEY", "test-key-not-real")
    monkeypatch.delenv("ZAI_API_KEY", raising=False)
    calls: list[str] = []

    def fake(prompt, *, model, timeout_sec, **kw):
        calls.append(model)
        if model == "slow":
            raise gemini_rest.GeminiRestError("timeout", status_code=None, body="")
        return {
            "bull": [{"text": "B ROE 15,0%", "refs": ["m2.roe"]}],
            "bear": [{"text": "R beta 1,2", "refs": ["m6.beta"]}],
            "_usage": {"input_tokens": 1, "output_tokens": 1},
        }

    monkeypatch.setattr(gen_mod.gemini_rest, "generate_content_json", fake)
    debate = {
        "providers": ["gemini"],
        "timeout_sec": 30,
        "max_retries_per_call": 1,  # không retry — failover ngay
        "cache_dir": str(tmp_path),
        "gemini": {"models": ["slow", "fast"], "timeout_sec": 30},
        "circuit_breaker": {"consecutive_failures": 99, "cooldown_minutes": 15},
        "pricing": {},
    }
    out = gen_mod.generate_json("hi", cfg={"debate": debate}, use_cache=False)
    assert calls == ["slow", "fast"]
    assert out["_meta"]["model"] == "fast"


def test_validator_blocks_small_valuation_gap():
    ok, gap = valuation_gap_ok(10.2, None, 10.3, None, min_gap_pct=0.10)
    assert not ok
    assert gap is not None and gap < 0.10
    ok2, _ = valuation_gap_ok(9.0, None, 10.0, None, min_gap_pct=0.10)
    assert ok2

    metrics = {
        "m4.pe": {"value": 10.2, "display": "10,2x", "display_name": "P/E"},
        "m4.sector_median_pe": {"value": 10.3, "display": "10,3x", "display_name": "P/E trung vị ngành"},
        "m2.roe": {"value": 0.15, "display": "15,0%", "display_name": "ROE"},
        "m6.beta": {"value": 1.2, "display": "1,2", "display_name": "Beta"},
    }
    bull = [
        {
            "text": "P/E 10,2x hấp dẫn hơn trung vị ngành 10,3x.",
            "refs": ["m4.pe"],
        },
        {"text": "ROE 15,0% hỗ trợ.", "refs": ["m2.roe"]},
    ]
    bear = [
        {"text": "Beta 1,2.", "refs": ["m6.beta"]},
        {"text": "Beta 1,2 vẫn cao.", "refs": ["m6.beta"]},
    ]
    errs = validate_debate_sides(
        bull,
        bear,
        metrics_allowed=["m4.pe", "m4.sector_median_pe", "m2.roe", "m6.beta"],
        news_ref_map={},
        payload_metrics=metrics,
        min_gap_pct=0.10,
    )
    assert any("valuation_claim" in e for e in errs)


def test_weird_numbers_dropped_in_repair():
    metrics = {
        "m2.roe": {"value": 0.15, "display": "15,0%", "display_name": "ROE"},
        "m6.beta": {"value": 1.2, "display": "1,2", "display_name": "Beta"},
    }
    bull = [
        {
            "text": "ROE 15,0% tốt. Con số 99,9 không có trong payload nên bỏ.",
            "refs": ["m2.roe"],
        },
        {"text": "ROE 15,0% ổn định.", "refs": ["m2.roe"]},
    ]
    bear = [
        {"text": "Beta 1,2.", "refs": ["m6.beta"]},
        {"text": "Beta 1,2 tăng.", "refs": ["m6.beta"]},
    ]
    fixed_b, fixed_r, errs = repair_debate_sides(
        bull,
        bear,
        metrics_allowed=["m2.roe", "m6.beta"],
        news_ref_map={},
        payload_metrics=metrics,
    )
    assert not errs
    assert all("99,9" not in (it.get("text") or "") for it in fixed_b)


def test_dividends_implausible_banks_not_fpt_hpg():
    # STB/OCB kiểu tỷ lệ cực nhỏ
    assert dividends_implausible(2_000_000.0, 10_087_495_000_000.0)
    assert dividends_implausible(28_225_069.0, 3_173_423_226_768.0)
    # FPT / HPG hợp lý hơn
    assert not dividends_implausible(3_291_859_792_121.0, 7_856_767_812_178.0)
    assert not dividends_implausible(2_261_459_543_241.0, 8_483_510_554_031.0)


def test_financials_flags_implausible_year():
    snap = _clone("STB")
    snap["company"] = {"is_bank": True, "sector": "Banks"}
    snap["financials"] = {
        "unit": "VND",
        "annual": [
            {
                "period": "2024",
                "items": {
                    "dividends_paid": 2_000_000.0,
                    "net_income_parent": 10_087_495_000_000.0,
                    "net_income": 10_087_495_000_000.0,
                    "revenue": 1e12,
                    "total_equity": 5e13,
                },
            },
            {
                "period": "2023",
                "items": {
                    "dividends_paid": 3e12,
                    "net_income_parent": 8e12,
                    "net_income": 8e12,
                    "revenue": 1e12,
                    "total_equity": 5e13,
                },
            },
        ],
    }
    out = build_financials_payload(snap, asof=ASOF, disclaimer="x")
    by_year = {str(r["period"]): r for r in out["annual"]}
    assert "dividends_implausible" in (by_year["2024"].get("flags") or [])
    assert "dividends_implausible" not in (by_year["2023"].get("flags") or [])
    # không xóa số gốc (đã đổi sang tỷ)
    assert by_year["2024"]["items"]["dividends_paid"] is not None
