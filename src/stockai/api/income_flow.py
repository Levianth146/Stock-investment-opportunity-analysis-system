"""Luồng P&L dạng Sankey (feature 017c).

Chỉ dùng số có trong items (đã quy về tỷ VND ở lớp financials).
Không bịa số; thiếu thì bỏ nút + ghi note. Phần dư gắn nhãn «Khác (cân đối)» (phái sinh).
"""
from __future__ import annotations

from typing import Any

from stockai.api.financials import build_financials_payload
from stockai.api.waterfall import sum_items

# Sai số bảo toàn tại mỗi nút: 0,5% giá trị nút (hoặc 1e-6 nếu gần 0)
_TOL_PCT = 0.005
_FLOW_KEYS = (
    "revenue",
    "gross_profit",
    "selling_expense",
    "admin_expense",
    "interest_expense",
    "pretax_profit",
    "net_income",
    "net_income_parent",
)


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


def _tol(magnitude: float) -> float:
    return max(abs(magnitude) * _TOL_PCT, 1e-6)


def _pct(value: float, revenue: float) -> float | None:
    if abs(revenue) < 1e-12:
        return None
    return value / revenue


def _expense_ratio(items: dict[str, Any]) -> float | None:
    """(BH + QL + lãi vay) / doanh thu — chỉ cộng chỉ tiêu có mặt; thiếu cả ba → null."""
    rev = _num(items.get("revenue"))
    if rev is None or abs(rev) < 1e-12:
        return None
    parts: list[float] = []
    for k in ("selling_expense", "admin_expense", "interest_expense"):
        v = _num(items.get(k))
        if v is not None:
            parts.append(abs(v))
    if not parts:
        return None
    return sum(parts) / abs(rev)


def _margins(items: dict[str, Any]) -> tuple[float | None, float | None]:
    rev = _num(items.get("revenue"))
    gp = _num(items.get("gross_profit"))
    nip = _num(items.get("net_income_parent"))
    if nip is None:
        nip = _num(items.get("net_income"))
    gm = (gp / rev) if rev is not None and abs(rev) >= 1e-12 and gp is not None else None
    nm = (nip / rev) if rev is not None and abs(rev) >= 1e-12 and nip is not None else None
    return gm, nm


def build_income_flow(items: dict[str, Any] | None) -> dict[str, Any] | None:
    """Xây nodes/links Sankey từ một kỳ items (tỷ VND).

    Trả ``None`` nếu thiếu doanh thu hoặc LNST (mẹ / tổng).
    Mọi link ``value`` ≥ 0. Bảo toàn tại mỗi nút trong sai số 0,5%.
    """
    if not isinstance(items, dict):
        return None
    rev = _num(items.get("revenue"))
    nip = _num(items.get("net_income_parent"))
    if nip is None:
        nip = _num(items.get("net_income"))
    if rev is None or nip is None:
        return None

    notes: list[str] = []
    gp = _num(items.get("gross_profit"))
    selling = _num(items.get("selling_expense"))
    admin = _num(items.get("admin_expense"))
    interest = _num(items.get("interest_expense"))
    pretax = _num(items.get("pretax_profit"))
    ni = _num(items.get("net_income"))
    if ni is None and _num(items.get("net_income_parent")) is not None:
        # Có LNST mẹ nhưng không có LNST hợp nhất → không suy CIT/CĐTS từ NI
        ni = None

    if selling is None:
        notes.append("Thiếu chi phí bán hàng — đã bỏ nút.")
    if admin is None:
        notes.append("Thiếu chi phí quản lý — đã bỏ nút.")
    if interest is None:
        notes.append("Thiếu chi phí lãi vay — đã bỏ nút.")

    # CIT phái sinh từ LNTT − LNST (khi đủ cả hai)
    cit: float | None = None
    if pretax is not None and ni is not None:
        cit = pretax - ni
        if cit < 0:
            # Tín dụng thuế / hoàn thuế: không tạo nút âm; gộp vào cân đối
            notes.append("Thuế TNDN âm (hoàn/tín dụng) — gộp vào cân đối, không tách nút.")
            cit = None
        elif abs(cit) < 1e-12:
            cit = None
    else:
        notes.append("Thiếu LNTT hoặc LNST — đã bỏ nút thuế TNDN.")

    # Lợi ích CĐTS = LNST − LNST mẹ (khi đủ cả hai và khác nhau)
    minority: float | None = None
    ni_for_mi = ni if ni is not None else _num(items.get("net_income"))
    nip_raw = _num(items.get("net_income_parent"))
    if ni_for_mi is not None and nip_raw is not None:
        minority = ni_for_mi - nip_raw
        if minority < 0:
            notes.append("Cổ đông thiểu số âm — gộp vào cân đối, không tách nút.")
            minority = None
        elif abs(minority) < 1e-12:
            minority = None
    elif nip_raw is None and ni_for_mi is not None:
        notes.append("Thiếu LNST cổ đông mẹ — dùng LNST tổng làm LNST mẹ.")
    else:
        notes.append("Thiếu LNST hoặc LNST mẹ — đã bỏ nút cổ đông thiểu số.")

    nodes: dict[str, dict[str, Any]] = {}
    links: list[dict[str, Any]] = []

    def add_node(
        nid: str,
        label: str,
        *,
        kind: str,
        derived: bool = False,
    ) -> None:
        if nid not in nodes:
            nodes[nid] = {
                "id": nid,
                "label": label,
                "kind": kind,
                "derived": derived,
                "value": 0.0,
            }

    def add_link(source: str, target: str, value: float) -> None:
        if value <= 1e-12:
            return
        links.append({"source": source, "target": target, "value": float(value)})

    add_node("revenue", "Doanh thu", kind="source")
    nodes["revenue"]["value"] = float(rev)

    # --- Tầng doanh thu → giá vốn | LN gộp ---
    pool_id = "revenue"
    if gp is None:
        notes.append("Thiếu lợi nhuận gộp — phân bổ chi phí từ doanh thu.")
        pool_id = "revenue"
    elif gp <= 0:
        notes.append("Lợi nhuận gộp ≤ 0 — không tách giá vốn/LN gộp; phân bổ từ doanh thu.")
        pool_id = "revenue"
    else:
        cogs = rev - gp
        add_node("gross_profit", "LN gộp", kind="intermediate")
        nodes["gross_profit"]["value"] = float(gp)
        if cogs > _tol(rev):
            add_node("cogs", "Giá vốn", kind="sink", derived=True)
            nodes["cogs"]["value"] = float(cogs)
            add_link("revenue", "cogs", cogs)
            add_link("revenue", "gross_profit", gp)
        elif cogs < -_tol(rev):
            # LN gộp > doanh thu: cần nguồn bổ sung vào LN gộp
            add_link("revenue", "gross_profit", rev)
            extra = gp - rev
            add_node("other_income", "Thu nhập khác (ròng)", kind="other_income", derived=True)
            nodes["other_income"]["value"] = float(
                nodes["other_income"]["value"] + extra
            )
            add_link("other_income", "gross_profit", extra)
            notes.append("LN gộp lớn hơn doanh thu — bổ sung «Thu nhập khác (ròng)» (phái sinh).")
        else:
            add_link("revenue", "gross_profit", gp)
        pool_id = "gross_profit"

    # --- Chi phí / thuế / CĐTS / LNST từ pool ---
    outflows: list[tuple[str, str, float, str, bool]] = []
    # id, label, value, kind, derived

    if selling is not None and abs(selling) > 1e-12:
        outflows.append(("selling", "Chi phí bán hàng", abs(selling), "sink", False))
    if admin is not None and abs(admin) > 1e-12:
        outflows.append(("admin", "Chi phí quản lý", abs(admin), "sink", False))
    if interest is not None and abs(interest) > 1e-12:
        outflows.append(("interest", "Chi phí lãi vay", abs(interest), "sink", False))
    if cit is not None and cit > 1e-12:
        outflows.append(("cit", "Thuế TNDN", float(cit), "sink", True))
    if minority is not None and minority > 1e-12:
        outflows.append(("minority", "Cổ đông thiểu số", float(minority), "sink", True))

    loss_case = nip < 0
    if nip > 1e-12:
        outflows.append(("npat", "LNST cổ đông mẹ", float(nip), "sink", False))
    elif loss_case:
        outflows.append(("loss", "Lỗ", abs(nip), "loss", False))
        notes.append(
            "LNST < 0: nút «Lỗ» (màu rủi ro); nếu chi phí vượt nguồn thì thêm "
            "«Thu nhập khác (ròng)» để mọi liên kết ≥ 0."
        )
    else:
        # nip ≈ 0
        notes.append("LNST cổ đông mẹ ≈ 0 — không vẽ nút LNST.")

    accounted = sum(o[2] for o in outflows)
    pool_val = float(nodes[pool_id]["value"])
    residual = pool_val - accounted

    if residual > _tol(pool_val):
        outflows.append(
            ("other_balance", "Khác (cân đối)", float(residual), "derived", True)
        )
        notes.append(
            "«Khác (cân đối)» là phần dư để bảo toàn luồng (phái sinh), không phải chỉ tiêu BCTC."
        )
    elif residual < -_tol(pool_val):
        need = -residual
        add_node("other_income", "Thu nhập khác (ròng)", kind="other_income", derived=True)
        nodes["other_income"]["value"] = float(nodes["other_income"]["value"] + need)
        add_link("other_income", pool_id, need)
        nodes[pool_id]["value"] = float(nodes[pool_id]["value"] + need)
        notes.append(
            "Chi phí/LN vượt nguồn có sẵn — thêm «Thu nhập khác (ròng)» (phái sinh) để mọi liên kết ≥ 0."
        )

    for oid, label, val, kind, derived in outflows:
        add_node(oid, label, kind=kind, derived=derived)
        nodes[oid]["value"] = float(val)
        add_link(pool_id, oid, val)

    # --- Gắn % doanh thu + kiểm bảo toàn ---
    node_list: list[dict[str, Any]] = []
    for n in nodes.values():
        n["pct_revenue"] = _pct(float(n["value"]), rev)
        node_list.append(n)

    link_list: list[dict[str, Any]] = []
    for lk in links:
        lk["pct_revenue"] = _pct(float(lk["value"]), rev)
        link_list.append(lk)

    # Bảo toàn: tại mỗi nút (trừ nguồn thuần / sink thuần) sum(in) ≈ sum(out)
    in_sum: dict[str, float] = {n["id"]: 0.0 for n in node_list}
    out_sum: dict[str, float] = {n["id"]: 0.0 for n in node_list}
    for lk in link_list:
        out_sum[lk["source"]] = out_sum.get(lk["source"], 0.0) + float(lk["value"])
        in_sum[lk["target"]] = in_sum.get(lk["target"], 0.0) + float(lk["value"])

    conservation_ok = True
    for n in node_list:
        nid = n["id"]
        kind = n["kind"]
        incoming = in_sum.get(nid, 0.0)
        outgoing = out_sum.get(nid, 0.0)
        val = float(n["value"])
        if kind in ("source", "other_income"):
            # Nguồn: tổng ra ≈ giá trị nút
            if abs(outgoing - val) > _tol(val):
                conservation_ok = False
        elif kind in ("sink", "loss", "derived"):
            if abs(incoming - val) > _tol(val):
                conservation_ok = False
            if outgoing > _tol(val):
                conservation_ok = False
        else:
            # Trung gian: tổng vào ≈ tổng ra
            if abs(incoming - outgoing) > _tol(max(incoming, outgoing, val)):
                conservation_ok = False

    gm, nm = _margins(items)
    return {
        "revenue": float(rev),
        "npat": float(nip),
        "loss": loss_case,
        "nodes": node_list,
        "links": link_list,
        "notes": notes,
        "conservation_ok": conservation_ok,
        "gross_margin": gm,
        "net_margin": nm,
        "expense_to_revenue": _expense_ratio(items),
    }


def _period_items_from_financials(
    fin: dict[str, Any], period: str
) -> tuple[dict[str, float | None] | None, list[str]]:
    """Lấy items một kỳ; period='TTM' cộng 4 quý gần nhất."""
    notes: list[str] = []
    annual = [p for p in (fin.get("annual") or []) if isinstance(p, dict)]
    quarterly = [p for p in (fin.get("quarterly") or []) if isinstance(p, dict)]

    if period.upper() == "TTM":
        last4 = quarterly[-4:]
        if len(last4) < 4:
            notes.append("Chưa đủ 4 quý để tính TTM.")
            return None, notes
        items = sum_items(last4, _FLOW_KEYS)
        return items, notes

    hit = next((p for p in annual if str(p.get("period")) == str(period)), None)
    if hit is None:
        notes.append(f"Không có kỳ {period}.")
        return None, notes
    raw = hit.get("items") if isinstance(hit.get("items"), dict) else {}
    return {k: _num(raw.get(k)) for k in _FLOW_KEYS}, notes


def _prior_items(fin: dict[str, Any], period: str) -> dict[str, float | None] | None:
    annual = [p for p in (fin.get("annual") or []) if isinstance(p, dict)]
    quarterly = [p for p in (fin.get("quarterly") or []) if isinstance(p, dict)]
    if period.upper() == "TTM":
        prev4 = quarterly[-8:-4]
        if len(prev4) < 4:
            # Fallback: năm gần nhất trước
            if len(annual) >= 2:
                raw = annual[-2].get("items") if isinstance(annual[-2].get("items"), dict) else {}
                return {k: _num(raw.get(k)) for k in _FLOW_KEYS}
            return None
        return sum_items(prev4, _FLOW_KEYS)
    idxs = [i for i, p in enumerate(annual) if str(p.get("period")) == str(period)]
    if not idxs or idxs[0] == 0:
        return None
    prev = annual[idxs[0] - 1]
    raw = prev.get("items") if isinstance(prev.get("items"), dict) else {}
    return {k: _num(raw.get(k)) for k in _FLOW_KEYS}


def available_periods(fin: dict[str, Any]) -> list[str]:
    annual = [p for p in (fin.get("annual") or []) if isinstance(p, dict)]
    quarterly = [p for p in (fin.get("quarterly") or []) if isinstance(p, dict)]
    years = [str(p.get("period")) for p in annual if p.get("period") is not None]
    out = list(years)
    if len(quarterly) >= 4:
        out.append("TTM")
    return out


def build_income_flow_payload(
    snapshot: dict[str, Any],
    *,
    period: str,
    asof: str,
    disclaimer: str,
) -> dict[str, Any]:
    """Payload GET /api/tickers/{symbol}/income-flow."""
    company = snapshot.get("company") if isinstance(snapshot.get("company"), dict) else {}
    meta = snapshot.get("meta") if isinstance(snapshot.get("meta"), dict) else {}
    symbol = str(meta.get("ticker") or "").upper()
    is_bank = company.get("is_bank") is True

    base = {
        "asof": asof,
        "disclaimer": disclaimer,
        "symbol": symbol,
        "period": period,
        "unit": "billion_vnd",
        "supported": not is_bank,
    }
    if is_bank:
        return {
            **base,
            "supported": False,
            "message": "Chưa hỗ trợ ngân hàng",
            "nodes": [],
            "links": [],
            "notes": [],
            "available_periods": [],
        }

    fin = build_financials_payload(snapshot, asof=asof, disclaimer=disclaimer)
    periods = available_periods(fin)
    if not period:
        period = periods[-2] if len(periods) >= 2 and periods[-1] == "TTM" else (
            periods[-1] if periods else ""
        )
        base["period"] = period

    items, fetch_notes = _period_items_from_financials(fin, period)
    if items is None:
        return {
            **base,
            "supported": True,
            "nodes": [],
            "links": [],
            "notes": fetch_notes,
            "available_periods": periods,
            "conservation_ok": False,
            "summary": None,
        }

    flow = build_income_flow(items)
    if flow is None:
        return {
            **base,
            "supported": True,
            "nodes": [],
            "links": [],
            "notes": fetch_notes + ["Thiếu doanh thu hoặc LNST — không dựng được luồng."],
            "available_periods": periods,
            "conservation_ok": False,
            "summary": None,
        }

    prior = _prior_items(fin, period)
    gm_p = nm_p = exp_p = None
    if prior is not None:
        gm_p, nm_p = _margins(prior)
        exp_p = _expense_ratio(prior)

    notes = list(fetch_notes) + list(flow.get("notes") or [])
    return {
        **base,
        "supported": True,
        "revenue": flow["revenue"],
        "npat": flow["npat"],
        "loss": flow["loss"],
        "nodes": flow["nodes"],
        "links": flow["links"],
        "notes": notes,
        "conservation_ok": flow["conservation_ok"],
        "available_periods": periods,
        "summary": {
            "gross_margin": flow["gross_margin"],
            "net_margin": flow["net_margin"],
            "expense_to_revenue": flow["expense_to_revenue"],
            "gross_margin_prior": gm_p,
            "net_margin_prior": nm_p,
            "expense_to_revenue_prior": exp_p,
            "prior_label": "kỳ trước",
        },
    }


__all__ = [
    "build_income_flow",
    "build_income_flow_payload",
    "available_periods",
]
