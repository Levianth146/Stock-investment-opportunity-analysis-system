"""Technical score (T) from adjusted closing prices in the M1 snapshot."""
from __future__ import annotations

def _clamp(value: float, low: float = 0, high: float = 100) -> float:
    return max(low, min(high, value))


def run(snapshot: dict, upstream: dict, cfg: dict) -> dict:
    out = {"module": "m3", "status": "partial", "score": None, "metrics": {}, "evidence": [], "flags": []}
    rows = sorted(snapshot.get("prices", {}).get("rows", []), key=lambda row: row.get("date", ""))
    closes = [
        float(row["close"])
        for row in rows
        if isinstance(row.get("close"), (int, float)) and row["close"] > 0
    ]
    if len(closes) < 20:
        out.update(status="partial", evidence=[], flags=["insufficient_price_history_for_technical_score"])
        return out

    changes = [current - previous for previous, current in zip(closes, closes[1:])]
    recent_changes = changes[-14:]
    avg_gain = sum(max(change, 0) for change in recent_changes) / len(recent_changes)
    avg_loss = sum(max(-change, 0) for change in recent_changes) / len(recent_changes)
    if avg_loss == 0:
        rsi = 100.0 if avg_gain > 0 else 50.0
    else:
        rsi = 100 - 100 / (1 + avg_gain / avg_loss)

    latest = closes[-1]
    ma20 = sum(closes[-20:]) / 20
    ma50 = sum(closes[-50:]) / 50 if len(closes) >= 50 else None
    ma200 = sum(closes[-200:]) / 200 if len(closes) >= 200 else None
    momentum20 = (latest / closes[-21] - 1) * 100
    trend_scores = [50 + _clamp((latest / ma20 - 1) * 500, -50, 50)]
    if ma50 is not None:
        trend_scores.append(50 + _clamp((latest / ma50 - 1) * 250, -50, 50))
    if ma200 is not None:
        trend_scores.append(50 + _clamp((latest / ma200 - 1) * 150, -50, 50))
    momentum_score = 50 + _clamp(momentum20 * 2, -50, 50)
    rsi_score = 100 - abs(rsi - 55) * (100 / 55) if rsi <= 55 else 100 - (rsi - 55) * (100 / 45)
    components = trend_scores + [momentum_score, _clamp(rsi_score)]
    out["score"] = round(sum(components) / len(components), 2)
    out["metrics"] = {
        "ma20": {"value": round(ma20, 2), "unit": "VND"},
        "ma50": {"value": round(ma50, 2) if ma50 is not None else None, "unit": "VND"},
        "ma200": {"value": round(ma200, 2) if ma200 is not None else None, "unit": "VND"},
        "rsi14": {"value": round(rsi, 2), "unit": "index"},
        "momentum20": {"value": round(momentum20, 2), "unit": "%"},
        "sessions": {"value": len(closes), "unit": "sessions"},
    }
    out["status"] = "ok" if len(closes) >= 200 else "partial"
    out["flags"] = [] if len(closes) >= 200 else ["price_history_shorter_than_200_sessions"]
    out["evidence"] = [{
        "text": f"Giá điều chỉnh so với MA20: {latest / ma20 - 1:+.1%}; RSI14 {rsi:.1f}; động lượng 20 phiên {momentum20:+.1f}%.",
        "source_id": snapshot.get("prices", {}).get("source_id", ""),
    }]
    return out
