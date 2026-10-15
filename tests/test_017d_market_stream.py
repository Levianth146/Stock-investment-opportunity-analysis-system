"""Feature 017d — SSE trang chủ: full → delta, seq, limiter, cache tĩnh, market_cap_ref."""
from __future__ import annotations

import json

import pytest

from stockai.api import insession
from stockai.api.market_stream import MarketDeltaState, index_for_delta
from tests.test_api_017b_watchlist_live import api_env  # noqa: F401


def _payload(chg_a=1.0, price=10.0, unmatched=1):
    return {
        "as_of_ts": "t0", "label": "x", "session": {}, "realtime": {"mode": "live", "state": "live"},
        "index": {"price": {"value": 1200.0}, "candles_1m": [{"t": 1}, {"t": 2}, {"t": 3}], "series_eod": [1, 2]},
        "breadth": {"up": {"value": 1}, "unmatched": {"value": unmatched}},
        "lists": {"strong_up": []},
        "heatmap": [
            {"symbol": "AAA", "change_pct": {"value": chg_a, "basis": "live"}, "label": "tạm tính"},
            {"symbol": "BBB", "change_pct": {"value": 0.0, "basis": "live"}, "label": "tạm tính"},
        ],
    }


def test_full_then_delta_only_changes():
    st = MarketDeltaState(lists_every=4.0)
    f = st.full(_payload())
    assert f["type"] == "full" and f["seq"] == 1
    assert st.delta(_payload(), now=1.0) is None  # không đổi → không gửi
    d = st.delta(_payload(chg_a=2.5, unmatched=0), now=2.0)
    assert d["type"] == "delta" and d["seq"] == 2
    assert d["heatmap"] == [["AAA", 2.5, "tạm tính", "live"]]  # chỉ mã đổi
    assert "breadth" in d and "lists" not in d
    assert "index" not in d  # index không đổi


def test_index_delta_has_no_series_and_only_tail():
    out = index_for_delta(_payload()["index"])
    assert "series_eod" not in out and "candles_1m" not in out
    assert out["candles_tail"] == [{"t": 2}, {"t": 3}] and out["candles_count"] == 3


def test_lists_throttled():
    st = MarketDeltaState(lists_every=4.0)
    st.full(_payload())
    p = _payload()
    p["lists"] = {"strong_up": [{"symbol": "AAA"}]}
    assert st.delta(p, now=1.0) is None or "lists" not in st.delta(p, now=1.0)
    import time
    d = st.delta(p, now=time.monotonic() + 10)
    assert d is not None and d["lists"]["strong_up"][0]["symbol"] == "AAA"


def test_endpoint_full_first_and_seq(api_env):  # noqa: F811
    client, *_ = api_env
    events = []
    with client.stream("GET", "/api/stream/market") as resp:
        assert resp.status_code == 200
        assert resp.headers["cache-control"] == "no-cache"
        assert resp.headers["x-accel-buffering"] == "no"
        for line in resp.iter_lines():
            if line.startswith("data: "):
                events.append(json.loads(line[6:]))
    assert events[0]["type"] == "full" and events[0]["seq"] == 1
    hm = events[0]["payload"]["heatmap"]
    assert len(hm) == 3 and all("market_cap_ref" in h for h in hm)
    assert "valuation_sample" in events[0]["payload"] and events[0]["payload"]["valuation_sample"] == []


def test_endpoint_limiter_two_per_ip(api_env):  # noqa: F811
    client, *_ = api_env
    lim = client.app.state.market_sse_limiter
    assert lim.max_per_key == 2
    assert lim.try_acquire("testclient") and lim.try_acquire("testclient")
    r = client.get("/api/stream/market")
    assert r.status_code == 429


def test_static_cache_reads_each_snapshot_once(api_env):  # noqa: F811
    client, hub, _fake, store = api_env
    calls = {"n": 0}
    orig = store.load_snapshot

    def counting(sym):
        calls["n"] += 1
        return orig(sym)

    store.load_snapshot = counting  # type: ignore[assignment]
    insession._STATIC_CACHE.update(asof=None, by_sym={})
    insession._MARKET_CACHE.update(asof=None, val=None)
    insession.build_market_analysis(hub, store, include_valuation=False)
    first = calls["n"]
    insession.build_market_analysis(hub, store, include_valuation=False)
    assert calls["n"] == first
