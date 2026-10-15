"""Feature 017e — lưu giá trong phiên, nạp lại sau restart, giá chốt phiên khi chưa có EOD."""
from __future__ import annotations

import json
from datetime import datetime

from stockai.api.realtime import FakeStream, RealtimeHub
from stockai.api.session_clock import ICT
from tests.test_api_017a_realtime import _snapshot_close, api_env  # noqa: F401


def _live(hub, hh=10):
    hub._now_fn = lambda: datetime(2026, 10, 15, hh, 0, tzinfo=ICT)  # noqa: SLF001
    hub._price_scale_effective = 1.0  # noqa: SLF001
    hub._scale_locked = True  # noqa: SLF001
    hub._sessions_behind = lambda: 0  # noqa: SLF001


def _new_hub(store, tmp_path, hh=16):
    cfg = {"realtime": {"price_scale": 1, "persist_dir": str(tmp_path)}}
    hub = RealtimeHub(
        store, cfg, fake_stream=FakeStream(),
        now_fn=lambda: datetime(2026, 10, 15, hh, 0, tzinfo=ICT),
    )
    hub._sessions_behind = lambda: 1  # noqa: SLF001  (phiên hôm nay chưa có snapshot)
    return hub


def test_save_restore_shows_session_close(api_env, tmp_path):  # noqa: F811
    _client, hub, _fake, store = api_env
    _live(hub)
    hub._persist_dir = tmp_path  # noqa: SLF001
    pc = _snapshot_close(hub)
    hub._ingest_event({"T": "t", "symbol": "AAA", "price": pc * 1.02, "volume": 500})  # noqa: SLF001
    hub.handle_raw_message(
        {"T": "mi", "indexName": "VNINDEX", "valueIndexes": 1700.5, "priorValueIndexes": 1710.0}
    )
    hub._persist_save()  # noqa: SLF001
    f = tmp_path / "intraday_2026-10-15.json"
    assert f.is_file()

    hub2 = _new_hub(store, tmp_path)
    assert hub2.close_active() and hub2.session_close_date() == "2026-10-15"
    q = hub2.get_quote("AAA")
    assert q.basis == "close" and q.state == "closed"
    assert abs(q.price - pc * 1.02) < 1e-6
    assert q.change_pct is not None and abs(q.change_pct - 2.0) < 1e-6
    iq = hub2.get_index_quote("VNINDEX")
    assert iq is not None and abs(iq.price - 1700.5) < 1e-9
    assert hub2.candles("VNINDEX")
    # mã không khớp hôm nay: giữ giá EOD, đứng giá (không bịa %)
    other = next(s for s in hub2._snapshot_close if s != "AAA")  # noqa: SLF001
    qo = hub2.get_quote(other)
    assert qo.basis == "eod" and (qo.change_pct in (0.0, None))


def test_restore_ignored_when_snapshot_not_older(api_env, tmp_path):  # noqa: F811
    _client, hub, _fake, store = api_env
    _live(hub)
    hub._persist_dir = tmp_path  # noqa: SLF001
    pc = _snapshot_close(hub)
    hub._ingest_event({"T": "t", "symbol": "AAA", "price": pc, "volume": 1})  # noqa: SLF001
    hub._persist_save()  # noqa: SLF001
    f = tmp_path / "intraday_2026-10-15.json"
    data = json.loads(f.read_text(encoding="utf-8"))
    data["date"] = store.asof  # ngày ≤ asof → EOD đã thay thế
    (tmp_path / f"intraday_{store.asof}.json").write_text(json.dumps(data), encoding="utf-8")
    f.unlink()
    hub2 = _new_hub(store, tmp_path)
    assert not hub2.close_active()
    assert hub2.get_quote("AAA").basis == "eod"


def test_new_session_clears_traded_flag(api_env, tmp_path):  # noqa: F811
    _client, hub, _fake, store = api_env
    _live(hub)
    hub._persist_dir = tmp_path  # noqa: SLF001
    pc = _snapshot_close(hub)
    hub._ingest_event({"T": "t", "symbol": "AAA", "price": pc, "volume": 1})  # noqa: SLF001
    hub._persist_save()  # noqa: SLF001
    hub2 = _new_hub(store, tmp_path, hh=10)
    hub2._now_fn = lambda: datetime(2026, 10, 16, 10, 0, tzinfo=ICT)  # noqa: SLF001
    hub2._ingest_event({"T": "t", "symbol": "BBB", "price": pc, "volume": 1})  # noqa: SLF001
    assert hub2.has_traded_session("BBB") and not hub2.has_traded_session("AAA")


def test_market_payload_after_close_uses_session_close(api_env, tmp_path):  # noqa: F811
    from stockai.api.insession import build_market_analysis

    _client, hub, _fake, store = api_env
    _live(hub)
    hub._persist_dir = tmp_path  # noqa: SLF001
    pc = _snapshot_close(hub)
    hub._ingest_event({"T": "t", "symbol": "AAA", "price": pc * 1.03, "volume": 500})  # noqa: SLF001
    hub.handle_raw_message(
        {"T": "mi", "indexName": "VNINDEX", "valueIndexes": 1700.5, "priorValueIndexes": 1710.0}
    )
    hub._persist_save()  # noqa: SLF001
    hub2 = _new_hub(store, tmp_path)
    out = build_market_analysis(hub2, store, include_valuation=False)
    assert "15/10" in out["label"] and "tạm tính" in out["label"]
    assert out["index"]["label"].startswith("đóng cửa 15/10")
    assert out["index"]["price"]["basis"] == "close"
    assert out["breadth"]["up"]["value"] >= 1
    hm = {r["symbol"]: r for r in out["heatmap"]}
    assert hm["AAA"]["change_pct"]["value"] is not None


def test_meta_exposes_scoring_config():
    from fastapi.testclient import TestClient

    from stockai.api.app import create_app

    r = TestClient(create_app()).get("/api/meta")
    assert r.status_code == 200
    sc = r.json()["scoring"]
    assert set(sc["profiles"]) >= {"long_term", "swing"}
    assert sc["risk_gate"]["R_threshold"] == 70
    assert r.json()["ratings"][0]["label"] == "Mua mạnh"
