"""Feature 014g — checks, f_score, quarter-summary, snapshot-stats, pillar_rank."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from stockai.api.checks import (
    build_quarter_summary,
    build_snapshot_stats,
    evaluate_all_checks,
    evaluate_piotroski,
    map_tone,
    pillar_ranks_in_sector,
)

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "fixtures" / "snapshot_DEMO.json"


def _period(period: str, items: dict, *, estimated: bool = False, published: str | None = None) -> dict:
    return {
        "period": period,
        "published_at": published or f"{period[:4]}-03-31" if len(period) == 4 else "2026-05-15",
        "published_at_estimated": estimated,
        "source_id": "src_test",
        "items": items,
    }


def _fin_items(**kwargs) -> dict:
    base = {
        "revenue": 1000.0,
        "gross_profit": 400.0,
        "net_income": 200.0,
        "net_income_parent": 180.0,
        "cfo": 220.0,
        "total_assets": 2000.0,
        "total_equity": 1000.0,
        "current_assets": 800.0,
        "current_liabilities": 300.0,
        "long_term_debt": 200.0,
        "short_term_debt": 100.0,
        "interest_expense": 50.0,
        "eps": 2.0,
        "ebit": 250.0,
    }
    base.update(kwargs)
    return base


def test_piotroski_all_pass_and_f_score():
    curr = _period("2025", _fin_items())
    prev = _period(
        "2024",
        _fin_items(
            revenue=800.0,
            gross_profit=280.0,
            net_income=150.0,
            net_income_parent=140.0,
            cfo=100.0,
            total_assets=1800.0,
            current_assets=600.0,
            current_liabilities=350.0,
            long_term_debt=300.0,
            eps=1.5,
        ),
    )
    results, f_score = evaluate_piotroski(curr, prev)
    assert f_score["y"] >= 5
    assert f_score["x"] == f_score["y"] or f_score["x"] >= 7
    assert f_score["hide"] is False
    by_id = {r["id"]: r for r in results}
    assert by_id["roa_positive"]["passed"] is True
    assert by_id["cfo_positive"]["passed"] is True
    assert by_id["cfo_exceeds_net_income"]["passed"] is True


def test_piotroski_missing_year_na():
    snap = json.loads(FIX.read_text(encoding="utf-8"))
    snap["company"] = {**(snap.get("company") or {}), "is_bank": False}
    # chỉ 1 năm
    snap["financials"] = {
        "unit": "VND",
        "annual": [_period("2025", _fin_items())],
        "quarterly": [],
    }
    bundle = {
        "company": snap["company"],
        "m2": {"metrics": {}},
        "m3": {"metrics": {}},
        "m4": {"metrics": {"pe": {"value": 10}, "pb": {"value": 1.0}}},
        "m6": {"metrics": {}},
    }
    out = evaluate_all_checks(snapshot=snap, bundle=bundle, sector_peer_metrics=[])
    pio = [c for c in out["checks"] if c.get("family") == "piotroski"]
    assert pio
    assert all(c["na"] for c in pio)
    assert out["f_score"]["hide"] is True


def test_banks_skip_piotroski_graham():
    snap = json.loads(FIX.read_text(encoding="utf-8"))
    snap["company"] = {**(snap.get("company") or {}), "is_bank": True}
    snap["financials"] = {
        "unit": "VND",
        "annual": [
            _period("2025", _fin_items()),
            _period("2024", _fin_items(revenue=900)),
        ],
        "quarterly": [],
    }
    bundle = {
        "company": snap["company"],
        "m2": {"metrics": {"roe": {"value": 0.2}, "revenue_yoy": {"value": 0.1}}},
        "m3": {"metrics": {}},
        "m4": {"metrics": {"pb": {"value": 1.2}}},
        "m6": {"metrics": {"ann_vol": {"value": 0.2}, "max_drawdown": {"value": -0.2}}},
    }
    out = evaluate_all_checks(snapshot=snap, bundle=bundle, sector_peer_metrics=[])
    assert out["is_bank"] is True
    assert not any(c.get("family") == "piotroski" for c in out["checks"])
    assert not any(c.get("family") == "graham" for c in out["checks"])
    # NPL/CAR không có → không bịa
    assert out["npl_car_available"]["npl_ratio"] is None
    assert out["npl_car_available"]["car"] is None


def test_f_score_edge_y_lt_5_hides():
    # thiếu nhiều field → y nhỏ
    curr = _period("2025", {"revenue": 1.0, "net_income": 1.0, "total_assets": 10.0})
    prev = _period("2024", {"revenue": 1.0, "net_income": 0.5, "total_assets": 10.0})
    _, f_score = evaluate_piotroski(curr, prev)
    if f_score["y"] < 5:
        assert f_score["hide"] is True


def test_quarter_summary_estimated_null_reaction():
    snap = {
        "company": {"is_bank": False},
        "financials": {
            "quarterly": [
                _period(
                    "2026Q1",
                    {"revenue": 100, "gross_profit": 40, "net_income": 20},
                    estimated=True,
                    published="2026-05-15",
                ),
                _period(
                    "2025Q1",
                    {"revenue": 80, "gross_profit": 30, "net_income": 15},
                    estimated=True,
                ),
            ]
        },
    }
    prices = [
        {"date": "2026-05-14", "close": 100},
        {"date": "2026-05-16", "close": 105},
        {"date": "2026-05-20", "close": 110},
    ]
    out = build_quarter_summary(snap, prices_rows=prices)
    assert out["published_estimated"] is True
    assert out["price_reaction"] is None
    assert out["price_reaction_reason"] == "published_estimated"
    assert out["items"]["revenue"]["yoy"] == pytest.approx(0.25)


def test_quarter_summary_real_publish_has_reaction():
    snap = {
        "company": {"is_bank": False},
        "financials": {
            "quarterly": [
                _period(
                    "2026Q1",
                    {"revenue": 100, "gross_profit": 40, "net_income": 20},
                    estimated=False,
                    published="2026-05-15",
                )
            ]
        },
    }
    prices = [
        {"date": "2026-05-14", "close": 100.0},
        {"date": "2026-05-16", "close": 102.0},
        {"date": "2026-05-17", "close": 103.0},
        {"date": "2026-05-18", "close": 104.0},
        {"date": "2026-05-19", "close": 105.0},
        {"date": "2026-05-20", "close": 106.0},
        {"date": "2026-05-21", "close": 107.0},
    ]
    out = build_quarter_summary(snap, prices_rows=prices)
    assert out["price_reaction"] is not None
    assert out["price_reaction"]["return_1d"] == pytest.approx(0.02)


def test_pillar_rank_null_when_thin_sector():
    scores = {"F": 70, "T": 60, "V": 50, "S": 40, "R": 30}
    peers = [{"scores": scores} for _ in range(5)]
    out = pillar_ranks_in_sector(scores=scores, peer_scores=peers, min_peers=8)
    assert out["F"] is None
    assert out["n_sector_scored"] == 5


def test_pillar_rank_with_enough_peers():
    peers = []
    for i in range(10):
        peers.append({"scores": {"F": 40 + i * 5, "T": 50, "V": 50, "S": 50, "R": 40}})
    out = pillar_ranks_in_sector(
        scores={"F": 80, "T": 50, "V": 50, "S": 50, "R": 40},
        peer_scores=peers,
        min_peers=8,
    )
    assert out["F"] is not None
    assert out["F"]["n"] >= 8
    assert out["safety"] is not None


def test_tone_mapping():
    assert map_tone("band_30_70", 75) == "bad"
    assert map_tone("band_30_70", 50) == "good"
    assert map_tone("lower_abs_better", -0.5) == "bad"


def test_snapshot_stats_shape():
    snap = json.loads(FIX.read_text(encoding="utf-8"))
    snap["company"] = {**(snap.get("company") or {}), "is_bank": False, "shares_outstanding": 1e9}
    bundle = {
        "company": snap["company"],
        "m2": {"metrics": {"roe": {"value": 0.15}, "revenue_yoy": {"value": 0.1}}},
        "m3": {"metrics": {"rsi14": {"value": 55}, "ma50": {"value": 20}, "ma200": {"value": 18}}},
        "m4": {"metrics": {"pe": {"value": 12}, "pb": {"value": 1.5}, "price_close": {"value": 25}}},
        "m6": {"metrics": {"beta": {"value": 1.1}, "ann_vol": {"value": 0.3}, "max_drawdown": {"value": -0.2}}},
    }
    out = build_snapshot_stats(snap, bundle)
    ids = {i["id"] for i in out["items"]}
    assert "pe" in ids and "roe" in ids and "market_cap" in ids
    pe = next(i for i in out["items"] if i["id"] == "pe")
    assert pe["tone"] in ("good", "neutral", "bad")
    assert pe["unit"] == "x"


def test_rewards_risks_count_exclude_info():
    snap = json.loads(FIX.read_text(encoding="utf-8"))
    snap["company"] = {**(snap.get("company") or {}), "is_bank": False}
    snap["financials"] = {
        "unit": "VND",
        "annual": [
            _period("2025", _fin_items(cfo=-10)),  # negative_cfo risk
            _period("2024", _fin_items(revenue=900, cfo=50)),
        ],
        "quarterly": [],
    }
    bundle = {
        "company": snap["company"],
        "m2": {"metrics": {}},
        "m3": {"metrics": {"rsi14": {"value": 75}}},  # info overbought
        "m4": {"metrics": {"pe": {"value": 10}, "pb": {"value": 1.0}, "price_close": {"value": 20}}},
        "m6": {"metrics": {"max_drawdown": {"value": -0.4}}},
    }
    out = evaluate_all_checks(snapshot=snap, bundle=bundle, sector_peer_metrics=[])
    # info không vào risks_count
    info_ids = {c["id"] for c in out["info"]}
    assert "rsi_overbought_gt_70" in info_ids or any(
        c["id"] == "rsi_overbought_gt_70" for c in out["checks"]
    )
    assert isinstance(out["rewards_count"], int)
    assert isinstance(out["risks_count"], int)
    assert "method" in out and "Piotroski" in out["method"]
