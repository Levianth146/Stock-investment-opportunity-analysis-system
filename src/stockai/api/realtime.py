"""RealtimeHub — giá phiên từ DNSE (display + phân tích tạm tính) hoặc snapshot.

Nguyên tắc cứng:
- M2–M7 chỉ dùng giá đóng cửa EOD; tick không bao giờ vào scoring.
- Không gọi accounts / orders / positions / trading-token / OTP.
- Không in key / secret / chữ ký.
- Mọi số realtime gắn nhãn ``basis=live`` và UI phải ghi "tạm tính".
"""
from __future__ import annotations

import asyncio
import json
import logging
import math
import os
import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
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
STALE_AFTER_SEC = 90.0  # hub: >90s không tick → stale (reason=no_ticks)
LIVE_TICK_MAX_AGE_SEC = 30.0  # live chỉ khi có ≥1 tick trong 30s (phiên liên tục)
DISPLAY_STALE_AFTER_SEC = 20.0  # UI từng mã: >20s không tick (theo receive monotonic)
SSE_COALESCE_SEC = 1.0  # tối đa 1 cập nhật/giây/mã/client
CANDLE_MAX_BARS = 400  # ~1 phiên phút
# Ghi phân bố T trong 60s đầu (để map sec_def / kênh lạ) — API nội bộ SDK.
T_DISTRIBUTION_WINDOW_SEC = 60.0
# SecurityDefinition trên wire: T="sd" (dnse-sdk-openapi 2.4.1 _MSG_TYPE_MAP).
SEC_DEF_MSG_TYPES = frozenset({"sd", "sec_def", "security_definition"})
# HOSE board G1: totalVolumeTraded trên T="t" là lot (1 lot = 10 CP).
# Đối chiếu live: hub_vol×10 ≈ grossTradeAmount(tỷ)×1e9 / matchPrice(VND), sai số <1%.
HOSE_LOT_SIZE = 10.0

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
CONNECTING_NO_TICKS_LABEL = "Đang kết nối — chưa nhận tick giá"
STALE_NO_TICKS_LABEL = "Luồng giá chậm — hơn 90 giây không có tick"
LIVE_LABEL = "trực tiếp (tạm tính)"

PrevCloseSource = Literal["tick", "snapshot", "none"]
# live | connecting | stale | closed | no_realtime | unit_mismatch | snapshot
HubMode = Literal[
    "live",
    "connecting",
    "stale",
    "closed",
    "no_realtime",
    "unit_mismatch",
    "snapshot",
]


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
        self._snapshot_prev_close: dict[str, float | None] = {}
        # Giá tham chiếu từ DNSE SecurityDefinition.basicPrice (ưu tiên cao nhất).
        self._tick_prev_close: dict[str, float] = {}
        self._snapshot_asof: str | None = getattr(store, "asof", None)
        self._candles: dict[str, deque[MinuteBar]] = defaultdict(
            lambda: deque(maxlen=CANDLE_MAX_BARS)
        )
        self._view_refs: dict[str, int] = defaultdict(int)
        self._liquid: set[str] = set()
        self._subscribed: set[str] = set()
        self._mode: HubMode = "no_realtime"
        # Lý do: disabled | missing_key | sdk_missing | connect_error:<code>
        # | no_ticks_yet | no_ticks — không chứa secrets
        self._degrade_reason: str | None = None
        self._last_error: str | None = None
        self._dnse_session_phase: str | None = None
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._started = False
        self._ws_connected = False
        self._connected_mono: float | None = None
        self._index_ok = False  # market_index channel — chưa đo
        self._session_channel_ok = False
        self._sec_def_ok = False
        self._scale_votes: dict[str, float] = {}  # symbol → scale bình chọn (tick đầu)
        self._dropped_ticks = 0
        self._drop_events: deque[tuple[float, str]] = deque()  # (monotonic_ts, symbol)
        self._last_tick_mono: float | None = None
        # Thời điểm nhận tick theo monotonic — staleness UI theo receive, không theo clock trình duyệt
        self._receive_mono: dict[str, float] = {}
        self._traded_session: set[str] = set()  # mã đã khớp trong phiên hiện tại
        self._index_quotes: dict[str, QuoteTick] = {}  # VNINDEX / VN30 / …
        # GTGD chỉ số (tỷ VND) từ mi.grossTradeAmount — không nằm trên QuoteTick
        self._index_value: dict[str, float] = {}
        # Log mỗi loại lỗi parse đúng một lần (exception class + thiếu field)
        self._logged_parse_errors: set[str] = set()
        self._mi_fields_logged = False  # log tên field T=mi đúng một lần
        self._volume_unit: str = "shares"  # sau khi chuẩn hoá lot→CP
        self._volume_scale: float = HOSE_LOT_SIZE  # hệ số lot→CP (STO/HOSE)
        self._t_dist_deadline: float | None = None
        self._stats: dict[str, Any] = {
            "ticks": 0,
            "raw_msgs": 0,
            "parsed_trades": 0,
            "parsed_index": 0,
            "parse_errors": 0,
            "msg_types": {},  # T → count (API nội bộ SDK)
            "reconnects": 0,
            "symbols_subscribed": 0,
            "dropped_ticks": 0,
            "measured": False,  # ngoài giờ / chưa chạy probe → False
            "last_parse_error": None,  # mô tả ngắn, không secrets
            "volume_unit": "shares",
            "volume_scale": HOSE_LOT_SIZE,
            "mi_fields": None,  # tên field T=mi (một lần)
        }

        # Lưu giá trong phiên (sống qua restart API). Tắt nếu không cấu hình persist_dir.
        pdir = rt.get("persist_dir")
        self._persist_dir: Path | None = None
        if pdir:
            pp = Path(str(pdir))
            if not pp.is_absolute():
                pp = Path(getattr(store, "root", None) or Path.cwd()) / pp
            self._persist_dir = pp
        self._persist_interval = float(rt.get("persist_interval_sec") or 15.0)
        self._persist_ticks = -1
        self._data_date: str | None = None  # ngày (ICT) của dữ liệu phiên đang giữ
        self._persist_thread: threading.Thread | None = None

        self._seed_from_snapshots()
        self._restore_intraday()

    # ------------------------------------------------------------------ ref / asof
    def _sessions_behind(self) -> int | None:
        asof = getattr(self._store, "asof", None) or self._snapshot_asof
        return sessions_behind(asof, self._now_fn())

    def _snapshot_is_fresh(self) -> bool:
        """Snapshot trùng phiên đóng gần nhất → được dùng làm giá tham chiếu %."""
        behind = self._sessions_behind()
        if behind is None:
            return False
        if behind == 0:
            return True
        # Sau giờ đóng cửa nhưng snapshot của phiên đó chưa có: snapshot (phiên trước đó)
        # chính là giá tham chiếu của phiên mà hub đang giữ dữ liệu.
        asof = str(getattr(self._store, "asof", None) or self._snapshot_asof or "")[:10]
        return behind == 1 and self._data_date is not None and self._data_date > asof

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
            try:
                self._snapshot_prev_close[t] = float(rows[-2].get("close")) if len(rows) > 1 else None
            except (TypeError, ValueError):
                self._snapshot_prev_close[t] = None
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

    def _ensure_dnse_env(self) -> tuple[str | None, str | None]:
        """Nạp DNSE_* từ ``<repo>/.env`` nếu thiếu trong environ. Không ghi đè, không log giá trị."""
        key = os.environ.get("DNSE_API_KEY")
        secret = os.environ.get("DNSE_API_SECRET_KEY") or os.environ.get("DNSE_API_SECRET")
        if key and secret:
            return key, secret
        from stockai.envfile import load_dotenv, repo_dotenv_path

        load_dotenv(
            repo_dotenv_path(),
            keys=("DNSE_API_KEY", "DNSE_API_SECRET_KEY", "DNSE_API_SECRET"),
        )
        key = os.environ.get("DNSE_API_KEY")
        secret = os.environ.get("DNSE_API_SECRET_KEY") or os.environ.get("DNSE_API_SECRET")
        return key, secret

    # ------------------------------------------------------------------ lifecycle
    def start(self) -> None:
        if self._started:
            return
        self._started = True
        self._start_persist()
        if self._fake is not None:
            # Chưa có tick → connecting (không tuyên bố "live"/"trực tiếp")
            self._ws_connected = True
            self._connected_mono = time.monotonic()
            self._mode = "connecting"
            self._degrade_reason = "no_ticks_yet"
            self._fake.connect()
            self._thread = threading.Thread(
                target=self._fake_loop, name="stockai-rt-fake", daemon=True
            )
            self._thread.start()
            return
        if not self.enabled:
            self._mode = "no_realtime"
            self._degrade_reason = "disabled"
            self._last_error = "disabled"
            _log.info("realtime disabled (realtime.enabled=false)")
            _log.info("DNSE key loaded: no")
            return
        key, secret = self._ensure_dnse_env()
        has_key = bool(key and secret)
        # Chỉ yes/no — không in giá trị khóa
        _log.info("DNSE key loaded: %s", "yes" if has_key else "no")
        if not has_key:
            self._mode = "no_realtime"
            self._degrade_reason = "missing_key"
            self._last_error = "missing_dnse_credentials"
            return
        # Kiểm tra SDK trước khi mở thread (tránh vòng reconnect vô ích)
        try:
            import dnse  # noqa: F401
        except ImportError:
            self._mode = "no_realtime"
            self._degrade_reason = "sdk_missing"
            self._last_error = "sdk_missing"
            _log.info("realtime degrade: thiếu SDK dnse")
            return
        self._thread = threading.Thread(
            target=self._dnse_loop, name="stockai-rt-dnse", daemon=True
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._persist_save()
        if self._fake is not None:
            self._fake.disconnect()

    def _fake_loop(self) -> None:
        assert self._fake is not None
        while not self._stop.is_set():
            for ev in self._fake.drain():
                # Fake: cùng đường parse raw như wrap _dispatch_message
                self.handle_raw_message(ev)
            if self._fake.disconnected:
                self._ws_connected = False
                self._mode = "no_realtime"
                self._degrade_reason = "connect_error:fake_disconnected"
                self._last_error = "fake_disconnected"
            time.sleep(0.05)

    def _dnse_loop(self) -> None:
        """Vòng asyncio trong thread nền; reconnect backoff."""
        backoff = 1.0
        while not self._stop.is_set():
            try:
                asyncio.run(self._dnse_session())
                backoff = 1.0
            except ImportError:
                self._mode = "no_realtime"
                self._degrade_reason = "sdk_missing"
                self._last_error = "sdk_missing"
                _log.warning("realtime DNSE lỗi (degrade): sdk_missing")
                break
            except Exception as exc:  # noqa: BLE001
                code = type(exc).__name__
                # Không đưa message/exception args (có thể chứa secrets) vào reason
                self._mode = "no_realtime"
                self._degrade_reason = f"connect_error:{code}"
                self._last_error = code
                self._stats["reconnects"] = int(self._stats.get("reconnects") or 0) + 1
                _log.warning("realtime DNSE lỗi (degrade): %s", code)
            if self._stop.wait(backoff):
                break
            backoff = min(backoff * 2.0, 60.0)

    async def _dnse_session(self) -> None:
        """Kết nối DNSE — ingest raw dict qua wrap ``client._dispatch_message``.

        Dùng API nội bộ SDK (``_dispatch_message``) — đã xác nhận với probe
        (~27 msg/s, ``T="t"`` + ``matchPrice``). Ghim ``dnse-sdk-openapi==2.4.1``.
        Không dùng callback ``on_trade`` (Trade model dùng ``.price``, không
        có ``matchPrice`` attribute → ticks=0 nếu đọc sai field + nuốt lỗi).
        """
        # Ép tắt DEBUG để SDK không in header/chữ ký
        os.environ["DEBUG"] = "false"
        try:
            from dnse import TradingClient
        except ImportError:
            self._mode = "no_realtime"
            self._degrade_reason = "sdk_missing"
            self._last_error = "sdk_missing"
            raise

        api_key = os.environ["DNSE_API_KEY"]
        api_secret = os.environ.get("DNSE_API_SECRET_KEY") or os.environ["DNSE_API_SECRET"]
        # Không log key
        symbols = self._desired_symbols()
        # Hạn mức DNSE: tối đa max_per_conn kênh / kết nối (trades + sec_def + index + session).
        # Kết nối đầu dành 2 kênh cho index + session → bớt 2 mã trade.
        first_n = max(1, self.max_per_conn - 2)
        chunks = [symbols[:first_n]] if symbols else []
        rest = symbols[first_n:]
        chunks += [
            rest[i : i + self.max_per_conn]
            for i in range(0, len(rest), self.max_per_conn)
        ]
        if not chunks:
            self._mode = "no_realtime"
            self._degrade_reason = self._degrade_reason or "connect_error:no_symbols"
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

            # --- Wrap _dispatch_message (API nội bộ SDK 2.4.1) ---
            orig_dispatch = client._dispatch_message

            async def tracked_dispatch(data: dict[str, Any]) -> None:
                try:
                    if isinstance(data, dict):
                        self.handle_raw_message(data)
                except Exception as exc:  # noqa: BLE001
                    self._note_parse_error(type(exc).__name__, ())
                await orig_dispatch(data)

            client._dispatch_message = tracked_dispatch  # type: ignore[method-assign]

            await client.connect()
            # Không truyền on_trade/on_sec_def — ingest từ raw dict ở trên
            if first:
                # Ưu tiên chỉ số + phiên trước khi chiếm hạn mức bằng trades
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
            await client.subscribe_trades(chunk, board_id="G1", encoding="json")
            # sec_def chỉ khi còn hạn mức kênh (2*len + index/session <= max)
            extras = 2 if first else 0
            if len(chunk) * 2 + extras <= self.max_per_conn:
                try:
                    await client.subscribe_sec_def(chunk, board_id="G1", encoding="json")
                    self._sec_def_ok = True
                except Exception:  # noqa: BLE001
                    self._sec_def_ok = self._sec_def_ok or False

            self._ws_connected = True
            self._connected_mono = time.monotonic()
            self._t_dist_deadline = self._connected_mono + T_DISTRIBUTION_WINDOW_SEC
            # Chưa có tick → connecting (không tuyên bố live)
            self._mode = "connecting"
            self._degrade_reason = "no_ticks_yet"
            with self._lock:
                self._subscribed |= set(chunk)
                self._stats["symbols_subscribed"] = len(self._subscribed)

            while not self._stop.is_set():
                await asyncio.sleep(0.5)
                # Cập nhật mode trung thực theo tuổi tick
                self._refresh_honest_mode()
                desired = set(self._desired_symbols())
                missing = [s for s in desired if s not in self._subscribed]
                if missing and len(self._subscribed) < self.max_symbols:
                    add = missing[: max(0, self.max_per_conn - len(chunk))]
                    if add:
                        try:
                            await client.subscribe_trades(
                                add, board_id="G1", encoding="json"
                            )
                            with self._lock:
                                self._subscribed |= set(add)
                                self._stats["symbols_subscribed"] = len(self._subscribed)
                        except Exception as exc:  # noqa: BLE001
                            self._note_parse_error(
                                f"subscribe:{type(exc).__name__}", ()
                            )

        try:
            await asyncio.gather(
                *[one(c, i == 0) for i, c in enumerate(chunks)]
            )
        finally:
            self._ws_connected = False
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

    # ------------------------------------------------------------------ raw WS ingest (probe-style)
    def _note_parse_error(self, kind: str, missing: tuple[str, ...] | list[str]) -> None:
        """Đếm lỗi + log mỗi loại đúng một lần (không secrets)."""
        miss = tuple(sorted(str(m) for m in missing if m))
        key = f"{kind}|{','.join(miss)}"
        with self._lock:
            self._stats["parse_errors"] = int(self._stats.get("parse_errors") or 0) + 1
            desc = kind if not miss else f"{kind} missing={','.join(miss)}"
            self._stats["last_parse_error"] = desc
        if key not in self._logged_parse_errors:
            self._logged_parse_errors.add(key)
            _log.warning("realtime parse: %s", desc)

    def _bump_msg_type(self, t_val: str | None) -> None:
        key = str(t_val) if t_val is not None else "_none"
        with self._lock:
            mt = self._stats.setdefault("msg_types", {})
            if not isinstance(mt, dict):
                mt = {}
                self._stats["msg_types"] = mt
            mt[key] = int(mt.get(key) or 0) + 1

    def handle_raw_message(self, data: dict[str, Any]) -> None:
        """Ingest dict thô từ WS (``T`` / ``matchPrice``…) — giống probe.

        Gọi từ wrap ``_dispatch_message`` hoặc FakeStream. Không nuốt lỗi.
        """
        with self._lock:
            self._stats["raw_msgs"] = int(self._stats.get("raw_msgs") or 0) + 1

        action = data.get("action") or data.get("a")
        msg_type = data.get("T")
        if msg_type is not None or action in (None, ""):
            self._bump_msg_type(str(msg_type) if msg_type is not None else None)

        if msg_type is None and action:
            # Chẩn đoán: đếm action + giữ mẫu ack/error (cắt ngắn)
            with self._lock:
                ac = self._stats.setdefault("actions", {})
                ac[str(action)] = int(ac.get(str(action)) or 0) + 1
                s_ = str(data)
                if action in ("error", "subscribed") and (
                    action == "error" or "market_index" in s_ or "session" in s_
                ):
                    self._stats.setdefault("action_samples", {})[str(action)] = s_[:300]

        # Ping/pong / subscribed — bỏ qua parse thị trường
        if action in ("ping", "pong", "subscribed", "auth", "error"):
            return

        if msg_type == "t":
            self._parse_raw_trade(data)
            return
        if msg_type in SEC_DEF_MSG_TYPES or (
            msg_type is not None
            and "basicPrice" in data
            and data.get("symbol")
            and msg_type not in ("t", "mi", "s")
        ):
            # T="sd" (SDK 2.4.1); cũng nhận sec_def / dict có basicPrice trong cửa sổ map
            self._parse_raw_sec_def(data, msg_type=str(msg_type) if msg_type else "sd")
            return
        if msg_type in ("mi", "index"):
            self._parse_raw_index(data)
            return
        if msg_type in ("s", "session"):
            self._parse_raw_session(data)
            return
        # Trong 60s đầu: chỉ đếm T lạ (đã bump); sau đó bỏ qua lặng lẽ
        if (
            msg_type is not None
            and self._t_dist_deadline is not None
            and time.monotonic() < self._t_dist_deadline
        ):
            return

    def _parse_raw_trade(self, data: dict[str, Any]) -> None:
        missing: list[str] = []
        sym = str(data.get("symbol") or data.get("Symbol") or "").upper()
        if not sym:
            missing.append("symbol")
        mp = data.get("matchPrice")
        if mp is None:
            mp = data.get("price")  # fake/test đã scale sẵn
        if mp is None:
            missing.append("matchPrice")
        if missing:
            self._note_parse_error("KeyError", missing)
            return
        try:
            price = float(mp)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            self._note_parse_error("ValueError", ("matchPrice",))
            return
        # totalVolumeTraded = KL luỹ kế phiên (lot HOSE) → × HOSE_LOT_SIZE ra CP.
        # Field "volume" (fake/test) coi là đã là cổ phiếu — không nhân lot.
        # Không cộng dồn từ lúc hub start: luôn lấy cumulative DNSE.
        raw_tvt = data.get("totalVolumeTraded")
        raw_vol_field = data.get("volume")
        vol_already_shares = bool(
            raw_tvt is None
            or data.get("volume_unit") == "shares"
            or data.get("_volume_shares")
            or data.get("volume_scale") == 1
        )
        vol = raw_tvt if raw_tvt is not None else raw_vol_field
        high = data.get("highestPrice")
        if high is None:
            high = data.get("high")
        low = data.get("lowestPrice")
        if low is None:
            low = data.get("low")
        # Fake/test: basicPrice trên tick
        bp = data.get("basicPrice")
        if bp is None:
            bp = data.get("basic_price")
        if bp is not None:
            try:
                with self._lock:
                    self._set_tick_prev(sym, float(bp))
            except (TypeError, ValueError):
                self._note_parse_error("ValueError", ("basicPrice",))
        try:
            vol_f: float | None
            if vol is None:
                vol_f = None
            else:
                raw_vol = float(vol)
                # Lot → cổ phiếu (khớp snapshot EOD / grossTradeAmount)
                if vol_already_shares:
                    vol_f = raw_vol
                else:
                    vol_f = raw_vol * float(self._volume_scale)
            self._apply_tick(
                sym,
                price,
                volume=vol_f,
                high=float(high) if high is not None else None,
                low=float(low) if low is not None else None,
                raw_scaled=False,
            )
            with self._lock:
                self._stats["parsed_trades"] = int(self._stats.get("parsed_trades") or 0) + 1
        except Exception as exc:  # noqa: BLE001
            self._note_parse_error(type(exc).__name__, ())

    def _parse_raw_sec_def(self, data: dict[str, Any], *, msg_type: str) -> None:
        missing: list[str] = []
        sym = str(data.get("symbol") or "").upper()
        if not sym:
            missing.append("symbol")
        bp = data.get("basicPrice")
        if bp is None:
            bp = data.get("basic_price")
        if bp is None:
            bp = data.get("prev_close")
        if bp is None:
            missing.append("basicPrice")
        if missing:
            self._note_parse_error("KeyError", missing)
            return
        try:
            with self._lock:
                self._set_tick_prev(sym, float(bp))  # type: ignore[arg-type]
                self._sec_def_ok = True
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
            _log.info(
                "realtime sec_def mapped: T=%s → basicPrice (prev_close_source=tick)",
                msg_type,
            )
        except (TypeError, ValueError):
            self._note_parse_error("ValueError", ("basicPrice",))

    def _parse_raw_index(self, data: dict[str, Any]) -> None:
        """MarketIndex T=\"mi\" (SDK 2.4.1) — valueIndexes / priorValueIndexes / indexName.

        Log tên field đúng một lần (không secrets). Nến 1 phút trong RAM.
        """
        if not self._mi_fields_logged:
            keys = sorted(str(k) for k in data.keys())
            self._mi_fields_logged = True
            with self._lock:
                self._stats["mi_fields"] = keys
            _log.info("realtime mi fields (once): %s", ",".join(keys))

        # MarketIndex: valueIndexes / indexName (wire đã xác nhận 2026-10-15)
        sym = str(
            data.get("indexName") or data.get("symbol") or "VNINDEX"
        ).upper()
        if sym in ("VNINDEX", "VN-INDEX", "VN INDEX"):
            sym = "VNINDEX"
        price = data.get("valueIndexes")
        if price is None:
            price = data.get("price")
        if price is None:
            self._note_parse_error("KeyError", ("valueIndexes",))
            return
        prev = data.get("priorValueIndexes")
        if prev is None:
            prev = data.get("prev_close") or data.get("basicPrice")
        vol = data.get("totalVolumeTraded")
        gta = data.get("grossTradeAmount")
        try:
            self._apply_index_tick(
                sym,
                float(price),
                prev_close=float(prev) if prev is not None else None,
                volume=float(vol) if vol is not None else None,
                value=float(gta) if gta is not None else None,
            )
            with self._lock:
                self._stats["parsed_index"] = int(self._stats.get("parsed_index") or 0) + 1
        except (TypeError, ValueError):
            self._note_parse_error("ValueError", ("valueIndexes",))

    def _parse_raw_session(self, data: dict[str, Any]) -> None:
        # Session: eventId / tradingSessionId (SDK 2.4.1)
        phase = (
            data.get("eventId")
            or data.get("phase")
            or data.get("status")
            or data.get("tradingSessionId")
        )
        if phase is not None and str(phase).strip():
            self._dnse_session_phase = str(phase)
            self._session_channel_ok = True

    def _tick_age_sec(self) -> float | None:
        if self._last_tick_mono is None:
            return None
        return time.monotonic() - self._last_tick_mono

    def _silence_age_sec(self) -> float | None:
        """Tuổi im lặng: từ tick cuối, hoặc từ lúc connect nếu chưa có tick."""
        age = self._tick_age_sec()
        if age is not None:
            return age
        if self._connected_mono is not None:
            return time.monotonic() - self._connected_mono
        return None

    def _resolve_honest_mode(self) -> tuple[HubMode, str | None]:
        """live chỉ khi phiên liên tục + ≥1 tick trong 30s gần nhất."""
        if self._mode == "unit_mismatch":
            return "unit_mismatch", None
        if self._mode == "no_realtime" or (
            not self._ws_connected and self._fake is None
        ):
            return "no_realtime", self._degrade_reason
        if not self._ws_connected and self._fake is not None and self._fake.disconnected:
            return "no_realtime", self._degrade_reason or "connect_error:fake_disconnected"

        sess = self.session_now()
        silence = self._silence_age_sec()
        continuous = sess.phase == "continuous"
        recent = silence is not None and silence <= LIVE_TICK_MAX_AGE_SEC
        has_tick = self._last_tick_mono is not None

        if continuous and has_tick and recent:
            return "live", None
        if continuous:
            if silence is not None and silence > STALE_AFTER_SEC:
                return "stale", "no_ticks"
            return "connecting", "no_ticks_yet"
        # Ngoài phiên liên tục: không tuyên bố live
        if sess.phase == "closed":
            return "closed", None
        if has_tick and recent:
            return "live", None
        if silence is not None and silence > STALE_AFTER_SEC:
            return "stale", "no_ticks"
        return "connecting", "no_ticks_yet"

    def _refresh_honest_mode(self) -> None:
        if self._mode == "unit_mismatch":
            return
        if self._mode == "no_realtime" and not self._ws_connected:
            return
        mode, reason = self._resolve_honest_mode()
        self._mode = mode
        if mode in ("connecting", "stale", "no_realtime"):
            self._degrade_reason = reason
        elif mode == "live":
            self._degrade_reason = None

    # ------------------------------------------------------------------ ingest (legacy / nội bộ)
    def _ingest_event(self, ev: dict[str, Any]) -> None:
        """Tương thích test cũ — uỷ quyền sang ``handle_raw_message``."""
        # Chuẩn hoá price → matchPrice nếu chỉ có price (test cũ)
        if ev.get("T") in ("t", None) and "matchPrice" not in ev and "price" in ev:
            ev = {**ev, "T": ev.get("T") or "t", "matchPrice": ev.get("price")}
        self.handle_raw_message(ev)

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
            if sess.phase != "closed":
                today = wall.date().isoformat()
                if self._data_date != today:
                    # Sang phiên mới: bỏ cờ "đã khớp" của phiên trước
                    self._traded_session.clear()
                    self._data_date = today
            if sess.phase == "closed":
                q.state = "closed"
                q.basis = "eod"
                q.source = "snapshot"
                # ngoài giờ: hiện đóng cửa snapshot (không bịa % từ giá cũ);
                # mã đã khớp trong phiên được giữ giá chốt phiên (xem get_quote).
                if snap is not None and self._mode != "live" and symbol not in self._traded_session:
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
            recv = time.monotonic()
            self._last_tick_mono = recv
            self._receive_mono[symbol] = recv
            if q.state == "live":
                self._traded_session.add(symbol)
            self._stats["ticks"] = int(self._stats.get("ticks") or 0) + 1
            self._update_candle(symbol, scaled, volume)
        # Ngoài lock: cập nhật mode hub (live nếu vừa có tick trong phiên)
        self._refresh_honest_mode()

    def _apply_index_tick(
        self,
        symbol: str,
        price: float,
        *,
        prev_close: float | None,
        volume: float | None = None,
        value: float | None = None,
    ) -> None:
        """Nến chỉ số — kênh market_index (T=mi) hoặc fake.

        Ngoài giờ vẫn giữ nến phiên gần nhất trong RAM (không xoá).
        """
        sess = self.session_now()
        wall = self._now_fn()
        ts = wall.isoformat(timespec="seconds")
        with self._lock:
            self._index_ok = True
            prev = prev_close
            q = self._index_quotes.get(symbol) or QuoteTick(symbol=symbol, price=None)
            q.price = price
            if prev is not None and prev != 0:
                q.prev_close = prev
                q.prev_close_source = "tick"
                q.change = price - prev
                q.change_pct = (price - prev) / prev * 100.0
            else:
                # Giữ prev cũ nếu có; change tính lại khi có đủ
                if q.prev_close is not None and q.prev_close != 0:
                    q.change = price - q.prev_close
                    q.change_pct = (price - q.prev_close) / q.prev_close * 100.0
                else:
                    q.change = None
                    q.change_pct = None
            if volume is not None:
                q.volume = float(volume)
            if value is not None:
                self._index_value[symbol] = float(value)
            q.ts = ts
            # Trong phiên (kể cả ATO/ATC/lunch có mi) → live; chỉ closed → eod nhãn
            if sess.phase == "closed":
                q.state = "closed"
                # Giữ basis=live nếu đã có nến phiên hôm nay (nearest session)
                if self._candles.get(symbol):
                    q.basis = "live"
                    q.state = "stale"
                else:
                    q.basis = "eod"
            else:
                q.state = "live"
                q.basis = "live"
            q.source = "dnse" if self._fake is None else "fake"
            self._index_quotes[symbol] = q
            self._receive_mono[symbol] = time.monotonic()
            # Nến 1 phút theo epoch phút tường (không theo _now_fn giả) — live OK;
            # test fake vẫn có ≥1 nến khi có mi.
            self._update_candle(symbol, price, volume)

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

    # ------------------------------------------------------------------ giá chốt phiên + lưu đĩa
    def _close_active_locked(self, sess: Any | None = None) -> bool:
        sess = sess or self.session_now()
        if sess.phase != "closed":
            return False
        asof = str(getattr(self._store, "asof", None) or self._snapshot_asof or "")[:10]
        return bool(self._data_date and self._data_date > asof and self._traded_session)

    def close_active(self) -> bool:
        """Đang ngoài giờ và hub giữ giá của một phiên mới hơn snapshot EOD."""
        with self._lock:
            return self._close_active_locked()

    def session_close_date(self) -> str | None:
        """Ngày (YYYY-MM-DD) của giá chốt phiên đang hiển thị, hoặc None."""
        with self._lock:
            return self._data_date if self._close_active_locked() else None

    def _persist_file(self, day: str) -> Path | None:
        if self._persist_dir is None:
            return None
        return self._persist_dir / f"intraday_{day}.json"

    def _persist_save(self) -> None:
        """Ghi snapshot trong phiên (atomic). Chỉ ghi khi có dữ liệu phiên."""
        if self._persist_dir is None or self._data_date is None:
            return
        with self._lock:
            day = self._data_date
            quotes = {}
            for sym, q in self._quotes.items():
                if sym not in self._traded_session or q.price is None:
                    continue
                quotes[sym] = [q.price, q.prev_close, q.volume, q.high, q.low, q.ts]
            if not quotes and not self._index_quotes:
                return
            index = {
                sym: {
                    "price": q.price, "prev_close": q.prev_close, "volume": q.volume,
                    "ts": q.ts, "value": self._index_value.get(sym),
                }
                for sym, q in self._index_quotes.items()
            }
            candles = {
                sym: [[b.t, b.o, b.h, b.l, b.c, b.v] for b in bars]
                for sym, bars in self._candles.items()
                if bars and (sym in self._traded_session or sym in self._index_quotes)
            }
            payload = {
                "version": 1,
                "date": day,
                "saved_at": self._now_fn().isoformat(timespec="seconds"),
                "price_scale": self._price_scale_effective,
                "quotes": quotes,
                "index": index,
                "candles": candles,
            }
            ticks = int(self._stats.get("ticks") or 0) + int(self._stats.get("parsed_index") or 0)
            if ticks == self._persist_ticks:
                return
            self._persist_ticks = ticks
        path = self._persist_file(day)
        if path is None:
            return
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix(".tmp")
            tmp.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
            os.replace(tmp, path)
        except OSError as exc:
            _log.warning("intraday persist lỗi: %s", type(exc).__name__)

    def _restore_intraday(self) -> None:
        """Nạp file trong phiên mới nhất nếu mới hơn snapshot EOD và không ở tương lai."""
        if self._persist_dir is None or not self._persist_dir.is_dir():
            return
        asof = str(getattr(self._store, "asof", None) or self._snapshot_asof or "")[:10]
        today = self._now_fn().date().isoformat()
        files = sorted(self._persist_dir.glob("intraday_*.json"), reverse=True)
        for f in files:
            day = f.stem.replace("intraday_", "")
            if day > today or day <= asof:
                continue
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            if data.get("version") != 1 or data.get("date") != day:
                continue
            scale = data.get("price_scale")
            if scale is not None and self._price_scale_effective is not None and float(scale) != float(self._price_scale_effective):
                continue
            with self._lock:
                n = 0
                for sym, row in (data.get("quotes") or {}).items():
                    try:
                        price, prev, vol, hi, lo, ts = row
                    except (TypeError, ValueError):
                        continue
                    if sym not in self._liquid and sym not in self._snapshot_close:
                        continue
                    q = self._quotes.get(sym) or QuoteTick(symbol=sym, price=None)
                    q.price, q.volume, q.high, q.low, q.ts = price, vol, hi, lo, ts
                    q.state, q.basis, q.source = "stale", "live", "dnse"
                    self._quotes[sym] = q
                    self._traded_session.add(sym)
                    n += 1
                for sym, row in (data.get("index") or {}).items():
                    q = QuoteTick(symbol=sym, price=row.get("price"), prev_close=row.get("prev_close"),
                                  prev_close_source="tick" if row.get("prev_close") else "none",
                                  volume=row.get("volume"), ts=row.get("ts"),
                                  state="stale", basis="live", source="dnse")
                    if q.price is not None and q.prev_close:
                        q.change = q.price - q.prev_close
                        q.change_pct = q.change / q.prev_close * 100.0
                    self._index_quotes[sym] = q
                    if row.get("value") is not None:
                        self._index_value[sym] = float(row["value"])
                for sym, bars in (data.get("candles") or {}).items():
                    dq = self._candles[sym]
                    for b in bars[-CANDLE_MAX_BARS:]:
                        try:
                            dq.append(MinuteBar(t=int(b[0]), o=b[1], h=b[2], l=b[3], c=b[4], v=b[5]))
                        except (TypeError, ValueError, IndexError):
                            continue
                self._data_date = day
                self._persist_ticks = -1
                self._stats["restored_from"] = {"date": day, "symbols": n, "saved_at": data.get("saved_at")}
            _log.info("realtime: khôi phục giá phiên %s (%d mã)", day, n)
            return

    def _start_persist(self) -> None:
        if self._persist_dir is None or self._persist_thread is not None:
            return

        def _loop() -> None:
            while not self._stop.wait(self._persist_interval):
                try:
                    self._persist_save()
                except Exception as exc:  # noqa: BLE001
                    _log.warning("intraday persist: %s", type(exc).__name__)

        self._persist_thread = threading.Thread(target=_loop, name="stockai-rt-persist", daemon=True)
        self._persist_thread.start()

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
        # Mode trung thực trước khi snapshot stats
        if self._mode != "unit_mismatch":
            self._refresh_honest_mode()
        mode, reason_h = self._resolve_honest_mode()
        if self._mode != "unit_mismatch":
            self._mode = mode
            if mode in ("connecting", "stale", "no_realtime"):
                self._degrade_reason = reason_h
            elif mode == "live":
                self._degrade_reason = None

        with self._lock:
            now_m = time.monotonic()
            n_live = 0
            for sym, q in self._quotes.items():
                if q.state != "live":
                    continue
                recv = self._receive_mono.get(sym)
                if recv is not None and (now_m - recv) <= LIVE_TICK_MAX_AGE_SEC:
                    n_live += 1
            n_sub = len(self._subscribed) or len(self._liquid)
            age: float | None
            if self._last_tick_mono is None:
                age = None
            else:
                age = round(now_m - self._last_tick_mono, 3)
            if self._mode == "unit_mismatch":
                label = UNIT_MISMATCH_LABEL
            elif self._mode == "live":
                label = LIVE_LABEL
            elif self._mode == "connecting":
                label = CONNECTING_NO_TICKS_LABEL
            elif self._mode == "stale":
                label = STALE_NO_TICKS_LABEL
            elif self._mode == "closed":
                label = "đóng cửa"
            else:
                label = "tạm tính"
            prev_src = self._hub_prev_close_source()
            stats_out = dict(self._stats)
            # msg_types copy nông
            mt = stats_out.get("msg_types")
            if isinstance(mt, dict):
                stats_out["msg_types"] = dict(mt)
            out: dict[str, Any] = {
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
                "index_channel": "ok" if (self._index_ok and int(self._stats.get("parsed_index") or 0) > 0) else ("chờ dữ liệu" if self._index_ok else "chưa đo"),
                "session_channel": "ok" if self._session_channel_ok else "chưa đo",
                "sec_def_channel": "ok" if self._sec_def_ok else "chưa đo",
                "last_error": self._last_error,
                "stats": stats_out,
                "label": label,
                "disclaimer_realtime": (
                    "Giá phiên chỉ để hiển thị và phân tích trong phiên (tạm tính). "
                    "Điểm M2–M7 dùng giá đóng cửa EOD."
                    if self._mode != "unit_mismatch"
                    else UNIT_MISMATCH_LABEL
                    + ". Điểm M2–M7 luôn dùng giá đóng cửa EOD."
                ),
            }
            # reason khi chưa live thật / degrade
            if self._mode in ("no_realtime", "connecting", "stale"):
                reason = self._degrade_reason or (
                    "missing_key" if self._mode == "no_realtime" else "no_ticks_yet"
                )
                if reason.startswith("connect_error:"):
                    code = reason.split(":", 1)[1].strip() or "unknown"
                    code = "".join(c for c in code if c.isalnum() or c in ("_", "-"))[:64]
                    reason = f"connect_error:{code or 'unknown'}"
                elif reason not in (
                    "disabled",
                    "missing_key",
                    "sdk_missing",
                    "no_ticks_yet",
                    "no_ticks",
                ) and not reason.startswith("connect_error:"):
                    if self._mode == "stale":
                        reason = "no_ticks"
                    elif self._mode == "connecting":
                        reason = "no_ticks_yet"
                    else:
                        reason = "missing_key"
                out["reason"] = reason
            return out

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
                if self._close_active_locked(sess) and symbol in self._traded_session and q.price is not None:
                    # Giá chốt phiên hôm nay từ DNSE (tạm tính) cho tới khi có snapshot EOD
                    out.price = q.price
                    out.basis = "close"
                    out.source = "dnse"
                elif snap is not None:
                    out.price = snap
                    # Đang hiển thị chính giá EOD của phiên cuối → % thay đổi so với phiên liền trước nó,
                    # không phải so với chính nó (luôn 0%).
                    p2 = self._snapshot_prev_close.get(symbol)
                    if p2 is not None and p2 != 0:
                        prev = p2
                        out.prev_close = p2
                        out.prev_close_source = "snapshot"
                if prev is not None and prev != 0 and out.price is not None:
                    out.change = out.price - prev
                    out.change_pct = (out.price - prev) / prev * 100.0
                else:
                    out.change = None
                    out.change_pct = None
            elif self._mode == "no_realtime":
                out.state = "no_realtime"
                out.basis = "eod"
                # Phiên mở nhưng không có luồng → không hiện % giả (+0%)
                if sess.phase != "closed":
                    out.change = None
                    out.change_pct = None
                elif out.price is not None and self._snapshot_prev_close.get(symbol):
                    p2 = float(self._snapshot_prev_close[symbol])  # type: ignore[arg-type]
                    out.prev_close, out.prev_close_source = p2, "snapshot"
                    out.change = out.price - p2
                    out.change_pct = (out.price - p2) / p2 * 100.0
                elif prev is not None and prev != 0 and out.price is not None:
                    out.change = out.price - prev
                    out.change_pct = (out.price - prev) / prev * 100.0
                else:
                    out.change = None
                    out.change_pct = None
            elif self._mode in ("connecting", "stale") and out.state not in (
                "live",
                "stale",
            ):
                # Đã kết nối nhưng chưa có tick (hoặc im lặng) — không tuyên bố trực tiếp
                out.state = self._mode
                out.basis = "eod"
                if sess.phase != "closed":
                    out.change = None
                    out.change_pct = None
            elif out.price is not None:
                if prev is not None and prev != 0:
                    out.change = out.price - prev
                    out.change_pct = (out.price - prev) / prev * 100.0
                else:
                    out.change = None
                    out.change_pct = None
                # Stale theo thời điểm nhận (monotonic), không so timestamp tick với đồng hồ trình duyệt
                if sess.phase != "closed" and out.state == "live":
                    recv = self._receive_mono.get(symbol)
                    if recv is not None:
                        age = time.monotonic() - recv
                        if age > DISPLAY_STALE_AFTER_SEC:
                            out.state = "stale"
            return out

    def receive_age_sec(self, symbol: str) -> float | None:
        """Tuổi tick theo receive monotonic — dùng cho test/UI."""
        with self._lock:
            recv = self._receive_mono.get(symbol)
        if recv is None:
            return None
        return time.monotonic() - recv

    def has_traded_session(self, symbol: str) -> bool:
        with self._lock:
            return symbol in self._traded_session

    def get_index_quote(self, symbol: str = "VNINDEX") -> QuoteTick | None:
        with self._lock:
            q = self._index_quotes.get(symbol)
            return QuoteTick(**q.__dict__) if q else None

    def get_index_value(self, symbol: str = "VNINDEX") -> float | None:
        """GTGD chỉ số (tỷ VND) từ mi.grossTradeAmount."""
        with self._lock:
            v = self._index_value.get(symbol)
            return float(v) if v is not None else None

    def available_indices(self) -> list[str]:
        """Chỉ trả kênh thật đã nhận tick — không bịa VN30/HNX."""
        with self._lock:
            return sorted(self._index_quotes.keys())

    def set_index_prev_from_eod(self, symbol: str, prev_close: float) -> None:
        """Điền prev_close từ series_eod khi mi thiếu priorValueIndexes."""
        if prev_close <= 0:
            return
        with self._lock:
            q = self._index_quotes.get(symbol)
            if q is None:
                return
            if q.prev_close is not None and q.prev_close != 0:
                return
            q.prev_close = float(prev_close)
            q.prev_close_source = "snapshot"
            if q.price is not None and prev_close != 0:
                q.change = q.price - prev_close
                q.change_pct = (q.price - prev_close) / prev_close * 100.0

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
