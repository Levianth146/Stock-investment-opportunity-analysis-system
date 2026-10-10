"""Offline tests: ICB cấp 2 → company.sector + peer cascade (không đụng contracts / M2–M9)."""
from __future__ import annotations

import copy
import json
from pathlib import Path

import yaml

from stockai.contracts.schemas import validate
from stockai.m1_data import icb_sector
from stockai.m1_data import universe as u

ROOT = Path(__file__).resolve().parents[1]
SNAP_DIR = ROOT / "data" / "snapshots"
AS_OF = "2026-10-08"
UNIVERSE = yaml.safe_load((ROOT / "config" / "universe.yaml").read_text(encoding="utf-8"))["tickers"]


def _vn30_snapshots() -> dict[str, dict]:
    out = {}
    for t in UNIVERSE:
        p = SNAP_DIR / f"{t}_{AS_OF}.json"
        assert p.exists(), f"missing snapshot {p}"
        out[t] = json.loads(p.read_text(encoding="utf-8"))
    return out


def _base_company(**kw) -> dict:
    c = {"name": "X", "exchange": "", "sector": "", "industry": None, "is_bank": False, "shares_outstanding": None}
    c.update(kw)
    return c


def test_listing_loads_and_maps_vn30_supersector():
    listing = icb_sector.load_listing()
    assert len(listing) > 1000
    for t in UNIVERSE:
        assert t in listing, f"{t} missing from listing_icb.csv"
        assert listing[t]["sector_en"], f"{t} L2 unmapped"
        assert listing[t]["exchange"] == "HSX"


def test_real_estate_parent_not_financials():
    listing = icb_sector.load_listing()
    for t in ("BCM", "VHM", "VIC", "VRE"):
        assert listing[t]["sector_en"] == "Real Estate"
        assert listing[t]["parent_en"] == "Real Estate"
        assert listing[t]["parent_en"] != "Financials"


def test_vn30_mapping_matches_existing_snapshots_100pct():
    """Xóa sector rồi điền từ ICB → khớp đúng sector đang có trên snapshot VN30."""
    listing = icb_sector.load_listing()
    snaps = _vn30_snapshots()
    for t, snap in snaps.items():
        expected = snap["company"]["sector"]
        assert expected, f"{t} snapshot sector empty"
        company = _base_company(name=t)
        flags: list[str] = []
        icb_sector.apply_to_company(company, t, listing=listing, flags=flags)
        assert company["sector"] == expected, f"{t}: got {company['sector']!r} want {expected!r}"
        assert "icb_sector_filled" in flags
        assert company["exchange"] == "HSX"


def test_keep_vnstock_sector_on_mismatch():
    listing = icb_sector.load_listing()
    company = _base_company(name="HPG", exchange="HSX", sector="Banks")
    flags: list[str] = []
    icb_sector.apply_to_company(company, "HPG", listing=listing, flags=flags)
    assert company["sector"] == "Banks"
    assert "icb_sector_mismatch" in flags
    assert listing["HPG"]["sector_en"] == "Basic Resources"


def test_ticker_not_in_csv_empty_sector_validates():
    listing = icb_sector.load_listing()
    assert "ZZZNOTREAL" not in listing
    company = _base_company(name="ZZZNOTREAL")
    flags: list[str] = []
    icb_sector.apply_to_company(company, "ZZZNOTREAL", listing=listing, flags=flags)
    assert company["sector"] == ""
    assert "icb_ticker_not_found" in flags
    snap = {
        "meta": {"ticker": "ZZZ", "as_of": AS_OF, "run_id": "t", "generated_at": "2026-10-08T00:00:00",
                 "code_version": "test", "data_status": {}, "flags": flags, "notes": ""},
        "prices": {"currency": "VND", "adjusted": True, "rows": [
            {"date": "2026-10-08", "open": 1, "high": 1, "low": 1, "close": 1, "volume": 1, "source_id": "s"}]},
        "index": {"name": "VNINDEX", "rows": [{"date": "2026-10-08", "close": 1, "source_id": "s"}]},
        "financials": {"unit": "VND", "scale": 1, "annual": [], "quarterly": []},
        "company": company,
        "peers": [],
        "news": [],
        "sources": [{"id": "s", "name": "t", "url": "http://x", "fetched_at": "2026-10-08T00:00:00"}],
    }
    validate(snap, "snapshot")


def test_keep_vnstock_when_ticker_missing_from_csv():
    listing = icb_sector.load_listing()
    company = _base_company(name="ZZZ", sector="Technology", exchange="HSX")
    flags: list[str] = []
    icb_sector.apply_to_company(company, "ZZZNOTREAL", listing=listing, flags=flags)
    assert company["sector"] == "Technology"
    assert "icb_ticker_not_found" in flags


def test_exchange_aliases():
    assert icb_sector.normalize_exchange("HOSE") == "HSX"
    assert icb_sector.normalize_exchange("UPCOM") == "UpCoM"
    assert icb_sector.normalize_exchange("HNX") == "HNX"


def test_cascade_parent_when_large_enough():
    listing = icb_sector.load_listing()
    # 2 Insurance → parent Financials với ≥10 mã tài chính
    views = {
        "BVH": {"sector": "Insurance", "parent": "Financials", "met": {"market_cap": 1e12}, "is_bank": False},
        "BIC": {"sector": "Insurance", "parent": "Financials", "met": {"market_cap": 2e11}, "is_bank": False},
    }
    for i in range(10):
        views[f"B{i:02d}"] = {
            "sector": "Banks", "parent": "Financials", "met": {"market_cap": 1e13 + i}, "is_bank": True,
        }
    group, small, blocked = icb_sector.resolve_peer_group(
        "BVH", views, listing=listing, min_size=10, apply_finance_filter=True,
    )
    assert small is True
    assert blocked is False
    assert "BIC" in group
    assert any(x.startswith("B") for x in group)


def test_cascade_real_estate_skips_parent_to_market_finance_filter():
    listing = icb_sector.load_listing()
    views = {
        "VHM": {"sector": "Real Estate", "parent": "Real Estate", "met": {"market_cap": 1e13}, "is_bank": False},
        "VIC": {"sector": "Real Estate", "parent": "Real Estate", "met": {"market_cap": 9e12}, "is_bank": False},
        "VCB": {"sector": "Banks", "parent": "Financials", "met": {"market_cap": 5e13}, "is_bank": True},
        "HPG": {"sector": "Basic Resources", "parent": "Basic Materials", "met": {"market_cap": 2e13}, "is_bank": False},
    }
    group, small, blocked = icb_sector.resolve_peer_group(
        "VHM", views, listing=listing, min_size=10, apply_finance_filter=True,
    )
    assert small is True
    assert "VIC" in group
    assert "VCB" not in group
    assert "HPG" in group
    assert blocked is False


def test_banks_never_peer_with_real_estate():
    listing = icb_sector.load_listing()
    views = {
        "VCB": {"sector": "Banks", "parent": "Financials", "met": {"market_cap": 5e13}, "is_bank": True},
        "TCB": {"sector": "Banks", "parent": "Financials", "met": {"market_cap": 4e13}, "is_bank": True},
        "BCM": {"sector": "Real Estate", "parent": "Real Estate", "met": {"market_cap": 1e12}, "is_bank": False},
        "VHM": {"sector": "Real Estate", "parent": "Real Estate", "met": {"market_cap": 2e12}, "is_bank": False},
        "VIC": {"sector": "Real Estate", "parent": "Real Estate", "met": {"market_cap": 3e12}, "is_bank": False},
        "VRE": {"sector": "Real Estate", "parent": "Real Estate", "met": {"market_cap": 4e12}, "is_bank": False},
    }
    # L2 Banks size 2 < 10 → market + finance filter
    g_bank, _, blocked_b = icb_sector.resolve_peer_group(
        "VCB", views, listing=listing, min_size=10, apply_finance_filter=True,
    )
    assert "TCB" in g_bank
    for re_t in ("BCM", "VHM", "VIC", "VRE"):
        assert re_t not in g_bank
    g_re, _, blocked_r = icb_sector.resolve_peer_group(
        "VHM", views, listing=listing, min_size=10, apply_finance_filter=True,
    )
    assert "VCB" not in g_re and "TCB" not in g_re


def test_finance_blocked_when_only_other_side():
    listing = icb_sector.load_listing()
    views = {
        "VCB": {"sector": "Banks", "parent": "Financials", "met": {"market_cap": 5e13}, "is_bank": True},
        "VHM": {"sector": "Real Estate", "parent": "Real Estate", "met": {"market_cap": 2e12}, "is_bank": False},
        "HPG": {"sector": "Basic Resources", "parent": "Basic Materials", "met": {"market_cap": 2e13}, "is_bank": False},
    }
    group, small, blocked = icb_sector.resolve_peer_group(
        "VCB", views, listing=listing, min_size=10, apply_finance_filter=True,
    )
    assert group == []
    assert small is True
    assert blocked is True


def test_empty_sector_excluded_as_peer_and_is_bank_financial():
    listing = icb_sector.load_listing()
    views = {
        "AAA": {"sector": "", "parent": None, "met": {"market_cap": 1e12}, "is_bank": True},
        "VCB": {"sector": "Banks", "parent": "Financials", "met": {"market_cap": 5e13}, "is_bank": True},
        "HPG": {"sector": "Basic Resources", "parent": "Basic Materials", "met": {"market_cap": 2e13}, "is_bank": False},
        "ZZZ": {"sector": "", "parent": None, "met": {"market_cap": 9e11}, "is_bank": False},
    }
    g_vcb, _, _ = icb_sector.resolve_peer_group(
        "VCB", views, listing=listing, min_size=10, apply_finance_filter=True,
    )
    assert "AAA" not in g_vcb and "ZZZ" not in g_vcb
    g_aaa, small, _ = icb_sector.resolve_peer_group(
        "AAA", views, listing=listing, min_size=10, apply_finance_filter=True,
    )
    assert small is True
    assert "VCB" in g_aaa
    assert "HPG" not in g_aaa
    assert "ZZZ" not in g_aaa


def _snap(t: str, sector: str, is_bank: bool, market_cap: float) -> dict:
    return {
        "meta": {"ticker": t, "as_of": AS_OF, "run_id": "t", "generated_at": "2026-10-08T00:00:00",
                 "code_version": "t", "data_status": {"peers": "missing"}, "flags": [], "notes": ""},
        "prices": {"currency": "VND", "adjusted": True, "rows": [
            {"date": "2026-10-08", "open": 1, "high": 1, "low": 1, "close": 10000, "volume": 1, "source_id": "s"}]},
        "index": {"name": "VNINDEX", "rows": [{"date": "2026-10-08", "close": 1, "source_id": "s"}]},
        "financials": {"unit": "VND", "scale": 1, "annual": [{
            "year": 2025, "published_at": "2026-01-01", "period_end": "2025-12-31",
            "items": {"net_income_parent": 1e12, "equity": market_cap / 2, "shares_outstanding": market_cap / 10000},
            "source_id": "s",
        }], "quarterly": []},
        "company": {"name": t, "exchange": "HSX", "sector": sector, "industry": None,
                    "is_bank": is_bank, "shares_outstanding": market_cap / 10000},
        "peers": [],
        "news": [],
        "sources": [{"id": "s", "name": "t", "url": "http://x", "fetched_at": "2026-10-08T00:00:00"}],
    }


def test_peer_order_via_closest_helper_deterministic():
    import math
    views = {
        "T0": {"sector": "Banks", "met": {"market_cap": 1e13}, "is_bank": True},
        "T1": {"sector": "Banks", "met": {"market_cap": 1.1e13}, "is_bank": True},
        "T2": {"sector": "Banks", "met": {"market_cap": 2e13}, "is_bank": True},
        "T3": {"sector": "Banks", "met": {"market_cap": 9e12}, "is_bank": True},
    }
    group = ["T1", "T2", "T3"]
    a = u._closest(group, "T0", views, 3, rank_by_market_cap=True)
    b = u._closest(group, "T0", views, 3, rank_by_market_cap=True)
    assert a == b
    expected = sorted(group, key=lambda x: (abs(math.log(views[x]["met"]["market_cap"] / 1e13)), x))
    assert a == expected


def test_vn30_peer_lists_preserved_with_cascade_off():
    """use_icb_peer_cascade=False → peers khớp đúng từng phần tử và thứ tự snapshot VN30."""
    snaps = _vn30_snapshots()
    baseline = {t: [p["ticker"] for p in s.get("peers") or []] for t, s in snaps.items()}
    work = {t: copy.deepcopy(s) for t, s in snaps.items()}
    u.fill_peers(work, cfg={"use_icb_peer_cascade": False, "icb_sector_enabled": True})
    for t in UNIVERSE:
        got = [p["ticker"] for p in work[t].get("peers") or []]
        assert got == baseline[t], f"{t}: got {got} want {baseline[t]}"


def test_cascade_default_false_does_not_mix_re_into_banks_legacy():
    """Mặc định cascade tắt — không dùng resolve finance path."""
    snaps = {
        "VCB": _snap("VCB", "Banks", True, 5e13),
        "VHM": _snap("VHM", "Real Estate", False, 2e12),
    }
    # _metrics có thể None nếu thiếu dữ liệu — gắn met bằng cách patch views qua fill với multiples
    # Đảm bảo met có mặt: shares và net income đã set trong _snap
    u.fill_peers(snaps, cfg={"use_icb_peer_cascade": False, "icb_sector_enabled": False})
    # Cùng sector Banks chỉ 1 mã → fallback nonbank có thể kéo VHM; với is_bank VCB không fallback
    assert all(p["ticker"] != "VHM" for p in snaps["VCB"]["peers"]) or "peers_cross_sector_vn30_nonbank_fallback" not in snaps["VCB"]["meta"]["flags"]
