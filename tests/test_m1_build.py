import json
"""build_snapshot end-to-end với nguồn giả: snapshot phải hợp lệ schema, đúng as_of, và lỗi 1 khối không làm sập."""
import numpy as np
import pandas as pd
import pytest

from stockai.contracts.helpers import check_no_lookahead
from stockai.contracts.schemas import validate
from stockai.m1_data import fetch as f
from stockai.m1_data import sources as src
from tests.test_m1_normalize import _fin, _px


@pytest.fixture
def fake_sources(monkeypatch):
    monkeypatch.setattr(src, "get_history", lambda t, s, e, c: (_px(1300) if t != "VNINDEX" else _px(1300, scale=50), "VCI"))
    inc, bal, cf = _fin()
    monkeypatch.setattr(src, "get_finance", lambda t, k, p, c: ({"income": inc, "balance": bal, "cashflow": cf}[k], "VCI"))
    monkeypatch.setattr(src, "get_exchange_map", lambda c: {"HPG": "HOSE"})
    monkeypatch.setattr(src, "get_overview", lambda t, c: (pd.DataFrame([{"exchange": "HOSE", "icb_name2": "Tài nguyên cơ bản", "icb_name4": "Thép", "issue_share": 6e9}]), "VCI"))
    monkeypatch.setattr(src, "get_news", lambda t, c: (pd.DataFrame({"title": [f"tin {i}" for i in range(12)], "publish_date": pd.date_range(end="2026-10-05", periods=12, freq="10D").astype(str), "link": [f"u{i}" for i in range(12)]}), "VCI"))


CFG = {"window_years": 5, "banks": ["VCB"], "peers_map": {"HPG": ["HSG", "NKG", "SMC"]}, "index_symbol": "VNINDEX", "price_multiplier": "auto", "financial_multiplier": "auto"}


def test_build_snapshot_valid(fake_sources):
    snap = f.build_snapshot("HPG", "2026-10-09", CFG)
    assert validate(snap, "snapshot") == [] and check_no_lookahead(snap) == []
    st = snap["meta"]["data_status"]
    assert st["prices"] == "ok" and st["financials"] == "ok" and st["peers"] == "ok" and st["news"] == "ok"
    assert snap["company"]["shares_outstanding"] == 6e9 and not snap["company"]["is_bank"] and snap["company"]["exchange"] == "HOSE"
    assert snap["financials"]["annual"][0]["items"]["revenue"] == 150e9 and snap["financials"]["column_map"]["annual"]["revenue"] == "Net sales"
    assert snap["peers"][0]["roe"] == pytest.approx(13 / 80)           # LNST công ty mẹ / VCSH, tự tính
    assert {s["id"] for s in snap["sources"]} >= {"src_price", "src_index", "src_company", "src_news"}


def test_one_block_failing_does_not_break_snapshot(fake_sources, monkeypatch):
    monkeypatch.setattr(src, "get_news", lambda t, c: (_ for _ in ()).throw(RuntimeError("boom")))
    snap = f.build_snapshot("HPG", "2026-10-09", CFG)
    assert validate(snap, "snapshot") == [] and snap["meta"]["data_status"]["news"] == "missing"
    assert any("news" in x for x in snap["meta"]["flags"])


def test_everything_down_still_returns_valid_snapshot(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("offline")
    for name in ("get_history", "get_finance", "get_overview", "get_news", "get_industry_peers"):
        monkeypatch.setattr(src, name, boom)
    snap = f.build_snapshot("HPG", "2026-10-09", {**CFG, "peers_map": {}})
    assert validate(snap, "snapshot") == []
    assert set(snap["meta"]["data_status"].values()) == {"missing"}


def test_backtest_as_of_in_past_excludes_later_data(fake_sources):
    snap = f.build_snapshot("HPG", "2025-06-30", CFG)
    assert check_no_lookahead(snap) == [] and snap["prices"]["rows"][-1]["date"] <= "2025-06-30"
    assert all(p["published_at"] <= "2025-06-30" for p in snap["financials"]["annual"])


def test_raw_csv_export_and_sources_json(tmp_path):
    cfg = {"cache_dir": str(tmp_path), "retries": 1, "request_interval_sec": 0}
    df = pd.DataFrame({"time": ["2026-10-09"], "close": [20.1]})
    src._cached(cfg, "hist", "HPG", "k", lambda: (df, "VCI"))
    src._cached(cfg, "fin-income", "HPG", "year", lambda: (df, "VCI"))
    assert (tmp_path / "HPG" / "hist.csv").exists() and (tmp_path / "HPG" / "fin-income_year.csv").exists()
    meta = json.loads((tmp_path / "HPG" / "_sources.json").read_text(encoding="utf-8"))
    assert meta["hist.csv"]["provider"] == "VCI" and meta["hist.csv"]["rows"] == 1
    assert pd.read_csv(tmp_path / "HPG" / "hist.csv", encoding="utf-8-sig").loc[0, "close"] == 20.1
