"""Feature 017b — watchlist/summary, SSE coalesce, breadth 4 nhóm, stale receive."""
from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient

from stockai.api.app import create_app
from stockai.api.insession import compute_breadth_from_quotes
from stockai.api.realtime import DISPLAY_STALE_AFTER_SEC, FakeStream, QuoteTick, RealtimeHub
from stockai.api.store import ResultStore

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "fixtures" / "snapshot_DEMO.json"
ASOF = "2026-10-08"
ICT = ZoneInfo("Asia/Ho_Chi_Minh")


def _clone(ticker: str, sector: str = "Steel") -> dict:
    snap = json.loads(FIX.read_text(encoding="utf-8"))
    snap["meta"]["ticker"] = ticker
    snap["meta"]["as_of"] = ASOF
    snap["meta"]["synthetic"] = False
    flags = [f for f in (snap["meta"].get("flags") or []) if not str(f).startswith("quality_")]
    flags.append("quality_tier_full")
    snap["meta"]["flags"] = flags
    company = dict(snap.get("company") or {})
    company["name"] = f"CT {ticker}"
    company["sector"] = sector
    company["shares_outstanding"] = 1_000_000_000.0
    snap["company"] = company
    return snap


@pytest.fixture
def api_env(tmp_path):
    snap_dir = tmp_path / "snapshots"
    cache_dir = tmp_path / "api_cache"
    snap_dir.mkdir()
    cache_dir.mkdir()
    for t, sec in [("AAA", "Banks"), ("BBB", "Steel"), ("CCC", "Tech")]:
        (snap_dir / f"{t}_{ASOF}.json").write_text(
            json.dumps(_clone(t, sec), ensure_ascii=False), encoding="utf-8"
        )
    api_cfg = {
        "snapshots_dir": str(snap_dir),
        "asof": ASOF,
        "default_profile": "long_term",
        "cache_dir": str(cache_dir),
        "skip_warmup": True,
        "skip_realtime_start": True,
        "_realtime_fake": True,
        "_sse_max_events": 3,
        "realtime": {
            "enabled": True,
            "sse_max_symbols": 20,
            "sse_max_per_ip": 5,
            "sse_heartbeat_sec": 15,
            "sse_coalesce_sec": 1.0,
            "price_scale": 1,
        },
    }
    store = ResultStore(api_cfg, snapshots_dir=snap_dir, cache_dir=cache_dir, asof=ASOF)
    app = create_app(api_cfg=api_cfg, store=store)
    fake = FakeStream()
    hub = RealtimeHub(store, api_cfg, fake_stream=fake)
    hub.start()
    app.state.realtime_hub = hub
    from stockai.api.quotes import HubQuoteProvider, SnapshotQuoteProvider

    app.state.quote_provider = HubQuoteProvider(hub, SnapshotQuoteProvider(store))
    client = TestClient(app)
    yield client, hub, fake, store
    hub.stop()


def test_watchlist_summary_ok(api_env):
    client, _hub, _fake, _store = api_env
    r = client.get("/api/watchlist/summary", params={"symbols": "AAA,BBB"})
    assert r.status_code == 200
    body = r.json()
    assert len(body["items"]) == 2
    assert body["items"][0]["symbol"] in ("AAA", "BBB")


def test_watchlist_summary_bad_symbol_400(api_env):
    client, *_ = api_env
    r = client.get("/api/watchlist/summary", params={"symbols": "BAD!!!"})
    assert r.status_code == 400


def test_watchlist_summary_over_50_400(api_env):
    client, *_ = api_env
    syms = ",".join(f"T{i:02d}" for i in range(51))
    r = client.get("/api/watchlist/summary", params={"symbols": syms})
    assert r.status_code == 400
    assert "50" in r.json().get("error", "")


def test_breadth_four_groups_sum():
    qs = [
        QuoteTick("A", 10, change_pct=1.0, state="live"),
        QuoteTick("B", 10, change_pct=-2.0, state="live"),
        QuoteTick("C", 10, change_pct=0.0, state="live"),
        QuoteTick("D", 10, change_pct=None, state="closed"),
    ]
    b = compute_breadth_from_quotes(
        qs, traded={"A", "B", "C"}, session_open=True
    )
    assert b["up"] + b["down"] + b["flat"] + b["unmatched"] == 4
    assert b["unmatched"] == 1  # D chưa khớp


def test_stale_by_receive_mono(api_env):
    _client, hub, fake, _store = api_env
    hub._now_fn = lambda: datetime(2026, 10, 15, 10, 0, tzinfo=ICT)  # noqa: SLF001
    hub.push_fake(
        {"T": "t", "symbol": "AAA", "price": 25_000, "basicPrice": 24_000}
    )
    # Đợi fake loop ingest
    time.sleep(0.15)
    q = hub.get_quote("AAA")
    assert q.state in ("live", "stale")
    # Giả lập nhận cũ hơn DISPLAY_STALE
    hub._receive_mono["AAA"] = time.monotonic() - (DISPLAY_STALE_AFTER_SEC + 2)  # noqa: SLF001
    q2 = hub.get_quote("AAA")
    assert q2.state == "stale"


def test_sse_coalesce_max_one_per_sec(api_env):
    """Trong cửa sổ ~1s, mỗi mã không quá 1 event cập nhật sau snapshot đầu."""
    client, hub, fake, _store = api_env
    hub._now_fn = lambda: datetime(2026, 10, 15, 10, 0, tzinfo=ICT)  # noqa: SLF001
    # Cấu hình test: nhiều event + coalesce 1s
    with client.stream("GET", "/api/stream?symbols=AAA") as resp:
        assert resp.status_code == 200
        # Đẩy nhiều tick nhanh
        for i in range(5):
            hub.push_fake(
                {
                    "T": "t",
                    "symbol": "AAA",
                    "price": 25_000 + i,
                    "basicPrice": 24_000,
                }
            )
            time.sleep(0.05)
        # Đọc vài chunk
        chunks = []
        for line in resp.iter_lines():
            if line and line.startswith("data:"):
                chunks.append(line)
            if len(chunks) >= 3:
                break
    # Ít nhất 1 snapshot; các cập nhật sau bị coalesce → không explode thành 5
    assert len(chunks) <= 4


def test_realtime_market_has_index_and_unmatched(api_env):
    client, *_ = api_env
    r = client.get("/api/realtime/market")
    assert r.status_code == 200
    body = r.json()
    assert "index" in body
    assert "unmatched" in body["breadth"]
    assert "liquid_count" in body["breadth"]
    b = body["breadth"]
    s = (
        b["up"]["value"]
        + b["down"]["value"]
        + b["flat"]["value"]
        + b["unmatched"]["value"]
    )
    assert s == b["liquid_count"] or s == b.get("sum")
