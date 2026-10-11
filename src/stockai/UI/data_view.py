from __future__ import annotations

from collections.abc import Iterable
from typing import Any


def _ordered_prices(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        (
            row
            for row in rows
            if isinstance(row.get("close"), (int, float))
        ),
        key=lambda row: row["date"],
    )


def market_summary(snapshot: dict[str, Any]) -> dict[str, Any] | None:
    prices = _ordered_prices(snapshot.get("prices", {}).get("rows", []))
    if not prices:
        return None

    latest = prices[-1]
    previous_close = prices[-2]["close"] if len(prices) > 1 else None
    change_pct = (
        (latest["close"] - previous_close) / previous_close * 100
        if previous_close
        else None
    )
    return {
        "date": latest["date"],
        "close": latest["close"],
        "change_pct": change_pct,
        "volume": latest.get("volume"),
    }


def close_history(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {"date": row["date"], "close": row["close"]}
        for row in _ordered_prices(rows)
    ]


def technical_summary(rows: Iterable[dict[str, Any]]) -> dict[str, Any] | None:
    closes = [row["close"] for row in _ordered_prices(rows)]
    if not closes:
        return None

    changes = [current - previous for previous, current in zip(closes, closes[1:])]
    gains = [max(change, 0) for change in changes[-14:]]
    losses = [max(-change, 0) for change in changes[-14:]]
    avg_gain = sum(gains) / len(gains) if gains else 0
    avg_loss = sum(losses) / len(losses) if losses else 0
    if len(changes) < 14:
        rsi14 = None
    elif avg_loss == 0:
        rsi14 = 100.0 if avg_gain > 0 else 50.0
    else:
        relative_strength = avg_gain / avg_loss
        rsi14 = 100 - 100 / (1 + relative_strength)

    return {
        "ma20": sum(closes[-20:]) / 20 if len(closes) >= 20 else None,
        "ma50": sum(closes[-50:]) / 50 if len(closes) >= 50 else None,
        "rsi14": rsi14,
        "sessions": len(closes),
    }


def annual_financial_table(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    periods = [
        period
        for period in snapshot.get("financials", {}).get("annual", [])
        if isinstance(period.get("items"), dict)
    ]
    periods.sort(key=lambda period: period.get("period", ""), reverse=True)
    metrics = (
        ("Doanh thu (tỷ VNĐ)", "revenue", 1_000_000_000),
        ("Lợi nhuận gộp (tỷ VNĐ)", "gross_profit", 1_000_000_000),
        ("Lợi nhuận sau thuế (tỷ VNĐ)", "net_income", 1_000_000_000),
        ("EPS (VNĐ)", "eps", 1),
    )
    rows = []
    for label, item_name, divisor in metrics:
        values = {
            period["period"]: round(value / divisor, 2)
            for period in periods
            if (value := period["items"].get(item_name)) is not None
        }
        if values:
            rows.append({"Chỉ tiêu": label, **values})
    return rows
