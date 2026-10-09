"""M2 - điểm F (cơ bản), thang 0-100. Chỉ N3 sửa trong thư mục này.

Đọc đúng schema snapshot (docs/CONTRACTS.md): snapshot["financials"]["annual"|"quarterly"][i]["items"], company.is_bank.
Kỳ trong danh sách xếp mới nhất trước. Mọi số tính bằng code; thiếu chỉ tiêu -> bỏ qua tiêu chí đó, gắn cờ, điểm tính trên các tiêu chí còn lại.
Doanh nghiệp thường và ngân hàng dùng bộ tiêu chí khác nhau (ngân hàng không có gross_profit, nợ vay, current ratio...).
"""
from __future__ import annotations

import math


def _g(items: dict, k: str):
    v = items.get(k)
    return v if isinstance(v, (int, float)) and math.isfinite(v) else None


def _div(a, b):
    return a / b if a is not None and b not in (None, 0) else None


def _growth(cur, prev):
    return (cur - prev) / abs(prev) if cur is not None and prev not in (None, 0) else None


def _band(x, bands, higher_better=True):
    """bands = [(ngưỡng, điểm), ...] theo thứ tự ưu tiên; trả điểm của ngưỡng đầu tiên thỏa; cuối cùng là điểm mặc định."""
    if x is None:
        return None
    for thr, pts in bands[:-1]:
        if (x >= thr) if higher_better else (x <= thr):
            return pts
    return bands[-1][1]


def _metrics_and_scores(cur: dict, prev: dict | None, is_bank: bool) -> tuple[dict, dict]:
    ni = _g(cur, "net_income_parent") if _g(cur, "net_income_parent") is not None else _g(cur, "net_income")
    ni_prev = None
    if prev:
        ni_prev = _g(prev, "net_income_parent") if _g(prev, "net_income_parent") is not None else _g(prev, "net_income")
    eq, ta, rev = _g(cur, "total_equity"), _g(cur, "total_assets"), _g(cur, "revenue")
    m: dict[str, tuple[float | None, str]] = {
        "roe": (_div(ni, eq), "ratio"),
        "roa": (_div(ni, ta), "ratio"),
        "net_income_growth": (_growth(ni, ni_prev), "ratio"),
        "revenue_growth": (_growth(rev, _g(prev, "revenue") if prev else None), "ratio"),
        "equity_to_assets": (_div(eq, ta), "ratio"),
        "cfo_to_net_income": (_div(_g(cur, "cfo"), ni), "ratio"),
    }
    if is_bank:
        m.update({
            "cir": (_g(cur, "cir"), "ratio"), "nim": (_g(cur, "nim"), "ratio"),
            "npl_ratio": (_g(cur, "npl_ratio"), "ratio"), "car": (_g(cur, "car"), "ratio"),
            "loan_to_deposit": (_div(_g(cur, "customer_loans"), _g(cur, "customer_deposits")), "ratio"),
            "provision_to_toi": (_div(abs(_g(cur, "provision_expense")) if _g(cur, "provision_expense") is not None else None,
                                      _g(cur, "total_operating_income")), "ratio"),
        })
        s = {
            "profitability": _band(m["roe"][0], [(0.18, 100), (0.14, 80), (0.10, 60), (0.05, 35), (0, 15)]),
            "growth": _band(m["net_income_growth"][0], [(0.25, 100), (0.15, 80), (0.05, 60), (0.0, 40), (0, 15)]),
            "efficiency": _band(m["cir"][0], [(0.35, 100), (0.40, 85), (0.45, 70), (0.55, 45), (0, 20)], higher_better=False),
            "margin": _band(m["nim"][0], [(0.035, 100), (0.030, 80), (0.025, 60), (0.020, 40), (0, 20)]),
            "asset_quality": _band(m["npl_ratio"][0], [(0.012, 100), (0.02, 80), (0.03, 55), (0.05, 30), (0, 10)], higher_better=False),
            "capital": _band(m["car"][0], [(0.14, 100), (0.12, 75), (0.10, 50), (0, 20)]),
        }
        return m, s
    ebit, intr = _g(cur, "ebit"), _g(cur, "interest_expense")
    debt = None
    if _g(cur, "short_term_debt") is not None or _g(cur, "long_term_debt") is not None:
        debt = (_g(cur, "short_term_debt") or 0) + (_g(cur, "long_term_debt") or 0)
    m.update({
        "gross_margin": (_div(_g(cur, "gross_profit"), rev), "ratio"),
        "net_margin": (_div(ni, rev), "ratio"),
        "debt_to_equity": (_div(debt, eq), "ratio"),
        "current_ratio": (_div(_g(cur, "current_assets"), _g(cur, "current_liabilities")), "ratio"),
        "interest_coverage": (_div(ebit, abs(intr) if intr is not None else None), "x"),
    })
    s = {
        "profitability": _band(m["roe"][0], [(0.20, 100), (0.15, 80), (0.10, 60), (0.05, 35), (0, 15)]),
        "growth": _band(m["net_income_growth"][0], [(0.25, 100), (0.15, 80), (0.05, 60), (0.0, 40), (0, 15)]),
        "leverage": _band(m["debt_to_equity"][0], [(0.3, 100), (0.6, 80), (1.0, 60), (1.5, 35), (0, 15)], higher_better=False),
        "liquidity": _band(m["current_ratio"][0], [(1.5, 100), (1.2, 80), (1.0, 60), (0.8, 35), (0, 15)]),
        "coverage": _band(m["interest_coverage"][0], [(8, 100), (4, 80), (2, 55), (1, 30), (0, 10)]),
        "cash_quality": _band(m["cfo_to_net_income"][0], [(1.0, 100), (0.7, 75), (0.3, 50), (0, 30), (0, 10)]),
    }
    return m, s


def run(snapshot: dict, upstream: dict, cfg: dict) -> dict:
    out = {"module": "m2", "status": "error", "score": None, "metrics": {}, "evidence": [], "flags": []}
    fin = snapshot.get("financials") or {}
    annual = fin.get("annual") or []
    if not annual:
        out["flags"].append("m2_no_annual_financials")
        return out
    is_bank = bool((snapshot.get("company") or {}).get("is_bank"))
    cur, prev = annual[0], (annual[1] if len(annual) > 1 else None)
    m, s = _metrics_and_scores(cur["items"], prev["items"] if prev else None, is_bank)

    out["metrics"] = {k: {"value": v, "unit": u} for k, (v, u) in m.items() if v is not None}
    for k, v in m.items():
        if v[0] is None:
            out["flags"].append(f"m2_missing_{k}")
    valid = {k: v for k, v in s.items() if v is not None}
    for k, v in s.items():
        if v is None:
            out["flags"].append(f"m2_criterion_skipped_{k}")
    if not valid:
        out["flags"].append("m2_no_usable_criteria")
        return out
    out["score"] = round(sum(valid.values()) / len(valid), 1)
    out["status"] = "ok" if len(valid) == len(s) else "partial"
    if prev is None:
        out["flags"].append("m2_single_year_no_growth")

    # xu hướng 4 năm gần nhất (chỉ để báo cáo, không vào điểm)
    ni_series = [(a["period"], a["items"].get("net_income_parent") if a["items"].get("net_income_parent") is not None else a["items"].get("net_income"))
                 for a in annual[:4]]
    src = cur.get("source_id") or "src_fin"
    out["evidence"] = [
        {"text": f"Kỳ {cur['period']} ({'ngân hàng' if is_bank else 'phi ngân hàng'}): "
                 + ", ".join(f"{k}={v:.3f}" for k, (v, _) in m.items() if v is not None and k in ("roe", "net_income_growth", "debt_to_equity", "cir", "nim")),
         "source_id": src},
        {"text": "Điểm F = trung bình các tiêu chí: " + ", ".join(f"{k}={v}" for k, v in valid.items()), "source_id": src},
        {"text": "LNST (công ty mẹ) các năm: " + ", ".join(f"{p}: {v/1e9:,.0f} tỷ" for p, v in ni_series if v is not None), "source_id": src},
    ]
    if cur.get("published_at_estimated"):
        out["flags"].append("m2_publish_date_estimated")
    return out
