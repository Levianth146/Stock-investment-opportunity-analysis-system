from datetime import date
from types import SimpleNamespace

import pymupdf
import pytest
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

from stockai.m9_report.layout import make_styles
from stockai.m9_report.professional_layout import ProDoc
from stockai.m9_report.theme import build_theme, load_report_cfg
from stockai.m9_report.pages.snapshot_pages import (
    draw_summary, draw_fundamental_performance, price_markers, news_rows,
    financial_health_metrics, conclusion_bullets, annual_observations, number,
)


def _metric(value):
    return {"value": value, "unit": "ratio"}


def test_price_scale_handles_extremes_missing_and_equal_prices():
    markers = price_markers({"bear": 1, "base": 1.00001, "bull": 100000}, 123456789)
    positions = [marker[2] for marker in sorted(markers, key=lambda marker: marker[1])]
    assert positions == sorted(positions)
    assert all(0 <= p <= 1 for p in positions)
    assert price_markers({"base": None, "bear": -2, "bull": 0}, None) == []
    assert price_markers({"base": 10}, 10) == [("Base", 10, 0.5), ("Hiện tại", 10, 0.5)]
    assert [m[0] for m in price_markers({"base": 10}, 20)] == ["Base", "Hiện tại"]


def test_missing_news_score_distinguishes_m7_neutral_fallback():
    data = SimpleNamespace(m={"m5": {"status": "partial", "score": None, "metrics": {}}},
                           m7={"flags": ["S_missing_used_neutral"], "scores": {"S": 50}},
                           m8={"status": "warn", "issues": [{"severity": "warn"}, {"severity": "info"}]})
    rows = dict(news_rows(data))
    assert rows["Tin tức M5"] == "Chưa đủ dữ liệu"
    assert rows["M7 trung tính"] == "50,0/100"
    assert "Điểm tin tức M5" not in rows
    assert rows["Cảnh báo M8"] == "1"


def test_bank_health_uses_only_available_bank_metrics():
    module = {"status": "partial", "score": 66.8, "metrics": {
        "nim": _metric(0.024), "cir": _metric(0.35), "loan_to_deposit": _metric(0.98),
        "npl_ratio": _metric(None), "car": _metric(None), "gross_margin": _metric(0.5),
    }}
    cards = financial_health_metrics(module, True)
    assert [key for key, _, _ in cards] == ["nim", "cir", "loan_to_deposit"]
    text = " ".join(conclusion_bullets(module, True))
    assert "M2 chưa có số liệu" in text
    assert "an toàn" not in text and "rất khỏe" not in text
    assert number(None, "x") == "N/A"
    assert number(0, "x") == "0x"


def test_highlights_ignore_missing_annual_values_and_keep_equality():
    lines = annual_observations(["2023", "2024", "2025"], [None, 3, 3], [None, -1, 2], "Doanh thu")
    assert "2 năm" in lines[0]
    assert "2025 bằng 2024" in lines[-1]
    assert "0,0" not in " ".join(lines)


def _data(bank):
    m2metrics = {
        "roe": _metric(0.123), "net_income_growth": _metric(-0.497), "revenue_growth": _metric(0),
        "nim": _metric(0.024), "cir": _metric(0.35), "loan_to_deposit": _metric(0.98),
        "npl_ratio": _metric(None), "car": _metric(None),
    } if bank else {
        "roe": _metric(0.123), "net_income_growth": _metric(-0.497), "revenue_growth": _metric(0),
        "gross_margin": _metric(0.3), "debt_to_equity": _metric(1234.56),
        "debt_to_assets": _metric(0.4), "interest_coverage": _metric(1234.56),
        "cfo_to_net_income": _metric(-0.9), "current_ratio": _metric(None),
    }
    scores = {"F": 66.8, "T": 73, "V": 10, "S": 50, "R": 60.1}
    return SimpleNamespace(
        ticker="ABCDE", profile="long_term", company={"name": "Công ty có tên rất dài để kiểm tra giới hạn tiêu đề và căn lề trong báo cáo tài chính", "sector": "Ngành rất dài", "is_bank": bank},
        close=123456789, target={"bear": 1, "base": 1.0001, "bull": 3}, score=41.6,
        rating="Giảm tỷ trọng", m7={"scores": scores, "contributions": dict.fromkeys(scores, 1.5),
                                  "flags": ["S_missing_used_neutral"]},
        bull=[{"text": "Dữ liệu hỗ trợ định lượng. "*40}]*4,
        bear=[{"text": "Dữ liệu gây áp lực định lượng. "*40}]*4,
        m={"m2": {"status": "partial", "score": 66.8, "metrics": m2metrics},
           "m3": {"status": "ok", "score": 73, "metrics": {"rsi14": _metric(63.2)}},
           "m4": {"status": "partial", "score": 10},
           "m5": {"status": "partial", "score": None, "metrics": {"news_story_count": _metric(123), "news_distinct_sources": _metric(99)}},
           "m6": {"status": "ok", "score": 60.1, "metrics": {"annualized_volatility": _metric(47.8), "max_drawdown": _metric(33.6), "beta": _metric(0.96)}}},
        m8={"status": "PASS WITH WARNING", "issues": [{"severity": "warn"}]},
        annual=[], quarterly=[],
    )


@pytest.mark.parametrize("bank", [False, True])
def test_page23_long_text_and_missing_values_stay_inside_bounds(tmp_path, bank):
    cfg = load_report_cfg()
    theme = build_theme(cfg)
    doc = ProDoc(theme, make_styles(theme), _data(bank), cfg, {}, {}, date(2026, 10, 15))
    path = tmp_path / f"page23-{bank}.pdf"
    doc.c = canvas.Canvas(str(path), pagesize=A4)
    draw_summary(doc, 2, 9); doc.c.showPage()
    draw_fundamental_performance(doc, 3, 9); doc.c.save()
    with pymupdf.open(path) as pdf:
        assert len(pdf) == 2
        for index, page in enumerate(pdf):
            text_regions = [region for region in doc._insight_regions if region["page"] == index+2 and region["kind"] == "text"]
            for region in text_regions:
                assert region["height"] <= region["box"][3]+0.01
            rectangles = [pymupdf.Rect(x*mm, y*mm, (x+w)*mm, (y+h)*mm) for x, y, w, h in (r["box"] for r in text_regions)]
            for block in page.get_text("dict")["blocks"]:
                for line in block.get("lines", []):
                    for span in line["spans"]:
                        bbox = pymupdf.Rect(span["bbox"])
                        assert pymupdf.Rect(-1, -1, page.rect.width+1, page.rect.height+1).contains(bbox)
                        assert any((rect+(-1.5, -1.5, 1.5, 1.5)).contains(bbox) for rect in rectangles), (span["text"], bbox)
            for prefix in ("kpi.0", "kpi.1", "kpi.2", "kpi.3"):
                boxes = [r["box"] for r in text_regions if r["name"].startswith(prefix+".")]
                rects = [pymupdf.Rect(x, y, x+w, y+h) for x, y, w, h in boxes]
                assert all((a & b).is_empty for k, a in enumerate(rects) for b in rects[k+1:])
        assert "Chưa đủ dữ liệu" in pdf[0].get_text()
        assert "M7 trung tính" in " ".join(pdf[0].get_text().split())
        assert "PASS WITH WARNING" in " ".join(pdf[0].get_text().split())
        assert "123.456.789" in pdf[0].get_text()
        assert "NPL" not in pdf[1].get_text() if not bank else "N/A" in pdf[1].get_text()
