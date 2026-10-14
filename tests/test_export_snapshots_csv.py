"""Offline tests for scripts/export_snapshots_csv.py — viết trước, fail trước khi implement."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _load_export():
    sys.path.insert(0, str(ROOT / "scripts"))
    import export_snapshots_csv as mod  # noqa: E402
    return mod


def _snap(
    ticker: str,
    as_of: str = "2026-10-08",
    *,
    flags: list | None = None,
    prices: list | None = None,
    annual: list | None = None,
    quarterly: list | None = None,
    index_rows: list | None = None,
) -> dict:
    return {
        "meta": {
            "schema_version": "1.0",
            "ticker": ticker,
            "as_of": as_of,
            "flags": flags or [],
            "data_status": {},
            "synthetic": False,
        },
        "company": {
            "name": f"Co {ticker}",
            "exchange": "HOSE",
            "sector": "Steel",
            "industry": None,
            "is_bank": False,
            "shares_outstanding": 1e9,
        },
        "prices": {"adjusted": True, "source_id": "src_prices", "rows": prices if prices is not None else []},
        "index": {
            "symbol": "VNINDEX",
            "source_id": "src_index",
            "rows": index_rows if index_rows is not None else [
                {"date": "2026-10-07", "close": 1200.0},
                {"date": "2026-10-08", "close": 1210.0},
            ],
        },
        "financials": {
            "unit": "VND",
            "annual": annual if annual is not None else [],
            "quarterly": quarterly if quarterly is not None else [],
            "column_map": {"annual": {}, "quarterly": {}},
        },
        "peers": [],
        "news": [],
        "sources": [],
    }


def _write_snap(d: Path, snap: dict) -> None:
    t = snap["meta"]["ticker"]
    a = snap["meta"]["as_of"]
    (d / f"{t}_{a}.json").write_text(json.dumps(snap, ensure_ascii=False), encoding="utf-8")


def test_full_ticker_all_files(tmp_path):
    mod = _load_export()
    ind, out = tmp_path / "in", tmp_path / "out"
    ind.mkdir()
    prices = [
        {"date": "2026-10-07", "open": 1.0, "high": 2.0, "low": 0.5, "close": 1.5, "volume": 100},
        {"date": "2026-10-08", "open": 1.5, "high": 2.5, "low": 1.0, "close": 2.0, "volume": 200},
    ]
    annual = [{
        "period": "2024",
        "published_at": "2025-03-31",
        "published_at_estimated": True,
        "source_id": "src_fin_year",
        "items": {"revenue": 1e12, "net_income": 1e11},
    }]
    quarterly = [{
        "period": "2026Q1",
        "published_at": "2026-05-15",
        "published_at_estimated": True,
        "source_id": "src_fin_quarter",
        "items": {"revenue": 2e11},
    }]
    _write_snap(ind, _snap(
        "HPG", flags=["quality_tier_full", "prices_scaled_x1000_to_VND"],
        prices=prices, annual=annual, quarterly=quarterly,
    ))
    mod.export_all(ind, out, "2026-10-08")
    uni = (out / "universe_summary.csv").read_text(encoding="utf-8")
    assert "HPG" in uni and "quality_tier" in uni.splitlines()[0]
    assert "full" in uni
    assert "false" in uni.lower() or "False" not in uni  # fetch_skipped_early=false
    assert len((out / "prices.csv").read_text(encoding="utf-8").strip().splitlines()) == 3  # header+2
    assert len((out / "index.csv").read_text(encoding="utf-8").strip().splitlines()) == 3
    assert "revenue" in (out / "financials_annual.csv").read_text(encoding="utf-8")
    assert "2026Q1" in (out / "financials_quarterly.csv").read_text(encoding="utf-8")
    assert (out / "README_export.txt").exists()


def test_early_exit_stub(tmp_path):
    mod = _load_export()
    ind, out = tmp_path / "in", tmp_path / "out"
    ind.mkdir()
    prices = [{"date": "2026-10-08", "open": 1, "high": 1, "low": 1, "close": 1, "volume": 0}]
    _write_snap(ind, _snap(
        "STUB",
        flags=["fetch_skipped_early", "quality_tier_insufficient", "quality_illiquid"],
        prices=prices, annual=[], quarterly=[],
    ))
    mod.export_all(ind, out, "2026-10-08")
    uni_lines = (out / "universe_summary.csv").read_text(encoding="utf-8").strip().splitlines()
    assert len(uni_lines) == 2
    row = uni_lines[1]
    assert "STUB" in row and "insufficient" in row and "true" in row
    assert len((out / "prices.csv").read_text(encoding="utf-8").strip().splitlines()) == 2
    assert len((out / "financials_annual.csv").read_text(encoding="utf-8").strip().splitlines()) == 1  # header only
    assert len((out / "financials_quarterly.csv").read_text(encoding="utf-8").strip().splitlines()) == 1


def test_empty_prices_no_crash(tmp_path):
    import csv as _csv

    mod = _load_export()
    ind, out = tmp_path / "in", tmp_path / "out"
    ind.mkdir()
    _write_snap(ind, _snap("ATP", prices=[], annual=[], quarterly=[], index_rows=[]))
    mod.export_all(ind, out, "2026-10-08")
    with (out / "universe_summary.csv").open(encoding="utf-8", newline="") as fh:
        rows = list(_csv.DictReader(fh))
    assert len(rows) == 1 and rows[0]["ticker"] == "ATP"
    assert rows[0]["n_price_rows"] == "0"
    assert rows[0]["last_price_date"] == ""


def test_union_financial_keys(tmp_path):
    mod = _load_export()
    ind, out = tmp_path / "in", tmp_path / "out"
    ind.mkdir()
    _write_snap(ind, _snap("AAA", annual=[{
        "period": "2024", "published_at": "2025-03-31", "published_at_estimated": True,
        "source_id": "s", "items": {"revenue": 1, "eps": 2},
    }]))
    _write_snap(ind, _snap("BBB", annual=[{
        "period": "2024", "published_at": "2025-03-31", "published_at_estimated": True,
        "source_id": "s", "items": {"revenue": 3, "total_assets": 4},
    }]))
    mod.export_all(ind, out, "2026-10-08")
    header = (out / "financials_annual.csv").read_text(encoding="utf-8").splitlines()[0]
    assert "eps" in header and "total_assets" in header and "revenue" in header
    # BBB row: eps empty
    rows = (out / "financials_annual.csv").read_text(encoding="utf-8").splitlines()[1:]
    by_t = {r.split(",")[0]: r for r in rows}
    # empty cell between commas for missing key — not "0" or "nan"
    assert "nan" not in by_t["BBB"].lower()


def test_published_at_columns(tmp_path):
    mod = _load_export()
    ind, out = tmp_path / "in", tmp_path / "out"
    ind.mkdir()
    _write_snap(ind, _snap("HPG", annual=[{
        "period": "2024", "published_at": "2025-03-31", "published_at_estimated": True,
        "source_id": "s", "items": {"revenue": 1},
    }], quarterly=[{
        "period": "2026Q1", "published_at": "2026-05-15", "published_at_estimated": False,
        "source_id": "s", "items": {"revenue": 2},
    }]))
    mod.export_all(ind, out, "2026-10-08")
    for name in ("financials_annual.csv", "financials_quarterly.csv"):
        h = (out / name).read_text(encoding="utf-8").splitlines()[0]
        assert "published_at" in h and "published_at_estimated" in h


def test_deterministic_bytes(tmp_path):
    mod = _load_export()
    ind, out1, out2 = tmp_path / "in", tmp_path / "o1", tmp_path / "o2"
    ind.mkdir()
    _write_snap(ind, _snap("HPG", prices=[
        {"date": "2026-10-08", "open": 1, "high": 1, "low": 1, "close": 1, "volume": 1},
    ], annual=[{
        "period": "2024", "published_at": "2025-03-31", "published_at_estimated": True,
        "source_id": "s", "items": {"z_key": 1, "a_key": 2},
    }]))
    mod.export_all(ind, out1, "2026-10-08")
    mod.export_all(ind, out2, "2026-10-08")
    for name in (
        "universe_summary.csv", "prices.csv", "index.csv",
        "financials_annual.csv", "financials_quarterly.csv",
    ):
        assert (out1 / name).read_bytes() == (out2 / name).read_bytes()


def test_skip_underscore_and_wrong_asof(tmp_path):
    mod = _load_export()
    ind, out = tmp_path / "in", tmp_path / "out"
    ind.mkdir()
    _write_snap(ind, _snap("HPG", as_of="2026-10-08"))
    (ind / "_summary_vn100_2026-10-08.json").write_text("{}", encoding="utf-8")
    (ind / "HPG_2020-01-01.json").write_text(json.dumps(_snap("HPG", as_of="2020-01-01")), encoding="utf-8")
    sub = ind / "subdir"
    sub.mkdir()
    (sub / "XXX_2026-10-08.json").write_text(json.dumps(_snap("XXX")), encoding="utf-8")
    mod.export_all(ind, out, "2026-10-08")
    uni = (out / "universe_summary.csv").read_text(encoding="utf-8")
    assert "HPG" in uni
    assert "XXX" not in uni
    assert uni.count("\n") == 2  # header + 1


def test_index_once_warn_on_mismatch(tmp_path, capsys):
    mod = _load_export()
    ind, out = tmp_path / "in", tmp_path / "out"
    ind.mkdir()
    _write_snap(ind, _snap("AAA", index_rows=[{"date": "2026-10-08", "close": 100}]))
    _write_snap(ind, _snap("BBB", index_rows=[{"date": "2026-10-08", "close": 999}]))
    mod.export_all(ind, out, "2026-10-08")
    idx = (out / "index.csv").read_text(encoding="utf-8").strip().splitlines()
    assert len(idx) == 2  # header + 1 row from first snapshot only
    captured = capsys.readouterr()
    assert "cảnh báo" in captured.out.lower() or "warn" in captured.out.lower() or "khác" in captured.out.lower()


def test_no_tmp_left(tmp_path):
    mod = _load_export()
    ind, out = tmp_path / "in", tmp_path / "out"
    ind.mkdir()
    _write_snap(ind, _snap("HPG"))
    mod.export_all(ind, out, "2026-10-08")
    tmps = list(out.glob("*.tmp")) + list(out.glob("*.csv.tmp"))
    assert tmps == []
