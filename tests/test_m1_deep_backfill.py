"""Offline tests for Feature 005 deep fetch & quarterly backfill.

Coverage: SC-001…003, FR-001…015 (CLI reject exit 2, deep, backfill, regression).
Ops SC-004: xem specs/005-deep-backfill-quarterly/quickstart.md — không CI.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
import pytest

from stockai.contracts.helpers import check_no_lookahead
from stockai.contracts.schemas import validate
from stockai.m1_data import fetch as f
from stockai.m1_data import news_extra, news_portals
from stockai.m1_data import sources as src
from stockai.m1_data import universe as u
from tests.test_m1_normalize import _fin, _px

ROOT = Path(__file__).resolve().parents[1]


def _cfg(**kw):
    base = {
        "window_years": 5,
        "banks": ["VCB"],
        "peers_map": {},
        "index_symbol": "VNINDEX",
        "price_multiplier": "auto",
        "financial_multiplier": "auto",
        "news_enabled": True,
        "news_google": True,
        "news_google_wide": True,
        "news_months": 12,
        "max_news": 50,
        "request_interval_sec": 0,
        "icb_sector_enabled": True,
        "skip_peer_fetch": True,
        "vnf_enabled": False,
    }
    base.update(kw)
    return base


@pytest.fixture
def fake_sources(monkeypatch):
    calls: list[str] = []

    def hist(t, s, e, c):
        calls.append(f"hist:{t}")
        return (_px(1300) if t != "VNINDEX" else _px(1300, scale=50), "VCI")

    def finance(t, k, p, c):
        calls.append(f"fin:{p}:{k}")
        inc, bal, cf = _fin(annual=(p == "year"))
        return ({"income": inc, "balance": bal, "cashflow": cf}[k], "VCI")

    def overview(t, c):
        calls.append(f"overview:{t}")
        return (pd.DataFrame([{
            "exchange": "HOSE", "icb_name2": "Tài nguyên cơ bản",
            "icb_name4": "Thép", "issue_share": 6e9,
        }]), "VCI")

    def news(t, c):
        calls.append(f"news:{t}")
        return (pd.DataFrame({
            "title": [f"tin {i}" for i in range(12)],
            "publish_date": pd.date_range(end="2026-10-05", periods=12, freq="10D").astype(str),
            "link": [f"u{i}" for i in range(12)],
        }), "VCI")

    monkeypatch.setattr(src, "get_history", hist)
    monkeypatch.setattr(src, "get_finance", finance)
    monkeypatch.setattr(src, "get_exchange_map", lambda c: {"HPG": "HOSE", "VCB": "HOSE"})
    monkeypatch.setattr(src, "get_overview", overview)
    monkeypatch.setattr(src, "get_news", news)

    def _gnews(*a, **k):
        calls.append("google")
        return [], []

    monkeypatch.setattr(news_extra, "google_news", _gnews)
    monkeypatch.setattr(news_portals, "portals_enabled", lambda c: False)
    return calls


def _load_fu():
    sys.path.insert(0, str(ROOT / "scripts"))
    import fetch_universe as fu  # noqa: E402
    return fu


def _main_exit(fu, argv: list[str]) -> tuple[int, str]:
    import io
    from contextlib import redirect_stderr, redirect_stdout

    buf_out, buf_err = io.StringIO(), io.StringIO()
    try:
        with redirect_stdout(buf_out), redirect_stderr(buf_err):
            fu.main(argv)
        code = 0
    except SystemExit as e:
        code = int(e.code) if e.code is not None else 0
    return code, (buf_out.getvalue() + buf_err.getvalue())


# ----- T005: CLI reject/accept (fail-first; MUST fail before T006 wire) -----

def test_t005_deep_reject_no_tickers():
    fu = _load_fu()
    code, text = _main_exit(fu, ["--deep", "--as-of", "2026-10-08", "--universe", "VN100"])
    assert code == 2
    low = text.lower()
    assert "tickers" in low or "deep" in low


def test_t005_deep_reject_non_wide():
    fu = _load_fu()
    code, text = _main_exit(
        fu, ["--deep", "--tickers", "HPG", "--universe", "VN30", "--as-of", "2026-10-08"],
    )
    assert code == 2
    low = text.lower()
    assert "wide" in low or "vn30" in low or "deep" in low


def test_t005_deep_reject_with_backfill():
    fu = _load_fu()
    code, text = _main_exit(fu, [
        "--deep", "--backfill-quarterly", "--tickers", "HPG",
        "--universe", "VN100", "--as-of", "2026-10-08",
    ])
    assert code == 2
    low = text.lower()
    assert "backfill" in low or "deep" in low


def test_t005_deep_tickers_file_wide_not_fr001_exit2(tmp_path, monkeypatch):
    """--tickers-file → wide; không exit 2 vì FR-001 (thiếu wide/tickers)."""
    fu = _load_fu()
    tf = tmp_path / "list.txt"
    tf.write_text("HPG\n", encoding="utf-8")
    monkeypatch.setattr(fu, "run_deep_fetch", lambda *a, **k: {"HPG": {"status": "ok"}})
    code, _text = _main_exit(fu, [
        "--deep", "--tickers-file", str(tf), "--as-of", "2026-10-08",
        "--out-dir", str(tmp_path / "out"),
    ])
    assert code != 2


# ----- T007/T008: deep path (SC-001) -----

def test_t007_deep_from_early_exit_flags_company(fake_sources, monkeypatch):
    calls = fake_sources
    src_box = {"illiquid": True}

    def hist(t, s, e, c):
        calls.append(f"hist:{t}")
        if src_box["illiquid"] and t != "VNINDEX":
            # ít phiên / GTGD thấp → early-exit
            d = pd.bdate_range(end="2026-10-08", periods=10)
            return (pd.DataFrame({
                "time": d, "open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0, "volume": 0,
            }), "VCI")
        return (_px(800) if t != "VNINDEX" else _px(800, scale=50), "VCI")

    monkeypatch.setattr(src, "get_history", hist)
    stub = f.build_snapshot("HPG", "2026-10-08", _cfg(use_icb_peer_cascade=True))
    assert "fetch_skipped_early" in stub["meta"]["flags"]
    assert stub["company"].get("source_id") == "src_company_listing"
    src_box["illiquid"] = False
    calls.clear()
    snap = f.build_snapshot("HPG", "2026-10-08", _cfg(use_icb_peer_cascade=True, _deep=True))
    assert validate(snap, "snapshot") == []
    assert check_no_lookahead(snap) == []
    fl = snap["meta"]["flags"]
    assert "deep_fetch" in fl
    assert "fetch_skipped_early" not in fl
    assert "fast_mode" not in fl
    assert "quarterly_skipped_fast_mode" not in fl
    assert "company_name_missing_listing" not in fl
    assert snap["company"].get("source_id") == "src_company"
    assert any(c.startswith("fin:quarter:") for c in calls)
    assert snap["financials"]["quarterly"]
    assert any(c.startswith("overview:") for c in calls)


def test_t007_deep_create_new_and_redeep(fake_sources, tmp_path):
    out = tmp_path / "out"
    cfg = _cfg(use_icb_peer_cascade=True)
    res = f.run_deep_fetch(["HPG"], "2026-10-08", cfg, out_dir=str(out))
    assert res["HPG"]["status"] == "ok"
    p = out / "HPG_2026-10-08.json"
    assert p.exists()
    snap1 = json.loads(p.read_text(encoding="utf-8"))
    assert "deep_fetch" in snap1["meta"]["flags"]
    # re-deep
    res2 = f.run_deep_fetch(["HPG"], "2026-10-08", cfg, out_dir=str(out))
    assert res2["HPG"]["status"] == "ok"
    snap2 = json.loads(p.read_text(encoding="utf-8"))
    assert "deep_fetch" in snap2["meta"]["flags"]
    # file ngày khác không bị đụng
    other = out / "HPG_2020-01-01.json"
    other.write_text('{"keep": true}', encoding="utf-8")
    f.run_deep_fetch(["HPG"], "2026-10-08", cfg, out_dir=str(out))
    assert json.loads(other.read_text(encoding="utf-8")) == {"keep": True}


def test_t008_deep_no_auto_peers_google_sequential(fake_sources, monkeypatch, tmp_path):
    peers_called = []
    monkeypatch.setattr(u, "fill_peers", lambda *a, **k: peers_called.append(1))
    monkeypatch.setattr(u, "fill_peers_dir", lambda *a, **k: peers_called.append(1))
    cfg = _cfg(use_icb_peer_cascade=True, news_google_wide=False)  # wide gate off; deep vẫn Google qua news_google
    threads_before = set(th.name for th in __import__("threading").enumerate())
    res = f.run_deep_fetch(["HPG"], "2026-10-08", cfg, out_dir=str(tmp_path))
    assert res["HPG"]["status"] == "ok"
    assert peers_called == []
    # không yêu cầu Event A8; google có trong calls nếu news_google
    assert "google" in fake_sources
    # không còn thread google-* lạ sau khi xong
    alive = [th.name for th in __import__("threading").enumerate() if th.name.startswith("google-")]
    assert alive == []


# ----- T011/T012: backfill -----

def test_t011_backfill_three_calls_and_parity(fake_sources, tmp_path):
    calls = fake_sources
    # control non-fast
    control = f.build_snapshot("HPG", "2026-10-08", _cfg(use_icb_peer_cascade=False))
    # wide-fast snap thiếu quý
    fast_snap = f.build_snapshot("HPG", "2026-10-08", _cfg(use_icb_peer_cascade=True))
    assert fast_snap["financials"]["quarterly"] == []
    assert "quarterly_skipped_fast_mode" in fast_snap["meta"]["flags"]
    ind = tmp_path / "in"
    ind.mkdir()
    (ind / "HPG_2026-10-08.json").write_text(json.dumps(fast_snap, ensure_ascii=False), encoding="utf-8")
    calls.clear()
    out = tmp_path / "out"
    res = f.backfill_quarterly(
        ["HPG"], "2026-10-08", _cfg(), in_dir=str(ind), out_dir=str(out), in_place=False,
    )
    assert res["HPG"]["status"] == "ok"
    qcalls = [c for c in calls if c.startswith("fin:quarter:")]
    assert len(qcalls) == 3
    assert not any(c.startswith("fin:year:") for c in calls)
    filled = json.loads((out / "HPG_2026-10-08.json").read_text(encoding="utf-8"))
    assert filled["financials"]["quarterly"] == control["financials"]["quarterly"]
    assert "quarterly_backfilled" in filled["meta"]["flags"]
    assert "quarterly_skipped_fast_mode" not in filled["meta"]["flags"]
    assert filled["prices"] == fast_snap["prices"]
    assert filled["meta"]["as_of"] == fast_snap["meta"]["as_of"]
    # bank
    bank_fast = f.build_snapshot("VCB", "2026-10-08", _cfg(use_icb_peer_cascade=True, banks=["VCB"]))
    bank_fast["company"]["is_bank"] = True
    (ind / "VCB_2026-10-08.json").write_text(json.dumps(bank_fast, ensure_ascii=False), encoding="utf-8")
    calls.clear()
    res_b = f.backfill_quarterly(
        ["VCB"], "2026-10-08", _cfg(banks=["VCB"]), in_dir=str(ind), out_dir=str(out), in_place=False,
    )
    assert res_b["VCB"]["status"] == "ok"
    assert len([c for c in calls if c.startswith("fin:quarter:")]) == 3
    bank_out = json.loads((out / "VCB_2026-10-08.json").read_text(encoding="utf-8"))
    # không bịa NPL/CAR
    for per in bank_out["financials"].get("quarterly") or []:
        items = per.get("items") or {}
        if "npl_ratio" in items:
            assert items["npl_ratio"] is None or isinstance(items["npl_ratio"], (int, float))


def test_t012_backfill_skip_idempotent_inplace(fake_sources, tmp_path, monkeypatch):
    import shutil

    def hist_illiquid(t, s, e, c):
        fake_sources.append(f"hist:{t}")
        d = pd.bdate_range(end="2026-10-08", periods=10)
        return (pd.DataFrame({
            "time": d, "open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0, "volume": 0,
        }), "VCI")

    monkeypatch.setattr(src, "get_history", hist_illiquid)
    stub = f.build_snapshot("AAA", "2026-10-08", _cfg(use_icb_peer_cascade=True))
    assert "fetch_skipped_early" in stub["meta"]["flags"]
    ind = tmp_path / "in"
    ind.mkdir()
    (ind / "AAA_2026-10-08.json").write_text(json.dumps(stub), encoding="utf-8")

    def hist_ok(t, s, e, c):
        fake_sources.append(f"hist:{t}")
        return (_px(800) if t != "VNINDEX" else _px(800, scale=50), "VCI")

    monkeypatch.setattr(src, "get_history", hist_ok)
    res = f.backfill_quarterly(
        ["AAA"], "2026-10-08", _cfg(), in_dir=str(ind), out_dir=str(tmp_path / "o"), in_place=False,
    )
    assert res["AAA"]["status"] == "skipped_early_exit"
    full = f.build_snapshot("HPG", "2026-10-08", _cfg(use_icb_peer_cascade=False))
    (ind / "HPG_2026-10-08.json").write_text(json.dumps(full), encoding="utf-8")
    res2 = f.backfill_quarterly(
        ["HPG"], "2026-10-08", _cfg(), in_dir=str(ind), out_dir=str(tmp_path / "o2"), in_place=False,
    )
    assert res2["HPG"]["status"] == "skipped"
    fast = f.build_snapshot("BMP", "2026-10-08", _cfg(use_icb_peer_cascade=True))
    (ind / "BMP_2026-10-08.json").write_text(json.dumps(fast), encoding="utf-8")
    res3 = f.backfill_quarterly(
        ["BMP"], "2026-10-08", _cfg(), in_dir=str(ind), out_dir=str(ind), in_place=False,
    )
    assert res3["BMP"]["status"] == "error"
    assert "in-place" in res3["BMP"]["error"]
    out = tmp_path / "bf"
    f.backfill_quarterly(["BMP"], "2026-10-08", _cfg(), in_dir=str(ind), out_dir=str(out), in_place=False)
    shutil.copy(out / "BMP_2026-10-08.json", ind / "BMP_2026-10-08.json")
    fake_sources.clear()
    res4 = f.backfill_quarterly(
        ["BMP"], "2026-10-08", _cfg(), in_dir=str(ind), out_dir=str(ind), in_place=True,
    )
    assert res4["BMP"]["status"] == "skipped"
    assert not any(c.startswith("fin:quarter:") for c in fake_sources)


# ----- T015 US3 regression -----

def test_t015_vn30_and_fast_default_unchanged(fake_sources, monkeypatch):
    snap = f.build_snapshot("HPG", "2026-10-08", _cfg(use_icb_peer_cascade=False))
    assert "deep_fetch" not in snap["meta"]["flags"]
    assert "quarterly_backfilled" not in snap["meta"]["flags"]
    assert snap["financials"]["quarterly"]

    def hist_illiquid(t, s, e, c):
        fake_sources.append(f"hist:{t}")
        d = pd.bdate_range(end="2026-10-08", periods=10)
        return (pd.DataFrame({
            "time": d, "open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0, "volume": 0,
        }), "VCI")

    monkeypatch.setattr(src, "get_history", hist_illiquid)
    stub = f.build_snapshot("HPG", "2026-10-08", _cfg(use_icb_peer_cascade=True))
    assert "fetch_skipped_early" in stub["meta"]["flags"]


# ----- T017/T018 polish -----

def test_t017_refresh_on_deep_not_skipped(fake_sources, tmp_path):
    out = tmp_path / "d"
    f.run_deep_fetch(["HPG"], "2026-10-08", _cfg(use_icb_peer_cascade=True), out_dir=str(out))
    res = f.refresh_news_prices(
        ["HPG"], "2026-10-08", _cfg(), in_dir=str(out), out_dir=str(tmp_path / "r"), in_place=False,
    )
    assert res["HPG"]["status"] != "skipped_early_exit"
    assert res["HPG"]["status"] == "ok"


def test_t018_deep_eligible_for_peers(fake_sources, tmp_path):
    out = tmp_path / "d"
    f.run_deep_fetch(["HPG"], "2026-10-08", _cfg(use_icb_peer_cascade=True), out_dir=str(out))
    snap = json.loads((out / "HPG_2026-10-08.json").read_text(encoding="utf-8"))
    assert "fetch_skipped_early" not in snap["meta"]["flags"]
    # _view / assign: mã không early-exit được vào peers
    views = {
        "HPG": {"sector": "Basic Resources", "parent": "Basic Materials",
                "met": {"market_cap": 1e13}, "is_bank": False, "flags": snap["meta"]["flags"]},
        "HSG": {"sector": "Basic Resources", "parent": "Basic Materials",
                "met": {"market_cap": 5e12}, "is_bank": False, "flags": []},
    }
    # chỉ cần không bị loại vì fetch_skipped_early
    assert "fetch_skipped_early" not in (views["HPG"].get("flags") or [])


def test_effective_fast_respects_deep():
    assert f.effective_fast({"use_icb_peer_cascade": True}) is True
    assert f.effective_fast({"use_icb_peer_cascade": True, "_deep": True}) is False
    assert f.effective_fast({}) is False
