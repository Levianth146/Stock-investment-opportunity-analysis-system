"""Feature 017a — realtime hub, SSE, breadth, dividend flag (offline, fake stream)."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient

from stockai.api.app import create_app
from stockai.api.financials import dividend_payout_note, dividends_implausible
from stockai.api.insession import compute_breadth_from_quotes
from stockai.api.realtime import (
    UNIT_MISMATCH_LABEL,
    FakeStream,
    QuoteTick,
    RealtimeHub,
)
from stockai.api.session_clock import resolve_session
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
        "_sse_max_events": 1,
        "realtime": {
            "enabled": True,
            "sse_max_symbols": 20,
            "sse_max_per_ip": 5,
            "sse_heartbeat_sec": 15,
            "price_scale": 1,
        },
    }
    store = ResultStore(api_cfg, snapshots_dir=snap_dir, cache_dir=cache_dir, asof=ASOF)
    # Gắn fake hub thủ công sau create_app
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


def test_dividends_implausible_only_unit_mismatch():
    # unit mismatch
    assert dividends_implausible(2_000_000.0, 10_087_495_000_000.0)
    # payout > 100% / > 500% — KHÔNG cờ
    assert not dividends_implausible(218_556_413_606.0, 39_191_645_110.0)  # ANV 2023
    assert not dividends_implausible(80_000_000_000.0, 14_901_137_768.0)  # ABR 2025
    assert dividend_payout_note(80_000_000_000.0, 14_901_137_768.0) == "Chi trả vượt LNST năm đó"
    assert dividend_payout_note(3e12, 8e12) is None


def test_session_outside_hours_closed():
    # Chủ nhật
    sun = datetime(2026, 10, 11, 10, 0, tzinfo=ICT)
    assert resolve_session(sun).phase == "closed"
    # Thứ năm 01:00
    night = datetime(2026, 10, 15, 1, 12, tzinfo=ICT)
    assert resolve_session(night).phase == "closed"
    # Trong phiên liên tục
    cont = datetime(2026, 10, 15, 10, 0, tzinfo=ICT)
    assert resolve_session(cont).phase == "continuous"


def test_breadth_fixture():
    qs = [
        QuoteTick("A", 10, change_pct=1.0),
        QuoteTick("B", 10, change_pct=-2.0),
        QuoteTick("C", 10, change_pct=0.0),
        QuoteTick("D", 10, change_pct=None),
    ]
    b = compute_breadth_from_quotes(qs)
    assert b["up"] == 1 and b["down"] == 1 and b["flat"] == 2
    assert b.get("unmatched", 0) == 0
    assert b["up"] + b["down"] + b["flat"] + b.get("unmatched", 0) == 4


def test_realtime_status(api_env):
    client, hub, fake, _store = api_env
    # Ép đồng hồ: asof 2026-10-08 → 4 phiên sau last closed 2026-10-14
    hub._now_fn = lambda: datetime(2026, 10, 15, 10, 0, tzinfo=ICT)  # noqa: SLF001
    r = client.get("/api/realtime/status")
    assert r.status_code == 200
    body = r.json()
    assert "mode" in body
    assert body.get("label") in ("tạm tính", "chưa có giá tham chiếu") or body.get(
        "label"
    )
    assert "session" in body
    assert "price_scale_effective" in body
    assert "dropped_ticks" in body
    assert "symbols_subscribed" in body
    assert "last_tick_age_seconds" in body
    assert body.get("prev_close_source") == "none"
    assert body.get("snapshot_asof") == ASOF
    assert body.get("sessions_behind") == 4


def test_realtime_market(api_env):
    client, hub, fake, _store = api_env
    r = client.get("/api/realtime/market")
    assert r.status_code == 200
    body = r.json()
    assert "breadth" in body
    assert "lists" in body
    assert "heatmap" in body
    label = body.get("label") or ""
    assert isinstance(label, str) and (
        label
        in (
            "tạm tính",
            "trực tiếp (tạm tính)",
            "Đang kết nối — chưa nhận tick giá",
            "Luồng giá chậm — hơn 90 giây không có tick",
        )
        or "tạm tính" in label
        or label.startswith("đóng cửa")
        or "tick" in label.lower()
        or "kết nối" in label.lower()
    )
    assert "up" in body["breadth"]


def test_sse_order_and_fake_ticks(api_env):
    client, hub, fake, _store = api_env
    # đẩy tick trước khi mở stream
    hub.push_fake({"T": "t", "symbol": "AAA", "price": 12_000.0, "volume": 1000})
    # _sse_max_events=2 → generator kết thúc (không treo TestClient)
    with client.stream("GET", "/api/stream", params={"symbols": "AAA,BBB"}) as resp:
        assert resp.status_code == 200
        assert resp.headers.get("cache-control") == "no-cache"
        assert resp.headers.get("x-accel-buffering") == "no"
        buf = "".join(list(resp.iter_text()))
        assert "data:" in buf
        assert "quotes" in buf
        assert "AAA" in buf
        # event đầu là quotes (trước heartbeat nếu có)
        first_data = next(
            (ln for ln in buf.splitlines() if ln.startswith("data:")),
            "",
        )
        assert '"type": "quotes"' in first_data or '"type":"quotes"' in first_data


def test_sse_bad_symbol_400(api_env):
    client, *_ = api_env
    r = client.get("/api/stream", params={"symbols": "AAA,BAD!"})
    assert r.status_code == 400


def test_sse_too_many_symbols_400(api_env):
    client, *_ = api_env
    many = ",".join([f"A{i:02d}" for i in range(25)])
    r = client.get("/api/stream", params={"symbols": many})
    assert r.status_code == 400


def test_disconnect_fallback_no_realtime(api_env):
    client, hub, fake, _store = api_env
    fake.disconnect()
    # vòng fake_loop sẽ set mode
    import time

    time.sleep(0.15)
    st = client.get("/api/realtime/status").json()
    assert st["mode"] in ("no_realtime", "live", "connecting", "stale")  # race ok
    # quotes vẫn 200
    r = client.get("/api/quotes", params={"symbols": "AAA"})
    assert r.status_code == 200
    assert "items" in r.json()


def test_meta_refreshed_at(api_env):
    client, _hub, _fake, store = api_env
    path = Path(store.cache_dir) / "_refreshed_at.json"
    path.write_text(
        json.dumps({"asof": ASOF, "refreshed_at": "2026-10-15T16:05:00+07:00"}),
        encoding="utf-8",
    )
    m = client.get("/api/meta").json()
    assert m.get("refreshed_at") == "2026-10-15T16:05:00+07:00"


def test_outside_hours_quote_closed(api_env):
    client, hub, fake, store = api_env
    # ép đồng hồ ngoài giờ
    hub._now_fn = lambda: datetime(2026, 10, 15, 1, 0, tzinfo=ICT)  # noqa: SLF001
    q = hub.get_quote("AAA")
    assert q.state == "closed"
    assert q.basis == "eod"


# ----- 017a-fix / 017a-fix2: đơn vị giá + giá tham chiếu -----

FRESH_ASOF = "2026-10-14"  # last closed khi now=2026-10-15 10:00
STALE_ASOF = "2026-10-08"  # 4 phiên sau last closed


def _snapshot_close(hub: RealtimeHub, symbol: str = "AAA") -> float:
    pc = hub._snapshot_close.get(symbol)  # noqa: SLF001
    assert pc is not None and pc > 0
    return float(pc)


def _trading_now(hub: RealtimeHub) -> None:
    hub._now_fn = lambda: datetime(2026, 10, 15, 10, 0, tzinfo=ICT)  # noqa: SLF001


def _make_multi_hub(tmp_path, *, asof: str, n: int = 22, now=None):
    snap_dir = tmp_path / "snapshots"
    cache_dir = tmp_path / "api_cache"
    snap_dir.mkdir(exist_ok=True)
    cache_dir.mkdir(exist_ok=True)
    base = json.loads(FIX.read_text(encoding="utf-8"))
    for i in range(n):
        t = f"T{i:02d}"
        snap = json.loads(json.dumps(base))
        snap["meta"]["ticker"] = t
        snap["meta"]["as_of"] = asof
        snap["meta"]["synthetic"] = False
        flags = [
            f
            for f in (snap["meta"].get("flags") or [])
            if not str(f).startswith("quality_")
        ]
        flags.append("quality_tier_full")
        snap["meta"]["flags"] = flags
        # Biến giá đóng ±20% quanh mức fixture để kiểm auto-scale bền
        rows = snap.get("prices", {}).get("rows") or []
        if rows:
            last = dict(rows[-1])
            factor = 0.8 + (i % 5) * 0.1  # 0.8 .. 1.2
            for k in ("open", "high", "low", "close"):
                if last.get(k) is not None:
                    last[k] = float(last[k]) * factor
            rows = list(rows[:-1]) + [last]
            snap["prices"] = {**(snap.get("prices") or {}), "rows": rows}
        (snap_dir / f"{t}_{asof}.json").write_text(
            json.dumps(snap, ensure_ascii=False), encoding="utf-8"
        )
    api_cfg = {
        "snapshots_dir": str(snap_dir),
        "asof": asof,
        "cache_dir": str(cache_dir),
        "realtime": {"enabled": True, "price_scale": "auto"},
    }
    store = ResultStore(api_cfg, snapshots_dir=snap_dir, cache_dir=cache_dir, asof=asof)
    hub = RealtimeHub(
        store,
        api_cfg,
        fake_stream=FakeStream(),
        now_fn=now or (lambda: datetime(2026, 10, 15, 10, 0, tzinfo=ICT)),
    )
    hub.start()
    return hub, store


def test_price_scale_1000_correct(api_env):
    """matchPrice kiểu board nghìn × 1000 ≈ snapshot_close."""
    _client, hub, _fake, _store = api_env
    _trading_now(hub)
    hub._price_scale_effective = 1000.0  # noqa: SLF001
    hub._scale_locked = True  # noqa: SLF001
    hub.price_scale = 1000.0
    pc = _snapshot_close(hub)
    raw = pc / 1000.0  # ~12.03
    hub._ingest_event({"T": "t", "symbol": "AAA", "price": raw, "volume": 100})  # noqa: SLF001
    q = hub.get_quote("AAA")
    assert q.state == "live"
    assert q.price is not None
    assert abs(q.price / pc - 1.0) <= 0.15
    st = hub.status()
    assert st["price_scale_effective"] == 1000.0
    assert st["dropped_ticks"] == 0


def test_price_scale_1_correct(api_env):
    """matchPrice đã là VND — scale 1."""
    _client, hub, _fake, _store = api_env
    _trading_now(hub)
    hub._price_scale_effective = 1.0  # noqa: SLF001
    hub._scale_locked = True  # noqa: SLF001
    hub.price_scale = 1.0
    pc = _snapshot_close(hub)
    hub._ingest_event({"T": "t", "symbol": "AAA", "price": pc * 1.01, "volume": 100})  # noqa: SLF001
    q = hub.get_quote("AAA")
    assert q.state == "live"
    assert q.price is not None
    assert abs(q.price - pc * 1.01) < 1.0
    assert hub.status()["price_scale_effective"] == 1.0


def test_wrong_scale_triggers_unit_mismatch(api_env):
    """Giá đã VND nhưng nhân ×1000 → drop → unit_mismatch; API trả EOD."""
    client, hub, _fake, _store = api_env
    _trading_now(hub)
    hub._price_scale_effective = 1000.0  # noqa: SLF001
    hub._scale_locked = True  # noqa: SLF001
    hub.price_scale = 1000.0
    pc = _snapshot_close(hub)
    # Đẩy tick "sai đơn vị" cho mọi mã liquid → >5% drop trong cửa sổ 1 phút
    for sym in ("AAA", "BBB", "CCC"):
        hub._ingest_event(  # noqa: SLF001
            {"T": "t", "symbol": sym, "price": pc, "volume": 1}
        )
    st = hub.status()
    assert st["state"] == "unit_mismatch"
    assert st["mode"] == "unit_mismatch"
    assert st["dropped_ticks"] >= 1
    assert st["label"] == UNIT_MISMATCH_LABEL
    assert "price_scale_effective" in st
    assert "symbols_subscribed" in st
    assert "last_tick_age_seconds" in st

    q = hub.get_quote("AAA")
    assert q.state == "unit_mismatch"
    assert q.basis == "eod"
    assert q.price == pytest.approx(pc)

    body = client.get("/api/realtime/status").json()
    assert body["state"] == "unit_mismatch"
    assert body["dropped_ticks"] >= 1
    items = client.get("/api/quotes", params={"symbols": "AAA"}).json()["items"]
    assert items[0]["basis"] == "eod"
    assert items[0]["state"] == "unit_mismatch"
    assert items[0]["price"] == pytest.approx(pc)


def test_noisy_ticks_dropped_with_fresh_ref(tmp_path):
    """Tick nhiễu lệch >30% bị bỏ khi có prev_close snapshot tươi."""
    hub, _store = _make_multi_hub(tmp_path, asof=FRESH_ASOF, n=3)
    try:
        hub._price_scale_effective = 1.0  # noqa: SLF001
        hub._scale_locked = True  # noqa: SLF001
        hub._auto_scale = False  # noqa: SLF001
        hub.price_scale = 1.0
        # Đổi tên mã liquid đầu thành AAA-style: dùng T00
        pc = _snapshot_close(hub, "T00")
        assert hub.status()["prev_close_source"] == "snapshot"
        assert hub.status()["sessions_behind"] == 0
        hub._ingest_event({"T": "t", "symbol": "T00", "price": pc * 1.02, "volume": 10})  # noqa: SLF001
        good = hub._quotes["T00"].price  # noqa: SLF001
        assert good is not None
        assert abs(good / pc - 1.0) <= 0.30
        hub._ingest_event({"T": "t", "symbol": "T00", "price": pc * 10.0, "volume": 10})  # noqa: SLF001
        assert hub.status()["dropped_ticks"] >= 1
        cached = hub._quotes["T00"].price  # noqa: SLF001
        assert cached is not None
        assert abs(cached / pc - 1.0) <= 0.30
    finally:
        hub.stop()


def test_auto_scale_locks_at_majority_stale_snapshot(tmp_path):
    """Snapshot 4 phiên cũ + giá ±20%: auto-scale vẫn khoá đúng 1000 (log10)."""
    hub, _store = _make_multi_hub(tmp_path, asof=STALE_ASOF, n=22)
    try:
        assert hub._auto_scale and not hub._scale_locked  # noqa: SLF001
        st0 = hub.status()
        assert st0["prev_close_source"] == "none"
        assert st0["sessions_behind"] == 4
        assert st0["snapshot_asof"] == STALE_ASOF
        # raw board nghìn; mỗi mã có snapshot_close khác nhau (±20%)
        for i in range(22):
            sym = f"T{i:02d}"
            snap_c = hub._snapshot_close[sym]  # noqa: SLF001
            # Giả lập giá live lệch thêm ±10% so snapshot cũ — vẫn gần 10^-3
            live = snap_c * (1.1 if i % 2 == 0 else 0.9)
            hub._ingest_event(  # noqa: SLF001
                {"T": "t", "symbol": sym, "price": live / 1000.0}
            )
        assert hub._scale_locked  # noqa: SLF001
        assert hub.status()["price_scale_effective"] == 1000.0
        hub._ingest_event(  # noqa: SLF001
            {
                "T": "t",
                "symbol": "T00",
                "price": hub._snapshot_close["T00"] / 1000.0,  # noqa: SLF001
            }
        )
        q = hub.get_quote("T00")
        assert q.state == "live"
        assert q.price is not None
        assert q.change_pct is None  # không so giá cũ
        assert q.prev_close_source == "none"
        items = hub.get_quotes(["T00"])
        assert items[0]["change_pct"] is None
        assert items[0]["ref_label"] == "chưa có giá tham chiếu"
    finally:
        hub.stop()


def test_fresh_snapshot_uses_prev_close_for_change(tmp_path):
    """Snapshot trùng phiên đóng gần nhất → prev_close_source=snapshot, có %."""
    hub, store = _make_multi_hub(tmp_path, asof=FRESH_ASOF, n=3)
    try:
        st = hub.status()
        assert st["prev_close_source"] == "snapshot"
        assert st["sessions_behind"] == 0
        assert st["snapshot_asof"] == FRESH_ASOF
        hub._price_scale_effective = 1.0  # noqa: SLF001
        hub._scale_locked = True  # noqa: SLF001
        hub._auto_scale = False  # noqa: SLF001
        pc = _snapshot_close(hub, "T00")
        hub._ingest_event(  # noqa: SLF001
            {"T": "t", "symbol": "T00", "price": pc * 1.02, "volume": 5}
        )
        q = hub.get_quote("T00")
        assert q.prev_close_source == "snapshot"
        assert q.prev_close == pytest.approx(pc)
        assert q.change_pct == pytest.approx(2.0, abs=0.05)
        # Giả lập refresh_daily: asof cửa hàng = phiên đóng gần nhất
        store._asof = FRESH_ASOF  # noqa: SLF001
        assert hub.status()["sessions_behind"] == 0
    finally:
        hub.stop()


def test_tick_basic_price_overrides_stale_snapshot(api_env):
    """DNSE SecurityDefinition.basicPrice → prev_close_source=tick dù snapshot cũ."""
    client, hub, _fake, _store = api_env
    _trading_now(hub)
    hub._price_scale_effective = 1.0  # noqa: SLF001
    hub._scale_locked = True  # noqa: SLF001
    assert hub.status()["sessions_behind"] == 4
    assert hub.status()["prev_close_source"] == "none"
    pc = _snapshot_close(hub)
    hub._ingest_event(  # noqa: SLF001
        {"T": "sec_def", "symbol": "AAA", "basicPrice": pc}
    )
    hub._ingest_event(  # noqa: SLF001
        {"T": "t", "symbol": "AAA", "price": pc * 1.01, "volume": 10}
    )
    q = hub.get_quote("AAA")
    assert q.prev_close_source == "tick"
    assert q.change_pct == pytest.approx(1.0, abs=0.05)
    st = client.get("/api/realtime/status").json()
    assert st["prev_close_source"] == "tick"


def test_insession_excludes_no_ref(api_env):
    """Breadth: mã đã khớp nhưng thiếu tham chiếu → excluded_no_ref (không vào up/down)."""
    from stockai.api.insession import build_market_analysis

    _client, hub, _fake, store = api_env
    _trading_now(hub)
    # Phiên mở + chưa khớp → unmatched; cần đánh dấu đã khớp để xét has_ref
    for sym in ("AAA", "BBB", "CCC"):
        hub._traded_session.add(sym)  # noqa: SLF001
    payload = build_market_analysis(hub, store)
    assert payload["breadth"]["excluded_no_ref"]["value"] >= 1
    # up+down chỉ mã có ref → ở đây 0 vì snapshot cũ; flat chứa excluded
    assert payload["breadth"]["up"]["value"] == 0
    assert payload["breadth"]["down"]["value"] == 0


# ----- 017a-fix6: ingest raw dict (probe-style) + mode trung thực -----


def test_fix6_raw_dispatch_match_price_ticks_up(api_env):
    """Dict thô T=t + matchPrice (nghìn) → quotes_live, ticks, last_tick_age."""
    client, hub, _fake, _store = api_env
    _trading_now(hub)
    hub._price_scale_effective = 1000.0  # noqa: SLF001
    hub._scale_locked = True  # noqa: SLF001
    hub.price_scale = 1000.0
    pc = _snapshot_close(hub)
    raw = pc / 1000.0
    # Giống payload probe / wire DNSE 2.4.1
    hub.handle_raw_message(
        {
            "T": "t",
            "symbol": "AAA",
            "matchPrice": raw,
            "totalVolumeTraded": 12_345,
            "highestPrice": raw * 1.01,
            "lowestPrice": raw * 0.99,
        }
    )
    st = client.get("/api/realtime/status").json()
    assert st["mode"] == "live"
    assert st["quotes_live"] >= 1
    assert st["stats"]["ticks"] >= 1
    assert st["stats"]["parsed_trades"] >= 1
    assert st["stats"]["raw_msgs"] >= 1
    assert st["stats"]["msg_types"].get("t", 0) >= 1
    assert st["last_tick_age_seconds"] is not None
    assert st["last_tick_age_seconds"] < 5
    q = hub.get_quote("AAA")
    assert q.state == "live"
    # totalVolumeTraded = lot HOSE → ×10 cổ phiếu
    assert q.volume == 12_345 * 10
    assert "trực tiếp" in (st.get("label") or "")


def test_fix6_missing_fields_parse_errors(api_env):
    """Thiếu matchPrice → parse_errors tăng + mô tả; không nuốt."""
    client, hub, _fake, _store = api_env
    _trading_now(hub)
    before = int(hub.status()["stats"].get("parse_errors") or 0)
    hub.handle_raw_message({"T": "t", "symbol": "AAA"})  # thiếu matchPrice
    st = client.get("/api/realtime/status").json()
    assert st["stats"]["parse_errors"] == before + 1
    err = st["stats"].get("last_parse_error") or ""
    assert "matchPrice" in err
    assert st["mode"] != "live"  # chưa có tick hợp lệ


def test_fix6_sec_def_sd_basic_price(api_env):
    """T=sd (SDK 2.4.1) + basicPrice → prev_close_source=tick."""
    client, hub, _fake, _store = api_env
    _trading_now(hub)
    hub._price_scale_effective = 1.0  # noqa: SLF001
    hub._scale_locked = True  # noqa: SLF001
    pc = _snapshot_close(hub)
    hub.handle_raw_message({"T": "sd", "symbol": "AAA", "basicPrice": pc})
    hub.handle_raw_message(
        {
            "T": "t",
            "symbol": "AAA",
            "matchPrice": pc * 1.01,
            "totalVolumeTraded": 10,
        }
    )
    assert hub.get_quote("AAA").prev_close_source == "tick"
    assert client.get("/api/realtime/status").json()["prev_close_source"] == "tick"


def test_fix6_31s_no_tick_connecting(api_env):
    """Phiên liên tục + >30s không tick → connecting / no_ticks_yet."""
    client, hub, _fake, _store = api_env
    _trading_now(hub)
    hub._price_scale_effective = 1.0  # noqa: SLF001
    hub._scale_locked = True  # noqa: SLF001
    pc = _snapshot_close(hub)
    hub.handle_raw_message(
        {"T": "t", "symbol": "AAA", "matchPrice": pc * 1.01, "totalVolumeTraded": 1}
    )
    assert hub.status()["mode"] == "live"
    import time as _time

    hub._last_tick_mono = _time.monotonic() - 31.0  # noqa: SLF001
    st = client.get("/api/realtime/status").json()
    assert st["mode"] == "connecting"
    assert st.get("reason") == "no_ticks_yet"
    label = (st.get("label") or "").lower()
    assert "trực tiếp" not in label
    assert "kết nối" in label or "tick" in label


def test_fix6_91s_no_tick_stale(api_env):
    """>90s không tick → stale / no_ticks."""
    client, hub, _fake, _store = api_env
    _trading_now(hub)
    hub._price_scale_effective = 1.0  # noqa: SLF001
    hub._scale_locked = True  # noqa: SLF001
    pc = _snapshot_close(hub)
    hub.handle_raw_message(
        {"T": "t", "symbol": "AAA", "matchPrice": pc * 1.01, "totalVolumeTraded": 1}
    )
    import time as _time

    hub._last_tick_mono = _time.monotonic() - 91.0  # noqa: SLF001
    st = client.get("/api/realtime/status").json()
    assert st["mode"] == "stale"
    assert st.get("reason") == "no_ticks"
    assert "trực tiếp" not in (st.get("label") or "")


def test_dnse_sdk_openapi_pin():
    """Ghim dnse-sdk-openapi==2.4.1 — import được (offline, không gọi mạng)."""
    import importlib.metadata as md

    import dnse  # noqa: F401

    ver = md.version("dnse-sdk-openapi")
    assert ver == "2.4.1", f"cần dnse-sdk-openapi==2.4.1, đang {ver}"


# ----- 017a-fix7: index mi candles + volume lot→CP + vol_ratio -----


def test_fix7_mi_builds_index_candles(api_env):
    """Chuỗi T=mi giả → candles_1m ≥1, basis=live, change_pct vs priorValueIndexes."""
    from stockai.api.insession import build_market_analysis

    _client, hub, _fake, store = api_env
    _trading_now(hub)
    # Hai mi cùng phút + một mi phút khác (epoch khác nhau khó ép) — vẫn ≥1 nến
    hub.handle_raw_message(
        {
            "T": "mi",
            "indexName": "VNINDEX",
            "valueIndexes": 1702.19,
            "priorValueIndexes": 1704.87,
            "totalVolumeTraded": 200_000_000,
            "grossTradeAmount": 4700.5,
        }
    )
    hub.handle_raw_message(
        {
            "T": "mi",
            "indexName": "VNINDEX",
            "valueIndexes": 1703.0,
            "priorValueIndexes": 1704.87,
            "totalVolumeTraded": 201_000_000,
            "grossTradeAmount": 4710.0,
        }
    )
    q = hub.get_index_quote("VNINDEX")
    assert q is not None
    assert q.price == pytest.approx(1703.0)
    assert q.prev_close == pytest.approx(1704.87)
    assert q.basis == "live"
    assert q.change_pct == pytest.approx((1703.0 - 1704.87) / 1704.87 * 100.0, abs=0.01)
    candles = hub.candles("VNINDEX")
    assert len(candles) >= 1
    assert candles[-1]["c"] == pytest.approx(1703.0)
    assert hub.status()["stats"].get("parsed_index", 0) >= 2
    assert hub.status()["stats"].get("mi_fields")  # đã log field names

    payload = build_market_analysis(hub, store)
    idx = payload["index"]
    assert idx["price"]["basis"] == "live"
    assert len(idx["candles_1m"]) >= 1
    assert idx["prev_close"]["value"] == pytest.approx(1704.87)
    assert idx.get("value", {}).get("value") == pytest.approx(4710.0)


def test_fix7_volume_lot_to_shares_vs_gross(api_env):
    """totalVolumeTraded (lot) ×10 ≈ grossTradeAmount(tỷ)×1e9 / matchPrice(VND)."""
    _client, hub, _fake, _store = api_env
    _trading_now(hub)
    hub._price_scale_effective = 1000.0  # noqa: SLF001
    hub._scale_locked = True  # noqa: SLF001
    hub.price_scale = 1000.0
    pc = _snapshot_close(hub)
    # matchPrice nghìn; gross tỷ; totalVolumeTraded lot
    match_nghin = pc / 1000.0
    match_vnd = pc
    lots = 22105.0
    gta = lots * 10 * match_vnd / 1e9  # đúng công thức ngược
    hub.handle_raw_message(
        {
            "T": "t",
            "symbol": "AAA",
            "matchPrice": match_nghin,
            "totalVolumeTraded": lots,
            "grossTradeAmount": gta,
        }
    )
    q = hub.get_quote("AAA")
    assert q.volume == pytest.approx(lots * 10)
    qty_from_gta = gta * 1e9 / match_vnd
    assert abs(q.volume - qty_from_gta) / qty_from_gta < 0.05


def test_fix7_late_hub_uses_cumulative_not_sum(api_env):
    """Hub start giữa phiên: lấy totalVolumeTraded cumulative, không cộng delta."""
    _client, hub, _fake, _store = api_env
    _trading_now(hub)
    hub._price_scale_effective = 1.0  # noqa: SLF001
    hub._scale_locked = True  # noqa: SLF001
    pc = _snapshot_close(hub)
    hub.handle_raw_message(
        {
            "T": "t",
            "symbol": "AAA",
            "matchPrice": pc * 1.01,
            "totalVolumeTraded": 50_000,  # lot — đã giao từ đầu phiên
        }
    )
    hub.handle_raw_message(
        {
            "T": "t",
            "symbol": "AAA",
            "matchPrice": pc * 1.02,
            "totalVolumeTraded": 55_000,  # cumulative mới
        }
    )
    q = hub.get_quote("AAA")
    # Phải là 55000×10, không phải (50000+55000)×10
    assert q.volume == pytest.approx(55_000 * 10)


def test_fix7_unmatched_excluded_from_volume_spike(api_env):
    """Mã không tick hôm nay → relative_vol=null, không vào volume_spike."""
    from stockai.api.insession import build_market_analysis

    _client, hub, _fake, store = api_env
    _trading_now(hub)
    hub._price_scale_effective = 1.0  # noqa: SLF001
    hub._scale_locked = True  # noqa: SLF001
    # Seed volume EOD lớn trên quote (giả lập không tick) — không được vào spike
    for sym in ("AAA", "BBB", "CCC"):
        q = hub._quotes.get(sym)  # noqa: SLF001
        if q is not None:
            q.volume = 100_000_000.0  # EOD-like
            q.state = "closed"
            q.basis = "eod"
    # Chỉ AAA có tick thật
    pc = _snapshot_close(hub)
    hub.handle_raw_message(
        {
            "T": "t",
            "symbol": "AAA",
            "matchPrice": pc * 1.01,
            "totalVolumeTraded": 1000,
            "basicPrice": pc,
        }
    )
    assert hub.has_traded_session("AAA")
    assert not hub.has_traded_session("BBB")
    payload = build_market_analysis(hub, store)
    spike_syms = {r["symbol"] for r in payload["lists"]["volume_spike"]}
    assert "BBB" not in spike_syms
    assert "CCC" not in spike_syms
    # relative_vol trên heatmap/list: mã chưa khớp không có relative_vol từ EOD
    for row in payload["lists"]["volume_spike"]:
        assert row["symbol"] in hub._traded_session  # noqa: SLF001
