"""M8 - kiểm chứng (N6). Giữ nguyên chữ ký run(snapshot, upstream, cfg) -> dict (VALIDATION_SCHEMA).

Kiểm tra bằng code (không dùng LLM): dữ liệu (look-ahead, synthetic, trạng thái nguồn), module (stub/error, điểm trong 0-100,
số liệu hữu hạn, nguồn trích dẫn tồn tại), kết quả M7 (tính lại điểm + khuyến nghị, target chỉ đến từ M4).
Lỗi nặng -> status="fail" nhưng pipeline VẪN xuất PDF kèm khung cảnh báo.
Không đặt hàm chạy thử có input()/dữ liệu mô phỏng trong file này.
"""
from __future__ import annotations

import math

from stockai.contracts.helpers import check_no_lookahead

RATING_ORDER = ["Bán", "Giảm tỷ trọng", "Nắm giữ", "Mua", "Mua mạnh"]


def _issue(sev: str, msg: str, where: str | None = None) -> dict:
    d = {"severity": sev, "message": msg}
    if where:
        d["where"] = where
    return d


def _check_data(snapshot: dict, issues: list, counter: list) -> None:
    counter[0] += 1
    if snapshot["meta"].get("synthetic"):
        issues.append(_issue("warn", "Snapshot là dữ liệu GIẢ (synthetic) - không dùng cho báo cáo thật", "meta.synthetic"))
    counter[0] += 1
    for v in check_no_lookahead(snapshot):
        issues.append(_issue("fatal", f"Look-ahead: {v}", "snapshot"))
    for k, v in snapshot["meta"].get("data_status", {}).items():
        counter[0] += 1
        if v == "missing":
            issues.append(_issue("warn", f"Dữ liệu '{k}' bị thiếu", f"meta.data_status.{k}"))
        elif v == "partial":
            issues.append(_issue("info", f"Dữ liệu '{k}' chưa đầy đủ", f"meta.data_status.{k}"))
    fl = snapshot["meta"].get("flags", [])
    if any(p.get("published_at_estimated") for p in snapshot["financials"]["annual"][:1]):
        issues.append(_issue("info", "Ngày công bố BCTC là ước lượng (nguồn không cung cấp)", "financials"))
    if "universe_membership_current_not_point_in_time" in fl:
        issues.append(_issue("info", "Peers lấy theo thành viên VN30 hiện hành, không phải thời điểm as_of", "peers"))
    if "peers_cross_sector_vn30_nonbank_fallback" in fl:
        issues.append(_issue("warn", "Peers khác ngành (ngành chỉ có 1 mã trong VN30) - so sánh định giá chỉ mang tính tham khảo", "peers"))


def _check_modules(snapshot: dict, upstream: dict, issues: list, counter: list) -> None:
    src_ids = {s["id"] for s in snapshot.get("sources", [])}
    news_ids = {n["id"] for n in snapshot.get("news", [])}
    stubs, errors = [], []
    for name in ("m2", "m3", "m4", "m5", "m6"):
        o = upstream.get(name)
        counter[0] += 1
        if o is None:
            errors.append(name)
            continue
        if o.get("status") == "stub":
            stubs.append(name)
        elif o.get("status") == "error":
            errors.append(name)
            issues.append(_issue("warn", f"Module {name} lỗi: {str(o.get('error', ''))[:120]}", name))
        sc = o.get("score")
        if sc is not None and not (isinstance(sc, (int, float)) and 0 <= sc <= 100):
            issues.append(_issue("fatal", f"Điểm {name} ngoài thang 0-100: {sc}", f"{name}.score"))
        for k, m in (o.get("metrics") or {}).items():
            v = m.get("value") if isinstance(m, dict) else None
            if v is not None and not (isinstance(v, (int, float)) and math.isfinite(v)):
                issues.append(_issue("fatal", f"Chỉ số {k} không phải số hữu hạn", f"{name}.metrics.{k}"))
        for ev in o.get("evidence") or []:
            counter[0] += 1
            sid, nid = ev.get("source_id"), ev.get("news_id")
            if sid and sid not in src_ids:
                issues.append(_issue("warn", f"Trích dẫn nguồn không tồn tại trong snapshot: {sid}", f"{name}.evidence"))
            if nid and nid not in news_ids:
                issues.append(_issue("warn", f"Trích dẫn tin không tồn tại trong snapshot: {nid}", f"{name}.evidence"))
    if stubs:
        issues.append(_issue("warn", f"Module chưa triển khai (dùng điểm trung tính): {', '.join(m.upper() for m in stubs)}"))
    if errors:
        issues.append(_issue("warn", f"Module lỗi/thiếu: {', '.join(m.upper() for m in errors)}"))


def _check_m7(upstream: dict, cfg: dict, issues: list, counter: list) -> None:
    r = upstream.get("m7")
    counter[0] += 1
    if not isinstance(r, dict) or "score" not in r:
        issues.append(_issue("fatal", "Thiếu kết quả M7", "m7"))
        return
    qg = r.get("quality_gate") or {}
    # FR-008: không kiểm tra công thức điểm / ngưỡng khuyến nghị khi không xếp hạng
    skip_score_rating = qg.get("scored") is False or r.get("score") is None
    if not skip_score_rating:
        try:
            prof = cfg["profiles"][r["profile"]]
            sc = r["scores"]
            expect = sum(prof["weights"][k] * sc[k] for k in ("F", "T", "V", "S")) - prof["lambda_R"] * sc["R"]
            expect = max(0.0, min(100.0, expect))
            counter[0] += 1
            if abs(expect - r["score"]) > 0.05:
                issues.append(_issue("fatal", f"Điểm M7 {r['score']:.2f} không khớp công thức ({expect:.2f})", "m7.score"))
            counter[0] += 1
            label = next(x["label"] for x in cfg["ratings"] if expect >= x["min"])
            gate = cfg["risk_gate"]
            if sc["R"] >= gate["R_threshold"] and RATING_ORDER.index(label) > RATING_ORDER.index(gate["max_rating"]):
                label = gate["max_rating"]
            if label != r["rating"]:
                issues.append(_issue("fatal", f"Khuyến nghị '{r['rating']}' không khớp ngưỡng điểm (kỳ vọng '{label}')", "m7.rating"))
        except (KeyError, StopIteration, TypeError, ValueError) as e:
            issues.append(_issue("fatal", f"Không kiểm tra lại được M7: {e}", "m7"))
    else:
        counter[0] += 1  # ghi nhận đã xét nhánh skip công thức/ngưỡng
        if r.get("rating") != "Không xếp hạng":
            issues.append(_issue("warn", "quality_gate không xếp hạng nhưng rating không phải 'Không xếp hạng'", "m7.rating"))
    counter[0] += 1
    # Khi không xếp hạng: target buộc null — không so với M4
    if not skip_score_rating:
        if r.get("target") != (upstream.get("m4") or {}).get("target"):
            issues.append(_issue("fatal", "Giá mục tiêu trong kết quả khác M4 (chỉ M4 được tạo giá mục tiêu)", "m7.target"))
        if not (upstream.get("m4") or {}).get("target") and (upstream.get("m4") or {}).get("status") in ("stub", "error", None):
            issues.append(_issue("info", "Chưa có giá mục tiêu (M4 chưa chạy thật)", "m4"))
    elif r.get("target") is not None:
        issues.append(_issue("warn", "quality_gate không xếp hạng nhưng target không null", "m7.target"))


def run(snapshot: dict, upstream: dict, cfg: dict) -> dict:
    issues: list[dict] = []
    counter = [0]
    _check_data(snapshot, issues, counter)
    _check_modules(snapshot, upstream, issues, counter)
    _check_m7(upstream, cfg, issues, counter)
    if any(i["severity"] == "fatal" for i in issues):
        status = "fail"
    elif any(i["severity"] == "warn" for i in issues):
        status = "warn"
    else:
        status = "pass"
    return {"status": status, "checked": counter[0], "issues": issues}
