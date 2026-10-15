from datetime import date
from types import SimpleNamespace

import pymupdf
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

from stockai.m9_report.data import _cover_company_metadata
from stockai.m9_report.pages.cover import draw_cover
from stockai.m9_report.theme import build_theme, load_report_cfg


def _render_cover(path, ticker, company, rating):
    cfg = load_report_cfg()
    build_theme(cfg)  # Register the report fonts used by the ReportLab canvas.
    pdf = canvas.Canvas(str(path), pagesize=A4)
    doc = SimpleNamespace(
        c=pdf,
        rc=cfg,
        export_date=date(2026, 10, 15),
        data=SimpleNamespace(
            ticker=ticker,
            company=company,
            rating=rating,
            as_of="2026-10-08",
        ),
    )
    draw_cover(doc, 1, 9)
    pdf.save()
    return pymupdf.open(path)


def test_local_listing_supplies_dynamic_legal_and_brand_names():
    gas = _cover_company_metadata("GAS", {"name": "PV Gas", "exchange": "HSX"})
    vnm = _cover_company_metadata("VNM", {"name": "VINAMILK", "exchange": "HSX"})
    vcb = _cover_company_metadata("VCB", {"name": "Vietcombank", "exchange": "HSX"})

    assert gas["full_name"] == "Tổng Công ty Khí Việt Nam - Công ty Cổ phần"
    assert gas["short_name"] == "PV Gas"
    assert vnm["full_name"] == "Công ty Cổ phần Sữa Việt Nam"
    assert vcb["full_name"] == "Ngân hàng Thương mại Cổ phần Ngoại thương Việt Nam"
    assert vcb["name"] == "Vietcombank"  # Preserve the snapshot's existing display field.


def test_snapshot_legal_name_takes_precedence_over_listing():
    company = _cover_company_metadata(
        "GAS", {"name": "Snapshot display", "full_name": "Snapshot legal name"}
    )
    assert company["full_name"] == "Snapshot legal name"


def test_cover_text_is_dynamic_and_long_fields_stay_on_page(tmp_path):
    long_name = (
        "Ngân hàng Thương mại Cổ phần Ngoại thương Việt Nam "
        "Công ty trách nhiệm hữu hạn quản lý tài sản"
    )
    long_sector = "Ngân hàng thương mại và dịch vụ tài chính doanh nghiệp quốc tế"
    document = _render_cover(
        tmp_path / "cover.pdf",
        "VCB",
        {"full_name": long_name, "name": "Vietcombank", "sector": long_sector, "exchange": "HSX"},
        "Giảm tỷ trọng",
    )
    page = document[0]
    text = " ".join(page.get_text().split())
    for token in ("VCB", "Ngân hàng", "Ngoại thương Việt Nam", "Ngành:", "HSX",
                  "Giảm tỷ trọng", "08/10/2026", "15/10/2026"):
        assert token in text
    for block in page.get_text("dict")["blocks"]:
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                x0, y0, x1, y1 = span["bbox"]
                assert x0 >= 0 and y0 >= 0
                assert x1 <= page.rect.width and y1 <= page.rect.height
