"""Chuẩn hoá BCTC cho GET /api/tickers/{symbol}/financials (feature 014).

Đơn vị phản hồi: tỷ VND (chia 1e9 một lần từ snapshot ``financials.unit`` = VND).
ROE năm: LNST cổ đông mẹ / vốn chủ sở hữu trung bình (đầu kỳ + cuối kỳ)/2;
nếu thiếu vốn đầu kỳ thì dùng vốn cuối kỳ. Ghi rõ trong ``meta.roe_basis``.
Không điền số thiếu — để null.
"""
from __future__ import annotations

from typing import Any

# Chia VND thô → tỷ VND
_VND_TO_BILLION = 1e9
# Cổ tức bất thường (unit mismatch): |div|/|NI| < 0.0001 khi NI đủ lớn.
# Payout > 100% KHÔNG gắn cờ — chỉ chú thích "Chi trả vượt LNST năm đó".
_DIV_NI_MIN_VND = 100e9
_DIV_RATIO_TOO_SMALL = 0.0001
_DIV_PAYOUT_OVER_NOTE = "Chi trả vượt LNST năm đó"

_RAW_KEYS = (
    "revenue",
    "gross_profit",
    "net_income",
    "net_income_parent",
    "total_equity",
    "short_term_debt",
    "long_term_debt",
    "cfo",
    "capex",
    "total_assets",
    "total_liabilities",
    "eps",
    # Additive 014e — cầu P&L / cổ tức (đã có trên snapshot)
    "selling_expense",
    "admin_expense",
    "ebit",
    "interest_expense",
    "pretax_profit",
    "dividends_paid",
)


def _num(v: Any) -> float | None:
    if v is None:
        return None
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    if x != x:  # NaN
        return None
    return x


def _to_billion(v: float | None) -> float | None:
    if v is None:
        return None
    return round(v / _VND_TO_BILLION, 6)


def _div(a: float | None, b: float | None) -> float | None:
    if a is None or b is None or b == 0:
        return None
    return a / b


def _yoy(curr: float | None, prev: float | None) -> float | None:
    if curr is None or prev is None or prev == 0:
        return None
    return (curr - prev) / abs(prev)


def _total_debt(items: dict) -> float | None:
    st = _num(items.get("short_term_debt"))
    lt = _num(items.get("long_term_debt"))
    if st is None and lt is None:
        return None
    return (st or 0.0) + (lt or 0.0)


def dividends_implausible(
    dividends_paid: float | None,
    net_income_parent: float | None,
    *,
    ni_min_vnd: float = _DIV_NI_MIN_VND,
    too_small: float = _DIV_RATIO_TOO_SMALL,
) -> bool:
    """True chỉ khi nghi lệch đơn vị: |div|/|NI| < 0.0001 (NI đủ lớn).

    Payout > 100% không gắn cờ (dùng ``dividend_notes``). ``div == 0`` hợp lệ.
    """
    div = _num(dividends_paid)
    nip = _num(net_income_parent)
    if div is None or nip is None or nip == 0 or div == 0:
        return False
    ratio = abs(div) / abs(nip)
    if abs(nip) > ni_min_vnd and ratio < too_small:
        return True
    return False


def dividend_payout_note(
    dividends_paid: float | None,
    net_income_parent: float | None,
) -> str | None:
    """Chú thích khi chi trả vượt LNST năm đó (không làm mờ / không gắn cờ)."""
    div = _num(dividends_paid)
    nip = _num(net_income_parent)
    if div is None or nip is None or nip == 0 or div == 0:
        return None
    if abs(div) / abs(nip) > 1.0:
        return _DIV_PAYOUT_OVER_NOTE
    return None


def _period_sort_key(period: Any) -> tuple[int, int, str]:
    """Sắp kỳ tăng dần: năm ``YYYY`` hoặc quý ``YYYYQn``."""
    s = str(period or "")
    if len(s) == 4 and s.isdigit():
        return (int(s), 0, s)
    if "Q" in s.upper():
        # dạng 2024Q3 hoặc 2024 Q3
        try:
            y = int(s[:4])
            q = int("".join(ch for ch in s[4:] if ch.isdigit()) or "0")
            return (y, q, s)
        except ValueError:
            return (0, 0, s)
    return (0, 0, s)


def _enrich_series(periods: list[dict], *, kind: str) -> list[dict[str, Any]]:
    """Thêm chỉ số phái sinh; periods đã sort tăng dần."""
    out: list[dict[str, Any]] = []
    for i, p in enumerate(periods):
        items = p.get("items") if isinstance(p.get("items"), dict) else {}
        rev = _num(items.get("revenue"))
        gp = _num(items.get("gross_profit"))
        ni = _num(items.get("net_income"))
        nip = _num(items.get("net_income_parent"))
        if nip is None:
            nip = ni
        eq = _num(items.get("total_equity"))
        debt = _total_debt(items)
        cfo = _num(items.get("cfo"))
        capex = _num(items.get("capex"))

        prev_eq = None
        if i > 0:
            prev_items = periods[i - 1].get("items") if isinstance(periods[i - 1].get("items"), dict) else {}
            prev_eq = _num(prev_items.get("total_equity"))

        if kind == "annual":
            if eq is not None and prev_eq is not None:
                avg_eq = (eq + prev_eq) / 2.0
                roe = _div(nip, avg_eq)
                roe_basis = "avg_equity"
            else:
                roe = _div(nip, eq)
                roe_basis = "ending_equity" if eq is not None else None
        else:
            # Quý: ROE trên vốn cuối kỳ (không annualize) — minh bạch trong field
            roe = _div(nip, eq)
            roe_basis = "ending_equity" if eq is not None else None

        prev = periods[i - 1] if i > 0 else None
        prev_items = prev.get("items") if prev and isinstance(prev.get("items"), dict) else {}
        prev_rev = _num(prev_items.get("revenue")) if prev else None
        prev_ni = _num(prev_items.get("net_income")) if prev else None
        if prev_ni is None and prev:
            prev_ni = _num(prev_items.get("net_income_parent"))

        raw_billion = {k: _to_billion(_num(items.get(k))) for k in _RAW_KEYS}
        div_raw = _num(items.get("dividends_paid"))
        period_flags: list[str] = []
        notes: list[str] = []
        if kind == "annual" and dividends_implausible(div_raw, nip):
            period_flags.append("dividends_implausible")
        if kind == "annual":
            note = dividend_payout_note(div_raw, nip)
            if note:
                notes.append(note)

        row: dict[str, Any] = {
            "period": p.get("period"),
            "published_at": p.get("published_at"),
            "published_at_estimated": bool(p.get("published_at_estimated")),
            "source_id": p.get("source_id"),
            "items": raw_billion,
            "gross_margin": _div(gp, rev),
            "net_margin": _div(ni if ni is not None else nip, rev),
            "roe": roe,
            "roe_basis": roe_basis,
            "debt_to_equity": _div(debt, eq),
            "fcf": _to_billion((cfo - capex) if cfo is not None and capex is not None else None),
            "revenue_yoy": _yoy(rev, prev_rev) if kind == "annual" else None,
            "net_income_yoy": _yoy(ni if ni is not None else nip, prev_ni) if kind == "annual" else None,
            "revenue_qoq": _yoy(rev, prev_rev) if kind == "quarterly" else None,
            "flags": period_flags,
            "notes": notes,
        }
        out.append(row)
    return out


def build_financials_payload(snapshot: dict, *, asof: str, disclaimer: str) -> dict[str, Any]:
    """Tạo payload financials từ snapshot. Kỳ tăng dần; tối đa 10 năm / 8 quý."""
    fin = snapshot.get("financials") if isinstance(snapshot.get("financials"), dict) else {}
    annual_raw = [p for p in (fin.get("annual") or []) if isinstance(p, dict)]
    quarterly_raw = [p for p in (fin.get("quarterly") or []) if isinstance(p, dict)]
    annual_raw = sorted(annual_raw, key=lambda p: _period_sort_key(p.get("period")))[-10:]
    quarterly_raw = sorted(quarterly_raw, key=lambda p: _period_sort_key(p.get("period")))[-8:]

    return {
        "asof": asof,
        "disclaimer": disclaimer,
        "symbol": (snapshot.get("meta") or {}).get("ticker"),
        "meta": {
            "unit": "VND_billions",
            "unit_note": "Số liệu gốc VND đã chia 1e9 → tỷ VND; tỷ suất (margin, ROE, D/E, YoY/QoQ) là tỷ lệ thập phân.",
            "roe_basis": "annual: LNST cổ đông mẹ / vốn CSH trung bình (đầu+cuối)/2, thiếu đầu kỳ thì vốn cuối kỳ; quarterly: / vốn cuối kỳ (không annualize).",
            "fcf_note": "fcf = cfo - capex (capex lưu dương là chi đầu tư).",
            "source_unit": fin.get("unit") or "VND",
            "n_annual": len(annual_raw),
            "n_quarterly": len(quarterly_raw),
        },
        "annual": _enrich_series(annual_raw, kind="annual"),
        "quarterly": _enrich_series(quarterly_raw, kind="quarterly"),
    }
