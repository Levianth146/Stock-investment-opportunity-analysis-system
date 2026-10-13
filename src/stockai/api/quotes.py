"""QuoteProvider — giá realtime (stub DNSE) hoặc đóng cửa từ snapshot."""
from __future__ import annotations

from abc import ABC, abstractmethod
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
            out.append(item)
        return out


class DNSEQuoteProvider(ABC):
    """Chỗ dành cho DNSE realtime — chưa triển khai (feature sau)."""

    @abstractmethod
    def get_quotes(self, symbols: list[str]) -> list[dict[str, Any]]:
        raise NotImplementedError("DNSEQuoteProvider chưa triển khai")
