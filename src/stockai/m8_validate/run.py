"""Basic quality gate for synthetic, incomplete and unimplemented analysis inputs."""


def run(snapshot: dict, upstream: dict, cfg: dict) -> dict:
    issues = []
    if snapshot["meta"].get("synthetic"):
        issues.append({"severity": "warn", "message": "Snapshot là dữ liệu GIẢ (synthetic) - không dùng cho báo cáo thật"})
    stubs = [m for m, o in upstream.items() if isinstance(o, dict) and o.get("status") in {"stub", "error"}]
    if stubs:
        issues.append({"severity": "warn", "message": f"Module lỗi hoặc chưa triển khai: {', '.join(stubs)}"})
    partial = [m for m, o in upstream.items() if isinstance(o, dict) and o.get("status") == "partial"]
    if partial:
        issues.append({"severity": "warn", "message": f"Module có dữ liệu chưa đầy đủ: {', '.join(partial)}"})
    incomplete_groups = [
        name for name, status in snapshot["meta"].get("data_status", {}).items()
        if status != "ok"
    ]
    if incomplete_groups:
        issues.append({"severity": "warn", "message": f"Nhóm dữ liệu chưa đầy đủ: {', '.join(incomplete_groups)}"})
    return {"status": "warn" if issues else "pass", "checked": 3, "issues": issues}
