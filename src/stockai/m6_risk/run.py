"""Risk penalty (R) from realized volatility, drawdown and benchmark beta."""
from __future__ import annotations

from math import sqrt
from statistics import mean, stdev

def _price_map(rows: list[dict]) -> dict[str, float]:
    return {
        row["date"]: float(row["close"])
        for row in rows
        if isinstance(row.get("close"), (int, float)) and row["close"] > 0
    }


def _clamp(value: float, low: float = 0, high: float = 100) -> float:
    return max(low, min(high, value))


def run(snapshot: dict, upstream: dict, cfg: dict) -> dict:
    out = {"module": "m6", "status": "partial", "score": None, "metrics": {}, "evidence": [], "flags": []}
    stock_rows = snapshot.get("prices", {}).get("rows", [])
    index_rows = snapshot.get("index", {}).get("rows", [])
    stock = _price_map(stock_rows)
    index = _price_map(index_rows)
    dates = sorted(set(stock) & set(index))
    if len(dates) < 31:
        out.update(status="partial", evidence=[], flags=["insufficient_aligned_prices_for_risk_score"])
        return out

    dates = dates[-253:]
    stock_returns = [stock[right] / stock[left] - 1 for left, right in zip(dates, dates[1:])]
    index_returns = [index[right] / index[left] - 1 for left, right in zip(dates, dates[1:])]
    volatility = stdev(stock_returns) * sqrt(252) * 100 if len(stock_returns) > 1 else None
    peak = stock[dates[0]]
    drawdowns = []
    for day in dates:
        peak = max(peak, stock[day])
        drawdowns.append((stock[day] / peak - 1) * 100)
    max_drawdown = min(drawdowns)
    variance = sum((value - mean(index_returns)) ** 2 for value in index_returns) / (len(index_returns) - 1)
    covariance = sum(
        (stock_return - mean(stock_returns)) * (index_return - mean(index_returns))
        for stock_return, index_return in zip(stock_returns, index_returns)
    ) / (len(stock_returns) - 1)
    beta = covariance / variance if variance > 0 else None
    volatility_risk = _clamp(volatility / 60 * 100) if volatility is not None else None
    drawdown_risk = _clamp(abs(max_drawdown) / 50 * 100)
    out["score"] = round(
        0.6 * volatility_risk + 0.4 * drawdown_risk
        if volatility_risk is not None else drawdown_risk,
        2,
    )
    out["status"] = "ok" if len(stock_returns) >= 200 else "partial"
    out["flags"] = [] if len(stock_returns) >= 200 else ["risk_window_shorter_than_200_returns"]
    out["metrics"] = {
        "annualized_volatility": {"value": round(volatility, 2) if volatility is not None else None, "unit": "%"},
        "max_drawdown": {"value": round(max_drawdown, 2), "unit": "%"},
        "beta": {"value": round(beta, 3) if beta is not None else None, "unit": "x", "note": snapshot.get("index", {}).get("symbol", "benchmark")},
        "aligned_returns": {"value": len(stock_returns), "unit": "sessions"},
    }
    out["evidence"] = [{
        "text": f"Biến động năm hóa {volatility:.1f}%, drawdown tối đa {max_drawdown:.1f}%"
        + (f", beta {beta:.2f}." if beta is not None else "."),
        "source_id": snapshot.get("prices", {}).get("source_id", ""),
    }]
    return out
