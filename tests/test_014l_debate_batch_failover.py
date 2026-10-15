"""Feature 014l: failover model/provider; batch chỉ STOP khi mọi model bị chặn."""
from __future__ import annotations

import importlib.util
from pathlib import Path
from unittest.mock import patch

import pytest

from stockai.llm import generate as gen_mod
from stockai.llm.generate import (
    all_keyed_models_blocked,
    generate_json,
    load_llm_cfg,
    reset_circuit_state,
    reset_network_call_count,
    should_stop_batch,
)
from stockai.llm.providers.gemini_rest import GeminiRestError
from stockai.llm.quota_state import load_quota_state, mark_blocked

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def _clean():
    reset_circuit_state()
    reset_network_call_count()
    gen_mod.set_max_live_calls(None)
    yield
    reset_circuit_state()
    reset_network_call_count()
    gen_mod.set_max_live_calls(None)


@pytest.fixture
def keys(monkeypatch, tmp_path):
    monkeypatch.setattr("stockai.llm.generate.load_dotenv_keys", lambda *a, **k: None)
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-not-real")
    monkeypatch.setenv("ZAI_API_KEY", "test-zai-not-real")
    cfg = load_llm_cfg()
    debate = dict(cfg.get("debate") or {})
    debate["cache_dir"] = str(tmp_path)
    debate["max_retries_per_call"] = 2
    debate["providers"] = ["gemini", "glm"]
    debate["rpm_limit"] = 0
    debate["gemini"] = {
        "model": "gemini-3.8-flash",
        "models": [
            "gemini-3.8-flash",
            "gemini-3.6-flash",
            "gemini-3.1-flash-lite",
        ],
        "timeout_sec": 5,
        "max_output_tokens": 2048,
        "thinking_level": "lowest",
    }
    debate["glm"] = {
        "model": "glm-4.7-flash",
        "models": ["glm-4.7-flash"],
        "paid_models": ["glm-5.3-flash"],
        "use_paid_models": False,
        "timeout_sec": 5,
        "base_url": "https://api.z.ai/api/paas/v4/",
    }
    debate["circuit_breaker"] = {"consecutive_failures": 99, "cooldown_minutes": 15}
    return {**cfg, "debate": debate}


def _ok():
    return {
        "bull": [{"text": "ok", "refs": ["m2.roe"]}],
        "bear": [{"text": "ok", "refs": ["m6.beta"]}],
        "_usage": {"input_tokens": 1, "output_tokens": 1},
    }


def test_failover_38_quota_36_503_lite_ok(keys, monkeypatch):
    """3.8 quota → 3.6 503 (hết retry) → 3.1-lite ok; không ghi quota cho 503."""
    monkeypatch.setattr("stockai.llm.generate.time.sleep", lambda s: None)
    seen: list[str] = []

    def gemini_by_model(prompt, *, model, **k):
        seen.append(model)
        if model == "gemini-3.8-flash":
            raise GeminiRestError(
                "quota_exhausted",
                status_code=429,
                quota_exhausted=True,
                body='{"error":{"message":"quota exceeded. Please retry in 2h"}}',
            )
        if model == "gemini-3.6-flash":
            raise GeminiRestError("http_503", status_code=503, body="unavailable")
        if model == "gemini-3.1-flash-lite":
            return _ok()
        raise AssertionError(f"unexpected model {model}")

    with patch(
        "stockai.llm.providers.gemini_rest.generate_content_json",
        side_effect=gemini_by_model,
    ):
        out = generate_json(
            "x",
            cfg=keys,
            cache_key_parts={
                "ticker": "AAA",
                "as_of": "2026-10-08",
                "prompt_version": "v1",
                "payload_hash": "014l_a",
            },
            use_cache=False,
        )
    assert out["_meta"]["model"] == "gemini-3.1-flash-lite"
    assert "gemini-3.8-flash" in seen
    assert "gemini-3.6-flash" in seen
    assert "gemini-3.1-flash-lite" in seen
    tried = out["_meta"]["models_tried"]
    by_m = {f"{r['provider']}/{r['model']}": r["reason"] for r in tried}
    assert by_m["gemini/gemini-3.8-flash"] == "quota_exhausted"
    assert by_m["gemini/gemini-3.6-flash"] == "http_503"
    assert by_m["gemini/gemini-3.1-flash-lite"] == "ok"
    st = load_quota_state(Path(keys["debate"]["cache_dir"]) / "_quota_state.json")
    assert "gemini/gemini-3.8-flash" in st
    assert "gemini/gemini-3.6-flash" not in st  # 503 không ghi quota


def test_then_lite_quota_glm_ok(keys, monkeypatch):
    """Sau khi lite hết quota → GLM ok (cùng ticker / lần gọi tiếp)."""
    monkeypatch.setattr("stockai.llm.generate.time.sleep", lambda s: None)
    mark_blocked(
        "gemini",
        "gemini-3.8-flash",
        body="retry in 6h",
        path=Path(keys["debate"]["cache_dir"]) / "_quota_state.json",
    )
    mark_blocked(
        "gemini",
        "gemini-3.6-flash",
        body="retry in 6h",
        path=Path(keys["debate"]["cache_dir"]) / "_quota_state.json",
    )

    def gemini_by_model(prompt, *, model, **k):
        if model == "gemini-3.1-flash-lite":
            raise GeminiRestError(
                "quota_exhausted",
                status_code=429,
                quota_exhausted=True,
                body='{"error":{"message":"quota exceeded. Please retry in 3h"}}',
            )
        raise AssertionError(f"should skip blocked gemini model {model}")

    def glm_ok(*a, **k):
        return _ok()

    with patch(
        "stockai.llm.providers.gemini_rest.generate_content_json",
        side_effect=gemini_by_model,
    ):
        with patch(
            "stockai.llm.providers.glm_rest.chat_completions_json",
            side_effect=glm_ok,
        ):
            out = generate_json(
                "x",
                cfg=keys,
                cache_key_parts={
                    "ticker": "BBB",
                    "as_of": "2026-10-08",
                    "prompt_version": "v1",
                    "payload_hash": "014l_b",
                },
                use_cache=False,
            )
    assert out["_meta"]["provider"] == "glm"
    assert out["_meta"]["model"] == "glm-4.7-flash"
    tried = out["_meta"]["models_tried"]
    reasons = {f"{r['provider']}/{r['model']}": r["reason"] for r in tried}
    assert reasons.get("gemini/gemini-3.1-flash-lite") == "quota_exhausted"
    assert reasons.get("glm/glm-4.7-flash") == "ok"
    assert not should_stop_batch(keys)[0]  # GLM còn sống → không STOP batch


def test_all_blocked_should_stop_batch(keys, monkeypatch, tmp_path):
    """Mọi model có key bị quota → should_stop_batch True."""
    qpath = Path(keys["debate"]["cache_dir"]) / "_quota_state.json"
    for prov, model in (
        ("gemini", "gemini-3.8-flash"),
        ("gemini", "gemini-3.6-flash"),
        ("gemini", "gemini-3.1-flash-lite"),
        ("glm", "glm-4.7-flash"),
    ):
        mark_blocked(prov, model, body="retry in 6h", path=qpath)
    assert all_keyed_models_blocked(keys) is True
    stop, why = should_stop_batch(keys)
    assert stop is True
    assert why == "all_models_blocked"


def test_one_model_quota_does_not_stop_batch(keys, monkeypatch):
    """Một model hết quota → không dừng batch."""
    mark_blocked(
        "gemini",
        "gemini-3.8-flash",
        body="retry in 6h",
        path=Path(keys["debate"]["cache_dir"]) / "_quota_state.json",
    )
    assert all_keyed_models_blocked(keys) is False
    stop, why = should_stop_batch(keys, flags=["llm_quota_exhausted:gemini"])
    assert stop is False
    assert why == ""


def test_max_live_calls_stops_batch(keys):
    stop, why = should_stop_batch(keys, flags=["llm_max_live_calls"])
    assert stop is True
    assert why == "max_live_calls"


def _load_batch_module():
    path = ROOT / "scripts" / "run_debate_batch.py"
    spec = importlib.util.spec_from_file_location("run_debate_batch_014l", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_batch_all_blocked_lists_missing_ai(keys, monkeypatch, tmp_path, capsys):
    """Batch: mọi model blocked → STOP + MISSING_AI liệt kê mã còn lại chưa AI."""
    import json

    as_of = "2026-10-08"
    snap_dir = tmp_path / "snaps"
    snap_dir.mkdir()
    demo = json.loads((ROOT / "fixtures" / "snapshot_DEMO.json").read_text(encoding="utf-8"))
    for t in ("T1", "T2", "T3"):
        s = json.loads(json.dumps(demo))
        s["meta"]["ticker"] = t
        s["meta"]["as_of"] = as_of
        (snap_dir / f"{t}_{as_of}.json").write_text(json.dumps(s), encoding="utf-8")

    # Chặn mọi model trước khi batch chạy
    qpath = Path(keys["debate"]["cache_dir"]) / "_quota_state.json"
    for prov, model in (
        ("gemini", "gemini-3.8-flash"),
        ("gemini", "gemini-3.6-flash"),
        ("gemini", "gemini-3.1-flash-lite"),
        ("glm", "glm-4.7-flash"),
    ):
        mark_blocked(prov, model, body="retry in 6h", path=qpath)

    mod = _load_batch_module()
    cfg_path = tmp_path / "llm.yaml"
    # Ghi config tạm trỏ cache_dir vào tmp (quota state)
    import yaml

    cfg_disk = load_llm_cfg()
    d = dict(cfg_disk.get("debate") or {})
    d["cache_dir"] = str(tmp_path)
    d["providers"] = ["gemini", "glm"]
    d["gemini"] = keys["debate"]["gemini"]
    d["glm"] = keys["debate"]["glm"]
    d["mode"] = "llm"
    cfg_disk["debate"] = d
    cfg_path.write_text(yaml.safe_dump(cfg_disk, allow_unicode=True), encoding="utf-8")

    monkeypatch.setattr(mod, "load_dotenv_keys", lambda *a, **k: None)
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-not-real")
    monkeypatch.setenv("ZAI_API_KEY", "test-zai-not-real")

    # generate luôn fail all_providers (models đã blocked → targets rỗng)
    def boom(*a, **k):
        err = RuntimeError("all_providers_failed:no_targets")
        setattr(err, "flags", ["llm_quota_skip_gemini_gemini-3.8-flash"])
        setattr(
            err,
            "models_tried",
            [
                {"provider": "gemini", "model": "gemini-3.8-flash", "reason": "quota_skip"},
                {"provider": "glm", "model": "glm-4.7-flash", "reason": "quota_skip"},
            ],
        )
        raise err

    monkeypatch.setattr("stockai.m7_scoring.debate._generate_fn", None)
    # Patch generate_json trong debate path
    monkeypatch.setattr("stockai.llm.generate.generate_json", boom)
    monkeypatch.setattr("stockai.m7_scoring.debate.generate_json", boom)

    # Tránh chạy M2–M6 nặng: stub upstream
    def fake_up(snap, cfg):
        return {
            m: {
                "module": m,
                "status": "ok",
                "score": 60.0,
                "metrics": {
                    "roe": {"value": 18, "unit": "ratio"},
                    "pe": {"value": 12, "unit": "x"},
                    "beta": {"value": 1.1, "unit": "x"},
                    "vol_20d": {"value": 0.02, "unit": "ratio"},
                },
                "evidence": [{"text": "e", "source_id": "s1"}],
                "flags": [],
            }
            for m in ("m2", "m3", "m4", "m5", "m6")
        }

    monkeypatch.setattr(mod, "build_upstream_m2_m6", fake_up)

    argv = [
        "run_debate_batch.py",
        "--as-of",
        as_of,
        "--snapshots-dir",
        str(snap_dir),
        "--tickers",
        "T1,T2,T3",
        "--config",
        str(cfg_path),
        "--max-live-calls",
        "50",
        "--providers",
        "gemini,glm",
    ]
    monkeypatch.setattr("sys.argv", argv)
    rc = mod.main()
    out = capsys.readouterr().out
    assert "STOP all_models_blocked" in out
    assert "MISSING_AI" in out
    assert "T1:" in out
    # Dừng sớm sau T1 vì all blocked — T2/T3 có thể chưa chạy hoặc cũng missing
    assert "providers=gemini,glm" in out
    assert rc in (0, 1)


def test_batch_providers_cli_order(keys, monkeypatch, tmp_path, capsys):
    """--providers glm đặt GLM trước trong log đầu batch."""
    import json
    import yaml

    as_of = "2026-10-08"
    snap_dir = tmp_path / "snaps"
    snap_dir.mkdir()
    demo = json.loads((ROOT / "fixtures" / "snapshot_DEMO.json").read_text(encoding="utf-8"))
    s = json.loads(json.dumps(demo))
    s["meta"]["ticker"] = "ZZZ"
    s["meta"]["as_of"] = as_of
    (snap_dir / f"ZZZ_{as_of}.json").write_text(json.dumps(s), encoding="utf-8")

    cfg_path = tmp_path / "llm.yaml"
    cfg_disk = load_llm_cfg()
    d = dict(cfg_disk.get("debate") or {})
    d["cache_dir"] = str(tmp_path)
    d["providers"] = ["gemini", "glm"]
    d["mode"] = "template"  # không gọi mạng
    cfg_disk["debate"] = d
    cfg_path.write_text(yaml.safe_dump(cfg_disk, allow_unicode=True), encoding="utf-8")

    mod = _load_batch_module()
    monkeypatch.setattr(mod, "load_dotenv_keys", lambda *a, **k: None)
    monkeypatch.setattr(
        mod,
        "build_upstream_m2_m6",
        lambda snap, cfg: {
            m: {
                "module": m,
                "status": "ok",
                "score": 50.0,
                "metrics": {},
                "evidence": [],
                "flags": [],
            }
            for m in ("m2", "m3", "m4", "m5", "m6")
        },
    )
    monkeypatch.setattr(
        "sys.argv",
        [
            "run_debate_batch.py",
            "--as-of",
            as_of,
            "--snapshots-dir",
            str(snap_dir),
            "--tickers",
            "ZZZ",
            "--config",
            str(cfg_path),
            "--template-only",
            "--providers",
            "glm",
        ],
    )
    mod.main()
    out = capsys.readouterr().out
    assert "providers=glm" in out
