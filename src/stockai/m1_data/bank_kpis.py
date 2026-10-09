"""NPL, CAR của ngân hàng: không có trong BCTC nên nhập tay từ báo cáo thường niên vào config/bank_kpis.csv (chỉ N2 sửa).

Cột: ticker, period (2025 hoặc 2026Q2), npl_ratio (%), car (%), source (tên + trang/URL báo cáo), note.
Ô trống = chưa có -> giữ null và gắn cờ. Đơn vị nhập là PHẦN TRĂM (1.2 nghĩa là 1,2%); snapshot lưu dạng tỷ lệ (0.012)."""
from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path


def _num(x):
    try:
        return round(float(str(x).replace(",", ".").strip()) / 100.0, 6) if str(x).strip() else None
    except ValueError:
        return None


def apply(snap: dict, path: str = "config/bank_kpis.csv") -> None:
    p, t, flags = Path(path), snap["meta"]["ticker"], snap["meta"]["flags"]
    rows = []
    if p.exists():
        with p.open(encoding="utf-8-sig", newline="") as f:
            rows = [r for r in csv.DictReader(f) if (r.get("ticker") or "").strip().upper() == t]
    used, srcs = 0, []
    for blk in ("annual", "quarterly"):
        for per in snap["financials"][blk]:
            for r in rows:
                if (r.get("period") or "").strip() == per["period"]:
                    for k in ("npl_ratio", "car"):
                        v = _num(r.get(k))
                        if v is not None:
                            per["items"][k] = v
                            used += 1
                    if (r.get("source") or "").strip():
                        srcs.append(r["source"].strip())
    flags[:] = [f for f in flags if f not in ("bank_npl_car_not_in_statements", "bank_kpis_manual_partial")]
    latest = snap["financials"]["annual"][0]["items"] if snap["financials"]["annual"] else {}
    if used:
        snap["sources"].append({"id": "src_bank_kpis", "name": "NPL, CAR nhập tay từ báo cáo thường niên", "url": "internal://config/bank_kpis.csv",
                                "fetched_at": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"), "note": "; ".join(dict.fromkeys(srcs))[:300] or "xem config/bank_kpis.csv"})
        flags.append("bank_kpis_manual")
    if latest.get("npl_ratio") is None or latest.get("car") is None:
        flags.append("bank_npl_car_not_in_statements" if not used else "bank_kpis_manual_partial")
