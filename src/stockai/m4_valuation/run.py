"""Relative valuation score (V) using reported earnings/equity and available peers."""
from __future__ import annotations

from statistics import median

def _valid_positive(values) -> list[float]:
    return [float(value) for value in values if isinstance(value, (int, float)) and value > 0]


def _clamp(value: float, low: float = 0, high: float = 100) -> float:
    return max(low, min(high, value))


def _standalone_score(multiple: float, bank: bool) -> float:
    if bank:
        anchors = ((0.5, 95), (1.0, 80), (1.5, 60), (2.5, 30), (4.0, 5))
    else:
        anchors = ((5, 95), (10, 80), (15, 60), (25, 30), (40, 5))
    if multiple <= anchors[0][0]:
        return anchors[0][1]
    for (left_x, left_y), (right_x, right_y) in zip(anchors, anchors[1:]):
        if multiple <= right_x:
            fraction = (multiple - left_x) / (right_x - left_x)
            return left_y + fraction * (right_y - left_y)
    return anchors[-1][1]


def run(snapshot: dict, upstream: dict, cfg: dict) -> dict:
    out = {"module": "m4", "status": "partial", "score": None, "metrics": {}, "evidence": [], "flags": [], "target": None}
    company = snapshot.get("company", {})
    prices = sorted(
        (
            row for row in snapshot.get("prices", {}).get("rows", [])
            if isinstance(row.get("close"), (int, float)) and row["close"] > 0
        ),
        key=lambda row: row.get("date", ""),
    )
    annual = [
        period for period in snapshot.get("financials", {}).get("annual", [])
        if period.get("published_at", "")[:10] <= snapshot.get("meta", {}).get("as_of", "")
        and isinstance(period.get("items"), dict)
    ]
    annual.sort(key=lambda period: period.get("period", ""))
    if not prices or not annual:
        out.update(status="partial", evidence=[], flags=["price_or_annual_financial_data_missing"])
        return out

    price = float(prices[-1]["close"])
    items = annual[-1]["items"]
    shares = company.get("shares_outstanding")
    earnings = items.get("net_income_parent") or items.get("net_income")
    eps = items.get("eps")
    if (not isinstance(eps, (int, float)) or eps <= 0) and isinstance(earnings, (int, float)) and isinstance(shares, (int, float)) and shares > 0:
        eps = earnings / shares
    equity = items.get("total_equity")
    book_value_per_share = equity / shares if isinstance(equity, (int, float)) and isinstance(shares, (int, float)) and shares > 0 else None
    bank = bool(company.get("is_bank"))
    multiple_name = "pb" if bank else "pe"
    current_basis = book_value_per_share if bank else eps
    current_multiple = price / current_basis if isinstance(price, (int, float)) and current_basis and current_basis > 0 else None
    peer_multiples = _valid_positive(peer.get(multiple_name) for peer in snapshot.get("peers", []))
    peer_multiple = median(peer_multiples) if peer_multiples else None

    if current_multiple is not None:
        if peer_multiple is not None:
            upside = ((current_basis * peer_multiple) / price - 1) * 100
            score = _clamp(50 + upside)
            target_base = current_basis * peer_multiple
            out["target"] = {
                "base": round(target_base, 2),
                "bull": round(target_base * 1.2, 2),
                "bear": round(target_base * 0.8, 2),
                "method": f"Định giá tương đối bằng {multiple_name.upper()} trung vị nhóm peers",
                "assumptions": [f"Dùng {len(peer_multiples)} peers có {multiple_name.upper()} dương", f"{annual[-1]['period']} là kỳ BCTC mới nhất đã công bố"],
            }
            out["status"] = "ok" if len(peer_multiples) >= 3 else "partial"
            if len(peer_multiples) < 3:
                out["flags"] = ["fewer_than_three_usable_peers"]
        else:
            score = _standalone_score(current_multiple, bank)
            out["status"] = "partial"
            out["flags"] = ["peer_multiples_unavailable_target_not_calculated"]
        out["score"] = round(score, 2)

    out["metrics"] = {
        "current_price": {"value": float(price), "unit": "VND"},
        "valuation_multiple": {"value": round(current_multiple, 2) if current_multiple is not None else None, "unit": multiple_name.upper()},
        "peer_median_multiple": {"value": round(peer_multiple, 2) if peer_multiple is not None else None, "unit": multiple_name.upper()},
        "peer_count": {"value": len(peer_multiples), "unit": "companies"},
    }
    if out["score"] is None:
        out["status"] = "partial"
        out["flags"].append("earnings_or_equity_per_share_unavailable")
    evidence_text = (
        f"{multiple_name.upper()} hiện tại {current_multiple:.2f}x"
        if current_multiple is not None
        else "Chưa đủ EPS/giá trị sổ sách trên mỗi cổ phiếu để tính hệ số định giá."
    )
    if peer_multiple is not None and out["target"] is not None:
        evidence_text += f"; trung vị peers {peer_multiple:.2f}x, giá mục tiêu cơ sở {out['target']['base']:,.0f} VNĐ."
    out["evidence"] = [{"text": evidence_text, "source_id": annual[-1].get("source_id", "")}]
    return out
