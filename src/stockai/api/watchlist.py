"""Tóm tắt danh sách theo dõi — tối đa 50 mã, không cost basis."""
from __future__ import annotations

from typing import Any

from stockai.api.insession import _live_valuation
from stockai.api.realtime import RealtimeHub
from stockai.api.ref_price import evaluate_ref_gap


def build_watchlist_summary(
    hub: RealtimeHub,
    store: Any,
    symbols: list[str],
    *,
    profile: str = "long_term",
) -> dict[str, Any]:
    """Ghép giá live + điểm M7 EOD + cổ tức + khoảng cách giá tham chiếu ngành."""
    sess = hub.session_now()
    as_of_ts = sess.as_of_ts
    status = hub.status()
    mode = status.get("mode") or "no_realtime"

    # Hạng EOD: duyệt rankings một lần
    ranked_rows = list(store.iter_ranking_rows(profile, include_unranked=True))
    by_ticker: dict[str, dict] = {}
    scored_sorted = sorted(
        [r for r in ranked_rows if r.get("ranked") and r.get("score") is not None],
        key=lambda r: (-float(r["score"]), str(r.get("ticker") or "")),
    )
    rank_map: dict[str, int] = {
        str(r["ticker"]): i + 1 for i, r in enumerate(scored_sorted)
    }
    total_scored = len(scored_sorted)
    for r in ranked_rows:
        t = str(r.get("ticker") or "")
        if t:
            by_ticker[t] = r

    items: list[dict[str, Any]] = []
    for sym in symbols:
        row = by_ticker.get(sym) or {}
        q = hub.get_quote(sym)
        try:
            snap = store.load_snapshot(sym)
        except Exception:  # noqa: BLE001
            snap = {}
        basis = q.basis if q.state == "live" else "eod"
        val = _live_valuation(snap if isinstance(snap, dict) else {}, q.price, as_of_ts=as_of_ts, basis=basis)
        ref = row.get("reference_price")
        price = q.price if q.price is not None else row.get("price")
        gap = evaluate_ref_gap(price, ref)

        if q.state == "unit_mismatch":
            label = "Đơn vị giá lệch — đang dùng giá đóng cửa EOD"
        elif q.state == "live":
            label = "trực tiếp (tạm tính)"
        elif q.state == "stale":
            label = "Giá tạm tính — cập nhật chậm"
        elif q.state == "connecting":
            label = "Đang chờ tick giá"
        elif q.state == "closed":
            label = f"đóng cửa { _fmt_ddmm(store.asof) }"
        elif q.state == "no_realtime":
            label = "EOD"
        else:
            label = "EOD"

        items.append(
            {
                "symbol": sym,
                "name": row.get("name") or ((snap.get("company") or {}).get("name") if isinstance(snap, dict) else None),
                "sector": row.get("sector")
                or ((snap.get("company") or {}).get("sector") if isinstance(snap, dict) else None),
                "price": {"value": price, "as_of_ts": as_of_ts, "basis": basis},
                "change_pct": {
                    "value": q.change_pct,
                    "as_of_ts": as_of_ts,
                    "basis": basis,
                },
                "prev_close_source": q.prev_close_source,
                "score": row.get("score"),
                "rank": rank_map.get(sym),
                "total_scored": total_scored,
                "rating": row.get("rating"),
                "dividend_yield": val.get("dividend_yield"),
                "sector_ref": {
                    "value": gap["display"],
                    "gap_pct": gap["gap_pct"],
                    "unreliable": gap["unreliable"],
                    "label": gap["label"],
                    "as_of_ts": as_of_ts,
                    "basis": "eod",
                },
                "state": q.state,
                "label": label,
                "data_asof": store.asof,
            }
        )

    return {
        "asof": store.asof,
        "as_of_ts": as_of_ts,
        "profile": profile,
        "realtime_mode": mode,
        "items": items,
        "label": "tạm tính" if mode == "live" else "EOD",
    }


def _fmt_ddmm(asof: str | None) -> str:
    if not asof or len(asof) < 10:
        return "—"
    # YYYY-MM-DD → dd/mm
    return f"{asof[8:10]}/{asof[5:7]}"
