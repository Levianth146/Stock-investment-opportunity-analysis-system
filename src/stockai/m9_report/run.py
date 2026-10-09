"""M9 - xuất PDF (N6). Stub: PDF 1 trang chữ ASCII để pipeline chạy được end-to-end.

TODO(N6): font tiếng Việt (đăng ký TTF như DejaVuSans/Roboto qua reportlab.pdfbase.ttfonts),
bố cục 10 mục, biểu đồ (matplotlib), footnote nguồn từ snapshot["sources"], khung cảnh báo từ validation.
"""
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas


def run(snapshot: dict, upstream: dict, cfg: dict) -> dict:
    result, validation = upstream["m7"], upstream["m8"]
    out = Path(cfg.get("out_dir", "reports")) / f"{result['ticker']}_{result['as_of']}_{result['profile']}.pdf"
    out.parent.mkdir(parents=True, exist_ok=True)
    c = canvas.Canvas(str(out), pagesize=A4)
    y = 800
    for line in [f"STOCK REPORT (STUB) - {result['ticker']} - as_of {result['as_of']}",
                 f"Profile: {result['profile']}   Score: {result['score']:.1f}   Rating(code): {result['rating'].encode('ascii','ignore').decode() or 'n/a'}",
                 f"Validation: {validation['status']} ({len(validation['issues'])} issue)",
                 "TODO: Vietnamese font + full 10-section layout"]:
        c.drawString(50, y, line); y -= 20
    c.save()
    return {"pdf_path": str(out)}
