"""TDD M4 relative valuation — offline fixtures."""
from __future__ import annotations

from pathlib import Path

import pytest

from stockai.contracts.schemas import validate
from stockai.m4_valuation.run import run as run_m4
from tests.helpers_m4_snapshots import (
    snap_bank_pb_only,
    snap_cheap_tech,
    snap_eps_zero_quarterly_annual_ok,
    snap_expensive_tech,
    snap_lookahead,
    snap_missing_price,
    snap_missing_shares_equity,
    snap_stale_price,
    snap_tiny_sector,
    snap_unknown_sector,
    snap_unknown_sector_weight,
)

_FIXTURE_STATS = Path(__file__).parent / "fixtures" / "m4_sector_stats_mini.json"


def _cfg(**extra) -> dict:
    m4 = {
        "sector_stats_path": str(_FIXTURE_STATS),
        "stale_calendar_days": 7,
        "min_sector_n": 5,
        "enable_dcf": False,
    }
    m4.update(extra)
    return {"m4": m4}


def _run(snap: dict, cfg: dict | None = None) -> dict:
    out = run_m4(snap, {}, cfg or _cfg())
    errs = validate(out, "module_out")
    assert errs == [], errs
    return out


# ---------- US1 ----------


def test_us1_polarity_cheap_score_gt_expensive():
    cheap = _run(snap_cheap_tech())
    expensive = _run(snap_expensive_tech())
    assert cheap["score"] is not None
    assert expensive["score"] is not None
    assert cheap["score"] > expensive["score"]


def test_us1_bank_pb_primary_numeric_v():
    out = _run(snap_bank_pb_only())
    assert out["score"] is not None
    assert 0 <= out["score"] <= 100
    assert "m4_bank_primary_pb" in out["flags"]
    # w_pe=0: m4_pe_unavailable không đủ để ép partial một mình
    assert "m4_pe_unavailable" in out["flags"]
    # (fixture bank có thể vẫn partial vì stale_financials — không assert ok ở đây)


def test_us1_sector_weight_default_unknown_sector_only():
    """m4_sector_weight_default chỉ khi sector không có trong by_sector."""
    out = _run(snap_unknown_sector_weight())
    assert "m4_sector_weight_default" in (out.get("flags") or [])
    # Ngành đã map tường minh trong yaml không nhận flag default
    for sector in (
        "Industrial Goods & Services",
        "Chemicals",
        "Media",
        "Travel & Leisure",
    ):
        snap = snap_cheap_tech()
        snap["company"]["sector"] = sector
        out_mapped = _run(snap)
        assert "m4_sector_weight_default" not in (out_mapped.get("flags") or []), sector


def test_us1_informational_flags_do_not_force_partial():
    """Chỉ minority flag → status ok khi vẫn chấm được."""
    snap = snap_cheap_tech()
    # Equity/NI mới đủ gần as_of để không stale; lệch NI parent → minority flag
    snap["financials"]["quarterly"] = [
        {
            "period": f"2026Q{i}",
            "published_at": f"2026-{3 + i:02d}-15",
            "source_id": "src_fin",
            "items": {
                "eps": 500.0,
                "net_income": 50_000_000_000.0,
                "net_income_parent": 40_000_000_000.0,  # lệch 20% > 5%
                "total_equity": 2_000_000_000_000.0,
            },
        }
        for i in (1, 2, 3, 4)
    ]
    snap["financials"]["annual"][0]["published_at"] = "2026-09-30"
    snap["financials"]["annual"][0]["items"]["net_income_parent"] = 160_000_000_000.0
    snap["financials"]["annual"][0]["items"]["net_income"] = 200_000_000_000.0
    out = _run(snap)
    assert "m4_pb_uses_total_equity" in (out.get("flags") or [])
    assert out["score"] is not None
    assert out["status"] == "ok", out.get("flags")


def test_us1_null_score_not_fifty_when_missing():
    out = _run(snap_missing_price())
    assert out["score"] is None
    assert out["score"] != 50
    assert any(
        f in out["flags"]
        for f in ("m4_insufficient_for_score", "m4_no_valid_price")
    )


def test_us1_null_when_no_valuation_legs():
    out = _run(snap_missing_shares_equity())
    # thiếu equity/shares → PB fail; vẫn có PE nếu đủ eps+price
    # ép thiếu luôn bằng cách xoá giá
    snap = snap_missing_shares_equity()
    snap["prices"]["rows"] = []
    out = _run(snap)
    assert out["score"] is None
    assert out["score"] != 50
    assert "m4_insufficient_for_score" in out["flags"] or "m4_no_valid_price" in out["flags"]


def test_us1_lookahead_rows_excluded():
    out = _run(snap_lookahead())
    assert out["score"] is not None
    # giá lookahead 99k bị loại → dùng 10k; PE = 10000/2000 = 5 vs median 15 → rẻ
    pe = (out.get("metrics") or {}).get("pe", {}).get("value")
    assert pe is not None
    assert pe < 50  # không dùng close 99000
    assert "m4_lookahead_rows_excluded" in out["flags"]


def test_us1_stale_price_flag_still_scores():
    out = _run(snap_stale_price())
    assert "m4_stale_price_data" in out["flags"]
    assert out["score"] is not None


def test_us1_eps_ttm_fallback_annual():
    out = _run(snap_eps_zero_quarterly_annual_ok())
    assert "m4_eps_ttm_fallback_annual" in out["flags"]
    eps = (out.get("metrics") or {}).get("eps_used", {}).get("value")
    assert eps == 1500.0
    pe = (out.get("metrics") or {}).get("pe", {}).get("value")
    assert pe is not None
    assert pe < 1e6  # không PE vô hạn


# ---------- US2 ----------


def test_us2_metrics_expose_sector_median_and_version():
    out = _run(snap_cheap_tech())
    m = out.get("metrics") or {}
    assert m.get("sector_median_pe", {}).get("value") == 15.0
    assert m.get("sector_median_pb", {}).get("value") == 3.0
    assert m.get("sector_stats_version", {}).get("value") == 2
    assert m.get("sector_n_pe", {}).get("value") == 8
    assert m.get("sector_n_pb", {}).get("value") == 8


def test_us2_missing_sector_uses_fallback_or_flags():
    out = _run(snap_unknown_sector())
    flags = out.get("flags") or []
    assert any(
        f in flags
        for f in (
            "m4_sector_stats_missing",
            "m4_sector_median_unavailable",
            "m4_sector_fallback",
            "m4_peer_group_small",
        )
    )
    # Có market fallback trong fixture → vẫn có thể chấm
    # Nếu không chấm được thì score null ≠ 50
    if out["score"] is None:
        assert out["score"] != 50


def test_us2_tiny_sector_fallback_market():
    out = _run(snap_tiny_sector())
    flags = out.get("flags") or []
    assert "m4_sector_fallback" in flags or "m4_peer_group_small" in flags
    assert out["score"] is not None or "m4_insufficient_for_score" in flags


def test_us2_relative_target_shape():
    out = _run(snap_cheap_tech())
    t = out.get("target")
    assert t is not None
    for k in ("base", "bull", "bear", "method", "assumptions"):
        assert k in t
    assert "relative" in str(t["method"]).lower() or "pe" in str(t["method"]).lower()
    assert "dcf" not in str(t["method"]).lower()
    assert isinstance(t["assumptions"], list)


def test_us2_enable_dcf_false_no_dcf_branch():
    out = _run(snap_cheap_tech(), _cfg(enable_dcf=False))
    t = out.get("target") or {}
    method = str(t.get("method") or "")
    assert "dcf" not in method.lower()
    metrics = out.get("metrics") or {}
    assert not any("dcf" in k.lower() for k in metrics)


def test_us2_evidence_vietnamese_no_required_news_id():
    out = _run(snap_cheap_tech())
    ev = out.get("evidence") or []
    assert len(ev) >= 1
    for e in ev:
        text = e.get("text") or ""
        assert any(ch.isalpha() for ch in text)
        # Có dấu tiếng Việt hoặc từ khóa VI phổ biến
        assert any(
            tok in text.lower()
            for tok in ("pe", "pb", "ngành", "định giá", "rẻ", "đắt", "so", "median", "p/b", "p/e")
        ) or any(ord(c) > 127 for c in text)
        # news_id không bắt buộc
        assert "news_id" not in e or e.get("news_id") is None or isinstance(e.get("news_id"), str)


def test_us2_missing_stats_file():
    out = _run(snap_cheap_tech(), _cfg(sector_stats_path="data/does_not_exist_m4_stats.json"))
    assert "m4_sector_stats_missing" in (out.get("flags") or [])
    assert out["score"] is None
    assert out["score"] != 50
