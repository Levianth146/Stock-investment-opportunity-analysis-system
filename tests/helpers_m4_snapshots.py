"""Snapshot builders offline cho test M4 (không mạng)."""
from __future__ import annotations

from copy import deepcopy
from typing import Any

_AS_OF = "2026-10-08"


def _base(
    ticker: str,
    *,
    sector: str = "Technology",
    is_bank: bool = False,
    shares: float | None = 100_000_000.0,
    as_of: str = _AS_OF,
    synthetic: bool = False,
) -> dict[str, Any]:
    meta: dict[str, Any] = {
        "schema_version": "1.0",
        "ticker": ticker,
        "as_of": as_of,
        "window_start": "2021-10-08",
        "fetched_at": f"{as_of}T10:00:00",
        "data_status": {
            "prices": "ok",
            "index": "ok",
            "financials": "ok",
            "company": "ok",
            "peers": "ok",
            "news": "ok",
        },
        "flags": ["quality_tier_full"],
    }
    if synthetic:
        meta["synthetic"] = True
    return {
        "meta": meta,
        "company": {
            "name": ticker,
            "exchange": "HOSE",
            "sector": sector,
            "industry": None,
            "is_bank": is_bank,
            "shares_outstanding": shares,
            "source_id": "src_co",
        },
        "prices": {
            "adjusted": True,
            "source_id": "src_px",
            "rows": [
                {
                    "date": "2026-10-08",
                    "open": 20_000.0,
                    "high": 21_000.0,
                    "low": 19_500.0,
                    "close": 20_000.0,
                    "volume": 1_000_000.0,
                }
            ],
        },
        "index": {"symbol": "VNINDEX", "source_id": "src_ix", "rows": []},
        "financials": {
            "unit": "VND",
            "annual": [
                {
                    "period": "2025",
                    "published_at": "2026-03-31",
                    "source_id": "src_fin",
                    "items": {
                        "eps": 2_000.0,
                        "net_income_parent": 200_000_000_000.0,
                        "net_income": 200_000_000_000.0,
                        "total_equity": 2_000_000_000_000.0,
                    },
                }
            ],
            # 4 quý liên tiếp; NI/shares = 500 → EPS TTM NI = 2000 (không cộng items.eps)
            "quarterly": [
                {
                    "period": f"2025Q{i}",
                    "published_at": f"2025-{3 * i:02d}-15" if i < 4 else "2026-01-15",
                    "source_id": "src_fin",
                    "items": {
                        "eps": 500.0,
                        "net_income_parent": 50_000_000_000.0,
                        "net_income": 50_000_000_000.0,
                        "total_equity": 2_000_000_000_000.0,
                    },
                }
                for i in (1, 2, 3, 4)
            ],
        },
        "peers": [],
        "news": [],
        "sources": [
            {"id": "src_co", "name": "co", "url": "http://x", "fetched_at": f"{as_of}T10:00:00"},
            {"id": "src_px", "name": "px", "url": "http://x", "fetched_at": f"{as_of}T10:00:00"},
            {"id": "src_fin", "name": "fin", "url": "http://x", "fetched_at": f"{as_of}T10:00:00"},
        ],
    }


def snap_cheap_tech(price: float = 10_000.0) -> dict:
    """Cùng ngành Technology, multiple thấp (rẻ) — EPS TTM=2000, book=20k."""
    s = _base("CHEAP", sector="Technology")
    s["prices"]["rows"][0]["close"] = price
    return s


def snap_expensive_tech(price: float = 40_000.0) -> dict:
    """Cùng ngành Technology, multiple cao (đắt)."""
    s = _base("EXP", sector="Technology")
    s["prices"]["rows"][0]["close"] = price
    return s


def snap_bank_pb_only() -> dict:
    """Bank: equity/shares đủ PB; EPS quý/năm <=0 → PE unavailable."""
    s = _base("BANK", sector="Banks", is_bank=True, shares=1_000_000_000.0)
    s["prices"]["rows"][0]["close"] = 30_000.0
    # book = 1.5e15 / 1e9 = 1_500_000 → PB = 30000/1500000 = 0.02 (rất rẻ vs median 1.5)
    s["financials"]["quarterly"] = [
        {
            "period": f"2025Q{i}",
            "published_at": f"2025-{3 * i:02d}-15" if i < 4 else "2026-01-15",
            "source_id": "src_fin",
            "items": {"eps": -100.0, "total_equity": 1_500_000_000_000_000.0},
        }
        for i in (1, 2, 3, 4)
    ]
    s["financials"]["annual"] = [
        {
            "period": "2025",
            "published_at": "2026-03-31",
            "source_id": "src_fin",
            "items": {"eps": -400.0, "total_equity": 1_500_000_000_000_000.0},
        }
    ]
    return s


def snap_missing_price() -> dict:
    s = _base("NOPX")
    s["prices"]["rows"] = []
    return s


def snap_missing_shares_equity() -> dict:
    s = _base("NOSH", shares=None)
    s["company"]["shares_outstanding"] = None
    for block in ("annual", "quarterly"):
        for p in s["financials"][block]:
            p["items"]["total_equity"] = None
    return s


def snap_eps_zero_quarterly_annual_ok() -> dict:
    """SSI-like: không có NI quý đủ TTM, annual >0 → fallback annual."""
    s = _base("SSI", sector="Technology")
    s["prices"]["rows"][0]["close"] = 25_000.0
    for p in s["financials"]["quarterly"]:
        p["items"]["eps"] = 0.0
        p["items"].pop("net_income_parent", None)
        p["items"].pop("net_income", None)
    s["financials"]["annual"][0]["items"]["eps"] = 1_500.0
    return s


def snap_hpg_like_eps_misleading() -> dict:
    """Hand fixture: eps quý [1781,0,1973,0] (mang năm) — TTM phải từ NI/shares."""
    shares = 8_442_964_520.0
    # NI 4Q → EPS ≈ 2750 (không phải sum eps = 3754)
    nis = [
        3_988_318_474_539.0,  # 2025Q3
        3_864_083_625_532.0,  # 2025Q4
        8_994_003_244_142.0,  # 2026Q1
        6_371_019_004_563.0,  # 2026Q2
    ]
    eps_misleading = [0.0, 1973.0, 0.0, 1781.0]
    periods = [
        ("2025Q3", "2025-11-14"),
        ("2025Q4", "2026-02-14"),
        ("2026Q1", "2026-05-15"),
        ("2026Q2", "2026-08-14"),
    ]
    s = _base("HPGX", sector="Basic Resources", shares=shares)
    s["prices"]["rows"][0]["close"] = 20_150.0
    s["financials"]["quarterly"] = []
    for (period, pub), ni, eps in zip(periods, nis, eps_misleading):
        s["financials"]["quarterly"].append(
            {
                "period": period,
                "published_at": pub,
                "source_id": "src_fin",
                "items": {
                    "eps": eps,
                    "net_income_parent": ni,
                    "net_income": ni * 1.01,
                    "total_equity": 141_516_026_790_697.0,
                },
            }
        )
    s["financials"]["annual"] = [
        {
            "period": "2025",
            "published_at": "2026-03-31",
            "source_id": "src_fin",
            "items": {"eps": 1973.0, "total_equity": 131_220_010_876_575.0},
        }
    ]
    return s


def snap_quarter_gap() -> dict:
    """Thiếu quý giữa → m4_eps_quarter_gap + fallback annual."""
    s = _base("GAP", sector="Technology")
    s["financials"]["quarterly"] = [
        {
            "period": "2025Q1",
            "published_at": "2025-05-15",
            "source_id": "src_fin",
            "items": {
                "eps": 100.0,
                "net_income_parent": 10_000_000_000.0,
                "total_equity": 2e12,
            },
        },
        {
            "period": "2025Q2",
            "published_at": "2025-08-15",
            "source_id": "src_fin",
            "items": {
                "eps": 100.0,
                "net_income_parent": 10_000_000_000.0,
                "total_equity": 2e12,
            },
        },
        # thiếu 2025Q3
        {
            "period": "2025Q4",
            "published_at": "2026-02-15",
            "source_id": "src_fin",
            "items": {
                "eps": 100.0,
                "net_income_parent": 10_000_000_000.0,
                "total_equity": 2e12,
            },
        },
        {
            "period": "2026Q1",
            "published_at": "2026-05-15",
            "source_id": "src_fin",
            "items": {
                "eps": 100.0,
                "net_income_parent": 10_000_000_000.0,
                "total_equity": 2e12,
            },
        },
    ]
    s["financials"]["annual"][0]["items"]["eps"] = 1_800.0
    return s


def snap_lookahead() -> dict:
    """Có rows date/published_at > as_of — không được vào PE/PB."""
    s = _base("LOOK")
    s["prices"]["rows"] = [
        {
            "date": "2026-10-01",
            "open": 10_000.0,
            "high": 10_000.0,
            "low": 10_000.0,
            "close": 10_000.0,
            "volume": 1.0,
        },
        {
            "date": "2026-10-20",
            "open": 99_000.0,
            "high": 99_000.0,
            "low": 99_000.0,
            "close": 99_000.0,
            "volume": 1.0,
        },
    ]
    s["financials"]["quarterly"].append(
        {
            "period": "2026Q4",
            "published_at": "2026-12-01",
            "source_id": "src_fin",
            "items": {"eps": 999_999.0, "total_equity": 9e18},
        }
    )
    return s


def snap_stale_price(days_before: int = 20) -> dict:
    """Giá cuối cách as_of > stale_calendar_days."""
    s = _base("STALE")
    # as_of 2026-10-08 → 20 ngày trước = 2026-09-18
    s["prices"]["rows"][0]["date"] = "2026-09-18"
    s["prices"]["rows"][0]["close"] = 15_000.0
    return s


def snap_synthetic() -> dict:
    return _base("SYN", synthetic=True)


def snap_missing_sector() -> dict:
    s = _base("NOSEC")
    s["company"]["sector"] = ""
    return s


def snap_tiny_sector() -> dict:
    """Sector với n < min_sector_n trong fixture mini."""
    s = _base("TINY", sector="TinySector")
    s["prices"]["rows"][0]["close"] = 20_000.0
    return s


def snap_unknown_sector() -> dict:
    """Sector không có trong sector stats (fallback thị trường)."""
    s = _base("UNK", sector="DoesNotExistInStats")
    return s


def snap_unknown_sector_weight() -> dict:
    """Sector không có trong weights.by_sector → m4_sector_weight_default."""
    s = _base("UNW", sector="Unknown Sector")
    return s


def clone(snap: dict) -> dict:
    return deepcopy(snap)
