"""Cầu doanh thu → LNST (feature 014e). Không bịa số; thiếu gộp vào «Khác»."""
from __future__ import annotations

from typing import Any


def _num(v: Any) -> float | None:
    if v is None:
        return None
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    if x != x:
        return None
    return x


def build_income_bridge(items: dict[str, Any] | None) -> dict[str, Any] | None:
    """Xây cầu từ items (cùng đơn vị).

    Trả ``None`` nếu thiếu doanh thu hoặc LNST CĐCT mẹ.
    ``steps``: {label, value, kind} với kind ``absolute`` (neo) hoặc ``delta``.
    ``start + Σ delta == end`` trong sai số 1e-6.
    """
    if not isinstance(items, dict):
        return None
    rev = _num(items.get("revenue"))
    nip = _num(items.get("net_income_parent"))
    if nip is None:
        nip = _num(items.get("net_income"))
    if rev is None or nip is None:
        return None

    gp = _num(items.get("gross_profit"))
    selling = _num(items.get("selling_expense"))
    admin = _num(items.get("admin_expense"))
    ebit = _num(items.get("ebit"))
    interest = _num(items.get("interest_expense"))
    pretax = _num(items.get("pretax_profit"))

    # Chuỗi neo có sẵn (bỏ qua null)
    path: list[tuple[str, float]] = [("Doanh thu", rev)]
    if gp is not None:
        path.append(("LN gộp", gp))
    if ebit is not None:
        path.append(("LN HĐ", ebit))
    if pretax is not None:
        path.append(("LNTT", pretax))
    path.append(("LNST CĐCT mẹ", nip))

    # Gỡ neo trùng giá trị liền kề
    cleaned: list[tuple[str, float]] = [path[0]]
    for lab, val in path[1:]:
        if abs(val - cleaned[-1][1]) < 1e-12 and lab != "LNST CĐCT mẹ":
            continue
        cleaned.append((lab, val))
    path = cleaned

    steps: list[dict[str, Any]] = [
        {"label": path[0][0], "value": path[0][1], "kind": "absolute"},
    ]

    for i in range(len(path) - 1):
        a_lab, a_val = path[i]
        b_lab, b_val = path[i + 1]
        needed = b_val - a_val  # thường âm khi giảm

        comps: list[tuple[str, float]] = []
        if a_lab == "Doanh thu" and b_lab == "LN gộp":
            comps.append(("Giá vốn", needed))
        elif a_lab in ("Doanh thu", "LN gộp") and b_lab == "LN HĐ":
            sga = None
            if selling is not None or admin is not None:
                sga = (selling or 0.0) + (admin or 0.0)
            if sga is not None and a_lab == "LN gộp":
                comps.append(("Chi phí BH+QL", -sga))
                residual = needed - (-sga)
                if abs(residual) > 1e-9:
                    comps.append(("Khác", residual))
            else:
                comps.append(("Khác", needed))
        elif b_lab == "LNTT":
            if interest is not None and a_lab == "LN HĐ":
                comps.append(("Lãi vay và khác", -interest))
                residual = needed - (-interest)
                if abs(residual) > 1e-9:
                    comps.append(("Khác", residual))
            else:
                comps.append(("Lãi vay và khác", needed))
        elif b_lab == "LNST CĐCT mẹ":
            comps.append(("Thuế và CĐTS", needed))
        else:
            comps.append(("Khác", needed))

        for lab, val in comps:
            if abs(val) < 1e-12:
                continue
            steps.append({"label": lab, "value": val, "kind": "delta"})
        steps.append({"label": b_lab, "value": b_val, "kind": "absolute"})

    # Gộp «Khác» liền kề
    merged: list[dict[str, Any]] = []
    for s in steps:
        if (
            merged
            and s["label"] == "Khác"
            and merged[-1]["label"] == "Khác"
            and s["kind"] == "delta"
            and merged[-1]["kind"] == "delta"
        ):
            merged[-1]["value"] = float(merged[-1]["value"]) + float(s["value"])
        else:
            merged.append(dict(s))

    check = rev
    for s in merged[1:]:
        if s["kind"] == "delta":
            check += float(s["value"])
        else:
            check = float(s["value"])

    return {
        "start": rev,
        "end": nip,
        "steps": merged,
        "reconcile_ok": abs(check - nip) <= 1e-6,
    }


def sum_items(
    periods: list[dict[str, Any]], keys: tuple[str, ...]
) -> dict[str, float | None]:
    """Cộng chỉ tiêu qua nhiều kỳ (TTM)."""
    acc: dict[str, float | None] = {k: None for k in keys}
    for p in periods:
        items = p.get("items") if isinstance(p.get("items"), dict) else {}
        for k in keys:
            v = _num(items.get(k))
            if v is None:
                continue
            acc[k] = v if acc[k] is None else float(acc[k]) + v
    return acc


BRIDGE_KEYS = (
    "revenue",
    "gross_profit",
    "selling_expense",
    "admin_expense",
    "ebit",
    "interest_expense",
    "pretax_profit",
    "net_income",
    "net_income_parent",
    "dividends_paid",
)
