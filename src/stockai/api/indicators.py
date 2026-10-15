"""Chuỗi chỉ báo kỹ thuật cho API prices (cùng công thức M3, không sửa module M3).

MA: rolling mean; RSI14: Wilder ewm alpha=1/14; MACD(12,26,9): EMA hiệu.
Không dùng phiên sau ``as_of``.
"""
from __future__ import annotations

from typing import Any

import pandas as pd


def _finite(x: Any) -> float | None:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    if v != v or v in (float("inf"), float("-inf")):
        return None
    return v


def _series_points(dates: list[str], values: pd.Series) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for i, d in enumerate(dates):
        v = _finite(values.iloc[i]) if i < len(values) else None
        out.append({"time": d, "value": v})
    return out


def compute_indicator_series(
    ohlcv: list[dict[str, Any]],
    *,
    as_of: str,
    rsi_period: int = 14,
    macd_fast: int = 12,
    macd_slow: int = 26,
    macd_signal: int = 9,
) -> dict[str, list[dict[str, Any]]]:
    """Tính ma20/ma50/ma200, rsi14, macd/signal/hist theo từng ngày (đã lọc ≤ as_of)."""
    empty = {
        "ma20": [],
        "ma50": [],
        "ma200": [],
        "rsi14": [],
        "macd": [],
        "signal": [],
        "hist": [],
    }
    rows: list[dict[str, Any]] = []
    for r in ohlcv:
        if not isinstance(r, dict):
            continue
        day = str(r.get("time") or r.get("date") or "")[:10]
        if not day or day > as_of:
            continue
        close = _finite(r.get("close"))
        if close is None:
            continue
        rows.append({"date": day, "close": close})
    if not rows:
        return empty

    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").drop_duplicates("date", keep="last").reset_index(drop=True)
    c = df["close"].astype(float)
    dates = [d.strftime("%Y-%m-%d") for d in df["date"]]

    ma20 = c.rolling(20, min_periods=20).mean()
    ma50 = c.rolling(50, min_periods=50).mean()
    ma200 = c.rolling(200, min_periods=200).mean()

    change = c.diff()
    gain = change.clip(lower=0).fillna(0.0)
    loss = (-change.clip(upper=0)).fillna(0.0)
    avg_gain = gain.ewm(alpha=1 / rsi_period, adjust=False, min_periods=rsi_period).mean()
    avg_loss = loss.ewm(alpha=1 / rsi_period, adjust=False, min_periods=rsi_period).mean()
    rs = avg_gain / avg_loss.replace(0, float("nan"))
    rsi_series = 100 - 100 / (1 + rs)
    # Khớp M3: khi avg_loss=0
    rsi_vals = rsi_series.copy()
    for i in range(len(rsi_vals)):
        if avg_loss.iloc[i] == 0:
            rsi_vals.iloc[i] = 100.0 if avg_gain.iloc[i] > 0 else 50.0

    ema_fast = c.ewm(span=macd_fast, adjust=False).mean()
    ema_slow = c.ewm(span=macd_slow, adjust=False).mean()
    macd = ema_fast - ema_slow
    signal = macd.ewm(span=macd_signal, adjust=False).mean()
    hist = macd - signal

    return {
        "ma20": _series_points(dates, ma20),
        "ma50": _series_points(dates, ma50),
        "ma200": _series_points(dates, ma200),
        "rsi14": _series_points(dates, rsi_vals),
        "macd": _series_points(dates, macd),
        "signal": _series_points(dates, signal),
        "hist": _series_points(dates, hist),
    }


def align_index_series(
    index_rows: list[dict[str, Any]],
    ohlcv_times: list[str],
    *,
    as_of: str,
) -> list[dict[str, Any]] | None:
    """Chuỗi VN-Index (close) căn theo ngày OHLCV; thiếu nguồn → None."""
    if not index_rows:
        return None
    by_date: dict[str, float | None] = {}
    for r in index_rows:
        if not isinstance(r, dict):
            continue
        day = str(r.get("date") or "")[:10]
        if not day or day > as_of:
            continue
        by_date[day] = _finite(r.get("close"))
    if not by_date:
        return None
    return [{"time": t, "close": by_date.get(t)} for t in ohlcv_times]
