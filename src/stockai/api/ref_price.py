"""Quy tắc giá tham chiếu ngành — khớp web/src/refPrice.ts."""
from __future__ import annotations

from typing import Any


REF_UNRELIABLE_LABEL = "Chưa đủ tin cậy"


def evaluate_ref_gap(
    price: float | None,
    ref: float | None,
) -> dict[str, Any]:
    """Nếu |ref/price - 1| > 0.5 → không hiện số, nhãn chưa đủ tin cậy."""
    if (
        price is None
        or ref is None
        or not isinstance(price, (int, float))
        or not isinstance(ref, (int, float))
        or price <= 0
    ):
        return {
            "display": None,
            "gap_pct": None,
            "unreliable": False,
            "label": None,
        }
    ratio = float(ref) / float(price) - 1.0
    if abs(ratio) > 0.5:
        return {
            "display": None,
            "gap_pct": None,
            "unreliable": True,
            "label": REF_UNRELIABLE_LABEL,
        }
    return {
        "display": float(ref),
        "gap_pct": round(ratio * 100.0, 2),
        "unreliable": False,
        "label": None,
    }
