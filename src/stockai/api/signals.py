"""Tín hiệu kỹ thuật additive trên rankings (feature 014e) — chỉ đọc metrics M3."""
from __future__ import annotations

from typing import Any


def _metric_val(metrics: dict[str, Any], key: str) -> float | None:
    raw = metrics.get(key)
    if isinstance(raw, dict):
        v = raw.get("value")
        return float(v) if isinstance(v, (int, float)) else None
    if isinstance(raw, (int, float)):
        return float(raw)
    return None


def build_signals_from_m3(m3: dict[str, Any] | None) -> dict[str, Any]:
    """Sinh signals từ metrics M3. Thiếu số → null/false an toàn, không bịa."""
    metrics = (m3 or {}).get("metrics") if isinstance(m3, dict) else None
    if not isinstance(metrics, dict):
        return {
            "above_ma50": None,
            "above_ma200": None,
            "rsi_zone": None,
            "volume_up": None,
        }
    close = _metric_val(metrics, "close")
    ma50 = _metric_val(metrics, "ma50")
    ma200 = _metric_val(metrics, "ma200")
    rsi = _metric_val(metrics, "rsi14")
    vol_ratio = _metric_val(metrics, "volume_ratio_20")

    above_ma50 = None
    if close is not None and ma50 is not None:
        above_ma50 = close > ma50
    above_ma200 = None
    if close is not None and ma200 is not None:
        above_ma200 = close > ma200

    rsi_zone: str | None = None
    if rsi is not None:
        if rsi > 70:
            rsi_zone = "overbought"
        elif rsi < 30:
            rsi_zone = "oversold"
        else:
            rsi_zone = "neutral"

    volume_up = None
    if vol_ratio is not None:
        volume_up = vol_ratio > 1.0

    return {
        "above_ma50": above_ma50,
        "above_ma200": above_ma200,
        "rsi_zone": rsi_zone,
        "volume_up": volume_up,
    }
