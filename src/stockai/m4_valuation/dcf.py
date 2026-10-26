"""M4 - DCF theo FCFF (hai giai đoạn) từ báo cáo tài chính trong snapshot M1.

Nguyên tắc:
- Chỉ dùng dữ liệu đã công bố đến ``as_of`` (không lookahead): ``published_at <= as_of``.
- Mọi giả định (lãi suất phi rủi ro, phần bù rủi ro, thuế, tăng trưởng dài hạn...) nằm trong
  ``config/valuation.yaml`` mục ``m4.dcf`` và được in lại trong ``assumptions``; không có số cứng ẩn.
- Tổ chức tài chính (ngân hàng, chứng khoán, bảo hiểm) không áp dụng: dòng tiền hoạt động của họ
  gắn với huy động/cho vay, FCFF không có ý nghĩa. Trả ``not_applicable`` kèm lý do.
- Không bịa số: thiếu dữ liệu, FCFF bình quân không dương, giá trị vốn âm → không có kết quả và nêu lý do.
- Kết quả lệch quá xa giá thị trường vẫn hiển thị nhưng ``usable_for_target=False`` (không đưa vào giá mục tiêu).

Đơn vị: VND thô, cổ phiếu thô (giống ``multiples.py``).
"""
from __future__ import annotations

import math
from copy import deepcopy
from typing import Any

from stockai.m4_valuation.multiples import MultipleInputs, _finite_num, _finite_pos, _parse_date

DEFAULT_DCF: dict[str, Any] = {
    "tax_rate": 0.20,
    "risk_free": 0.035,
    "equity_risk_premium": 0.085,
    "beta_default": 1.0,
    "beta_min": 0.5,
    "beta_max": 1.6,
    "cost_of_debt_default": 0.09,
    "cost_of_debt_min": 0.05,
    "cost_of_debt_max": 0.13,
    "terminal_growth": 0.03,
    "stage_years": 5,
    "growth_min": 0.0,
    "growth_max": 0.12,
    "wacc_min_spread": 0.03,
    "fcff_years": 3,
    "min_history_years": 4,
    "max_data_age_years": 2,
    "blend_weight": 0.3,
    "plausible_ratio_min": 0.25,
    "plausible_ratio_max": 4.0,
    "tv_heavy_share": 0.85,
    "scenario": {
        "wacc_shift": 0.01,
        "terminal_shift": 0.005,
        "growth_bear_mult": 0.5,
        "growth_bull_mult": 1.25,
    },
    "sensitivity": {
        "wacc_offsets": [-0.02, -0.01, 0.0, 0.01, 0.02],
        "terminal_offsets": [-0.01, -0.005, 0.0, 0.005, 0.01],
    },
    "excluded_sectors": ["Banks", "Financial Services", "Insurance"],
}


def merge_dcf_cfg(overlay: dict | None) -> dict[str, Any]:
    out = deepcopy(DEFAULT_DCF)
    for k, v in (overlay or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = {**out[k], **v}
        else:
            out[k] = v
    return out


def _f(cfg: dict, key: str) -> float:
    return float(cfg[key])


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def _year(period: Any) -> int | None:
    try:
        return int(str(period).strip()[:4])
    except (TypeError, ValueError):
        return None


def _annual_rows(snapshot: dict, as_of) -> list[dict]:
    """Báo cáo năm đã công bố đến as_of, tăng dần theo năm."""
    fin = snapshot.get("financials") if isinstance(snapshot.get("financials"), dict) else {}
    rows = []
    for r in fin.get("annual") or []:
        if not isinstance(r, dict) or not isinstance(r.get("items"), dict):
            continue
        y = _year(r.get("period"))
        if y is None:
            continue
        pub = _parse_date(r.get("published_at"))
        if as_of is not None:
            if pub is not None and pub > as_of:
                continue
            if pub is None and y >= as_of.year:  # chưa rõ ngày công bố: không dùng năm hiện tại
                continue
        rows.append({"year": y, "items": r["items"], "published": pub})
    rows.sort(key=lambda r: r["year"])
    return rows


def _latest_balance(snapshot: dict, annual: list[dict], as_of) -> tuple[float, float, str | None, list[str]]:
    """(nợ vay, tiền) lấy từ kỳ mới nhất đã công bố (quý hoặc năm)."""
    fin = snapshot.get("financials") if isinstance(snapshot.get("financials"), dict) else {}
    cands: list[tuple[Any, str, dict]] = []
    for r in fin.get("quarterly") or []:
        if isinstance(r, dict) and isinstance(r.get("items"), dict):
            pub = _parse_date(r.get("published_at"))
            if pub is not None and (as_of is None or pub <= as_of):
                cands.append((pub, str(r.get("period")), r["items"]))
    for r in annual:
        if r["published"] is not None:
            cands.append((r["published"], str(r["year"]), r["items"]))
    cands.sort(key=lambda c: c[0], reverse=True)
    flags: list[str] = []
    for _pub, period, it in cands:
        cash = _finite_num(it.get("cash"))
        if cash is None:
            continue
        total = _finite_num(it.get("total_debt"))
        st, lt = _finite_num(it.get("short_term_debt")), _finite_num(it.get("long_term_debt"))
        if total is None and st is None and lt is None:
            flags.append("m4_dcf_debt_missing")
            debt = 0.0
        else:
            debt = total if total is not None else (st or 0.0) + (lt or 0.0)
        return max(debt, 0.0), cash, period, flags
    return 0.0, 0.0, None, ["m4_dcf_balance_missing"]


def _project(base: float, g1: float, g_t: float, wacc: float, years: int) -> tuple[list[dict], float, float]:
    """Dự phóng FCFF với tăng trưởng giảm tuyến tính từ g1 về g_t; trả (bảng, PV các năm, PV giá trị cuối kỳ)."""
    rows: list[dict] = []
    fcff = base
    pv_sum = 0.0
    for t in range(1, years + 1):
        g = g1 + (g_t - g1) * ((t - 1) / (years - 1) if years > 1 else 1.0)
        fcff = fcff * (1.0 + g)
        pv = fcff / (1.0 + wacc) ** t
        pv_sum += pv
        rows.append({"year": t, "growth": g, "fcff": fcff, "pv": pv})
    tv = fcff * (1.0 + g_t) / (wacc - g_t)
    pv_tv = tv / (1.0 + wacc) ** years
    return rows, pv_sum, pv_tv


def _value_per_share(base: float, g1: float, g_t: float, wacc: float, years: int, debt: float,
                     cash: float, shares: float) -> float | None:
    if wacc <= g_t or shares <= 0:
        return None
    _rows, pv_sum, pv_tv = _project(base, g1, g_t, wacc, years)
    return (pv_sum + pv_tv - debt + cash) / shares


def _result(status: str, reason: str | None, flags: list[str], **extra: Any) -> dict[str, Any]:
    return {"status": status, "reason": reason, "usable_for_target": False, "flags": flags, **extra}


def compute_dcf(snapshot: dict, mi: MultipleInputs, cfg: dict | None, *, beta: float | None = None) -> dict[str, Any]:
    c = merge_dcf_cfg(cfg)
    flags: list[str] = []
    if mi.is_bank or (mi.sector in set(c["excluded_sectors"])):
        return _result("not_applicable",
                       "DCF theo dòng tiền doanh nghiệp không áp dụng cho ngân hàng, chứng khoán, bảo hiểm.",
                       ["m4_dcf_not_applicable_financial"])
    price, shares = mi.price_close, _finite_pos(mi.shares)
    if price is None or shares is None:
        return _result("insufficient", "Thiếu giá hoặc số cổ phiếu lưu hành.", ["m4_dcf_missing_price_or_shares"])

    tax = _f(c, "tax_rate")
    annual = _annual_rows(snapshot, mi.as_of)
    history: list[dict] = []
    for r in annual:
        it = r["items"]
        cfo, capex = _finite_num(it.get("cfo")), _finite_num(it.get("capex"))
        if cfo is None or capex is None:
            continue
        interest = abs(_finite_num(it.get("interest_expense")) or 0.0)
        history.append({"year": r["year"], "cfo": cfo, "capex": abs(capex), "interest": interest,
                        "fcff": cfo - abs(capex) + interest * (1.0 - tax),
                        "revenue": _finite_pos(it.get("revenue"))})
    if len(history) < int(c["min_history_years"]):
        return _result("insufficient",
                       f"Cần tối thiểu {int(c['min_history_years'])} năm báo cáo có dòng tiền kinh doanh và chi đầu tư.",
                       ["m4_dcf_short_history"],
                       history_years=len(history))

    if mi.as_of is not None and history[-1]["year"] < mi.as_of.year - int(c["max_data_age_years"]):
        return _result("insufficient",
                       f"Báo cáo năm mới nhất có dòng tiền là năm {history[-1]['year']}, quá cũ so với ngày dữ liệu.",
                       ["m4_dcf_stale_financials"], history_years=len(history))

    n_avg = max(1, int(c["fcff_years"]))
    recent = history[-n_avg:]
    base = sum(h["fcff"] for h in recent) / len(recent)
    proxy = False
    if base <= 0:
        # Chi đầu tư mở rộng lớn làm FCFF âm: dùng dòng tiền chủ sở hữu duy trì (CFO − khấu hao + lãi sau thuế)
        # và KHÔNG cho tăng trưởng giai đoạn 1 (đầu tư tăng trưởng đã bị bỏ qua), nên kết quả thận trọng.
        dep = [_finite_num(r["items"].get("depreciation")) for r in annual[-n_avg:]]
        if all(d is not None for d in dep) and len(dep) == len(recent):
            alt = sum(h["cfo"] - abs(d) + h["interest"] * (1.0 - tax) for h, d in zip(recent, dep)) / len(recent)
            if alt > 0:
                base, proxy = alt, True
                flags.append("m4_dcf_maintenance_capex_proxy")
    if base <= 0:
        return _result("insufficient",
                       f"FCFF bình quân {len(recent)} năm gần nhất không dương, không dự phóng được dòng tiền.",
                       ["m4_dcf_fcff_not_positive"],
                       fcff_base=base)

    # Tăng trưởng giai đoạn 1: CAGR doanh thu, chặn trong [growth_min, growth_max]
    revs = [(h["year"], h["revenue"]) for h in history if h["revenue"]]
    g_t = _f(c, "terminal_growth")
    if proxy:
        cagr, g1 = None, g_t
    elif len(revs) >= 2:
        window = revs[-6:]
        (y0, r0), (y1, r1) = window[0], window[-1]
        cagr = (r1 / r0) ** (1.0 / (y1 - y0)) - 1.0 if y1 > y0 else g_t
        g1 = _clamp(cagr, _f(c, "growth_min"), _f(c, "growth_max"))
    else:
        cagr, g1 = None, g_t
        flags.append("m4_dcf_growth_default")

    # Chi phí vốn
    beta_ok = beta is not None and math.isfinite(beta) and beta > 0
    if not beta_ok:
        flags.append("m4_dcf_beta_default")
    b = beta if beta_ok else _f(c, "beta_default")
    b = _clamp(b, _f(c, "beta_min"), _f(c, "beta_max"))
    ke = _f(c, "risk_free") + b * _f(c, "equity_risk_premium")
    debt, cash, bal_period, bflags = _latest_balance(snapshot, annual, mi.as_of)
    flags += [f for f in bflags if f not in flags]
    interest_last = history[-1]["interest"]
    kd = _f(c, "cost_of_debt_default")
    if debt > 0 and interest_last > 0:
        kd = _clamp(interest_last / debt, _f(c, "cost_of_debt_min"), _f(c, "cost_of_debt_max"))
    mcap = price * shares
    w_e = mcap / (mcap + debt)
    wacc = w_e * ke + (1.0 - w_e) * kd * (1.0 - tax)
    floor = g_t + _f(c, "wacc_min_spread")
    if wacc < floor:
        wacc = floor
        flags.append("m4_dcf_wacc_floored")

    years = max(2, int(c["stage_years"]))
    rows, pv_sum, pv_tv = _project(base, g1, g_t, wacc, years)
    ev = pv_sum + pv_tv
    equity = ev - debt + cash
    per_share = equity / shares
    tv_share = pv_tv / ev if ev > 0 else None
    out_common = {
        "unit": "VND",
        "fcff_base": base, "fcff_history": [{"year": h["year"], "fcff": h["fcff"]} for h in history[-6:]],
        "revenue_cagr": cagr, "stage_growth_start": g1, "terminal_growth": g_t, "stage_years": years,
        "beta": b, "cost_of_equity": ke, "cost_of_debt": kd, "equity_weight": w_e, "wacc": wacc,
        "debt": debt, "cash": cash, "net_debt": debt - cash, "balance_period": bal_period,
        "ev": ev, "equity_value": equity, "pv_stage1": pv_sum, "pv_terminal": pv_tv, "tv_share": tv_share,
        "price": price, "shares": shares,
        "projection": rows,
    }
    if per_share <= 0:
        return _result("not_meaningful", "Giá trị vốn chủ sở hữu theo DCF không dương (nợ vay vượt giá trị doanh nghiệp).",
                       flags + ["m4_dcf_negative_equity"], **out_common)
    if tv_share is not None and tv_share > _f(c, "tv_heavy_share"):
        flags.append("m4_dcf_tv_heavy")

    # Kịch bản và bảng nhạy cảm
    sc = c["scenario"]
    bear = _value_per_share(base, g1 * float(sc["growth_bear_mult"]), g_t - float(sc["terminal_shift"]),
                            wacc + float(sc["wacc_shift"]), years, debt, cash, shares)
    bull = _value_per_share(base, g1 * float(sc["growth_bull_mult"]), g_t + float(sc["terminal_shift"]),
                            wacc - float(sc["wacc_shift"]), years, debt, cash, shares)
    s_cfg = c["sensitivity"]
    w_offs = [float(x) for x in s_cfg["wacc_offsets"]]
    g_offs = [float(x) for x in s_cfg["terminal_offsets"]]
    grid = [[_value_per_share(base, g1, g_t + go, wacc + wo, years, debt, cash, shares) for go in g_offs] for wo in w_offs]
    sens = {
        "wacc": [wacc + wo for wo in w_offs], "terminal_growth": [g_t + go for go in g_offs],
        "per_share": [[None if v is None or v <= 0 else round(v, 0) for v in row] for row in grid],
    }

    ratio = per_share / price
    usable = _f(c, "plausible_ratio_min") <= ratio <= _f(c, "plausible_ratio_max")
    if not usable:
        flags.append("m4_dcf_implausible")
    reason = None if usable else (
        f"Kết quả DCF bằng {ratio:.2f} lần giá thị trường, ngoài ngưỡng hợp lý "
        f"[{_f(c, 'plausible_ratio_min')}, {_f(c, 'plausible_ratio_max')}]; không đưa vào giá mục tiêu.")
    assumptions = [
        (f"Dòng tiền gốc = CFO − khấu hao + lãi vay sau thuế (thay cho chi đầu tư vì FCFF âm), không tăng trưởng giai đoạn 1; bình quân {len(recent)} năm ({recent[0]['year']}–{recent[-1]['year']})."
         if proxy else
         f"FCFF = CFO − chi đầu tư + lãi vay sau thuế, bình quân {len(recent)} năm gần nhất ({recent[0]['year']}–{recent[-1]['year']})."),
        f"Tăng trưởng {years} năm: bắt đầu {g1:.1%} (CAGR doanh thu"
        + (f" {cagr:.1%}" if cagr is not None else " không đủ dữ liệu")
        + f", chặn [{_f(c, 'growth_min'):.0%}, {_f(c, 'growth_max'):.0%}]), giảm tuyến tính về {g_t:.1%}.",
        f"Chi phí vốn chủ = {_f(c, 'risk_free'):.1%} + beta {b:.2f} × {_f(c, 'equity_risk_premium'):.1%} = {ke:.1%}.",
        f"Chi phí nợ {kd:.1%}, thuế {tax:.0%}; tỷ trọng vốn chủ theo vốn hóa {w_e:.0%}; WACC {wacc:.1%}.",
        f"Giá trị vốn chủ = EV − nợ vay {debt:,.0f} + tiền {cash:,.0f} (kỳ {bal_period}).".replace(",", "."),
        "Các giả định là tham số minh họa trong config/valuation.yaml, chưa hiệu chỉnh bằng dữ liệu thị trường Việt Nam.",
    ]
    return {
        "status": "ok", "reason": reason, "usable_for_target": usable, "flags": flags, **out_common,
        "per_share": per_share, "bear": bear, "bull": bull, "upside_pct": (per_share / price - 1.0) * 100.0,
        "sensitivity": sens, "assumptions": assumptions,
    }
