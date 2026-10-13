"""m3 - điểm T kỹ thuật (trend / momentum / volume / volatility).

Chữ ký: run(snapshot, upstream, cfg) -> dict đã validate module_out.
Ngưỡng cửa sổ và rubric đọc từ cfg / config/technical.yaml (không hard-code).
Giá đóng cửa / MA / ATR tính bằng VND/share theo snapshot.prices.
"""
from __future__ import annotations

import math
from copy import deepcopy
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

from stockai.contracts.schemas import validate

_ROOT = Path(__file__).resolve().parents[3]
_TECHNICAL_YAML = _ROOT / "config" / "technical.yaml"

_DEFAULT_M3: dict[str, Any] = {
    "min_sessions_ma200": 200,
    "stale_calendar_days": 7,
    "rsi_period": 14,
    "macd": {"fast": 12, "slow": 26, "signal": 9},
    "volume_ma": 20,
    "atr_period": 14,
    "trend": {"above_ma_points": 10, "alignment_bonus": 5},
    "momentum": {
        "macd_above_signal": 10,
        "macd_above_zero": 10,
        "rsi": {
            "mid_low": 45,
            "mid_high": 70,
            "mid_points": 10,
            "outer_low": 30,
            "outer_high": 80,
            "outer_points": 5,
        },
    },
    "volume": {
        "ratio_high": 1.2,
        "ratio_mid": 0.8,
        "up_high": 20,
        "up_mid": 12,
        "low_ratio": 8,
        "else_points": 3,
    },
    "volatility_atr_pct": [
        {"max": 2, "points": 15},
        {"max": 4, "points": 10},
        {"max": 6, "points": 5},
        {"else": True, "points": 0},
    ],
}


def _deep_merge(base: dict, overlay: dict) -> dict:
    out = deepcopy(base)
    for k, v in (overlay or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def _load_m3_cfg(cfg: dict | None) -> tuple[dict[str, Any], bool]:
    """Gộp cfg.m3 với technical.yaml; thiếu file/khóa → default + m3_config_defaulted."""
    defaulted = False
    file_m3: dict[str, Any] = {}
    try:
        if _TECHNICAL_YAML.is_file():
            raw = yaml.safe_load(_TECHNICAL_YAML.read_text(encoding="utf-8")) or {}
            file_m3 = dict(raw.get("m3") or {})
        else:
            defaulted = True
    except (OSError, yaml.YAMLError, TypeError):
        defaulted = True
        file_m3 = {}

    merged = _deep_merge(_DEFAULT_M3, file_m3)
    cfg = cfg if isinstance(cfg, dict) else {}
    overlay = cfg.get("m3") if isinstance(cfg.get("m3"), dict) else {}
    flat_keys = ("min_sessions_ma200", "stale_calendar_days", "rsi_period", "volume_ma", "atr_period")
    flat = {k: cfg[k] for k in flat_keys if k in cfg}
    if flat:
        overlay = _deep_merge(overlay, flat)
    if overlay:
        merged = _deep_merge(merged, overlay)
    if not file_m3 and not overlay:
        defaulted = True
    return merged, defaulted


def _finite(x):
    if x is None or isinstance(x, bool):
        return None
    try:
        v = float(x)
        return v if math.isfinite(v) else None
    except (TypeError, ValueError):
        return None


def _metric_num(value, unit, note=None):
    m = {"value": _finite(value), "unit": unit}
    if note:
        m["note"] = note
    return m


def _volatility_points(atr_pct: float, bands: list) -> int:
    for band in bands or []:
        if band.get("else"):
            return int(band.get("points", 0))
        mx = band.get("max")
        if mx is not None and atr_pct <= float(mx):
            return int(band.get("points", 0))
    return 0


def run(snapshot: dict, upstream: dict, cfg: dict) -> dict:
    m3_cfg, cfg_defaulted = _load_m3_cfg(cfg)
    flags: list[str] = []
    if cfg_defaulted:
        flags.append("m3_config_defaulted")

    out: dict[str, Any] = {
        "module": "m3",
        "status": "partial",
        "score": None,
        "metrics": {},
        "evidence": [],
        "flags": flags,
    }

    def finish():
        errors = validate(out, "module_out")
        if errors:
            raise ValueError("M3 output invalid: " + "; ".join(errors[:5]))
        return out

    if not isinstance(snapshot, dict):
        flags.append("m3_invalid_snapshot")
        return finish()

    meta = snapshot.get("meta") or {}
    prices = snapshot.get("prices") or {}
    as_of = str(meta.get("as_of") or "")[:10]
    if not as_of:
        flags.append("m3_missing_as_of")
        return finish()
    if meta.get("synthetic"):
        flags.append("m3_synthetic_data")
    if prices.get("adjusted") is not True:
        flags.append("m3_unadjusted_prices")

    min_sessions = int(m3_cfg.get("min_sessions_ma200", 200))
    stale_days = int(m3_cfg.get("stale_calendar_days", 7))
    rsi_period = int(m3_cfg.get("rsi_period", 14))
    macd_cfg = m3_cfg.get("macd") or {}
    macd_fast = int(macd_cfg.get("fast", 12))
    macd_slow = int(macd_cfg.get("slow", 26))
    macd_signal_span = int(macd_cfg.get("signal", 9))
    volume_ma_n = int(m3_cfg.get("volume_ma", 20))
    atr_period = int(m3_cfg.get("atr_period", 14))
    trend_cfg = m3_cfg.get("trend") or {}
    mom_cfg = m3_cfg.get("momentum") or {}
    vol_cfg = m3_cfg.get("volume") or {}
    atr_bands = m3_cfg.get("volatility_atr_pct") or _DEFAULT_M3["volatility_atr_pct"]

    records = []
    invalid_count = 0
    for r in prices.get("rows") or []:
        if not isinstance(r, dict):
            invalid_count += 1
            continue
        day = str(r.get("date") or "")[:10]
        try:
            pd.Timestamp(day)
        except (TypeError, ValueError):
            invalid_count += 1
            continue
        if day > as_of:
            continue
        values = {k: _finite(r.get(k)) for k in ("open", "high", "low", "close", "volume")}
        if (
            any(v is None for v in values.values())
            or min(values["open"], values["high"], values["low"], values["close"]) <= 0
            or values["volume"] < 0
            or values["high"] < values["low"]
            or not values["low"] <= values["close"] <= values["high"]
        ):
            invalid_count += 1
            continue
        records.append({"date": day, **values})

    if invalid_count:
        flags.append("m3_invalid_price_rows_excluded")
    out["metrics"]["invalid_price_rows"] = {
        "value": int(invalid_count),
        "unit": "rows",
    }

    if not records:
        flags.append("m3_no_valid_price_rows")
        return finish()

    df = pd.DataFrame(records)
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").drop_duplicates("date", keep="last").reset_index(drop=True)
    n = len(df)
    out["metrics"]["observations"] = {"value": int(n), "unit": "sessions"}

    if n < min_sessions:
        flags.append("m3_insufficient_history_ma200")
        return finish()

    if (df["date"].iloc[-1].date() - pd.Timestamp(as_of).date()).days < -stale_days:
        flags.append("m3_stale_price_data")

    c, h, l, v = (df[k].astype(float) for k in ("close", "high", "low", "volume"))
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
    rsi = _finite(rsi_series.iloc[-1])
    if avg_loss.iloc[-1] == 0:
        rsi = 100.0 if avg_gain.iloc[-1] > 0 else 50.0

    ema_fast = c.ewm(span=macd_fast, adjust=False).mean()
    ema_slow = c.ewm(span=macd_slow, adjust=False).mean()
    macd = ema_fast - ema_slow
    signal = macd.ewm(span=macd_signal_span, adjust=False).mean()
    histogram = macd - signal
    volume_ma20 = v.rolling(volume_ma_n).mean()
    volume_ratio = (
        _finite(v.iloc[-1] / volume_ma20.iloc[-1]) if volume_ma20.iloc[-1] > 0 else None
    )
    previous_close = c.shift(1)
    true_range = pd.concat(
        [h - l, (h - previous_close).abs(), (l - previous_close).abs()],
        axis=1,
    ).max(axis=1)
    atr14 = true_range.ewm(alpha=1 / atr_period, adjust=False, min_periods=atr_period).mean().iloc[-1]

    last = float(c.iloc[-1])
    m20 = float(ma20.iloc[-1])
    m50 = float(ma50.iloc[-1])
    m200 = float(ma200.iloc[-1])
    md = float(macd.iloc[-1])
    sig = float(signal.iloc[-1])
    hist = float(histogram.iloc[-1])
    atr_pct = float(atr14 / last * 100)

    above_pts = int(trend_cfg.get("above_ma_points", 10))
    align_bonus = int(trend_cfg.get("alignment_bonus", 5))
    trend = (
        (above_pts if last > m20 else 0)
        + (above_pts if last > m50 else 0)
        + (above_pts if last > m200 else 0)
        + (align_bonus if m20 > m50 > m200 else 0)
    )

    macd_sig_pts = int(mom_cfg.get("macd_above_signal", 10))
    macd_zero_pts = int(mom_cfg.get("macd_above_zero", 10))
    rsi_cfg = mom_cfg.get("rsi") or {}
    momentum = (macd_sig_pts if md > sig else 0) + (macd_zero_pts if md > 0 else 0)
    if rsi is not None:
        mid_low = float(rsi_cfg.get("mid_low", 45))
        mid_high = float(rsi_cfg.get("mid_high", 70))
        outer_low = float(rsi_cfg.get("outer_low", 30))
        outer_high = float(rsi_cfg.get("outer_high", 80))
        mid_pts = int(rsi_cfg.get("mid_points", 10))
        outer_pts = int(rsi_cfg.get("outer_points", 5))
        if mid_low <= rsi <= mid_high:
            momentum += mid_pts
        elif outer_low <= rsi < mid_low or mid_high < rsi <= outer_high:
            momentum += outer_pts
    else:
        flags.append("m3_rsi_unavailable")

    volume_score = 0
    ratio_high = float(vol_cfg.get("ratio_high", 1.2))
    ratio_mid = float(vol_cfg.get("ratio_mid", 0.8))
    if volume_ratio is not None:
        up = last > float(c.iloc[-2])
        if up and volume_ratio >= ratio_high:
            volume_score = int(vol_cfg.get("up_high", 20))
        elif up and volume_ratio >= ratio_mid:
            volume_score = int(vol_cfg.get("up_mid", 12))
        elif volume_ratio < ratio_mid:
            volume_score = int(vol_cfg.get("low_ratio", 8))
        else:
            volume_score = int(vol_cfg.get("else_points", 3))
    else:
        flags.append("m3_volume_ratio_unavailable")

    volatility = _volatility_points(atr_pct, atr_bands)
    score = float(trend + momentum + volume_score + volatility)

    out["metrics"].update({
        "close": _metric_num(last, "VND/share"),
        "ma20": _metric_num(m20, "VND/share"),
        "ma50": _metric_num(m50, "VND/share"),
        "ma200": _metric_num(m200, "VND/share"),
        "rsi14": _metric_num(rsi, "points"),
        "macd": _metric_num(md, "VND/share"),
        "macd_signal": _metric_num(sig, "VND/share"),
        "macd_histogram": _metric_num(hist, "VND/share"),
        "volume": _metric_num(v.iloc[-1], "shares"),
        "volume_ma20": _metric_num(volume_ma20.iloc[-1], "shares"),
        "volume_ratio_20": _metric_num(volume_ratio, "times"),
        "atr14": _metric_num(atr14, "VND/share"),
        "atr_pct": _metric_num(atr_pct, "%"),
        "trend_score": _metric_num(trend, "points"),
        "momentum_score": _metric_num(momentum, "points"),
        "volume_score": _metric_num(volume_score, "points"),
        "volatility_score": _metric_num(volatility, "points"),
        "technical_score": _metric_num(score, "points"),
    })
    out["score"] = score
    out["evidence"].append({
        "text": (
            f"Technical indicators from {n} daily sessions through "
            f"{df['date'].iloc[-1].date().isoformat()}; heuristic T score, "
            "not a trade recommendation."
        ),
        "source_id": str(prices.get("source_id") or "unknown"),
    })
    out["flags"] = list(dict.fromkeys(flags))
    out["status"] = "partial" if out["flags"] else "ok"
    return finish()
