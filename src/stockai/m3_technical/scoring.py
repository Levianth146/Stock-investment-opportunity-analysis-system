"""Deterministic Technical Score V1 calculations."""

from __future__ import annotations

from collections.abc import Mapping

Number = int | float


def score_trend(close: Number | None, sma20: Number | None, sma50: Number | None, sma200: Number | None) -> int | None:
    if any(value is None for value in (close, sma20, sma50, sma200)):
        return None
    return (10 if close > sma20 else 0) + (15 if sma20 > sma50 else 0) + (20 if sma50 > sma200 else 0)


def score_rsi(rsi: Number | None) -> int | None:
    if rsi is None:
        return None
    if rsi < 30:
        return 5
    if rsi < 45:
        return 10
    if rsi < 55:
        return 15
    if rsi <= 70:
        return 20
    return 15


def score_macd(macd: Number | None, signal: Number | None) -> int | None:
    if macd is None or signal is None:
        return None
    if macd > signal and macd > 0:
        return 15
    if macd > signal:
        return 10
    if macd > 0:
        return 5
    return 0


def score_momentum(rsi: Number | None, macd: Number | None, signal: Number | None) -> int | None:
    rsi_score = score_rsi(rsi)
    macd_score = score_macd(macd, signal)
    if rsi_score is None or macd_score is None:
        return None
    return rsi_score + macd_score


def score_volume(five_day_return: Number | None, volume_ratio: Number | None) -> int | None:
    if five_day_return is None or volume_ratio is None:
        return None
    if five_day_return > 0.01:
        return 20 if volume_ratio >= 1.2 else 15
    if five_day_return < -0.01:
        return 0 if volume_ratio >= 1.2 else 5
    return 10


def calculate_technical_score(trend_score: int | None, momentum_score: int | None, volume_score: int | None) -> int | None:
    if any(value is None for value in (trend_score, momentum_score, volume_score)):
        return None
    return max(0, min(100, trend_score + momentum_score + volume_score))


def technical_rating(score: Number | None) -> str | None:
    if score is None:
        return None
    if score >= 80:
        return "Strong Bullish"
    if score >= 65:
        return "Bullish"
    if score >= 45:
        return "Neutral / Mixed"
    if score >= 30:
        return "Bearish"
    return "Strong Bearish"


def score_components(indicators: Mapping[str, Number | None]) -> dict[str, int | None]:
    trend = score_trend(indicators.get("latest_close"), indicators.get("sma20"), indicators.get("sma50"), indicators.get("sma200"))
    momentum = score_momentum(indicators.get("rsi14"), indicators.get("macd"), indicators.get("macd_signal"))
    volume = score_volume(indicators.get("five_day_return"), indicators.get("volume_ratio"))
    return {
        "trend_score": trend,
        "momentum_score": momentum,
        "volume_score": volume,
        "technical_score": calculate_technical_score(trend, momentum, volume),
    }
