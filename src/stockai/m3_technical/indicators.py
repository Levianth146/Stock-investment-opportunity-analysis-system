"""Pure, chronologically aligned technical-indicator calculations."""

from __future__ import annotations

from collections.abc import Sequence
from math import isfinite

from stockai.m3_technical.constants import (
    EMA12_PERIOD,
    EMA26_PERIOD,
    FIVE_DAY_RETURN_PERIOD,
    MACD_SIGNAL_PERIOD,
    RSI14_PERIOD,
    SMA20_PERIOD,
    SMA50_PERIOD,
    SMA200_PERIOD,
    VOLUME_MA20_PERIOD,
)

Number = int | float
MaybeNumber = Number | None


def _number(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    converted = float(value)
    return converted if isfinite(converted) else None


def sma(values: Sequence[MaybeNumber], period: int) -> list[MaybeNumber]:
    """Return a rolling simple moving average aligned to ``values``."""
    if period <= 0:
        raise ValueError("period must be positive")

    result: list[MaybeNumber] = [None] * len(values)
    for index in range(period - 1, len(values)):
        window = [_number(value) for value in values[index - period + 1 : index + 1]]
        if all(value is not None for value in window):
            result[index] = sum(window) / period
    return result


def ema(values: Sequence[MaybeNumber], period: int) -> list[MaybeNumber]:
    """Return an SMA-seeded EMA aligned to the original sequence."""
    if period <= 0:
        raise ValueError("period must be positive")

    result: list[MaybeNumber] = [None] * len(values)
    valid: list[tuple[int, float]] = []
    for index, value in enumerate(values):
        number = _number(value)
        if number is None:
            continue
        valid.append((index, number))
        if len(valid) < period:
            continue
        if len(valid) == period:
            previous = sum(number for _, number in valid) / period
        else:
            alpha = 2 / (period + 1)
            previous = alpha * number + (1 - alpha) * previous
        result[index] = previous
    return result


def rsi_wilder(
    closes: Sequence[MaybeNumber], period: int = RSI14_PERIOD
) -> list[MaybeNumber]:
    """Return Wilder RSI values, without fabricating the warm-up period."""
    if period <= 0:
        raise ValueError("period must be positive")

    result: list[MaybeNumber] = [None] * len(closes)
    if len(closes) <= period:
        return result

    numbers = [_number(value) for value in closes]
    gains: list[float] = []
    losses: list[float] = []
    for index in range(1, len(numbers)):
        current, previous = numbers[index], numbers[index - 1]
        if current is None or previous is None:
            gains.clear()
            losses.clear()
            continue

        gain = max(current - previous, 0.0)
        loss = max(previous - current, 0.0)
        gains.append(gain)
        losses.append(loss)
        if len(gains) < period:
            continue

        if len(gains) == period:
            average_gain = sum(gains) / period
            average_loss = sum(losses) / period
        else:
            average_gain = (average_gain * (period - 1) + gain) / period
            average_loss = (average_loss * (period - 1) + loss) / period

        if average_loss == 0:
            result[index] = 100.0 if average_gain > 0 else 50.0
        elif average_gain == 0:
            result[index] = 0.0
        else:
            result[index] = 100 - (100 / (1 + average_gain / average_loss))

    return result


def macd(
    closes: Sequence[MaybeNumber],
    fast_period: int = EMA12_PERIOD,
    slow_period: int = EMA26_PERIOD,
    signal_period: int = MACD_SIGNAL_PERIOD,
) -> dict[str, list[MaybeNumber]]:
    """Return aligned MACD, signal, and histogram series."""
    fast = ema(closes, fast_period)
    slow = ema(closes, slow_period)
    macd_values: list[MaybeNumber] = [
        fast_value - slow_value
        if fast_value is not None and slow_value is not None
        else None
        for fast_value, slow_value in zip(fast, slow)
    ]
    signal = ema(macd_values, signal_period)
    histogram: list[MaybeNumber] = [
        macd_value - signal_value
        if macd_value is not None and signal_value is not None
        else None
        for macd_value, signal_value in zip(macd_values, signal)
    ]
    return {"macd": macd_values, "signal": signal, "histogram": histogram}


def volume_ma(
    volumes: Sequence[MaybeNumber], period: int = VOLUME_MA20_PERIOD
) -> list[MaybeNumber]:
    """Return a rolling volume moving-average series."""
    return sma(volumes, period)


def volume_ratio(current_volume: MaybeNumber, moving_average: MaybeNumber) -> float | None:
    """Return current volume divided by its moving average."""
    current = _number(current_volume)
    average = _number(moving_average)
    if current is None or average is None or average <= 0:
        return None
    return current / average


def five_day_return(
    closes: Sequence[MaybeNumber],
    period: int = FIVE_DAY_RETURN_PERIOD,
) -> list[MaybeNumber]:
    """Return aligned returns comparing each close with the close ``period`` ago."""
    if period <= 0:
        raise ValueError("period must be positive")

    result: list[MaybeNumber] = [None] * len(closes)
    for index in range(period, len(closes)):
        current = _number(closes[index])
        previous = _number(closes[index - period])
        if current is not None and previous is not None and previous != 0:
            result[index] = current / previous - 1
    return result


def standard_indicators(
    closes: Sequence[MaybeNumber],
    volumes: Sequence[MaybeNumber],
) -> dict[str, list[MaybeNumber]]:
    """Calculate the M3 v1 indicator series using the named standard periods."""
    macd_values = macd(closes)
    return {
        "sma20": sma(closes, SMA20_PERIOD),
        "sma50": sma(closes, SMA50_PERIOD),
        "sma200": sma(closes, SMA200_PERIOD),
        "ema12": ema(closes, EMA12_PERIOD),
        "ema26": ema(closes, EMA26_PERIOD),
        "rsi14": rsi_wilder(closes, RSI14_PERIOD),
        "macd": macd_values["macd"],
        "macd_signal": macd_values["signal"],
        "macd_histogram": macd_values["histogram"],
        "volume_ma20": volume_ma(volumes, VOLUME_MA20_PERIOD),
        "five_day_return": five_day_return(closes, FIVE_DAY_RETURN_PERIOD),
    }
