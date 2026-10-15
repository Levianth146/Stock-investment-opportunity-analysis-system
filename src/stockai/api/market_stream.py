"""Luồng SSE trang chủ (017d): full khi kết nối, sau đó delta nhỏ có ``seq``.

- Một bản tính chung cho mọi client (cache ≥ ``min_age`` giây) — không tính lại mỗi client.
- Heatmap: chỉ gửi mã đổi (%/nhãn); diện tích ô dùng ``market_cap_ref`` (cố định theo phiên).
- Breadth/index gửi khi đổi; lists tối đa mỗi ``lists_every`` giây.
- Ngoài giờ giao dịch: 1 full rồi chỉ heartbeat (kiểm tra thưa).
"""
from __future__ import annotations

import json
import threading
import time
from typing import Any

from stockai.api.insession import build_market_analysis

_LOCK = threading.Lock()
_CACHE: dict[str, Any] = {"t": 0.0, "key": None, "payload": None}


def shared_market(hub: Any, store: Any, *, min_age: float = 1.0) -> dict[str, Any]:
    """Payload thị trường dùng chung (không valuation_sample)."""
    key = (id(hub), getattr(store, "asof", None))
    now = time.monotonic()
    with _LOCK:
        if _CACHE["payload"] is not None and _CACHE["key"] == key and now - _CACHE["t"] < min_age:
            return _CACHE["payload"]
        payload = build_market_analysis(hub, store, include_valuation=False)
        _CACHE.update(t=now, key=key, payload=payload)
        return payload


def _sig(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, default=str)


def _hm_value(item: dict[str, Any]) -> tuple[Any, Any]:
    chg = item.get("change_pct")
    v = chg.get("value") if isinstance(chg, dict) else chg
    return (v, item.get("label"))


def index_for_delta(index: dict[str, Any]) -> dict[str, Any]:
    """Bỏ series_eod; candles_1m chỉ giữ 2 nến cuối (client gộp theo ``t``)."""
    out = {k: v for k, v in index.items() if k not in ("series_eod", "candles_1m")}
    candles = index.get("candles_1m") or []
    out["candles_tail"] = candles[-2:]
    out["candles_count"] = len(candles)
    return out


class MarketDeltaState:
    """Trạng thái per-client: biết đã gửi gì để chỉ gửi phần đổi."""

    def __init__(self, *, lists_every: float = 4.0) -> None:
        self.seq = 0
        self.lists_every = lists_every
        self._hm: dict[str, tuple[Any, Any]] = {}
        self._sigs: dict[str, str] = {}
        self._lists_t = 0.0
        self._meta: str | None = None

    def full(self, payload: dict[str, Any]) -> dict[str, Any]:
        self.seq += 1
        self._hm = {h["symbol"]: _hm_value(h) for h in payload.get("heatmap") or []}
        self._sigs = {
            "index": _sig(index_for_delta(payload.get("index") or {})),
            "breadth": _sig(payload.get("breadth")),
            "lists": _sig(payload.get("lists")),
        }
        self._lists_t = time.monotonic()
        self._meta = _sig([payload.get("label"), payload.get("session"), payload.get("realtime"), payload.get("as_of_ts")])
        return {"type": "full", "seq": self.seq, "payload": payload}

    def delta(self, payload: dict[str, Any], now: float | None = None) -> dict[str, Any] | None:
        """Trả None nếu không có gì đổi (khi đó chỉ chờ heartbeat)."""
        now = time.monotonic() if now is None else now
        d: dict[str, Any] = {}
        meta = _sig([payload.get("label"), payload.get("session"), payload.get("realtime"), payload.get("as_of_ts")])
        if meta != self._meta:
            self._meta = meta
            for k in ("label", "session", "realtime"):
                d[k] = payload.get(k)
            d["as_of_ts"] = payload.get("as_of_ts")
        idx = index_for_delta(payload.get("index") or {})
        s = _sig(idx)
        if s != self._sigs.get("index"):
            self._sigs["index"] = s
            d["index"] = idx
        s = _sig(payload.get("breadth"))
        if s != self._sigs.get("breadth"):
            self._sigs["breadth"] = s
            d["breadth"] = payload.get("breadth")
        if now - self._lists_t >= self.lists_every:
            s = _sig(payload.get("lists"))
            if s != self._sigs.get("lists"):
                self._sigs["lists"] = s
                d["lists"] = payload.get("lists")
            self._lists_t = now
        hm: list[list[Any]] = []
        for h in payload.get("heatmap") or []:
            sym = h["symbol"]
            cur = _hm_value(h)
            if self._hm.get(sym) != cur:
                self._hm[sym] = cur
                chg = h.get("change_pct") or {}
                hm.append([sym, cur[0], cur[1], chg.get("basis")])
        if hm:
            d["heatmap"] = hm
        if not d:
            return None
        self.seq += 1
        return {"type": "delta", "seq": self.seq, **d}
