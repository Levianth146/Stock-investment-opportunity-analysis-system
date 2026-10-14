"""RealtimeHub — giá phiên từ DNSE (display + phân tích tạm tính) hoặc snapshot.

Nguyên tắc cứng:
- M2–M7 chỉ dùng giá đóng cửa EOD; tick không bao giờ vào scoring.
- Không gọi accounts / orders / positions / trading-token / OTP.
- Không in key / secret / chữ ký.
- Mọi số realtime gắn nhãn ``basis=live`` và UI phải ghi "tạm tính".
"""
from __future__ import annotations

import asyncio
import logging
import math
import os
import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Iterator, Literal

from stockai.api.session_clock import (
    ICT,
    SessionSnapshot,
    resolve_session,
    sessions_behind,
)

_log = logging.getLogger(__name__)

MAX_STREAMS_PER_CONN = 200
DEFAULT_HEARTBEAT = 25.0
STALE_AFTER_SEC = 90.0
CANDLE_MAX_BARS = 400  # ~1 phiên phút

# Bảo vệ đơn vị giá (017a-fix / 017a-fix2)
# Auto-scale: nearest power-of-10 từ tick/snapshot_close (KHÔNG dùng prev_close %).
AUTO_SCALE_LOG10_TOL = 0.35  # |log10(r)-round| ≤ 0.35 ≈ 0.45×–2.2× quanh 10^k
DROP_REL_BAND = 0.30  # khi có giá tham chiếu hợp lệ (tick | snapshot tươi)
DROP_REL_BAND_WIDE = 0.60  # khi chưa có ref — so snapshot_close (rộng hơn)
AUTO_LOCK_MIN_SYMBOLS = 20
AUTO_LOCK_MAJORITY = 0.90
DROP_WINDOW_SEC = 60.0
DROP_SYMBOL_FRAC = 0.05  # >5% mã bị drop trong 1 phút → unit_mismatch
UNIT_MISMATCH_LABEL = "Đơn vị giá lệch — đang dùng giá đóng cửa EOD"
NO_REF_LABEL = "chưa có giá tham chiếu"

PrevCloseSource = Literal["tick", "snapshot", "none"]


@dataclass
class QuoteTick:
    symbol: str
    price: float | None
    prev_close: float | None = None
    prev_close_source: PrevCloseSource = "none"
    change: float | None = None
    change_pct: float | None = None
    volume: float | None = None  # cumulative day volume
    high: float | None = None
    low: float | None = None
    ts: str | None = None
    state: str = "closed"  # live | stale | closed | no_realtime
    basis: str = "eod"  # live | eod
    source: str = "snapshot"


@dataclass
class MinuteBar:
    t: int  # epoch minute
    o: float
    h: float
    l: float
    c: float
    v: float = 0.0


@dataclass
class SymbolViewRef:
    """Refcount SSE — unsubscribe khi về 0 và mã ngoài liquid set."""

    count: int = 0


class FakeStream:
    """Luồng giả cho test — đẩy tick theo thứ tự, không mạng."""

    def __init__(self) -> None:
        self._queue: deque[dict[str, Any]] = deque()
        self._lock = threading.Lock()
        self.connected = False
        self.disconnected = False

    def push(self, event: dict[str, Any]) -> None:
        with self._lock:
            self._queue.append(event)

    def connect(self) -> None:
        self.connected = True
        self.disconnected = False

    def disconnect(self) -> None:
        self.connected = False
        self.disconnected = True

    def drain(self) -> list[dict[str, Any]]:
        with self._lock:
            out = list(self._queue)
            self._queue.clear()
            return out


class RealtimeHub:
    """Bộ nhớ giá phiên + (tuỳ chọn) kết nối DNSE nền.

    Khi ``enabled=False`` / thiếu key / lỗi kết nối → dùng SnapshotQuoteProvider,
    ``state=no_realtime``, API không crash.
    """

    def __init__(
        self,
        store: Any,
        cfg: dict[str, Any] | None = None,
        *,
        fake_stream: FakeStream | None = None,
        now_fn: Callable[[], datetime] | None = None,
    ) -> None:
        rt = dict((cfg or {}).get("realtime") or {})
        self._store = store
        self._cfg = rt
        self.enabled = bool(rt.get("enabled", True))
        self.max_symbols = int(rt.get("max_symbols") or 250)
        self.max_per_conn = int(rt.get("max_per_connection") or MAX_STREAMS_PER_CONN)
        self.stale_after = float(rt.get("stale_after_sec") or STALE_AFTER_SEC)
        self._fake = fake_stream
        self._now_fn = now_fn or (lambda: datetime.now(ICT))

        # price_scale: số cố định (khoá ngay) hoặc "auto" (bình chọn rồi khoá)
        raw_scale = rt.get("price_scale", 1000)
        self._auto_scale = isinstance(raw_scale, str) and raw_scale.strip().lower() == "auto"
        if self._auto_scale:
            self._price_scale_effective: float | None = None
            self._scale_locked = False
            self.price_scale = 1.0  # tạm; chỉ dùng sau khi khoá
        else:
            try:
                self._price_scale_effective = float(raw_scale if raw_scale is not None else 1000)
            except (TypeError, ValueError):
                self._price_scale_effective = 1000.0
            self._scale_locked = True
            self.price_scale = self._price_scale_effective

        self._lock = threading.RLock()
        self._quotes: dict[str, QuoteTick] = {}
        # snapshot_close: luôn có (để auto-scale / drop rộng) — KHÔNG đồng nghĩa prev_close %.
        self._snapshot_close: dict[str, float] = {}
        # Giá tham chiếu từ DNSE SecurityDefinition.basicPrice (ưu tiên cao nhất).
        self._tick_prev_close: dict[str, float] = {}
        self._snapshot_asof: str | None = getattr(store, "asof", None)
        self._candles: dict[str, deque[MinuteBar]] = defaultdict(
            lambda: deque(maxlen=CANDLE_MAX_BARS)
        )
        self._view_refs: dict[str, int] = defaultdict(int)
        self._liquid: set[str] = set()
        self._subscribed: set[str] = set()
        self._mode = "no_realtime"  # live | snapshot | no_realtime | unit_mismatch
        self._last_error: str | None = None
        self._dnse_session_phase: str | None = None
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._started = False
        self._index_ok = False  # market_index channel — chưa đo
        self._session_channel_ok = False
        self._sec_def_ok = False
        self._scale_votes: dict[str, float] = {}  # symbol → scale bình chọn (tick đầu)
        self._dropped_ticks = 0
        self._drop_events: deque[tuple[float, str]] = deque()  # (monotonic_ts, symbol)
        self._last_tick_mono: float | None = None
        self._stats: dict[str, Any] = {
            "ticks": 0,
            "reconnects": 0,
            "symbols_subscribed": 0,
            "dropped_ticks": 0,
            "measured": False,  # ngoài giờ / chưa chạy probe → False
        }

        self._seed_from_snapshots()

    # ------------------------------------------------------------------ ref / asof
    def _sessions_behind(self) -> int | None:
        asof = getattr(self._store, "asof", None) or self._snapshot_asof
        return sessions_behind(asof, self._now_fn())

    def _snapshot_is_fresh(self) -> bool:
        """Snapshot trùng phiên đóng gần nhất → được dùng làm giá tham chiếu %."""
        behind = self._sessions_behind()
        return behind is not None and behind == 0

    def _resolve_prev(self, symbol: str) -> tuple[float | None, PrevCloseSource]:
        """Ưu tiên: (a) basicPrice/tick → (b) snapshot tươi → (c) none."""
        tick_pc = self._tick_prev_close.get(symbol)
        if tick_pc is not None and tick_pc != 0:
            return float(tick_pc), "tick"
        if self._snapshot_is_fresh():
            snap = self._snapshot_close.get(symbol)
            if snap is not None and snap != 0:
                return float(snap), "snapshot"
        return None, "none"

    def _set_tick_prev(self, symbol: str, value: float) -> None:
        if value <= 0:
            return
        self._tick_prev_close[symbol] = float(value)

    def _hub_prev_close_source(self) -> PrevCloseSource:
        """Nguồn tham chiếu tổng hợp cho /status (ưu tiên tick nếu đã có)."""
        if self._tick_prev_close:
            return "tick"
        if self._snapshot_is_fresh():
            return "snapshot"
        return "none"

    # ------------------------------------------------------------------ seed
    def _seed_from_snapshots(self) -> None:
        """Nạp snapshot_close + (nếu tươi) prev_close cho nhóm liquid."""
        try:
            from stockai.contracts.helpers import quality_tier

            tickers = list(self._store.list_tickers())
        except Exception as exc:  # noqa: BLE001
            _log.warning("realtime seed: %s", type(exc).__name__)
            return

        self._snapshot_asof = getattr(self._store, "asof", None)
        fresh = self._snapshot_is_fresh()

        liquid: list[str] = []
        for t in tickers:
            try:
                snap = self._store.load_snapshot(t)
                tier = quality_tier(snap)
            except Exception:  # noqa: BLE001
                continue
            if tier not in ("full", "limited"):
                continue
            liquid.append(t)
            rows = ((snap.get("prices") or {}).get("rows") or []) if isinstance(snap, dict) else []
            if not rows:
                continue
            last = rows[-1]
            try:
                close = float(last.get("close"))
            except (TypeError, ValueError):
                continue
            self._snapshot_close[t] = close
            # high/low/volume ngày từ nến EOD cuối nếu có
            high = last.get("high")
            low = last.get("low")
            vol = last.get("volume")
            try:
                high_f = float(high) if high is not None else close
            except (TypeError, ValueError):
                high_f = close
            try:
                low_f = float(low) if low is not None else close
            except (TypeError, ValueError):
                low_f = close
            try:
                vol_f = float(vol) if vol is not None else None
            except (TypeError, ValueError):
                vol_f = None
            ts = str(last.get("date") or self._store.asof)
            if fresh:
                prev, src = close, "snapshot"
                chg, chg_pct = 0.0, 0.0
            else:
                prev, src = None, "none"
                chg, chg_pct = None, None
            self._quotes[t] = QuoteTick(
                symbol=t,
                price=close,
                prev_close=prev,
                prev_close_source=src,  # type: ignore[arg-type]
                change=chg,
                change_pct=chg_pct,
                volume=vol_f,
                high=high_f,
                low=low_f,
                ts=ts,
                state="closed",
                basis="eod",
                source="snapshot",
            )

        liquid = sorted(set(liquid))[: self.max_symbols]
        self._liquid = set(liquid)
        self._stats["liquid_count"] = len(self._liquid)

    # ------------------------------------------------------------------ lifecycle
    def start(self) -> None:
        if self._started:
            return
        self._started = True
        if self._fake is not None:
            self._mode = "live"
            self._fake.connect()
            self._thread = threading.Thread(
                target=self._fake_loop, name="stockai-rt-fake", daemon=True
            )
            self._thread.start()
            return
        if not self.enabled:
            self._mode = "no_realtime"
            _log.info("realtime disabled (realtime.enabled=false)")
            return
        key = os.environ.get("DNSE_API_KEY")
        secret = os.environ.get("DNSE_API_SECRET_KEY") or os.environ.get("DNSE_API_SECRET")
        if not key or not secret:
            self._mode = "no_realtime"
            self._last_error = "missing_dnse_credentials"
            _log.info("realtime degrade: thiếu DNSE credentials (không in giá trị)")
            return
        self._thread = threading.Thread(
            target=self._dnse_loop, name="stockai-rt-dnse", daemon=True
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._fake is not None:
            self._fake.disconnect()

    def _fake_loop(self) -> None:
        assert self._fake is not None
        while not self._stop.is_set():
            for ev in self._fake.drain():
                self._ingest_event(ev)
            if self._fake.disconnected:
                self._mode = "no_realtime"
                self._last_error = "fake_disconnected"
            time.sleep(0.05)

    def _dnse_loop(self) -> None:
        """Vòng asyncio trong thread nền; reconnect backoff."""
        backoff = 1.0
        while not self._stop.is_set():
            try:
                asyncio.run(self._dnse_session())
                backoff = 1.0
            except Exception as exc:  # noqa: BLE001
                self._mode = "no_realtime"
                self._last_error = type(exc).__name__
                self._stats["reconnects"] = int(self._stats.get("reconnects") or 0) + 1
                _log.warning("realtime DNSE lỗi (degrade): %s", type(exc).__name__)
            if self._stop.wait(backoff):
                break
            backoff = min(backoff * 2.0, 60.0)

    async def _dnse_session(self) -> None:
        """Kết nối DNSE — chỉ market data (trades + tuỳ chọn index/session)."""
        # Ép tắt DEBUG để SDK không in header/chữ ký
        os.environ["DEBUG"] = "false"
        from dnse import TradingClient

        api_key = os.environ["DNSE_API_KEY"]
        api_secret = os.environ.get("DNSE_API_SECRET_KEY") or os.environ["DNSE_API_SECRET"]
        # Không log key
        symbols = self._desired_symbols()
        chunks = [
            symbols[i : i + self.max_per_conn]
            for i in range(0, len(symbols), self.max_per_conn)
        ]
        if not chunks:
            self._mode = "no_realtime"
            return

        clients: list[Any] = []

        async def one(chunk: list[str], first: bool) -> None:
            client = TradingClient(
                api_key=api_key,
                api_secret=api_secret,
                encoding="json",
                auto_reconnect=False,
                heartbeat_interval=DEFAULT_HEARTBEAT,
                timeout=30.0,
            )
            clients.append(client)

            def on_trade(trade: Any) -> None:
                # Truyền matchPrice thô — hub nhân price_scale (cố định hoặc auto).
                # Trade DNSE không có basicPrice/prev_close (xem SecurityDefinition).
                try:
                    sym = str(getattr(trade, "symbol", None) or "").upper()
                    mp = getattr(trade, "match_price", None)
                    if mp is None:
                        mp = getattr(trade, "matchPrice", None)
                    vol = getattr(trade, "total_volume_traded", None)
                    if vol is None:
                        vol = getattr(trade, "totalVolumeTraded", None)
                    high = getattr(trade, "highest_price", None) or getattr(
                        trade, "highestPrice", None
                    )
                    low = getattr(trade, "lowest_price", None) or getattr(
                        trade, "lowestPrice", None
                    )
                    self._ingest_event(
                        {
                            "T": "t",
                            "symbol": sym,
                            "price": float(mp) if mp is not None else None,
                            "volume": float(vol) if vol is not None else None,
                            "high": float(high) if high is not None else None,
                            "low": float(low) if low is not None else None,
                        }
                    )
                except Exception:  # noqa: BLE001
                    pass

            def on_sec_def(sec: Any) -> None:
                # SecurityDefinition.basicPrice = giá tham chiếu phiên (DNSE SDK thật).
                try:
                    sym = str(getattr(sec, "symbol", None) or "").upper()
                    bp = getattr(sec, "basicPrice", None)
                    if bp is None:
                        bp = getattr(sec, "basic_price", None)
                    if sym and bp is not None:
                        self._ingest_event(
                            {
                                "T": "sec_def",
                                "symbol": sym,
                                "basicPrice": float(bp),
                            }
                        )
                except Exception:  # noqa: BLE001
                    pass

            await client.connect()
            await client.subscribe_trades(chunk, on_trade=on_trade, board_id="G1", encoding="json")
            try:
                await client.subscribe_sec_def(
                    chunk, on_sec_def=on_sec_def, board_id="G1", encoding="json"
                )
                self._sec_def_ok = True
            except Exception:  # noqa: BLE001
                self._sec_def_ok = False
            if first:
                # Thử index/session — nếu entitlement lỗi thì bỏ qua (không crash)
                try:
                    await client.subscribe_market_index(
                        market_index="VNINDEX", encoding="json"
                    )
                    self._index_ok = True
                except Exception:  # noqa: BLE001
                    self._index_ok = False
                try:
                    await client.subscribe_session(
                        product_group_id="STO", board_id="G1", encoding="json"
                    )
                    self._session_channel_ok = True
                except Exception:  # noqa: BLE001
                    self._session_channel_ok = False

            self._mode = "live"
            with self._lock:
                self._subscribed |= set(chunk)
                self._stats["symbols_subscribed"] = len(self._subscribed)

            while not self._stop.is_set():
                await asyncio.sleep(0.5)
                # đồng bộ subscribe khi có mã đang xem ngoài liquid
                desired = set(self._desired_symbols())
                missing = [s for s in desired if s not in self._subscribed]
                if missing and len(self._subscribed) < self.max_symbols:
                    add = missing[: max(0, self.max_per_conn - len(chunk))]
                    if add:
                        try:
                            await client.subscribe_trades(
                                add, on_trade=on_trade, board_id="G1", encoding="json"
                            )
                            with self._lock:
                                self._subscribed |= set(add)
                        except Exception:  # noqa: BLE001
                            pass

        try:
            await asyncio.gather(
                *[one(c, i == 0) for i, c in enumerate(chunks)]
            )
        finally:
            for c in clients:
                try:
                    await c.disconnect()
                except Exception:  # noqa: BLE001
                    pass

    def _desired_symbols(self) -> list[str]:
        with self._lock:
            viewed = {s for s, n in self._view_refs.items() if n > 0}
            combined = sorted(self._liquid | viewed)
        return combined[: self.max_symbols]

    # ------------------------------------------------------------------ scale / drop
    @staticmethod
    def _power10_scale(raw: float, snapshot_close: float) -> float | None:
        """Scale = 10^(-round(log10(raw/snapshot_close))) khi gần lũy thừa 10.

        Dùng ``snapshot_close`` (không phải prev_close %) — chịu được snapshot lệch vài
        phiên và giá dịch ±20%. Tol 0.35 ≈ khoảng 0.45×–2.2× quanh 10^k.
        """
        if raw <= 0 or snapshot_close <= 0:
            return None
        r = raw / snapshot_close
        if r <= 0:
            return None
        lg = math.log10(r)
        k = int(round(lg))
        if abs(lg - k) > AUTO_SCALE_LOG10_TOL:
            return None
        return float(10.0 ** (-k))

    def _maybe_lock_scale(self) -> None:
        """Khoá scale hệ thống khi ≥20 mã đồng thuận và đa số ≥90%."""
        if self._scale_locked or not self._auto_scale:
            return
        votes = list(self._scale_votes.values())
        if len(votes) < AUTO_LOCK_MIN_SYMBOLS:
            return
        counts: dict[float, int] = defaultdict(int)
        for v in votes:
            counts[v] += 1
        winner, n = max(counts.items(), key=lambda kv: kv[1])
        if n / len(votes) < AUTO_LOCK_MAJORITY:
            return
        self._price_scale_effective = float(winner)
        self.price_scale = float(winner)
        self._scale_locked = True
        # Chỉ log scale đã chọn — không log giá / mã / bí mật
        _log.info("realtime price_scale locked: %s", winner)

    def _record_drop(self, symbol: str) -> None:
        now = time.monotonic()
        self._dropped_ticks += 1
        self._stats["dropped_ticks"] = self._dropped_ticks
        self._drop_events.append((now, symbol))
        cutoff = now - DROP_WINDOW_SEC
        while self._drop_events and self._drop_events[0][0] < cutoff:
            self._drop_events.popleft()
        dropped_syms = {s for _, s in self._drop_events}
        denom = max(
            len(self._subscribed) or len(self._liquid) or 1,
            1,
        )
        if len(dropped_syms) / denom > DROP_SYMBOL_FRAC:
            if self._mode != "unit_mismatch":
                self._mode = "unit_mismatch"
                self._last_error = "unit_mismatch"
                _log.warning("realtime state=unit_mismatch (dropped symbols ratio)")

    def _scale_raw(
        self, symbol: str, raw: float
    ) -> tuple[float | None, bool]:
        """Nhân scale hiệu lực; trả (scaled_or_None, dropped).

        Auto chưa khoá: bình chọn từ tick/snapshot_close (power-of-10), chưa hiển thị live.
        Drop 30% khi có prev_close hợp lệ; không thì 60% so snapshot_close.
        """
        snap = self._snapshot_close.get(symbol)
        prev, src = self._resolve_prev(symbol)
        if self._auto_scale and not self._scale_locked:
            if symbol not in self._scale_votes and snap is not None and snap != 0:
                picked = self._power10_scale(raw, snap)
                if picked is not None:
                    self._scale_votes[symbol] = picked
                    self._maybe_lock_scale()
            if not self._scale_locked:
                return None, False  # giữ EOD đến khi khoá
            scale = self._price_scale_effective
        else:
            scale = self._price_scale_effective
        if scale is None:
            return None, False
        scaled = raw * float(scale)
        if src in ("tick", "snapshot") and prev is not None and prev != 0:
            if abs(scaled / prev - 1.0) > DROP_REL_BAND:
                self._record_drop(symbol)
                return None, True
        elif snap is not None and snap != 0:
            if abs(scaled / snap - 1.0) > DROP_REL_BAND_WIDE:
                self._record_drop(symbol)
                return None, True
        return scaled, False

    # ------------------------------------------------------------------ ingest
    def _ingest_event(self, ev: dict[str, Any]) -> None:
        kind = ev.get("T") or ev.get("type")
        if kind in ("s", "session"):
            phase = str(ev.get("phase") or ev.get("status") or "")
            if phase:
                self._dnse_session_phase = phase
            return
        if kind in ("sec_def", "security_definition"):
            sym = str(ev.get("symbol") or "").upper()
            bp = ev.get("basicPrice")
            if bp is None:
                bp = ev.get("basic_price")
            if bp is None:
                bp = ev.get("prev_close")
            if sym and bp is not None:
                try:
                    with self._lock:
                        self._set_tick_prev(sym, float(bp))
                        q = self._quotes.get(sym)
                        if q is not None:
                            prev, src = self._resolve_prev(sym)
                            q.prev_close = prev
                            q.prev_close_source = src
                            if prev is not None and q.price is not None and prev != 0:
                                q.change = q.price - prev
                                q.change_pct = (q.price - prev) / prev * 100.0
                            else:
                                q.change = None
                                q.change_pct = None
                except (TypeError, ValueError):
                    pass
            return
        if kind in ("mi", "index"):
            # chỉ số — không áp price_scale cổ phiếu
            sym = str(ev.get("symbol") or "VNINDEX").upper()
            price = ev.get("price")
            if price is not None:
                self._apply_tick(
                    sym, float(price), volume=None, high=None, low=None, raw_scaled=True
                )
            return
        sym = str(ev.get("symbol") or "").upper()
        if not sym:
            return
        # Fake/test: cho phép đính basicPrice trên tick (Trade thật không có field này)
        bp = ev.get("basicPrice")
        if bp is None:
            bp = ev.get("basic_price")
        if bp is not None:
            try:
                with self._lock:
                    self._set_tick_prev(sym, float(bp))
            except (TypeError, ValueError):
                pass
        price = ev.get("price")
        if price is None:
            return
        self._apply_tick(
            sym,
            float(price),
            volume=ev.get("volume"),
            high=ev.get("high"),
            low=ev.get("low"),
            raw_scaled=False,
        )

    def _apply_tick(
        self,
        symbol: str,
        price: float,
        *,
        volume: float | None,
        high: float | None,
        low: float | None,
        raw_scaled: bool = False,
    ) -> None:
        sess = self.session_now()
        wall = self._now_fn()
        ts = wall.isoformat(timespec="seconds")
        with self._lock:
            if self._mode == "unit_mismatch":
                # Không cập nhật giá live; giữ EOD
                return

            prev, src = self._resolve_prev(symbol)
            scale = self._price_scale_effective
            snap = self._snapshot_close.get(symbol)

            if raw_scaled:
                scaled = price
                hi_s = float(high) if high is not None else None
                lo_s = float(low) if low is not None else None
            else:
                scaled_opt, dropped = self._scale_raw(symbol, price)
                if dropped or scaled_opt is None:
                    return
                scaled = scaled_opt
                sc = float(scale) if scale is not None else 1.0
                hi_s = float(high) * sc if high is not None else None
                lo_s = float(low) * sc if low is not None else None

            q = self._quotes.get(symbol)
            if q is None:
                q = QuoteTick(symbol=symbol, price=None)
            q.price = scaled
            q.prev_close = prev
            q.prev_close_source = src
            if prev is not None and prev != 0:
                q.change = scaled - prev
                q.change_pct = (scaled - prev) / prev * 100.0
            else:
                q.change = None
                q.change_pct = None
            if volume is not None:
                q.volume = float(volume)
            if hi_s is not None:
                q.high = hi_s
            elif q.high is None or scaled > (q.high or scaled):
                q.high = scaled if q.high is None else max(q.high, scaled)
            if lo_s is not None:
                q.low = lo_s
            elif q.low is None or scaled < (q.low or scaled):
                q.low = scaled if q.low is None else min(q.low, scaled)
            q.ts = ts
            if sess.phase == "closed":
                q.state = "closed"
                q.basis = "eod"
                q.source = "snapshot"
                # ngoài giờ: hiện đóng cửa snapshot (không bịa % từ giá cũ)
                if snap is not None and self._mode != "live":
                    q.price = snap
                if prev is not None and prev != 0 and q.price is not None:
                    q.change = q.price - prev
                    q.change_pct = (q.price - prev) / prev * 100.0
                else:
                    q.change = None
                    q.change_pct = None
            else:
                q.state = "live"
                q.basis = "live"
                q.source = "dnse" if self._fake is None else "fake"
            self._quotes[symbol] = q
            self._last_tick_mono = time.monotonic()
            self._stats["ticks"] = int(self._stats.get("ticks") or 0) + 1
            self._update_candle(symbol, scaled, volume)

    def _update_candle(self, symbol: str, price: float, volume: float | None) -> None:
        minute = int(time.time()) // 60
        bars = self._candles[symbol]
        if bars and bars[-1].t == minute:
            b = bars[-1]
            b.h = max(b.h, price)
            b.l = min(b.l, price)
            b.c = price
            if volume is not None:
                b.v = float(volume)
        else:
            bars.append(
                MinuteBar(
                    t=minute,
                    o=price,
                    h=price,
                    l=price,
                    c=price,
                    v=float(volume or 0.0),
                )
            )

    # ------------------------------------------------------------------ views / SSE refcount
    def acquire_view(self, symbols: list[str]) -> None:
        with self._lock:
            for s in symbols:
                self._view_refs[s] += 1

    def release_view(self, symbols: list[str]) -> None:
        with self._lock:
            for s in symbols:
                if self._view_refs[s] > 0:
                    self._view_refs[s] -= 1
                if self._view_refs[s] <= 0:
                    self._view_refs.pop(s, None)
                    # ngoài liquid → có thể bỏ subscribe (DNSE loop sẽ sync)
                    if s not in self._liquid:
                        self._subscribed.discard(s)

    # ------------------------------------------------------------------ queries
    def session_now(self) -> SessionSnapshot:
        return resolve_session(
            self._now_fn(),
            dnse_phase=self._dnse_session_phase if self._session_channel_ok else None,
        )

    def status(self) -> dict[str, Any]:
        sess = self.session_now()
        behind = self._sessions_behind()
        asof = getattr(self._store, "asof", None) or self._snapshot_asof
        with self._lock:
            n_live = sum(1 for q in self._quotes.values() if q.state == "live")
            n_sub = len(self._subscribed) or len(self._liquid)
            age: float | None
            if self._last_tick_mono is None:
                age = None
            else:
                age = round(time.monotonic() - self._last_tick_mono, 3)
            label = UNIT_MISMATCH_LABEL if self._mode == "unit_mismatch" else "tạm tính"
            prev_src = self._hub_prev_close_source()
            return {
                "enabled": self.enabled,
                "mode": self._mode,
                "state": self._mode,
                "session": {
                    "phase": sess.phase,
                    "exchange": sess.exchange,
                    "is_trading_day": sess.is_trading_day,
                    "session_fraction": round(sess.session_fraction, 4),
                    "as_of_ts": sess.as_of_ts,
                    "source": "dnse" if self._session_channel_ok else "default_clock",
                },
                "symbols_subscribed": n_sub,
                "liquid_count": len(self._liquid),
                "viewing_count": sum(1 for n in self._view_refs.values() if n > 0),
                "quotes_live": n_live,
                "price_scale_effective": self._price_scale_effective,
                "dropped_ticks": self._dropped_ticks,
                "last_tick_age_seconds": age,
                "prev_close_source": prev_src,
                "snapshot_asof": asof,
                "sessions_behind": behind,
                "index_channel": "ok" if self._index_ok else "chưa đo",
                "session_channel": "ok" if self._session_channel_ok else "chưa đo",
                "sec_def_channel": "ok" if self._sec_def_ok else "chưa đo",
                "last_error": self._last_error,
                "stats": dict(self._stats),
                "label": label,
                "disclaimer_realtime": (
                    "Giá phiên chỉ để hiển thị và phân tích trong phiên (tạm tính). "
                    "Điểm M2–M7 dùng giá đóng cửa EOD."
                    if self._mode != "unit_mismatch"
                    else UNIT_MISMATCH_LABEL
                    + ". Điểm M2–M7 luôn dùng giá đóng cửa EOD."
                ),
            }

    def get_quote(self, symbol: str) -> QuoteTick:
        sess = self.session_now()
        with self._lock:
            q = self._quotes.get(symbol)
            if q is None:
                return QuoteTick(
                    symbol=symbol,
                    price=None,
                    state="no_realtime" if self._mode == "no_realtime" else "closed",
                    basis="eod",
                    source="snapshot",
                    prev_close_source="none",
                )
            # Làm mới nguồn tham chiếu (asof có thể đổi sau refresh_daily)
            prev, src = self._resolve_prev(symbol)
            snap = self._snapshot_close.get(symbol)
            out = QuoteTick(**q.__dict__)
            out.prev_close = prev
            out.prev_close_source = src
            unit_bad = self._mode == "unit_mismatch"
            # unit_mismatch / ngoài giờ → EOD snapshot (không so giá cũ để bịa %)
            if unit_bad:
                out.state = "unit_mismatch"
                out.basis = "eod"
                out.source = "snapshot"
                if snap is not None:
                    out.price = snap
                if prev is not None and prev != 0 and out.price is not None:
                    out.change = out.price - prev
                    out.change_pct = (out.price - prev) / prev * 100.0
                else:
                    out.change = None
                    out.change_pct = None
            elif sess.phase == "closed":
                out.state = "closed"
                out.basis = "eod"
                if snap is not None:
                    out.price = snap
                if prev is not None and prev != 0 and out.price is not None:
                    out.change = out.price - prev
                    out.change_pct = (out.price - prev) / prev * 100.0
                else:
                    out.change = None
                    out.change_pct = None
            elif self._mode == "no_realtime":
                out.state = "no_realtime"
                out.basis = "eod"
                if prev is not None and prev != 0 and out.price is not None:
                    out.change = out.price - prev
                    out.change_pct = (out.price - prev) / prev * 100.0
                else:
                    out.change = None
                    out.change_pct = None
            elif out.price is not None:
                if prev is not None and prev != 0:
                    out.change = out.price - prev
                    out.change_pct = (out.price - prev) / prev * 100.0
                else:
                    out.change = None
                    out.change_pct = None
            return out

    def get_quotes(self, symbols: list[str]) -> list[dict[str, Any]]:
        """Tương thích QuoteProvider — poll fallback."""
        items: list[dict[str, Any]] = []
        for s in symbols:
            q = self.get_quote(s)
            if q.state == "unit_mismatch":
                label: str | None = UNIT_MISMATCH_LABEL
            elif q.prev_close_source == "none":
                label = NO_REF_LABEL
            elif q.basis == "live":
                label = "tạm tính"
            else:
                label = None
            # UI: change_pct null → hiện "—"; kèm nhãn khi chưa có tham chiếu
            items.append(
                {
                    "symbol": q.symbol,
                    "price": q.price,
                    "prev_close": q.prev_close,
                    "prev_close_source": q.prev_close_source,
                    "change": q.change,
                    "change_pct": q.change_pct,
                    "volume": q.volume,
                    "high": q.high,
                    "low": q.low,
                    "ts": q.ts,
                    "state": q.state,
                    "basis": q.basis,
                    "source": q.source,
                    "label": label,
                    "ref_label": NO_REF_LABEL if q.prev_close_source == "none" else None,
                }
            )
        return items

    def iter_liquid_quotes(self) -> Iterator[QuoteTick]:
        with self._lock:
            syms = list(self._liquid)
        for s in syms:
            yield self.get_quote(s)

    def candles(self, symbol: str) -> list[dict[str, Any]]:
        with self._lock:
            bars = list(self._candles.get(symbol) or [])
        return [
            {"t": b.t, "o": b.o, "h": b.h, "l": b.l, "c": b.c, "v": b.v} for b in bars
        ]

    def push_fake(self, event: dict[str, Any]) -> None:
        """Test helper."""
        if self._fake is not None:
            self._fake.push(event)
        else:
            self._ingest_event(event)
