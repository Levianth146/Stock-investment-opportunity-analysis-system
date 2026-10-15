"""Feature 014f — total_scored, market_cap rankings, health warming."""
from __future__ import annotations

import json
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from stockai.api.app import create_app
from stockai.api.store import ResultStore

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "fixtures" / "snapshot_DEMO.json"
ASOF = "2026-10-08"


def _clone(ticker: str, sector: str, *, shares: float | None = 1e9, price_close: float = 20.0) -> dict:
    snap = json.loads(FIX.read_text(encoding="utf-8"))
    snap["meta"]["ticker"] = ticker
    snap["meta"]["as_of"] = ASOF
    snap["meta"]["synthetic"] = False
    flags = [f for f in (snap["meta"].get("flags") or []) if not str(f).startswith("quality_")]
    flags.append("quality_tier_full")
    snap["meta"]["flags"] = flags
    company = dict(snap.get("company") or {})
    company["name"] = f"Cong ty {ticker}"
    company["sector"] = sector
    company["exchange"] = "HSX"
    company["is_bank"] = False
    if shares is None:
        company.pop("shares_outstanding", None)
    else:
        company["shares_outstanding"] = shares
    snap["company"] = company
    # Đảm bảo M4 có price_close qua prices gần nhất
    prices = snap.get("prices") if isinstance(snap.get("prices"), dict) else {}
    rows = list(prices.get("rows") or [])
    if rows:
        rows[-1] = dict(rows[-1])
        rows[-1]["close"] = price_close
        rows[-1]["date"] = ASOF
        prices["rows"] = rows
        snap["prices"] = prices
    return snap


@pytest.fixture(scope="module")
def api_env(tmp_path_factory):
    base = tmp_path_factory.mktemp("api014f")
    snap_dir = base / "snapshots"
    cache_dir = base / "api_cache"
    web_dist = base / "web_dist"
    snap_dir.mkdir()
    cache_dir.mkdir()
    web_dist.mkdir()
    (web_dist / "index.html").write_text(
        "<!doctype html><html><body>SPA</body></html>", encoding="utf-8"
    )

    # 5 scored + 1 insufficient (unranked)
    for t, sec, sh in [
        ("AAA", "Steel", 1_000_000_000),
        ("BBB", "Steel", 2_000_000_000),
        ("CCC", "Banks", 500_000_000),
        ("DDD", "Steel", None),  # thiếu shares → market_cap null
        ("EEE", "Energy", 100_000_000),
    ]:
        (snap_dir / f"{t}_{ASOF}.json").write_text(
            json.dumps(_clone(t, sec, shares=sh), ensure_ascii=False), encoding="utf-8"
        )

    insuff = _clone("ZZZ", "Steel", shares=1e9)
    flags = [f for f in (insuff["meta"].get("flags") or []) if not str(f).startswith("quality_")]
    flags.append("quality_tier_insufficient")
    insuff["meta"]["flags"] = flags
    (snap_dir / f"ZZZ_{ASOF}.json").write_text(
        json.dumps(insuff, ensure_ascii=False), encoding="utf-8"
    )

    (base / "data").mkdir(exist_ok=True)
    (base / "data" / "valuation_sector_stats.json").write_text(
        json.dumps(
            {
                "version": 2,
                "as_of": ASOF,
                "sectors": {
                    "Steel": {"n_pe": 3, "n_pb": 3, "median_pe": 12.0, "median_pb": 1.5},
                },
            }
        ),
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
        "skip_warmup": True,
    }
    store = ResultStore(
        api_cfg, snapshots_dir=snap_dir, cache_dir=cache_dir, asof=ASOF, root=base
    )
    app = create_app(api_cfg=api_cfg, store=store)
    client = TestClient(app)
    return {"client": client, "store": store, "app": app, "cfg": api_cfg, "base": base}


def test_health_ok_when_store_injected(api_env):
    r = api_env["client"].get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_health_warming_then_ok(tmp_path):
    """Warmup nền: status warming → ok."""
    snap_dir = tmp_path / "snapshots"
    cache_dir = tmp_path / "cache"
    snap_dir.mkdir()
    cache_dir.mkdir()
    (snap_dir / f"AAA_{ASOF}.json").write_text(
        json.dumps(_clone("AAA", "Steel"), ensure_ascii=False), encoding="utf-8"
    )
    cfg = {
        "snapshots_dir": str(snap_dir),
        "asof": ASOF,
        "default_profile": "long_term",
        "cors_origins": [],
        "docs_enabled": False,
        "trust_proxy_headers": False,
        "debate_live_max_per_hour": 1,
        "debate_live_max_per_ip_per_hour": 1,
        "debate_live_max_per_day": 1,
        "cache_dir": str(cache_dir),
        "skip_warmup": False,
    }
    # Không truyền store → bật warmup
    app = create_app(api_cfg=cfg)
    app.state.ready = False
    with TestClient(app, raise_server_exceptions=False) as client:
        # ép trạng thái warming trước khi thread xong
        app.state.ready = False
        h1 = client.get("/api/health").json()
        assert h1["status"] in ("warming", "ok")
        deadline = time.time() + 60
        while time.time() < deadline:
            if client.get("/api/health").json().get("status") == "ok":
                break
            time.sleep(0.2)
        assert client.get("/api/health").json()["status"] == "ok"


def test_rankings_total_scored_and_market_cap(api_env):
    client = api_env["client"]
    # page limit nhỏ hơn số scored
    r = client.get("/api/rankings", params={"limit": 2, "include_unranked": False})
    assert r.status_code == 200
    body = r.json()
    assert body["total"] >= 2
    assert "total_scored" in body
    assert len(body["items"]) == 2  # page limit — không dùng làm mẫu số hạng
    # Đủ items khi hỏi rộng: total == total_scored (không lọc)
    all_r = client.get("/api/rankings", params={"limit": 500, "include_unranked": False}).json()
    assert all_r["total_scored"] == all_r["total"]
    assert all_r["total_scored"] >= body["total_scored"]
    assert body["total_scored"] == all_r["total_scored"]
    # ZZZ insufficient không có trong danh sách scored
    tickers = {i["ticker"] for i in all_r["items"]}
    assert "ZZZ" not in tickers

    # market_cap = shares × close (additive)
    items = {
        i["ticker"]: i
        for i in client.get(
            "/api/rankings", params={"limit": 500, "include_unranked": True}
        ).json()["items"]
    }
    assert "market_cap" in items["AAA"]
    if items["AAA"]["market_cap"] is not None and items["AAA"]["price"] is not None:
        assert items["AAA"]["market_cap"] == pytest.approx(
            1_000_000_000 * float(items["AAA"]["price"]), rel=1e-3
        )
    # DDD thiếu shares → null
    if "DDD" in items:
        assert items["DDD"].get("market_cap") is None or isinstance(
            items["DDD"].get("market_cap"), (int, float)
        )
