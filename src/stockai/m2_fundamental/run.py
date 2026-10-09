
"""M2 - Fundamental analysis.
Reads snapshot.financials and returns module_out (F score).
"""

from __future__ import annotations

import math
from typing import Any


def _number(value: Any) -> float | None:
    """Convert a finite numeric value; missing/invalid values remain None."""
    if value is None or isinstance(value, bool):
        return None
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _divide(numerator: Any, denominator: Any) -> float | None:
    n = _number(numerator)
    d = _number(denominator)
    if n is None or d is None or d == 0:
        return None
    result = n / d
    return result if math.isfinite(result) else None


def _clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def _metric(
    value: float | None,
    unit: str,
    note: str | None = None,
) -> dict:
    result = {"value": value, "unit": unit}
    if note:
        result["note"] = note
    return result


def _get_items(row: dict) -> dict:
    items = row.get("items")
    return items if isinstance(items, dict) else {}


def _eligible_annual_rows(snapshot: dict, flags: list[str]) -> list[dict]:
    """Keep only annual reports published on or before meta.as_of."""
    financials = snapshot.get("financials")
    if not isinstance(financials, dict):
        return []

    rows = financials.get("annual")
    if not isinstance(rows, list) or not rows:
        return []

    as_of = (snapshot.get("meta") or {}).get("as_of")
    if not as_of:
        flags.append("m2_missing_as_of")
        return []

    eligible = []
    for row in rows:
        if not isinstance(row, dict):
            continue

        published_at = row.get("published_at")
        if not isinstance(published_at, str) or not published_at:
            continue

        # ISO date strings are sortable chronologically.
        if published_at[:10] <= str(as_of)[:10]:
            eligible.append(row)

    eligible.sort(
        key=lambda row: (
            str(row.get("period", "")),
            str(row.get("published_at", "")),
        ),
        reverse=True,
    )
    return eligible


def _base_output(
    status: str,
    score: float | None,
    metrics: dict | None = None,
    evidence: list | None = None,
    flags: list | None = None,
    error: str | None = None,
) -> dict:
    out = {
        "module": "m2",
        "status": status,
        "score": score,
        "metrics": metrics or {},
        "evidence": evidence or [],
        "flags": list(dict.fromkeys(flags or [])),
    }
    if error:
        out["error"] = error
    return out


def _add_metric(
    metrics: dict,
    key: str,
    value: float | None,
    unit: str,
    note: str | None = None,
) -> None:
    metrics[key] = _metric(value, unit, note)


def _growth(current: Any, previous: Any) -> float | None:
    current_value = _number(current)
    previous_value = _number(previous)
    if (
        current_value is None
        or previous_value is None
        or previous_value == 0
    ):
        return None
    return (current_value - previous_value) / abs(previous_value)


def _evidence_for_rows(rows: list[dict]) -> list[dict]:
    evidence = []
    seen = set()

    for row in rows:
        source_id = row.get("source_id")
        if not source_id or source_id in seen:
            continue
        seen.add(source_id)
        evidence.append({
            "text": (
                "Financial statement for period "
                f"{row.get('period', 'unknown')} "
                f"(published {row.get('published_at', 'unknown')})."
            ),
            "source_id": source_id,
        })

    return evidence


def _score_nonbank(metrics: dict) -> float:
    """Transparent heuristic score for non-bank companies."""
    roe = metrics["roe"]["value"]
    profit_growth = metrics["net_income_growth"]["value"]
    debt_equity = metrics["debt_to_equity"]["value"]
    cashflow_quality = metrics["cfo_to_net_income"]["value"]
    interest_coverage = metrics["interest_coverage"]["value"]

    components = []

    if roe is not None:
        components.append((0.25, _clamp(roe * 400)))
    if profit_growth is not None:
        components.append((0.20, _clamp(50 + profit_growth * 100)))
    if debt_equity is not None:
        components.append((0.20, _clamp(100 - debt_equity * 50)))
    if cashflow_quality is not None:
        components.append((0.20, _clamp(cashflow_quality * 60)))
    if interest_coverage is not None:
        components.append((0.15, _clamp(interest_coverage * 10)))

    if not components:
        return 50.0

    weight_sum = sum(weight for weight, _ in components)
    return round(
        sum(weight * value for weight, value in components) / weight_sum,
        2,
    )


def _score_bank(metrics: dict) -> float:
    """Bank score based on bank-relevant metrics only."""
    roe = metrics["roe"]["value"]
    profit_growth = metrics["net_income_growth"]["value"]
    nim = metrics["nim"]["value"]
    cir = metrics["cir"]["value"]
    loan_to_deposit = metrics["loan_to_deposit"]["value"]

    components = []

    if roe is not None:
        components.append((0.25, _clamp(roe * 400)))
    if profit_growth is not None:
        components.append((0.15, _clamp(50 + profit_growth * 100)))
    if nim is not None:
        components.append((0.25, _clamp(nim / 0.04 * 100)))
    if cir is not None:
        components.append((0.20, _clamp(100 - cir * 100)))
    if loan_to_deposit is not None:
        # A ratio near 1.0 scores well; unusually high leverage is penalized.
        components.append((
            0.15,
            _clamp(100 - max(0.0, loan_to_deposit - 1.0) * 100),
        ))

    if not components:
        return 50.0

    weight_sum = sum(weight for weight, _ in components)
    return round(
        sum(weight * value for weight, value in components) / weight_sum,
        2,
    )


def run(snapshot: dict, upstream: dict, cfg: dict) -> dict:
    """Calculate M2 fundamental score without modifying other modules."""
    flags: list[str] = []

    if not isinstance(snapshot, dict):
        return _base_output(
            "error", None, flags=["m2_invalid_snapshot"],
            error="Snapshot must be a dictionary.",
        )

    rows = _eligible_annual_rows(snapshot, flags)
    if not rows:
        flags.append("m2_financials_unavailable")
        return _base_output(
            "error",
            None,
            flags=flags,
            error="No eligible annual financial statements are available.",
        )

    company = snapshot.get("company") or {}
    is_bank = company.get("is_bank") is True

    latest = rows[0]
    previous = rows[1] if len(rows) > 1 else None
    items = _get_items(latest)
    previous_items = _get_items(previous) if previous else {}

    metrics: dict = {}
    latest_period = str(latest.get("period", "latest period"))

    # Core profitability metrics.
    roe = _divide(items.get("net_income_parent"), items.get("total_equity"))
    if roe is None:
        # Use net income if parent-attributable income is unavailable.
        roe = _divide(items.get("net_income"), items.get("total_equity"))

    net_income_growth = _growth(
        items.get("net_income_parent", items.get("net_income")),
        previous_items.get("net_income_parent", previous_items.get("net_income")),
    )
    revenue_growth = _growth(
        items.get("revenue"), previous_items.get("revenue")
    )

    _add_metric(metrics, "roe", roe, "ratio")
    _add_metric(metrics, "net_income_growth", net_income_growth, "ratio")
    _add_metric(metrics, "revenue_growth", revenue_growth, "ratio")

    if roe is None:
        flags.append("m2_missing_roe")
    if net_income_growth is None:
        flags.append("m2_missing_net_income_growth")
    if revenue_growth is None:
        flags.append("m2_missing_revenue_growth")

    if is_bank:
        # Bank-specific criteria: never apply industrial-company debt/equity
        # or gross-margin scoring to a bank.
        nim = _number(items.get("nim"))
        cir = _number(items.get("cir"))
        loan_to_deposit = _divide(
            items.get("customer_loans"),
            items.get("customer_deposits"),
        )
        npl_ratio = _number(items.get("npl_ratio"))
        car = _number(items.get("car"))

        _add_metric(metrics, "nim", nim, "ratio")
        _add_metric(metrics, "cir", cir, "ratio")
        _add_metric(metrics, "loan_to_deposit", loan_to_deposit, "ratio")
        _add_metric(metrics, "npl_ratio", npl_ratio, "ratio")
        _add_metric(metrics, "car", car, "ratio")

        if nim is None:
            flags.append("m2_missing_nim")
        if cir is None:
            flags.append("m2_missing_cir")
        if loan_to_deposit is None:
            flags.append("m2_missing_loan_to_deposit")
        if npl_ratio is None:
            flags.append("m2_missing_npl_ratio")
        if car is None:
            flags.append("m2_missing_car")

        score = _score_bank(metrics)

        # Missing material bank-risk indicators mean the result is partial.
        status = (
            "partial"
            if any(
                metrics[key]["value"] is None
                for key in ("roe", "nim", "cir", "loan_to_deposit",
                            "npl_ratio", "car")
            )
            else "ok"
        )

    else:
        # Non-bank metrics.
        gross_margin = _divide(
            items.get("gross_profit"), items.get("revenue")
        )
        debt = _number(items.get("short_term_debt"))
        long_term_debt = _number(items.get("long_term_debt"))
        if debt is not None and long_term_debt is not None:
            total_debt = debt + long_term_debt
        elif debt is not None:
            total_debt = debt
        elif long_term_debt is not None:
            total_debt = long_term_debt
        else:
            total_debt = None

        debt_to_equity = _divide(total_debt, items.get("total_equity"))
        debt_to_assets = _divide(total_debt, items.get("total_assets"))
        interest_coverage = _divide(
            items.get("ebit"), items.get("interest_expense")
        )
        cfo_to_net_income = _divide(
            items.get("cfo"), items.get("net_income")
        )
        current_ratio = _divide(
            items.get("current_assets"), items.get("current_liabilities")
        )

        _add_metric(metrics, "gross_margin", gross_margin, "ratio")
        _add_metric(metrics, "debt_to_equity", debt_to_equity, "ratio")
        _add_metric(metrics, "debt_to_assets", debt_to_assets, "ratio")
        _add_metric(metrics, "interest_coverage", interest_coverage, "x")
        _add_metric(metrics, "cfo_to_net_income", cfo_to_net_income, "ratio")
        _add_metric(metrics, "current_ratio", current_ratio, "x")

        if gross_margin is None:
            flags.append("m2_missing_gross_margin")
        if debt_to_equity is None:
            flags.append("m2_missing_debt_to_equity")
        if interest_coverage is None:
            flags.append("m2_missing_interest_coverage")
        if cfo_to_net_income is None:
            flags.append("m2_missing_cfo_to_net_income")
        if current_ratio is None:
            flags.append("m2_missing_current_ratio")

        score = _score_nonbank(metrics)
        status = (
            "partial"
            if any(
                metrics[key]["value"] is None
                for key in (
                    "roe", "net_income_growth", "gross_margin",
                    "debt_to_equity", "interest_coverage",
                    "cfo_to_net_income",
                )
            )
            else "ok"
        )

    evidence = _evidence_for_rows(
        [row for row in (latest, previous) if row is not None]
    )

    # Keep the score within the shared module_out contract.
    score = round(_clamp(score), 2)

    return _base_output(
        status=status,
        score=score,
        metrics=metrics,
        evidence=evidence,
        flags=flags,
    )