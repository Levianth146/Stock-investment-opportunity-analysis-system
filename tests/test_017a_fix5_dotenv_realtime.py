"""017a-fix5 — hub đọc .env DNSE; status.reason khi no_realtime (offline)."""
from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from stockai.api.realtime import RealtimeHub
from stockai.api.store import ResultStore
from stockai.envfile import load_dotenv, parse_dotenv_text

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "fixtures" / "snapshot_DEMO.json"
ASOF = "2026-10-08"
ICT = ZoneInfo("Asia/Ho_Chi_Minh")


def _clone(ticker: str) -> dict:
    snap = json.loads(FIX.read_text(encoding="utf-8"))
    snap["meta"]["ticker"] = ticker
    snap["meta"]["as_of"] = ASOF
    snap["meta"]["synthetic"] = False
    flags = [f for f in (snap["meta"].get("flags") or []) if not str(f).startswith("quality_")]
    flags.append("quality_tier_full")
    snap["meta"]["flags"] = flags
    return snap


def _hub(tmp_path: Path, *, enabled: bool = True) -> RealtimeHub:
    snap_dir = tmp_path / "snapshots"
    cache_dir = tmp_path / "api_cache"
    snap_dir.mkdir()
    cache_dir.mkdir()
    (snap_dir / f"AAA_{ASOF}.json").write_text(
        json.dumps(_clone("AAA"), ensure_ascii=False), encoding="utf-8"
    )
    cfg = {
        "snapshots_dir": str(snap_dir),
        "asof": ASOF,
        "cache_dir": str(cache_dir),
        "realtime": {"enabled": enabled, "price_scale": 1},
    }
    store = ResultStore(cfg, snapshots_dir=snap_dir, cache_dir=cache_dir, asof=ASOF)
    return RealtimeHub(store, cfg)


def test_parse_dotenv_spaces_quotes_crlf_bom():
    """Parser: KEY = value, quotes, export, CRLF, BOM — không print giá trị."""
    # BOM + CRLF + khoảng trắng + export + comment
    raw = (
        "\ufeff# comment\r\n"
        "DNSE_API_KEY = plain_key_xyz\r\n"
        'DNSE_API_SECRET_KEY = "quoted_secret_abc"\r\n'
        "export GEMINI_API_KEY = 'gemini_quoted'\r\n"
        "ZAI_API_KEY=no_space\r\n"
        "EMPTY=\r\n"
        "# DNSE_API_KEY = ignored\r\n"
    )
    parsed = parse_dotenv_text(raw)
    assert parsed["DNSE_API_KEY"] == "plain_key_xyz"
    assert parsed["DNSE_API_SECRET_KEY"] == "quoted_secret_abc"
    assert parsed["GEMINI_API_KEY"] == "gemini_quoted"
    assert parsed["ZAI_API_KEY"] == "no_space"
    assert "EMPTY" not in parsed
    # Không lộ giá trị trong repr helper (chỉ kiểm độ dài / tồn tại khóa)
    assert len(parsed["DNSE_API_KEY"]) == 13
    assert "plain_key_xyz" not in parse_dotenv_text.__doc__  # sanity


def test_load_dotenv_never_overwrite(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("DNSE_API_KEY = from_file\nOTHER = x\n", encoding="utf-8")
    monkeypatch.setenv("DNSE_API_KEY", "already_set")
    monkeypatch.delenv("OTHER", raising=False)
    flags = load_dotenv(env_file, keys=("DNSE_API_KEY", "OTHER"))
    assert flags["DNSE_API_KEY"] is False  # không ghi đè
    assert flags["OTHER"] is True
    assert __import__("os").environ["DNSE_API_KEY"] == "already_set"
    assert __import__("os").environ["OTHER"] == "x"


def test_status_missing_key_reason(tmp_path, monkeypatch, caplog):
    """Thiếu khóa → mode=no_realtime, reason=missing_key; log chỉ yes/no."""
    monkeypatch.delenv("DNSE_API_KEY", raising=False)
    monkeypatch.delenv("DNSE_API_SECRET_KEY", raising=False)
    monkeypatch.delenv("DNSE_API_SECRET", raising=False)
    empty = tmp_path / "empty.env"
    empty.write_text("# no keys\n", encoding="utf-8")
    monkeypatch.setattr(
        "stockai.envfile.repo_dotenv_path",
        lambda: empty,
    )
    hub = _hub(tmp_path, enabled=True)
    with caplog.at_level(logging.INFO, logger="stockai.api.realtime"):
        hub.start()
    st = hub.status()
    assert st["mode"] == "no_realtime"
    assert st["state"] == "no_realtime"
    assert st.get("reason") == "missing_key"
    # Log chỉ yes/no — không chứa giá trị khóa giả định
    joined = " ".join(r.message for r in caplog.records)
    assert "DNSE key loaded: no" in joined
    hub.stop()


def test_status_disabled_reason(tmp_path, monkeypatch):
    monkeypatch.delenv("DNSE_API_KEY", raising=False)
    monkeypatch.delenv("DNSE_API_SECRET_KEY", raising=False)
    hub = _hub(tmp_path, enabled=False)
    hub.start()
    st = hub.status()
    assert st["mode"] == "no_realtime"
    assert st.get("reason") == "disabled"
    hub.stop()


def test_hub_loads_dnse_from_dotenv(tmp_path, monkeypatch, caplog):
    """Hub start nạp KEY = value từ .env khi environ trống."""
    import builtins
    import os

    monkeypatch.delenv("DNSE_API_KEY", raising=False)
    monkeypatch.delenv("DNSE_API_SECRET_KEY", raising=False)
    monkeypatch.delenv("DNSE_API_SECRET", raising=False)
    env_file = tmp_path / ".env"
    # Giá trị giả — chỉ assert tồn tại, không print
    env_file.write_bytes(
        b"\xef\xbb\xbfDNSE_API_KEY = test_key_017a\r\n"
        b'DNSE_API_SECRET_KEY = "test_secret_017a"\r\n'
    )
    monkeypatch.setattr("stockai.envfile.repo_dotenv_path", lambda: env_file)

    hub = _hub(tmp_path, enabled=True)
    real_import = builtins.__import__

    def _fake_import(name, *a, **k):  # noqa: ANN001
        if name == "dnse" or (isinstance(name, str) and name.startswith("dnse.")):
            raise ImportError("blocked")
        return real_import(name, *a, **k)

    monkeypatch.setattr(builtins, "__import__", _fake_import)

    with caplog.at_level(logging.INFO, logger="stockai.api.realtime"):
        hub.start()

    assert os.environ.get("DNSE_API_KEY") == "test_key_017a"
    assert os.environ.get("DNSE_API_SECRET_KEY") == "test_secret_017a"
    joined = " ".join(r.message for r in caplog.records)
    assert "DNSE key loaded: yes" in joined
    assert "test_key_017a" not in joined
    assert "test_secret_017a" not in joined
    st = hub.status()
    assert st["mode"] == "no_realtime"
    assert st.get("reason") == "sdk_missing"
    hub.stop()


def test_no_realtime_open_session_null_pct(tmp_path, monkeypatch):
    """Phiên mở + no_realtime → change_pct None (không +0%)."""
    monkeypatch.delenv("DNSE_API_KEY", raising=False)
    monkeypatch.delenv("DNSE_API_SECRET_KEY", raising=False)
    empty = tmp_path / "empty.env"
    empty.write_text("", encoding="utf-8")
    monkeypatch.setattr("stockai.envfile.repo_dotenv_path", lambda: empty)
    hub = _hub(tmp_path, enabled=True)
    hub._now_fn = lambda: datetime(2026, 10, 15, 10, 0, tzinfo=ICT)  # noqa: SLF001
    hub.start()
    q = hub.get_quote("AAA")
    assert q.state == "no_realtime"
    assert q.change_pct is None
    assert q.change is None
    hub.stop()
