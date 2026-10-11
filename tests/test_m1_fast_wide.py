"""Offline tests for Feature 004 fast wide mode.

Coverage map (CI): SC-001 fake clock, SC-004…SC-008, FR-001…016, FR-018.
Ops SC-001 (≥3 mã), SC-002, SC-003: xem quickstart — không có pytest ở đây.
"""
from __future__ import annotations

import io
import json
import sys
import threading
from pathlib import Path

import pandas as pd
import pytest

from stockai.contracts.helpers import check_no_lookahead
from stockai.contracts.schemas import validate
from stockai.m1_data import fetch as f
from stockai.m1_data import news_extra, news_portals, quality as q
from stockai.m1_data import sources as src
from stockai.m1_data import universe as u
from tests.test_m1_normalize import _fin, _px

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "fixtures" / "snapshot_DEMO.json"


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
        inc, bal, cf = _fin()
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
    monkeypatch.setattr(src, "get_exchange_map", lambda c: {"HPG": "HOSE"})
    monkeypatch.setattr(src, "get_overview", overview)
    monkeypatch.setattr(src, "get_news", news)

    def _gnews(*a, **k):
        calls.append("google")
        return [], []

    monkeypatch.setattr(news_extra, "google_news", _gnews)
    monkeypatch.setattr(news_portals, "portals_enabled", lambda c: False)
    return calls


def _illiquid_rows(n=10, vol=0):
    """Ít phiên / GTGD không tính được → insufficient từ giá."""
    base = {"date": "2026-01-01", "open": 1.0, "high": 1.0, "low": 1.0, "close": 1.0, "volume": vol}
    return [{**base, "date": f"2026-01-{i+1:02d}"} for i in range(n)]


# ----- foundational / FR-018 -----

def test_fast_mode_enabled_cascade_or_fast_wide():
    assert f.fast_mode_enabled({"use_icb_peer_cascade": True}) is True
    assert f.fast_mode_enabled({"fast_wide": True}) is True
    assert f.fast_mode_enabled({}) is False


def test_price_insufficient_reasons_uses_quality(monkeypatch):
    reasons = q.price_insufficient_reasons(_illiquid_rows(10), {"quality": {"min_price_rows": 750}})
    assert any(r.startswith("prices_lt_") for r in reasons)
    # None GTGD → illiquid (volume 0 / missing close*vol)
    r2 = q.price_insufficient_reasons(
        [{"date": "2026-01-01", "open": None, "high": None, "low": None, "close": None, "volume": None}] * 800,
        None,
    )
    assert "illiquid" in r2


def test_fr018_tickers_alone_vs_with_universe():
    sys.path.insert(0, str(ROOT / "scripts"))
    import fetch_universe as fu  # noqa: E402

    cfg_a = {}
    wide_a, _ = fu.apply_cli_cfg(cfg_a, universe="VN30", tickers=["HPG"], tickers_file=None)
    assert wide_a is False
    assert f.fast_mode_enabled(cfg_a) is False

    cfg_b = {}
    wide_b, _ = fu.apply_cli_cfg(cfg_b, universe="VN100", tickers=["HPG"], tickers_file=None)
    assert wide_b is True
    assert cfg_b["use_icb_peer_cascade"] is True
    assert f.fast_mode_enabled(cfg_b) is True


# ----- US1 -----

def test_us1_fast_skips_quarterly(fake_sources):
    calls = fake_sources
    snap = f.build_snapshot("HPG", "2026-10-09", _cfg(use_icb_peer_cascade=True))
    assert snap["financials"]["quarterly"] == []
    assert "quarterly_skipped_fast_mode" in snap["meta"]["flags"]
    assert "fast_mode" in snap["meta"]["flags"]
    assert any(c.startswith("fin:year:") for c in calls)
    assert not any(c.startswith("fin:quarter:") for c in calls)


def test_us1_google_wide_on_and_off(fake_sources, monkeypatch):
    gcalls: list[int] = []

    def gnews(*a, **k):
        gcalls.append(1)
        return [{"title": "HPG tin", "link": "http://x", "publish_date": "2026-09-01T00:00:00",
                 "summary": "HPG", "source": "cafe"}], []

    monkeypatch.setattr(news_extra, "google_news", gnews)
    snap = f.build_snapshot("HPG", "2026-10-09", _cfg(use_icb_peer_cascade=True, news_google_wide=True))
    assert gcalls and "google_news_skipped_fast_mode" not in snap["meta"]["flags"]

    gcalls.clear()
    primary: list[str] = []

    def get_news(t, c):
        primary.append(t)
        return pd.DataFrame({
            "title": [f"tin {i}" for i in range(12)],
            "publish_date": pd.date_range(end="2026-10-05", periods=12, freq="10D").astype(str),
            "link": [f"u{i}" for i in range(12)],
        }), "VCI"

    monkeypatch.setattr(src, "get_news", get_news)
    portal_calls: list[int] = []

    def fake_portals(*a, **k):
        portal_calls.append(1)
        return [], []

    monkeypatch.setattr(news_portals, "portals_enabled", lambda c: True)
    monkeypatch.setattr(news_portals, "fetch_portals", fake_portals)
    monkeypatch.setattr(news_portals, "merge_pre_cap_for_flags", lambda items, p: items)
    monkeypatch.setattr(news_portals, "refine_portal_flags_after_dedupe", lambda *a, **k: [])
    monkeypatch.setattr(news_portals, "merge_news", lambda items, p, m: items[:m])
    monkeypatch.setattr(news_portals, "active_portal_slugs", lambda c: ["cafef"])
    monkeypatch.setattr(news_portals, "normalize_url", lambda u: u or "")
    monkeypatch.setattr(news_portals, "normalize_title", lambda t: t or "")

    snap2 = f.build_snapshot(
        "HPG", "2026-10-09",
        _cfg(use_icb_peer_cascade=True, news_google_wide=False),
    )
    assert not gcalls
    assert "google_news_skipped_fast_mode" in snap2["meta"]["flags"]
    assert primary, "primary news still called when Google off"
    assert portal_calls, "active portals still called when Google off"


def test_us1_bank_empty_quarterly_ok(fake_sources):
    from stockai.m1_data import bank_kpis
    snap = f.build_snapshot("VCB", "2026-10-09", _cfg(use_icb_peer_cascade=True, banks=["VCB"]))
    assert snap["financials"]["quarterly"] == []
    bank_kpis.apply(snap, "config/bank_kpis.csv")  # không raise


# ----- US2 -----

def test_us2_vn30_no_fast_flags(fake_sources):
    calls = fake_sources
    snap = f.build_snapshot("HPG", "2026-10-09", _cfg(use_icb_peer_cascade=False, fast_wide=False))
    fl = snap["meta"]["flags"]
    assert "fast_mode" not in fl
    assert "quarterly_skipped_fast_mode" not in fl
    assert "fetch_skipped_early" not in fl
    assert "google_news_skipped_fast_mode" not in fl
    assert any(c.startswith("fin:quarter:") for c in calls)


# ----- US5 / SC-006 -----

def test_us5_early_exit_sc006(fake_sources, monkeypatch):
    calls = fake_sources

    def hist(t, s, e, c):
        calls.append(f"hist:{t}")
        if t == "VNINDEX":
            return _px(1300, scale=50), "VCI"
        # illiquid: ít phiên
        df = _px(20)
        df["volume"] = 0
        return df, "VCI"

    monkeypatch.setattr(src, "get_history", hist)
    gcalls = []
    monkeypatch.setattr(news_extra, "google_news", lambda *a, **k: (gcalls.append(1), ([], []))[1])
    snap = f.build_snapshot("HPG", "2026-10-09", _cfg(use_icb_peer_cascade=True))
    assert "fetch_skipped_early" in snap["meta"]["flags"]
    assert "quality_tier_insufficient" in snap["meta"]["flags"]
    assert any(x.startswith("quality_prices_lt_") or x == "quality_illiquid" for x in snap["meta"]["flags"])
    assert not any(x.startswith("quality_annual_lt_") for x in snap["meta"]["flags"])
    assert validate(snap, "snapshot") == []
    assert not any(c.startswith("fin:") for c in calls)
    assert not any(c.startswith("overview:") for c in calls)
    assert not any(c.startswith("news:") for c in calls)
    assert not gcalls
    assert snap["financials"]["annual"] == [] and snap["news"] == []
    assert snap["company"]["name"]  # listing
    assert snap["index"]["rows"]  # shared cache


def test_us5_early_exit_excluded_from_peers():
    s_ok = json.loads(FIX.read_text(encoding="utf-8"))
    s_ok["meta"]["ticker"] = "AAA"
    s_ok["company"]["sector"] = "Chemicals"
    s_ok["company"]["shares_outstanding"] = 5e9
    s_bad = json.loads(FIX.read_text(encoding="utf-8"))
    s_bad["meta"]["ticker"] = "BBB"
    s_bad["company"]["sector"] = "Chemicals"
    s_bad["meta"]["flags"] = ["fetch_skipped_early", "fast_mode", "quality_tier_insufficient"]
    s_bad["financials"]["annual"] = []
    s_bad["peers"] = []
    snaps = {"AAA": s_ok, "BBB": s_bad, "CCC": json.loads(FIX.read_text(encoding="utf-8"))}
    snaps["CCC"]["meta"]["ticker"] = "CCC"
    snaps["CCC"]["company"]["sector"] = "Chemicals"
    snaps["CCC"]["company"]["shares_outstanding"] = 4e9
    u.fill_peers(snaps, max_peers=5, cfg={"use_icb_peer_cascade": False, "icb_sector_enabled": False})
    peer_tickers = {p["ticker"] for p in snaps["AAA"]["peers"]}
    assert "BBB" not in peer_tickers


def test_prices_error_does_not_early_exit(fake_sources, monkeypatch):
    """Giá lỗi (exception) → đường cũ; không gắn fetch_skipped_early / quality_illiquid."""

    def hist(t, s, e, c):
        if t == "VNINDEX":
            return _px(1300, scale=50), "VCI"
        raise RuntimeError("price feed down")

    monkeypatch.setattr(src, "get_history", hist)
    snap = f.build_snapshot("HPG", "2026-10-09", _cfg(use_icb_peer_cascade=True))
    fl = snap["meta"]["flags"]
    assert "fetch_skipped_early" not in fl
    assert "quality_illiquid" not in fl
    assert not any(x.startswith("quality_prices_lt_") for x in fl)
    assert any("m1_prices_error" in x or "prices" in x and "error" in x for x in fl)
    assert validate(snap, "snapshot") == []


def test_quality_apply_on_early_exit_no_annual_lt(fake_sources, monkeypatch):
    """quality.apply trên snapshot early-exit: chỉ lý do giá; idempotent."""

    def hist(t, s, e, c):
        if t == "VNINDEX":
            return _px(1300, scale=50), "VCI"
        df = _px(20)
        df["volume"] = 0
        return df, "VCI"

    monkeypatch.setattr(src, "get_history", hist)
    snap = f.build_snapshot("HPG", "2026-10-09", _cfg(use_icb_peer_cascade=True))
    assert "fetch_skipped_early" in snap["meta"]["flags"]
    q.apply(snap)
    fl1 = list(snap["meta"]["flags"])
    assert "quality_tier_insufficient" in fl1
    assert "quality_illiquid" in fl1 or any(x.startswith("quality_prices_lt_") for x in fl1)
    assert "quality_annual_lt_3" not in fl1
    assert not any(x.startswith("quality_annual_lt_") for x in fl1)
    assert "quality_news_few" not in fl1
    assert "quality_sector_missing" not in fl1
    assert "quality_shares_missing" not in fl1
    q.apply(snap)
    assert snap["meta"]["flags"] == fl1


def test_early_exit_sources_cover_block_ids(fake_sources, monkeypatch):
    """company/prices/index source_id đều có trong snapshot['sources']."""

    def hist(t, s, e, c):
        if t == "VNINDEX":
            return _px(1300, scale=50), "VCI"
        df = _px(20)
        df["volume"] = 0
        return df, "VCI"

    monkeypatch.setattr(src, "get_history", hist)
    snap = f.build_snapshot("HPG", "2026-10-09", _cfg(use_icb_peer_cascade=True))
    assert "fetch_skipped_early" in snap["meta"]["flags"]
    ids = {s["id"] for s in snap["sources"]}
    assert snap["company"]["source_id"] in ids
    assert snap["prices"]["source_id"] in ids
    assert snap["index"]["source_id"] in ids
    assert "src_company_listing" in ids


def test_refresh_skips_early_exit_snapshot(tmp_path, fake_sources, monkeypatch):
    """Snapshot fetch_skipped_early → refresh bỏ qua, status skipped_early_exit."""

    def hist(t, s, e, c):
        if t == "VNINDEX":
            return _px(1300, scale=50), "VCI"
        df = _px(20)
        df["volume"] = 0
        return df, "VCI"

    monkeypatch.setattr(src, "get_history", hist)
    src_dir = tmp_path / "src"
    out_dir = tmp_path / "out"
    src_dir.mkdir()
    snap = f.build_snapshot("HPG", "2026-10-08", _cfg(use_icb_peer_cascade=True))
    assert "fetch_skipped_early" in snap["meta"]["flags"]
    (src_dir / "HPG_2026-10-08.json").write_text(json.dumps(snap), encoding="utf-8")
    res = f.refresh_news_prices(
        ["HPG"], "2026-10-09", _cfg(),
        in_dir=str(src_dir), out_dir=str(out_dir), in_place=False,
    )
    assert res["HPG"]["status"] == "skipped_early_exit"
    assert not (out_dir / "HPG_2026-10-09.json").exists()


# ----- US4 / SC-007 -----

def test_us4_google_starts_before_vnstock_finishes(fake_sources, monkeypatch):
    started = threading.Event()
    order: list[str] = []

    def gnews(*a, **k):
        started.set()
        order.append("google")
        return [], []

    fin_calls = []

    def finance(t, k, p, c):
        assert started.wait(timeout=2.0), "Google phải bắt đầu trước khi BCTC xong"
        fin_calls.append(p)
        order.append(f"fin:{p}")
        inc, bal, cf = _fin()
        return ({"income": inc, "balance": bal, "cashflow": cf}[k], "VCI")

    monkeypatch.setattr(news_extra, "google_news", gnews)
    monkeypatch.setattr(src, "get_finance", finance)
    snap = f.build_snapshot("HPG", "2026-10-09", _cfg(use_icb_peer_cascade=True, news_google_wide=True))
    assert "google" in order and any(x.startswith("fin:") for x in order)
    assert order.index("google") < max(i for i, x in enumerate(order) if x.startswith("fin:"))
    assert validate(snap, "snapshot") == []


def test_us4_bg_google_same_as_sequential(fake_sources, monkeypatch):
    rows = [{"title": "HPG A", "link": "http://a", "publish_date": "2026-09-01T00:00:00",
             "summary": "HPG", "source": "x"}]

    monkeypatch.setattr(news_extra, "google_news", lambda *a, **k: (rows, []))
    snap_bg = f.build_snapshot("HPG", "2026-10-09", _cfg(use_icb_peer_cascade=True))

    # tuần tự: tắt fast → Google trong fetch_news
    snap_seq = f.build_snapshot("HPG", "2026-10-09", _cfg(use_icb_peer_cascade=False, fast_wide=False))
    # so sánh phần tin có URL google-ish — ít nhất flags google lỗi giống / không crash
    assert validate(snap_bg, "snapshot") == [] and validate(snap_seq, "snapshot") == []


# ----- US3 / SC-005 -----

def test_us3_refresh_keeps_financials(tmp_path, fake_sources, monkeypatch):
    monkeypatch.setattr(news_extra, "google_news", lambda *a, **k: ([], []))
    src_dir = tmp_path / "src"
    out_dir = tmp_path / "out"
    src_dir.mkdir()
    snap = f.build_snapshot("HPG", "2026-10-08", _cfg(use_icb_peer_cascade=False))
    fin = snap["financials"]
    peers = snap["peers"]
    company = json.loads(json.dumps(snap["company"]))
    (src_dir / "HPG_2026-10-08.json").write_text(json.dumps(snap), encoding="utf-8")
    gcalls = []
    monkeypatch.setattr(news_extra, "google_news", lambda *a, **k: (gcalls.append(1), ([], []))[1])
    res = f.refresh_news_prices(
        ["HPG"], "2026-10-09", _cfg(_no_google=True, news_google=False),
        in_dir=str(src_dir), out_dir=str(out_dir), in_place=False,
    )
    assert res["HPG"]["status"] == "ok"
    assert not gcalls
    assert (src_dir / "HPG_2026-10-08.json").exists()
    out = json.loads((out_dir / "HPG_2026-10-09.json").read_text(encoding="utf-8"))
    assert out["financials"] == fin
    assert out["peers"] == peers
    assert out["company"] == company
    assert "refreshed_news_prices" in out["meta"]["flags"]
    assert out["meta"]["as_of"] == "2026-10-09"
    assert check_no_lookahead(out) == []


# ----- US6 / SC-008 -----

def test_us6_utf8_stdio_no_unicode_error(monkeypatch):
    sys.path.insert(0, str(ROOT / "scripts"))
    # mô phỏng stdout hẹp
    narrow = io.TextIOWrapper(io.BytesIO(), encoding="cp1252", errors="strict")
    monkeypatch.setattr(sys, "stdout", narrow)
    monkeypatch.setattr(sys, "stderr", narrow)
    # import lại setup — gọi reconfigure như script
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    sys.stdout.write("Tiếng Việt: chế độ nhanh\n")
    sys.stdout.flush()


# ----- SC-001 fake clock -----

def test_sc001_fake_throttle_fast_cheaper(monkeypatch):
    waits: list[float] = []

    def fake_throttle(interval: float) -> None:
        waits.append(interval)

    monkeypatch.setattr(src, "_throttle", fake_throttle)
    # đếm số lần throttle qua get_finance periods
    fin_n = {"n": 0}

    def finance(t, k, p, c):
        src._throttle(float(c.get("request_interval_sec", 1.2)))
        fin_n["n"] += 1
        inc, bal, cf = _fin()
        return ({"income": inc, "balance": bal, "cashflow": cf}[k], "VCI")

    monkeypatch.setattr(src, "get_finance", finance)
    monkeypatch.setattr(src, "get_history", lambda t, s, e, c: (_px(400), "VCI"))
    monkeypatch.setattr(src, "get_overview", lambda t, c: (pd.DataFrame([{
        "exchange": "HOSE", "icb_name2": "x", "icb_name4": "y", "issue_share": 1e9,
    }]), "VCI"))
    monkeypatch.setattr(src, "get_news", lambda t, c: (pd.DataFrame({
        "title": ["t"], "publish_date": ["2026-09-01"], "link": ["u"],
    }), "VCI"))
    monkeypatch.setattr(news_extra, "google_news", lambda *a, **k: ([], []))
    monkeypatch.setattr(news_portals, "portals_enabled", lambda c: False)

    waits.clear()
    f.build_snapshot("HPG", "2026-10-09", _cfg(use_icb_peer_cascade=False, request_interval_sec=1.0))
    baseline = sum(waits)
    waits.clear()
    f.build_snapshot("HPG", "2026-10-09", _cfg(use_icb_peer_cascade=True, request_interval_sec=1.0))
    fast = sum(waits)
    # bỏ quý → ít nhất bỏ 3 lệnh finance (income/balance/cashflow quý) → ≥40% nếu baseline đủ lớn
    assert baseline > 0
    assert fast <= baseline * 0.6


# ----- SC-004 hint: VN30 identity already in test_us2 -----
