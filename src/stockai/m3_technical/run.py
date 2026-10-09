"""M3 deterministic technical-analysis module."""

from __future__ import annotations

from collections.abc import Mapping
from math import isfinite

from stockai.m3_technical.indicators import standard_indicators, volume_ratio
from stockai.m3_technical.scoring import score_components, technical_rating


def run(snapshot: dict, upstream: dict, cfg: dict) -> dict:
    del upstream, cfg
    base = {
        "module": "m3", "status": "error", "score": None,
        "metrics": {}, "evidence": [], "flags": [],
    }
    if not isinstance(snapshot, dict) or not isinstance(snapshot.get("prices"), dict):
        base["flags"].append("m3_unusable_prices")
        return base

    prices = snapshot["prices"]
    source_id = prices.get("source_id")
    if prices.get("adjusted") is not True:
        base["flags"].append("m3_unadjusted_prices")
        return base
    rows = prices.get("rows")
    as_of = (snapshot.get("meta") or {}).get("as_of")
    if not isinstance(rows, list) or not isinstance(as_of, str):
        base["flags"].append("m3_unusable_prices")
        return base

    excluded = sum(
        1 for row in rows
        if isinstance(row, Mapping)
        and isinstance(row.get("date"), str)
        and row["date"] > as_of
    )
    usable_rows = [
        row for row in rows
        if isinstance(row, Mapping)
        and isinstance(row.get("date"), str)
        and row["date"] <= as_of
    ]
    usable_rows.sort(key=lambda row: row["date"])
    if excluded:
        base["flags"].append("m3_lookahead_rows_excluded")
    if not usable_rows:
        base["flags"].append("m3_unusable_prices")
        return base

    closes = [_finite_number(row.get("close")) for row in usable_rows]
    volumes = [_finite_number(row.get("volume")) for row in usable_rows]
    indicator_series = standard_indicators(closes, volumes)
    latest = {name: values[-1] for name, values in indicator_series.items()}
    latest["latest_close"] = closes[-1]
    latest["volume_ratio"] = volume_ratio(volumes[-1], latest["volume_ma20"])
    components = score_components(latest)
    all_values = {**latest, **components}

    units = {
        "latest_close": "price", "sma20": "price", "sma50": "price",
        "sma200": "price", "ema12": "price", "ema26": "price",
        "rsi14": "points", "macd": "price", "macd_signal": "price",
        "macd_histogram": "price", "volume_ma20": "volume",
        "volume_ratio": "ratio", "five_day_return": "fraction",
        "trend_score": "points", "momentum_score": "points",
        "volume_score": "points", "technical_score": "points",
    }
    rating = technical_rating(components["technical_score"])
    metrics = {}
    for name, unit in units.items():
        metric = {"value": all_values.get(name), "unit": unit}
        if name == "technical_score" and rating is not None:
            metric["note"] = rating
        metrics[name] = metric

    flags = list(base["flags"])
    if latest["latest_close"] is None:
        flags.append("m3_missing_close")
    if volumes[-1] is None:
        flags.append("m3_missing_volume")
    for name, flag in (
        ("sma20", "m3_insufficient_history_sma20"),
        ("sma50", "m3_insufficient_history_sma50"),
        ("sma200", "m3_insufficient_history_sma200"),
        ("rsi14", "m3_insufficient_history_rsi14"),
        ("macd", "m3_insufficient_history_macd"),
        ("volume_ma20", "m3_insufficient_history_volume"),
    ):
        if latest[name] is None:
            flags.append(flag)
    if components["technical_score"] is None:
        flags.append("m3_insufficient_history_complete_score")

    evidence = []
    if source_id is not None:
        evidence.append({
            "text": "M3 calculated deterministic technical indicators from adjusted prices.",
            "source_id": source_id,
        })
        if components["trend_score"] is not None:
            evidence.append({
                "text": f"Trend conditions produced {components['trend_score']}/45.",
                "source_id": source_id,
            })
        if latest["rsi14"] is not None:
            evidence.append({
                "text": f"RSI14 is {latest['rsi14']:.2f}; its configured RSI band was scored.",
                "source_id": source_id,
            })
        if latest["macd"] is not None and latest["macd_signal"] is not None:
            evidence.append({
                "text": "MACD versus Signal and zero was scored using the four configured cases.",
                "source_id": source_id,
            })
        if components["volume_score"] is not None:
            evidence.append({
                "text": f"Five-day return and volume ratio produced {components['volume_score']}/20.",
                "source_id": source_id,
            })
        if rating is not None:
            evidence.append({
                "text": f"Technical score is {components['technical_score']}/100 ({rating}).",
                "source_id": source_id,
            })

    base.update({
        "status": "ok" if components["technical_score"] is not None else "partial",
        "score": components["technical_score"],
        "metrics": metrics,
        "evidence": evidence,
        "flags": flags,
    })
    return base


def _finite_number(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    converted = float(value)
    return converted if isfinite(converted) else None
