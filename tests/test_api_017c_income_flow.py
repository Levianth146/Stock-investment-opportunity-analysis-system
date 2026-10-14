"""Feature 017c — GET /api/tickers/{symbol}/income-flow."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from stockai.api.app import create_app
from stockai.api.income_flow import build_income_flow
from stockai.api.store import ResultStore

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "fixtures" / "snapshot_DEMO.json"
ASOF = "2026-10-08"


def _clone(ticker: str, *, is_bank: bool = False, loss: bool = False) -> dict:
    snap = json.loads(FIX.read_text(encoding="utf-8"))
    snap["meta"]["ticker"] = ticker
    snap["meta"]["as_of"] = ASOF
    snap["meta"]["synthetic"] = False
    flags = [f for f in (snap["meta"].get("flags") or []) if not str(f).startswith("quality_")]
    flags.append("quality_tier_full")
    snap["meta"]["flags"] = flags
    company = dict(snap.get("company") or {})
    company["name"] = f"Cong ty {ticker}"
    company["sector"] = "Banks" if is_bank else "Steel"
    company["exchange"] = "HSX"
    company["is_bank"] = is_bank
    company["shares_outstanding"] = 1_000_000_000
    snap["company"] = company

    if is_bank:
        # Ngân hàng: bỏ cấu trúc phi NH
        fin = snap.get("financials") if isinstance(snap.get("financials"), dict) else {}
        annual = []
        for p in fin.get("annual") or []:
            if not isinstance(p, dict):
                continue
            items = dict(p.get("items") or {})
            annual.append(
                {
                    **p,
                    "items": {
                        "net_interest_income": items.get("revenue"),
                        "net_income": items.get("net_income"),
                        "total_assets": items.get("total_assets"),
                        "total_equity": items.get("total_equity"),
                        "cfo": items.get("cfo"),
                        "capex": items.get("capex"),
                        "eps": items.get("eps"),
                    },
                }
            )
        fin["annual"] = annual
        fin["quarterly"] = []
        snap["financials"] = fin
        return snap

    # Bổ sung chỉ tiêu Sankey vào năm gần nhất
    fin = snap.get("financials") if isinstance(snap.get("financials"), dict) else {}
    annual = list(fin.get("annual") or [])
    if annual:
        last = dict(annual[-1])
        items = dict(last.get("items") or {})
        rev = float(items.get("revenue") or 150e9)
        if loss:
            items.update(
                {
                    "revenue": rev,
                    "gross_profit": rev * 0.2,
                    "selling_expense": rev * 0.15,
                    "admin_expense": rev * 0.12,
                    "interest_expense": rev * 0.03,
                    "pretax_profit": -rev * 0.05,
                    "net_income": -rev * 0.06,
                    "net_income_parent": -rev * 0.06,
                }
            )
        else:
            items.update(
                {
                    "revenue": rev,
                    "gross_profit": rev * 0.4,
                    "selling_expense": rev * 0.05,
                    "admin_expense": rev * 0.05,
                    "interest_expense": rev * 0.03,
                    "pretax_profit": rev * 0.24,
                    "net_income": rev * 0.2,
                    "net_income_parent": rev * 0.18,
                }
            )
        last["items"] = items
        annual[-1] = last
        fin["annual"] = annual
        snap["financials"] = fin
    return snap


@pytest.fixture(scope="module")
def api_env(tmp_path_factory):
    base = tmp_path_factory.mktemp("api017c")
    snap_dir = base / "snapshots"
    cache_dir = base / "api_cache"
    web_dist = base / "web_dist"
    snap_dir.mkdir()
    cache_dir.mkdir()
    web_dist.mkdir()
    (web_dist / "index.html").write_text(
        "<!doctype html><html><body>SPA</body></html>", encoding="utf-8"
    )

    (snap_dir / f"AAA_{ASOF}.json").write_text(
        json.dumps(_clone("AAA"), ensure_ascii=False), encoding="utf-8"
    )
    (snap_dir / f"LOSS_{ASOF}.json").write_text(
        json.dumps(_clone("LOSS", loss=True), ensure_ascii=False), encoding="utf-8"
    )
    (snap_dir / f"BNK_{ASOF}.json").write_text(
        json.dumps(_clone("BNK", is_bank=True), ensure_ascii=False), encoding="utf-8"
    )

    (base / "data").mkdir(exist_ok=True)
    (base / "data" / "valuation_sector_stats.json").write_text(
        json.dumps({"version": 2, "as_of": ASOF, "sectors": {}}),
        encoding="utf-8",
    )
    for name in ("scoring.yaml", "valuation.yaml"):
        src = ROOT / "config" / name
        dst = base / "config" / name
        dst.parent.mkdir(exist_ok=True)
        if src.is_file():
            dst.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")

    api_cfg = {
        "snapshots_dir": str(snap_dir),
        "asof": ASOF,
        "default_profile": "long_term",
        "cors_origins": [],
        "docs_enabled": True,
        "trust_proxy_headers": False,
        "debate_live_max_per_hour": 10,
        "debate_live_max_per_ip_per_hour": 3,
        "debate_live_max_per_day": 15,
        "cache_dir": str(cache_dir),
        "web_dist_dir": str(web_dist),
    }
    store = ResultStore(
        api_cfg, snapshots_dir=snap_dir, cache_dir=cache_dir, asof=ASOF, root=base
    )
    for t in ("AAA", "LOSS", "BNK"):
        store.get_bundle(t, "long_term", debate_mode="template")
    app = create_app(api_cfg=api_cfg, store=store)
    return {"client": TestClient(app), "store": store}


@pytest.fixture
def client(api_env):
    return api_env["client"]


def test_income_flow_endpoint_profit(client):
    r = client.get("/api/tickers/AAA/income-flow", params={"period": "2025"})
    assert r.status_code == 200
    body = r.json()
    assert body["supported"] is True
    assert body["unit"] == "billion_vnd"
    assert body["conservation_ok"] is True
    assert body["nodes"]
    assert body["links"]
    assert all(lk["value"] >= 0 for lk in body["links"])
    assert "available_periods" in body
    assert body["summary"] is not None
    assert "gross_margin" in body["summary"]


def test_income_flow_bank_unsupported(client):
    r = client.get("/api/tickers/BNK/income-flow", params={"period": "TTM"})
    assert r.status_code == 200
    body = r.json()
    assert body["supported"] is False
    assert "ngân hàng" in body["message"].lower() or "ngan hang" in body["message"].lower()
    assert body["nodes"] == []


def test_income_flow_loss_case(client):
    r = client.get("/api/tickers/LOSS/income-flow", params={"period": "2025"})
    assert r.status_code == 200
    body = r.json()
    assert body["supported"] is True
    assert body["loss"] is True
    ids = {n["id"] for n in body["nodes"]}
    assert "loss" in ids
    assert "npat" not in ids
    assert all(lk["value"] >= 0 for lk in body["links"])


def test_build_income_flow_conservation_unit():
    flow = build_income_flow(
        {
            "revenue": 1000.0,
            "gross_profit": 400.0,
            "selling_expense": 50.0,
            "admin_expense": 50.0,
            "interest_expense": 30.0,
            "pretax_profit": 240.0,
            "net_income": 200.0,
            "net_income_parent": 180.0,
        }
    )
    assert flow is not None
    assert flow["conservation_ok"] is True
    # Mỗi link ≥ 0; sum vào/ra trong 0,5%
    ins: dict[str, float] = {}
    outs: dict[str, float] = {}
    for lk in flow["links"]:
        outs[lk["source"]] = outs.get(lk["source"], 0.0) + lk["value"]
        ins[lk["target"]] = ins.get(lk["target"], 0.0) + lk["value"]
    for n in flow["nodes"]:
        val = float(n["value"])
        tol = max(abs(val) * 0.005, 1e-6)
        if n["kind"] in ("source", "other_income"):
            assert abs(outs.get(n["id"], 0.0) - val) <= tol
        elif n["kind"] in ("sink", "loss", "derived"):
            assert abs(ins.get(n["id"], 0.0) - val) <= tol
        else:
            assert abs(ins.get(n["id"], 0.0) - outs.get(n["id"], 0.0)) <= tol
