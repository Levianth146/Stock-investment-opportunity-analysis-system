"""Suy PE/PB từ snapshot offline — đơn vị VND thô, tôn trọng as_of.

- Giá: close phiên mới nhất date<=as_of, close>0
- EPS TTM: sum(NI parent|NI) đúng 4 quý liên tiếp / shares; KHÔNG cộng items.eps quý
- Equity: total_equity (gồm minority); book_ps = equity/shares
- Không lookahead; không scale thêm đơn vị
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from datetime import date
from typing import Any

_PERIOD_Q = re.compile(r"^(\d{4})Q([1-4])$", re.IGNORECASE)


def _parse_date(value: Any) -> date | None:
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    try:
        return date.fromisoformat(s[:10])
    except ValueError:
        return None


def _finite_pos(x: Any) -> float | None:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(v) or v <= 0:
        return None
    return v


def _finite_num(x: Any) -> float | None:
    """Số hữu hạn (cho phép 0 và âm)."""
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(v):
        return None
    return v


def parse_quarter_period(period: Any) -> tuple[int, int] | None:
    """'2026Q2' → (2026, 2); không hợp lệ → None."""
    if period is None:
        return None
    m = _PERIOD_Q.match(str(period).strip())
    if not m:
        return None
    return int(m.group(1)), int(m.group(2))


def quarter_index(year: int, quarter: int) -> int:
    """Chỉ số quý tuyến tính để kiểm tra liên tiếp."""
    return year * 4 + (quarter - 1)


def quarters_are_consecutive(parsed: list[tuple[int, int]]) -> bool:
    """True khi đúng n quý liên tiếp (không lỗ hổng), n>=1."""
    if len(parsed) < 2:
        return len(parsed) == 1
    idxs = sorted(quarter_index(y, q) for y, q in parsed)
    for i in range(1, len(idxs)):
        if idxs[i] != idxs[i - 1] + 1:
            return False
    return True


def pick_net_income(items: dict) -> float | None:
    """Ưu tiên net_income_parent, else net_income."""
    ni_p = _finite_num(items.get("net_income_parent"))
    if ni_p is not None:
        return ni_p
    return _finite_num(items.get("net_income"))


@dataclass
class MultipleInputs:
    """Input định giá tương đối suy từ snapshot."""

    as_of: date | None = None
    price_close: float | None = None
    price_date: date | None = None
    price_source_id: str | None = None
    eps_used: float | None = None
    eps_source: str | None = None  # ttm_ni | annual
    total_equity: float | None = None
    equity_period: str | None = None
    equity_published: date | None = None
    shares: float | None = None
    book_ps: float | None = None
    pe: float | None = None
    pb: float | None = None
    sector: str | None = None
    is_bank: bool = False
    ticker: str | None = None
    synthetic: bool = False
    lookahead_excluded: int = 0
    flags: list[str] = field(default_factory=list)


def _resolve_eps_ttm_ni(
    quarterly: list,
    as_of: date,
    shares: float | None,
    out: MultipleInputs,
) -> float | None:
    """EPS TTM = sum(NI 4 quý liên tiếp) / shares. Không cộng items.eps."""
    by_period: dict[tuple[int, int], tuple[date, str, float | None]] = {}
    for p in quarterly:
        if not isinstance(p, dict):
            continue
        pub = _parse_date(p.get("published_at"))
        if pub is None:
            continue
        if pub > as_of:
            out.lookahead_excluded += 1
            continue
        parsed = parse_quarter_period(p.get("period"))
        if parsed is None:
            continue
        items = p.get("items") if isinstance(p.get("items"), dict) else {}
        ni = pick_net_income(items)
        period_s = str(p.get("period") or "")
        prev = by_period.get(parsed)
        # Giữ bản published mới hơn; nếu hòa thì ưu tiên bản có NI
        if prev is None or pub > prev[0] or (pub == prev[0] and ni is not None and prev[2] is None):
            by_period[parsed] = (pub, period_s, ni)

    if not by_period:
        return None

    newest = sorted(by_period.keys(), key=lambda t: quarter_index(t[0], t[1]), reverse=True)
    if len(newest) < 4:
        out.flags.append("m4_eps_quarter_gap")
        return None

    last4_keys = newest[:4]
    last4_parsed = list(last4_keys)
    if not quarters_are_consecutive(last4_parsed):
        out.flags.append("m4_eps_quarter_gap")
        return None

    nis: list[float] = []
    for key in last4_keys:
        ni = by_period[key][2]
        if ni is None:
            return None
        nis.append(ni)

    if shares is None or shares <= 0:
        return None

    eps = sum(nis) / shares
    if not math.isfinite(eps):
        return None
    return float(eps)


def _resolve_eps_annual(annual: list, as_of: date, out: MultipleInputs) -> float | None:
    """EPS năm mới nhất published_at<=as_of và eps ≠ 0."""
    a_cands: list[tuple[date, str, float]] = []
    for p in annual:
        if not isinstance(p, dict):
            continue
        pub = _parse_date(p.get("published_at"))
        if pub is None:
            continue
        if pub > as_of:
            out.lookahead_excluded += 1
            continue
        items = p.get("items") if isinstance(p.get("items"), dict) else {}
        eps = _finite_num(items.get("eps"))
        if eps is None or eps == 0:
            continue
        a_cands.append((pub, str(p.get("period") or ""), eps))
    if not a_cands:
        return None
    a_cands.sort(key=lambda t: (t[0], t[1]))
    return a_cands[-1][2]


def _check_minority_flag(quarterly: list, annual: list, as_of: date, out: MultipleInputs) -> None:
    """Gắn m4_pb_uses_total_equity khi |NI_parent - NI|/|NI| > 5% trên kỳ mới nhất ≤ as_of."""
    best: tuple[date, float, float] | None = None  # pub, ni_p, ni
    for block in (quarterly, annual):
        for p in block:
            if not isinstance(p, dict):
                continue
            pub = _parse_date(p.get("published_at"))
            if pub is None or pub > as_of:
                continue
            items = p.get("items") if isinstance(p.get("items"), dict) else {}
            ni_p = _finite_num(items.get("net_income_parent"))
            ni = _finite_num(items.get("net_income"))
            if ni_p is None or ni is None:
                continue
            if abs(ni) <= 0:
                continue
            if best is None or pub > best[0]:
                best = (pub, ni_p, ni)
    if best is None:
        return
    _, ni_p, ni = best
    if abs(ni_p - ni) / abs(ni) > 0.05:
        out.flags.append("m4_pb_uses_total_equity")


def derive_multiples(
    snapshot: dict,
    *,
    stale_calendar_days: int = 7,
    stale_financials_days: int = 200,
) -> MultipleInputs:
    """Suy PE/PB và metadata từ snapshot; gắn flags thiếu dữ liệu / stale / lookahead."""
    out = MultipleInputs()
    if not isinstance(snapshot, dict):
        out.flags.append("m4_invalid_snapshot")
        return out

    meta = snapshot.get("meta") if isinstance(snapshot.get("meta"), dict) else {}
    company = snapshot.get("company") if isinstance(snapshot.get("company"), dict) else {}
    out.ticker = meta.get("ticker") if isinstance(meta.get("ticker"), str) else None
    out.synthetic = bool(meta.get("synthetic") is True)
    if out.synthetic:
        out.flags.append("m4_synthetic_data")

    as_of = _parse_date(meta.get("as_of"))
    out.as_of = as_of
    if as_of is None:
        out.flags.append("m4_missing_as_of")
        return out

    out.sector = company.get("sector") if isinstance(company.get("sector"), str) else None
    if not out.sector:
        out.flags.append("m4_missing_sector")
    out.is_bank = company.get("is_bank") is True

    shares = _finite_pos(company.get("shares_outstanding"))
    out.shares = shares
    if shares is None:
        out.flags.append("m4_missing_shares")

    # --- giá ---
    prices = snapshot.get("prices") if isinstance(snapshot.get("prices"), dict) else {}
    rows = prices.get("rows") if isinstance(prices.get("rows"), list) else []
    out.price_source_id = prices.get("source_id") if isinstance(prices.get("source_id"), str) else None
    best_row: dict | None = None
    best_d: date | None = None
    for r in rows:
        if not isinstance(r, dict):
            continue
        d = _parse_date(r.get("date"))
        if d is None:
            continue
        if d > as_of:
            out.lookahead_excluded += 1
            continue
        close = _finite_pos(r.get("close"))
        if close is None:
            continue
        if best_d is None or d > best_d:
            best_d = d
            best_row = r
    if best_row is None or best_d is None:
        out.flags.append("m4_no_valid_price")
    else:
        out.price_close = float(best_row["close"])
        out.price_date = best_d
        stale_days = (as_of - best_d).days
        if stale_days > int(stale_calendar_days):
            out.flags.append("m4_stale_price_data")

    # --- EPS (NI-based TTM) ---
    fins = snapshot.get("financials") if isinstance(snapshot.get("financials"), dict) else {}
    quarterly = fins.get("quarterly") if isinstance(fins.get("quarterly"), list) else []
    annual = fins.get("annual") if isinstance(fins.get("annual"), list) else []

    eps_ttm = _resolve_eps_ttm_ni(quarterly, as_of, shares, out)
    eps_annual = _resolve_eps_annual(annual, as_of, out)

    if eps_ttm is not None and eps_ttm > 0:
        out.eps_used = eps_ttm
        out.eps_source = "ttm_ni"
    elif eps_annual is not None and eps_annual > 0:
        out.eps_used = eps_annual
        out.eps_source = "annual"
        out.flags.append("m4_eps_ttm_fallback_annual")
    else:
        if eps_ttm is not None and eps_ttm < 0:
            out.flags.append("m4_pe_not_meaningful")
        out.flags.append("m4_pe_unavailable")

    # --- equity (total_equity gồm minority) ---
    eq_q: list[tuple[date, str, float]] = []
    for p in quarterly:
        if not isinstance(p, dict):
            continue
        pub = _parse_date(p.get("published_at"))
        if pub is None or pub > as_of:
            continue
        items = p.get("items") if isinstance(p.get("items"), dict) else {}
        eq = _finite_num(items.get("total_equity"))
        if eq is None or eq <= 0:
            continue
        eq_q.append((pub, str(p.get("period") or ""), eq))
    eq_a: list[tuple[date, str, float]] = []
    for p in annual:
        if not isinstance(p, dict):
            continue
        pub = _parse_date(p.get("published_at"))
        if pub is None or pub > as_of:
            continue
        items = p.get("items") if isinstance(p.get("items"), dict) else {}
        eq = _finite_num(items.get("total_equity"))
        if eq is None or eq <= 0:
            continue
        eq_a.append((pub, str(p.get("period") or ""), eq))

    chosen_eq: tuple[date, str, float] | None = None
    if eq_q:
        eq_q.sort(key=lambda t: (t[0], t[1]))
        chosen_eq = eq_q[-1]
    elif eq_a:
        eq_a.sort(key=lambda t: (t[0], t[1]))
        chosen_eq = eq_a[-1]

    if chosen_eq is None:
        out.flags.append("m4_missing_equity")
        out.flags.append("m4_pb_unavailable")
    else:
        out.equity_published, out.equity_period, out.total_equity = chosen_eq
        fin_age = (as_of - out.equity_published).days
        if fin_age > int(stale_financials_days):
            out.flags.append("m4_stale_financials")
        if shares is not None and out.total_equity is not None and shares > 0:
            out.book_ps = out.total_equity / shares
            if out.book_ps <= 0:
                out.flags.append("m4_pb_not_meaningful")
                out.flags.append("m4_pb_unavailable")
                out.book_ps = None

    _check_minority_flag(quarterly, annual, as_of, out)

    if out.lookahead_excluded > 0:
        out.flags.append("m4_lookahead_rows_excluded")

    # --- PE / PB ---
    if out.price_close is not None and out.eps_used is not None and out.eps_used > 0:
        out.pe = out.price_close / out.eps_used
    elif "m4_pe_unavailable" not in out.flags:
        out.flags.append("m4_pe_unavailable")

    if out.price_close is not None and out.book_ps is not None and out.book_ps > 0:
        out.pb = out.price_close / out.book_ps
    elif "m4_pb_unavailable" not in out.flags and (
        out.book_ps is None or out.price_close is None
    ):
        if "m4_pb_unavailable" not in out.flags:
            out.flags.append("m4_pb_unavailable")

    return out
