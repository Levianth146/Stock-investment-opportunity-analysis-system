"""QuoteProvider — giá realtime (RealtimeHub) hoặc đóng cửa từ snapshot."""
from __future__ import annotations

from typing import Any, Protocol


class QuoteProvider(Protocol):
    def get_quotes(self, symbols: list[str]) -> list[dict[str, Any]]:
        """Trả danh sách {symbol, price, source, ts, ...}."""
        ...


class SnapshotQuoteProvider:
    """Giá đóng cửa phiên gần nhất từ snapshot (source=snapshot, ts=asof)."""

    def __init__(self, store: Any) -> None:
        self._store = store

    def get_quotes(self, symbols: list[str]) -> list[dict[str, Any]]:
        asof = self._store.asof
        out: list[dict[str, Any]] = []
        for sym in symbols:
            item: dict[str, Any] = {
                "symbol": sym,
                "price": None,
                "source": "snapshot",
                "ts": asof,
                "state": "closed",
                "basis": "eod",
            }
            try:
                snap = self._store.load_snapshot(sym)
            except Exception:
                out.append(item)
                continue
            rows = ((snap.get("prices") or {}).get("rows") or []) if isinstance(snap, dict) else []
            if rows:
                last = rows[-1]
                try:
                    item["price"] = float(last.get("close"))
                except (TypeError, ValueError):
                    item["price"] = None
                if isinstance(last.get("date"), str):
                    item["ts"] = last["date"]
                try:
                    item["prev_close"] = float(last.get("close"))
                except (TypeError, ValueError):
                    pass
            out.append(item)
        return out


class HubQuoteProvider:
    """Bọc RealtimeHub — poll /api/quotes; degrade về snapshot khi hub no_realtime."""

    def __init__(self, hub: Any, fallback: SnapshotQuoteProvider) -> None:
        self._hub = hub
        self._fallback = fallback

    def get_quotes(self, symbols: list[str]) -> list[dict[str, Any]]:
        status = self._hub.status()
        if status.get("mode") == "no_realtime" and not bool(
            (status.get("stats") or {}).get("ticks")
        ):
            # chưa có tick nào → snapshot thuần
            items = self._fallback.get_quotes(symbols)
            for it in items:
                it["state"] = "no_realtime"
            return items
        return self._hub.get_quotes(symbols)


# Giữ tên cũ cho import tương thích
class DNSEQuoteProvider(HubQuoteProvider):
    """Alias lịch sử — dùng HubQuoteProvider."""

    pass
