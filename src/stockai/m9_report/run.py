"""M9 - xuất PDF (N6). Stub: PDF 1 trang chữ ASCII để pipeline chạy được end-to-end.

TODO(N6): font tiếng Việt (đăng ký TTF như DejaVuSans/Roboto qua reportlab.pdfbase.ttfonts),
bố cục 10 mục, biểu đồ (matplotlib), footnote nguồn từ snapshot["sources"], khung cảnh báo từ validation.
"""
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas


def _score_text(result: dict) -> str:
    sc = result.get("score")
    if sc is None:
        return "n/a (not ranked)"
    return f"{sc:.1f}"


def _rating_text(result: dict) -> str:
    raw = result.get("rating") or "n/a"
    return raw.encode("ascii", "ignore").decode() or "n/a"


def _quality_lines(result: dict) -> list[str]:
    qg = result.get("quality_gate") or {}
    tier = qg.get("tier", "absent")
    reasons = qg.get("reasons") or []
    reason_s = ", ".join(reasons) if reasons else "(none)"
    if qg.get("scored") is False:
        return [
            f"Quality gate: {tier} - NOT RANKED",
            f"Exclusion reasons: {reason_s}",
        ]
    if tier == "limited":
        return [
            f"Quality gate: limited - scored with limitations",
            f"Limitations: {reason_s}",
        ]
    if tier and tier != "absent":
        return [f"Quality gate: {tier}"]
    return []


def run(snapshot: dict, upstream: dict, cfg: dict) -> dict:
    result, validation = upstream["m7"], upstream["m8"]
    out = Path(cfg.get("out_dir", "reports")) / f"{result['ticker']}_{result['as_of']}_{result['profile']}.pdf"
    out.parent.mkdir(parents=True, exist_ok=True)
    # pageCompression=0: giữ text ASCII trong PDF để test/offline assert được
    c = canvas.Canvas(str(out), pagesize=A4, pageCompression=0)
    y = 800
    lines = [
        f"STOCK REPORT (STUB) - {result['ticker']} - as_of {result['as_of']}",
        f"Profile: {result['profile']}   Score: {_score_text(result)}   Rating(code): {_rating_text(result)}",
        f"Validation: {validation['status']} ({len(validation['issues'])} issue)",
        *_quality_lines(result),
        "TODO: Vietnamese font + full 10-section layout",
    ]
    for line in lines:
        c.drawString(50, y, line)
        y -= 20
    c.save()
    return {"pdf_path": str(out)}
