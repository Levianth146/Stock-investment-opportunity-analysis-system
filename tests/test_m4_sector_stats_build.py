"""Ops/unit: build_m4_sector_stats trên temp snapshots nhỏ."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

from stockai.m4_valuation.config_loader import _DEFAULT_M4
from stockai.m4_valuation.sector_stats import MARKET_KEY, winsorize, median_after_winsor
from tests.helpers_m4_snapshots import snap_cheap_tech, snap_expensive_tech, snap_bank_pb_only

_ROOT = Path(__file__).resolve().parents[1]


def _load_build_mod():
    path = _ROOT / "scripts" / "build_m4_sector_stats.py"
    spec = importlib.util.spec_from_file_location("build_m4_sector_stats", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_winsorize_then_median_helper():
    vals = [1.0, 2.0, 3.0, 4.0, 100.0]
    w = winsorize(vals, 0.05, 0.95)
    assert max(w) < 100.0 or len(w) == 5
    med = median_after_winsor(vals, 0.0, 1.0)
    assert med == 3.0


def test_build_script_mini_temp(tmp_path: Path):
    snaps_dir = tmp_path / "snaps"
    snaps_dir.mkdir()
    as_of = "2026-10-08"
    for snap in (snap_cheap_tech(), snap_expensive_tech(), snap_bank_pb_only()):
        t = snap["meta"]["ticker"]
        (snaps_dir / f"{t}_{as_of}.json").write_text(
            json.dumps(snap, ensure_ascii=False), encoding="utf-8"
        )
    out = tmp_path / "stats.json"
    cfg = dict(_DEFAULT_M4)
    cfg["min_sector_n"] = 1  # temp universe nhỏ
    mod = _load_build_mod()
    payload = mod.build(as_of=as_of, snapshots_dir=snaps_dir, out_path=out, cfg=cfg)
    assert out.is_file()
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["as_of"] == as_of
    assert "winsor" in data
    sectors = data["sectors"]
    assert "Technology" in sectors
    assert "Banks" in sectors
    assert MARKET_KEY in sectors
    tech = sectors["Technology"]
    assert tech["n_pe"] >= 1
    assert tech["median_pe"] is not None
    assert payload["n_universe"] == 3
