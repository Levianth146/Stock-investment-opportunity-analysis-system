"""
M9 - PDF Report Generator (N6-08 & N6-09)
Biên dịch dữ liệu đầu ra thành file PDF kèm nguồn trích dẫn (provenance).
"""
import os
from pathlib import Path
from typing import Dict, Any
from jinja2 import Environment, FileSystemLoader
from matplotlib import get_data_path
from xhtml2pdf import pisa


def _pdf_font_paths() -> dict[str, Path]:
    font_dir = Path(get_data_path()) / "fonts" / "ttf"
    fonts = {
        "stockai-font://regular": font_dir / "DejaVuSans.ttf",
        "stockai-font://bold": font_dir / "DejaVuSans-Bold.ttf",
    }
    if any(not font.is_file() for font in fonts.values()):
        raise FileNotFoundError(f"Vietnamese-capable PDF fonts not found in {font_dir}")
    return fonts


def _font_link_callback(uri: str, _rel: str) -> str:
    font_path = _pdf_font_paths().get(uri)
    return str(font_path) if font_path else uri


def generate_pdf_report(payload: Dict[str, Any], output_path: str, m8_validation: Dict[str, Any]) -> bool:
    # Điều kiện bắt buộc (Task N6-13 / M8 gating): Chặn xuất PDF nếu M8 trả về FAIL
    if not m8_validation.get("is_passed", True):
        raise ValueError("M8 Validation FAILED: Không thể xuất báo cáo do vi phạm kiểm định số liệu!")

    # 1. Định vị đường dẫn template HTML
    template_dir = Path(__file__).parent / "templates"
    env = Environment(loader=FileSystemLoader(str(template_dir)))
    template = env.get_template("report_template.html")

    # 2. Gắn thông tin trích dẫn nguồn (Task N6-09 - Provenance)
    provenance = payload.get("provenance", [
        {"metric": "Giá đóng cửa & Khối lượng", "value": "OHLCV 5 năm", "source": "HOSE", "published_at": payload.get("as_of", "2026-10-09")},
        {"metric": "BCTC & Tăng trưởng", "value": "FS 2021-2026", "source": "Báo cáo công bố chính thức", "published_at": payload.get("as_of", "2026-10-09")},
    ])

    render_context = {
        "ticker": payload.get("ticker", "DEMO"),
        "as_of": payload.get("as_of", "2026-10-09"),
        "profile": payload.get("profile", "Dài hạn (Long-term)"),
        "scores": payload.get("scores", {"F": 0, "T": 0, "V": 0, "S": 0, "R": 0, "final": 0}),
        "recommendation": payload.get("recommendation", "Chưa xác định"),
        "target_price": f"{payload.get('target_price', 0):,}",
        "debate": payload.get("debate", {"bull": "Chưa có", "bear": "Chưa có"}),
        "provenance": provenance,
        "pdf_render": True,
    }

    # 3. Render HTML
    html_content = template.render(render_context)

    # 4. Xuất ra file PDF
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    with open(output_path, "wb") as pdf_file:
        pisa_status = pisa.CreatePDF(
            html_content,
            dest=pdf_file,
            encoding="utf-8",
            link_callback=_font_link_callback,
        )

    return not pisa_status.err