"""M8 - kiểm chứng (N6). Stub: chỉ báo 'pass' với 0 mục kiểm tra.

Việc cần làm: (1) mọi số trong result/narrative phải khớp snapshot hoặc output module;
(2) mỗi claim có nguồn; (3) cảnh báo dữ liệu giả (meta.synthetic) / module stub.
Khuyến nghị: lỗi nặng -> status="fail" nhưng pipeline VẪN xuất PDF kèm khung cảnh báo (đừng chặn cứng sát giờ nộp).
"""


def run(snapshot: dict, upstream: dict, cfg: dict) -> dict:
    issues = []
    if snapshot["meta"].get("synthetic"):
        issues.append({"severity": "warn", "message": "Snapshot là dữ liệu GIẢ (synthetic) - không dùng cho báo cáo thật"})
    stubs = [m for m, o in upstream.items() if isinstance(o, dict) and o.get("status") == "stub"]
    if stubs:
        issues.append({"severity": "warn", "message": f"Module chưa triển khai: {', '.join(stubs)}"})
    return {"status": "warn" if issues else "pass", "checked": 0, "issues": issues}
