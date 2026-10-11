"""Fundamental score (F) calculated from the normalized M1 snapshot."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

def _number(items: Mapping[str, Any], key: str) -> float | None:
    value = items.get(key)
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    return None


def _ratio(numerator: float | None, denominator: float | None) -> float | None:
    if numerator is None or denominator in (None, 0):
        return None
    return numerator / denominator


def _between(value: float, anchors: tuple[tuple[float, float], ...]) -> float:
    if value <= anchors[0][0]:
        return anchors[0][1]
    for (left_x, left_y), (right_x, right_y) in zip(anchors, anchors[1:]):
        if value <= right_x:
            fraction = (value - left_x) / (right_x - left_x)
            return left_y + fraction * (right_y - left_y)
    return anchors[-1][1]


def run(snapshot: dict, upstream: dict, cfg: dict) -> dict:
    out = {"module": "m2", "status": "partial", "score": None, "metrics": {}, "evidence": [], "flags": []}
    meta = snapshot.get("meta", {})
    company = snapshot.get("company", {})
    annual = [
        period
        for period in snapshot.get("financials", {}).get("annual", [])
        if period.get("published_at", "")[:10] <= meta.get("as_of", "")
        and isinstance(period.get("items"), dict)
    ]
    annual.sort(key=lambda period: period.get("period", ""))
    if not annual:
        out.update(
            status="partial",
            evidence=[],
            flags=["financials_annual_missing"],
        )
        return out

    latest = annual[-1]
    previous = annual[-2] if len(annual) > 1 else None
    items = latest["items"]
    previous_items = previous["items"] if previous else {}
    is_bank = bool(company.get("is_bank"))
    revenue_key = "total_operating_income" if is_bank else "revenue"
    revenue = _number(items, revenue_key)
    net_income = _number(items, "net_income_parent") or _number(items, "net_income")
    equity = _number(items, "total_equity")
    roe = _ratio(net_income, equity)
    net_margin = _ratio(net_income, revenue)
    revenue_growth = _ratio(
        (revenue - _number(previous_items, revenue_key))
        if revenue is not None and _number(previous_items, revenue_key) is not None
        else None,
        _number(previous_items, revenue_key),
    )
    profit_growth = _ratio(
        (net_income - (_number(previous_items, "net_income_parent") or _number(previous_items, "net_income")))
        if net_income is not None
        and (_number(previous_items, "net_income_parent") or _number(previous_items, "net_income")) is not None
        else None,
        _number(previous_items, "net_income_parent") or _number(previous_items, "net_income"),
    )
    liabilities = _number(items, "total_liabilities")
    debt_to_equity = _ratio(liabilities, equity)
    cashflow_quality = _ratio(_number(items, "cfo"), net_income)
    nim = _number(items, "nim")
    npl = _number(items, "npl_ratio")

    measures: list[tuple[str, float, float]] = []
    if roe is not None:
        measures.append(("roe", _between(roe * 100, ((0, 10), (10, 50), (20, 80), (30, 100))), 0.30))
    if is_bank:
        bank_margin = nim if nim is not None else net_margin
        if bank_margin is not None:
            measures.append(("bank_margin", _between(bank_margin * 100, ((0, 10), (2, 45), (4, 75), (6, 100))), 0.20))
    elif net_margin is not None:
        measures.append(("net_margin", _between(net_margin * 100, ((0, 10), (5, 40), (10, 65), (20, 100))), 0.20))
    growth = profit_growth if profit_growth is not None else revenue_growth
    if growth is not None:
        measures.append(("growth", _between(growth * 100, ((-30, 0), (-10, 25), (0, 45), (10, 65), (30, 90), (50, 100))), 0.25))
    if debt_to_equity is not None and not is_bank:
        measures.append(("leverage", _between(debt_to_equity, ((0, 95), (0.5, 80), (1, 65), (2, 35), (3, 15))), 0.15))
    if cashflow_quality is not None:
        measures.append(("cashflow_quality", _between(cashflow_quality, ((-1, 0), (0, 20), (0.5, 45), (1, 70), (1.5, 90), (2, 100))), 0.10))
    if is_bank and npl is not None:
        measures.append(("credit_quality", _between(npl, ((0, 100), (0.02, 75), (0.04, 45), (0.08, 10))), 0.15))

    out["metrics"] = {
        "roe": {"value": round(roe * 100, 2) if roe is not None else None, "unit": "%"},
        "net_margin": {"value": round(net_margin * 100, 2) if net_margin is not None else None, "unit": "%"},
        "revenue_growth": {"value": round(revenue_growth * 100, 2) if revenue_growth is not None else None, "unit": "%"},
        "net_income_growth": {"value": round(profit_growth * 100, 2) if profit_growth is not None else None, "unit": "%"},
        "debt_to_equity": {"value": round(debt_to_equity, 3) if debt_to_equity is not None else None, "unit": "x"},
        "cashflow_to_net_income": {"value": round(cashflow_quality, 3) if cashflow_quality is not None else None, "unit": "x"},
        "annual_periods": {"value": len(annual), "unit": "years"},
    }
    flags = []
    if len(annual) < 5:
        flags.append("financials_less_than_five_annual_periods")
    if len(measures) < 4:
        flags.append("some_fundamental_indicators_unavailable")
    if meta.get("data_status", {}).get("financials") != "ok":
        flags.append("snapshot_financials_not_fully_ok")

    if len(measures) >= 2:
        weighted_score = sum(score * weight for _, score, weight in measures)
        available_weight = sum(weight for _, _, weight in measures)
        out["score"] = round(weighted_score / available_weight, 2)
        out["status"] = "ok" if not flags else "partial"
        out["evidence"] = [{
            "text": (
                f"BCTC năm {latest.get('period')}: ROE "
                f"{out['metrics']['roe']['value'] if roe is not None else 'chưa có'}%, "
                f"biên lợi nhuận ròng "
                f"{out['metrics']['net_margin']['value'] if net_margin is not None else 'chưa có'}%; "
                "điểm được tính từ các chỉ tiêu có dữ liệu."
            ),
            "source_id": latest.get("source_id", ""),
        }]
    else:
        out["status"] = "partial"
        flags.append("insufficient_fundamental_indicators_for_score")
    out["flags"] = flags
    return out
