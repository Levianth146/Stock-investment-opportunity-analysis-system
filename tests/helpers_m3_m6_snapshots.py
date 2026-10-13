"""Snapshot dựng tay offline cho test M3/M6 (không gọi mạng)."""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any


AS_OF = "2026-10-08"


def _iso(d: date) -> str:
    return d.isoformat()


def _business_days(end: date, n: int) -> list[date]:
    """n phiên làm việc kết thúc tại end (lùi bỏ T7/CN)."""
    days: list[date] = []
    cur = end
    while len(days) < n:
        if cur.weekday() < 5:
            days.append(cur)
        cur -= timedelta(days=1)
    days.reverse()
    return days


def _ohlcv_row(d: date, close: float, volume: float = 1_000_000.0) -> dict[str, Any]:
    c = float(close)
    return {
        "date": _iso(d),
        "open": c,
        "high": c * 1.01,
        "low": c * 0.99,
        "close": c,
        "volume": float(volume),
    }


def base_meta(
    *,
    ticker: str = "TEST",
    as_of: str = AS_OF,
    synthetic: bool = False,
    flags: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "schema_version": "1.0",
        "ticker": ticker,
        "as_of": as_of,
        "synthetic": synthetic,
        "flags": list(flags or []),
    }


def make_snapshot(
    *,
    price_rows: list[dict],
    index_rows: list[dict] | None = None,
    adjusted: bool = True,
    synthetic: bool = False,
    as_of: str = AS_OF,
    ticker: str = "TEST",
    meta_flags: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "meta": base_meta(ticker=ticker, as_of=as_of, synthetic=synthetic, flags=meta_flags),
        "prices": {
            "adjusted": adjusted,
            "source_id": "src_price_test",
            "rows": price_rows,
        },
        "index": {
            "symbol": "VNINDEX",
            "source_id": "src_index_test",
            "rows": list(index_rows or []),
        },
    }


def prices_trending(
    n: int,
    *,
    as_of: str = AS_OF,
    start: float = 20_000.0,
    daily_ret: float = 0.001,
    volume: float = 1_000_000.0,
) -> list[dict]:
    end = date.fromisoformat(as_of)
    days = _business_days(end, n)
    rows = []
    px = start
    for d in days:
        rows.append(_ohlcv_row(d, px, volume=volume))
        px *= 1.0 + daily_ret
    return rows


def index_from_prices(price_rows: list[dict], *, scale: float = 1.0) -> list[dict]:
    """Chuỗi chỉ số cùng ngày; scale nhân close (scale=1 → trùng tỷ lệ với giá)."""
    out = []
    for r in price_rows:
        out.append({"date": r["date"], "close": float(r["close"]) * scale})
    return out


def snapshot_enough_history(**kwargs: Any) -> dict[str, Any]:
    """≥200 phiên sạch, adjusted, không synthetic — đủ cho M3 score."""
    n = int(kwargs.pop("n", 220))
    rows = prices_trending(n)
    return make_snapshot(price_rows=rows, index_rows=index_from_prices(rows), **kwargs)


def snapshot_short_history(**kwargs: Any) -> dict[str, Any]:
    """<200 phiên → M3 score null."""
    n = int(kwargs.pop("n", 100))
    rows = prices_trending(n)
    return make_snapshot(price_rows=rows, index_rows=index_from_prices(rows), **kwargs)


def snapshot_with_future_rows(**kwargs: Any) -> dict[str, Any]:
    """Có ngày > as_of — lookahead phải bị bỏ."""
    as_of = kwargs.get("as_of", AS_OF)
    rows = prices_trending(220, as_of=as_of)
    end = date.fromisoformat(as_of)
    # Thêm vài phiên tương lai với giá cực lớn để lộ nếu bị dùng
    for i in range(1, 6):
        d = end + timedelta(days=i)
        if d.weekday() >= 5:
            continue
        rows.append(_ohlcv_row(d, 999_999.0, volume=9_999_999.0))
    return make_snapshot(price_rows=rows, index_rows=index_from_prices(rows), **kwargs)


def snapshot_bad_ohlc(**kwargs: Any) -> dict[str, Any]:
    """Trộn vài dòng OHLC lỗi vào chuỗi đủ dài."""
    rows = prices_trending(220)
    mid = rows[100]
    rows.insert(
        101,
        {
            "date": mid["date"],  # trùng ngày — sẽ bị dedupe
            "open": 100.0,
            "high": 90.0,  # high < low
            "low": 110.0,
            "close": 105.0,
            "volume": 1.0,
        },
    )
    rows.append(
        {
            "date": "2020-01-02",
            "open": -1.0,
            "high": 10.0,
            "low": 1.0,
            "close": 5.0,
            "volume": 100.0,
        }
    )
    rows.append(
        {
            "date": "2020-01-03",
            "open": 10.0,
            "high": 12.0,
            "low": 9.0,
            "close": 15.0,  # close ngoài [low, high]
            "volume": 100.0,
        }
    )
    return make_snapshot(price_rows=rows, index_rows=index_from_prices(rows), **kwargs)


def snapshot_stale(**kwargs: Any) -> dict[str, Any]:
    """Phiên cuối cách as_of > 7 ngày lịch."""
    as_of = kwargs.get("as_of", AS_OF)
    end = date.fromisoformat(as_of) - timedelta(days=14)
    days = _business_days(end, 220)
    rows = []
    px = 20_000.0
    for d in days:
        rows.append(_ohlcv_row(d, px))
        px *= 1.001
    return make_snapshot(price_rows=rows, index_rows=index_from_prices(rows), **kwargs)


def snapshot_empty_prices(**kwargs: Any) -> dict[str, Any]:
    """Giống ATP/BCH/MDD — không có prices.rows."""
    return make_snapshot(price_rows=[], index_rows=[], **kwargs)


def snapshot_identical_stock_index(**kwargs: Any) -> dict[str, Any]:
    """Giá cổ phiếu trùng chỉ số → beta ≈ 1 (cần nhiễu để Var(index) > 0)."""
    as_of = kwargs.get("as_of", AS_OF)
    n = int(kwargs.pop("n", 200))
    days = _business_days(date.fromisoformat(as_of), n)
    rows = []
    px = 20_000.0
    for i, d in enumerate(days):
        # Nhiễu xác định — stock và index cùng close → beta = 1
        px *= 1.0 + 0.0008 + (0.004 if i % 5 == 0 else -0.002 if i % 3 == 0 else 0.0005)
        rows.append(_ohlcv_row(d, max(px, 100.0)))
    idx = [{"date": r["date"], "close": float(r["close"])} for r in rows]
    return make_snapshot(price_rows=rows, index_rows=idx, **kwargs)


def snapshot_high_vol_deep_dd(**kwargs: Any) -> dict[str, Any]:
    """Biến động lớn + drawdown sâu (cùng khung ngày với stable)."""
    as_of = kwargs.get("as_of", AS_OF)
    n = int(kwargs.pop("n", 200))
    days = _business_days(date.fromisoformat(as_of), n)
    rows = []
    px = 50_000.0
    for i, d in enumerate(days):
        # Xen kẽ ±8% rồi sụp mạnh nửa sau
        if i < n // 2:
            px *= 1.08 if i % 2 == 0 else 0.92
        else:
            px *= 0.97
        rows.append(_ohlcv_row(d, max(px, 100.0), volume=2_000_000.0))
    # Index êm hơn
    idx = []
    ix = 1000.0
    for i, d in enumerate(days):
        ix *= 1.0005 if i % 2 == 0 else 0.9995
        idx.append({"date": _iso(d), "close": ix})
    return make_snapshot(price_rows=rows, index_rows=idx, ticker="RISK", **kwargs)


def snapshot_stable(**kwargs: Any) -> dict[str, Any]:
    """Biến động thấp, cùng số phiên / as_of với high-vol fixture."""
    as_of = kwargs.get("as_of", AS_OF)
    n = int(kwargs.pop("n", 200))
    days = _business_days(date.fromisoformat(as_of), n)
    rows = []
    px = 50_000.0
    for i, d in enumerate(days):
        px *= 1.0003 if i % 2 == 0 else 0.9997
        rows.append(_ohlcv_row(d, px, volume=1_000_000.0))
    idx = []
    ix = 1000.0
    for i, d in enumerate(days):
        ix *= 1.0005 if i % 2 == 0 else 0.9995
        idx.append({"date": _iso(d), "close": ix})
    return make_snapshot(price_rows=rows, index_rows=idx, ticker="SAFE", **kwargs)


def snapshot_unadjusted(**kwargs: Any) -> dict[str, Any]:
    n = int(kwargs.pop("n", 200))
    rows = prices_trending(n)
    return make_snapshot(
        price_rows=rows,
        index_rows=index_from_prices(rows),
        adjusted=False,
        **kwargs,
    )


def snapshot_synthetic(**kwargs: Any) -> dict[str, Any]:
    n = int(kwargs.pop("n", 200))
    rows = prices_trending(n)
    return make_snapshot(
        price_rows=rows,
        index_rows=index_from_prices(rows),
        synthetic=True,
        **kwargs,
    )


def snapshot_m6_misaligned_dates(**kwargs: Any) -> dict[str, Any]:
    """Stock và index lệch ngày — chỉ giao ngày chung được dùng (no forward-fill)."""
    as_of = kwargs.get("as_of", AS_OF)
    n = int(kwargs.pop("n", 180))
    days = _business_days(date.fromisoformat(as_of), n)
    stock_rows = []
    idx_rows = []
    px, ix = 20_000.0, 1000.0
    for i, d in enumerate(days):
        px *= 1.001
        ix *= 1.0005
        # Stock có mọi ngày; index bỏ mỗi ngày thứ 3 trong danh sách
        stock_rows.append(_ohlcv_row(d, px))
        if i % 3 != 2:
            idx_rows.append({"date": _iso(d), "close": ix})
        # Thêm ngày chỉ có index (không có stock) — không được forward-fill sang stock
        if i % 7 == 0:
            ghost = d - timedelta(days=1)
            if ghost.weekday() < 5:
                idx_rows.append({"date": _iso(ghost), "close": ix * 0.999})
    return make_snapshot(price_rows=stock_rows, index_rows=idx_rows, **kwargs)


def snapshot_shared_holiday_gap(**kwargs: Any) -> dict[str, Any]:
    """Stock + index cùng nghỉ ~9 ngày lịch (giống Tết) — không phải suspension."""
    as_of = kwargs.get("as_of", AS_OF)
    n = int(kwargs.pop("n", 200))
    holiday_calendar_days = int(kwargs.pop("holiday_calendar_days", 9))
    end = date.fromisoformat(as_of)
    # Đủ phiên trước nghỉ + sau nghỉ
    before = _business_days(end - timedelta(days=holiday_calendar_days + 40), n // 2 + 20)
    after_start = before[-1] + timedelta(days=holiday_calendar_days)
    after: list[date] = []
    cur = after_start
    while len(after) < n // 2 + 20:
        if cur.weekday() < 5:
            after.append(cur)
        cur += timedelta(days=1)
    # Cắt để phiên cuối ≤ as_of
    days = [d for d in (before + after) if d <= end][-n:]
    rows = []
    px = 20_000.0
    for i, d in enumerate(days):
        px *= 1.0 + 0.0008 + (0.003 if i % 5 == 0 else -0.0015 if i % 3 == 0 else 0.0004)
        rows.append(_ohlcv_row(d, max(px, 100.0)))
    idx = [{"date": r["date"], "close": float(r["close"])} for r in rows]
    return make_snapshot(price_rows=rows, index_rows=idx, ticker="HOL", **kwargs)


def snapshot_stock_suspended_vs_index(**kwargs: Any) -> dict[str, Any]:
    """Index giao dịch liên tục; stock bỏ 12 phiên giữa chừng (treo/suspended)."""
    as_of = kwargs.get("as_of", AS_OF)
    n = int(kwargs.pop("n", 200))
    suspend_sessions = int(kwargs.pop("suspend_sessions", 12))
    days = _business_days(date.fromisoformat(as_of), n)
    # Treo khoảng giữa chuỗi
    mid = len(days) // 2
    suspend_set = set(days[mid : mid + suspend_sessions])
    stock_rows = []
    idx_rows = []
    px, ix = 20_000.0, 1000.0
    for i, d in enumerate(days):
        ix *= 1.0 + 0.0006 + (0.002 if i % 4 == 0 else -0.001)
        idx_rows.append({"date": _iso(d), "close": max(ix, 1.0)})
        if d in suspend_set:
            continue
        px *= 1.0 + 0.0008 + (0.003 if i % 5 == 0 else -0.0015 if i % 3 == 0 else 0.0004)
        stock_rows.append(_ohlcv_row(d, max(px, 100.0)))
    return make_snapshot(
        price_rows=stock_rows, index_rows=idx_rows, ticker="SUSP", **kwargs
    )
