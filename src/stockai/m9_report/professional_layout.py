"""Layout M9 chuyên nghiệp, ưu tiên khả năng đọc và trung thực dữ liệu.

Thiết kế này tách các nội dung lớn thành nhiều trang. M9 không gọi mạng, không tạo forecast,
không tạo chỉ tiêu tài chính mới ngoài số học trực tiếp trên dữ liệu M1 và output M2-M8.
Trang bìa hỗ trợ asset branding tùy chọn; khi không có asset dùng motif theo ngành.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Sequence
from xml.sax.saxutils import escape

from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas as rl_canvas
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import Frame, KeepInFrame, Paragraph, Spacer

from stockai.m9_report import charts
from stockai.m9_report import professional_charts as pcharts
from stockai.m9_report.data import ReportData, metric
from stockai.m9_report.fmt import fmt_date, fmt_num, fmt_pct_points, fmt_pct_ratio, fmt_score, to_float
from stockai.m9_report.layout import Doc, Styles, contributions_rows, esc, make_styles
from stockai.m9_report.news_cluster import select_news_panel
from stockai.m9_report.theme import ROOT, SANS, SANS_BOLD, SANS_SEMI, Theme
from stockai.m9_report.text import reason_text, translate_flags

PAGE_W, PAGE_H = A4
PAGE_W_MM, PAGE_H_MM = PAGE_W/mm, PAGE_H/mm


def _hex(c: str):
    return HexColor(c)


def _draw_page_backdrop(c, theme: Theme) -> None:
    """Paint a restrained blue/aqua corner motif below the content layer."""
    colors = theme.c
    c.setFillColor(_hex(colors.get("page_bg", colors["paper"])))
    c.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)
    alpha = float(theme.cfg.get("layout", {}).get("page_wave_alpha", 0.20))
    if hasattr(c, "setFillAlpha"):
        c.setFillAlpha(max(0.0, min(alpha, 1.0)))
    c.setFillColor(_hex(colors.get("wave_blue", "#DDF3FF")))
    p = c.beginPath()
    p.moveTo(PAGE_W * .76, PAGE_H)
    p.curveTo(PAGE_W * .84, PAGE_H * .93, PAGE_W * 1.03, PAGE_H * .97, PAGE_W, PAGE_H * .88)
    p.lineTo(PAGE_W, PAGE_H)
    p.close()
    c.drawPath(p, fill=1, stroke=0)
    c.setFillColor(_hex(colors.get("wave_aqua", "#D9F5F1")))
    p = c.beginPath()
    p.moveTo(0, PAGE_H * .12)
    p.curveTo(PAGE_W * .12, PAGE_H * .04, PAGE_W * .21, PAGE_H * .11, PAGE_W * .25, 0)
    p.lineTo(0, 0)
    p.close()
    c.drawPath(p, fill=1, stroke=0)
    if hasattr(c, "setFillAlpha"):
        c.setFillAlpha(1)


def _vnd_tril(v) -> float | None:
    x = to_float(v)
    return None if x is None else x/1e12


def _period_rows(rows: list[dict]) -> tuple[list[str], list[dict]]:
    rows = sorted([r for r in rows if isinstance(r, dict)], key=lambda r: str(r.get("period")))
    return [str(r.get("period")) for r in rows], [r.get("items") or {} for r in rows]


def _value(items: dict, *keys):
    for k in keys:
        v = to_float(items.get(k))
        if v is not None:
            return v
    return None


def _asset(ticker: str, stem: str) -> Path | None:
    d = ROOT / "assets" / "branding" / ticker.upper()
    if not d.is_dir():
        return None
    for ext in (".png", ".jpg", ".jpeg", ".webp"):
        p = d / f"{stem}{ext}"
        if p.is_file():
            return p
    return None


def _sector_palette(sector: str | None, ticker: str) -> tuple[str, str, str]:
    sec = str(sector or "").lower()
    table = {
        "food & beverage": ("#0A6B78", "#27B38A", "#E8F7F4"),
        "banks": ("#113A67", "#C99A2E", "#EEF3F8"),
        "technology": ("#1557B0", "#20A6D8", "#EDF6FC"),
        "basic resources": ("#244A69", "#6E879D", "#EEF2F5"),
        "real estate": ("#51447D", "#C69B54", "#F5F1EA"),
        "retail": ("#C44B2D", "#F3A329", "#FFF3E7"),
        "travel & leisure": ("#1D73B7", "#5EC4DB", "#ECF8FC"),
    }
    if sec in table:
        return table[sec]
    # deterministic fallback khác nhau theo ticker
    s = sum(ord(ch) for ch in ticker.upper()) % 4
    return [
        ("#164D86", "#3A8DD8", "#EEF5FC"),
        ("#315F54", "#5BAF8D", "#EDF7F3"),
        ("#65466E", "#AA74B4", "#F7EFF8"),
        ("#6B4C28", "#C38A49", "#FAF4EC"),
    ][s]


def _clean_point(text: str, positive: bool) -> str:
    """Diễn đạt lại câu template M7, chỉ dùng chính số liệu/nội dung đã có trong M7."""
    s = str(text or "").strip()
    # phần sau dấu ':' chứa bằng chứng do M7 tạo
    head, sep, evidence = s.partition(":")
    evidence = evidence.strip() if sep else s
    evidence = re.sub(r"\s+", " ", evidence).strip().rstrip(".")
    low = head.lower()
    if "cơ bản" in low:
        return f"Nền tảng tài chính {'đang hỗ trợ đánh giá chung' if positive else 'đang gây áp lực'}: {evidence}."
    if "rủi ro" in low:
        return f"Mức rủi ro thị trường {'đang hỗ trợ điểm tổng hợp' if positive else 'đang gây áp lực'}: {evidence}."
    if "định giá" in low:
        return f"Định giá {'đang hỗ trợ' if positive else 'đang tạo áp lực'}: {evidence}."
    if "kỹ thuật" in low:
        return f"Tín hiệu kỹ thuật {'đang hỗ trợ' if positive else 'còn yếu'}: {evidence}."
    if "tin" in low:
        return f"Tin tức {'đang hỗ trợ' if positive else 'đang gây áp lực'}: {evidence}."
    return evidence + ("." if evidence and not evidence.endswith(".") else "")


@dataclass
class Page:
    name: str
    draw: Callable[["ProDoc", int, int], None]


class ProDoc(Doc):
    def header(self, i: int, n: int, kicker: str = "") -> None:
        c = self.theme.c
        self.text("STOCKINSIGHT AI", self.x(0), 10.0, SANS_BOLD, 8.2, c["series_1"])
        nm = self.data.company.get("name") or self.data.ticker
        right = f"{self.data.ticker}  |  {nm}  |  Trang {i}/{n}"
        from reportlab.pdfbase.pdfmetrics import stringWidth
        w = stringWidth(right, SANS, 8.0)
        self.text(right, PAGE_W-self.x(0)-w, 10.0, SANS, 8.0, c["ink_3"])
        self.hrule(13.4)
        if kicker:
            self.text(kicker, self.x(0), 20.0, SANS_SEMI, 7.5, c["ink_3"])

    def footer(self, i: int, n: int) -> None:
        # Chủ ý không lặp nguồn/disclaimer/pipeline trên mọi trang.
        return

    def heading(self, i: int, n: int, title: str, subtitle: str = "", kicker: str = "") -> float:
        self.header(i, n, kicker)
        self.text(title, self.x(0), 31.0, SANS_BOLD, 23, self.theme.c["ink"])
        if subtitle:
            self.text(subtitle, self.x(0), 41.0, SANS, 10.5, self.theme.c["ink_2"])
        return 48.0

    def rounded_panel(self, col: int, span: int, top_mm: float, h_mm: float, *, fill: str = "#FFFFFF",
                      border: str | None = None, radius_mm: float | None = None) -> None:
        colors = self.theme.c
        radius_mm = radius_mm if radius_mm is not None else float(
            self.rc.get("layout", {}).get("panel_radius_mm", 3.2)
        )
        self.c.setFillColor(_hex(fill))
        self.c.setStrokeColor(_hex(border or colors.get("panel_border", colors["rule"])))
        self.c.setLineWidth(0.6)
        self.c.roundRect(self.x(col), self.y(top_mm+h_mm), self.w(span), h_mm*mm, radius_mm*mm, fill=1, stroke=1)

    def kpi(self, col: int, span: int, top_mm: float, h_mm: float, label: str, value: str, note: str = "",
            accent: str | None = None) -> None:
        colors = self.theme.c
        self.rounded_panel(col, span, top_mm, h_mm, fill=colors.get("panel_tint", colors["paper"]),
                           border=colors.get("kpi_border", colors.get("panel_border", colors["rule"])))
        ac = accent or colors.get("kpi_accent", colors["series_1"])
        self.c.setStrokeColor(_hex(ac)); self.c.setLineWidth(2.5)
        self.c.line(self.x(col)+4*mm, self.y(top_mm+5), self.x(col)+11*mm, self.y(top_mm+5))
        pad = 4.0 * mm
        text_w = max(1.0, self.w(span) - 2 * pad)
        label_style = ParagraphStyle(
            "kpi_label", fontName=SANS_SEMI, fontSize=7.5, leading=10.5,
            textColor=_hex(self.theme.c["ink_3"]), spaceBefore=0, spaceAfter=0,
        )
        note_style = ParagraphStyle(
            "kpi_note", fontName=SANS, fontSize=7, leading=9.8,
            textColor=_hex(self.theme.c["ink_3"]), spaceBefore=0, spaceAfter=0,
        )
        label_p = Paragraph(escape(str(label).upper()), label_style)
        note_p = Paragraph(escape(str(note)), note_style) if note else None
        _, label_h = label_p.wrap(text_w, h_mm * mm)
        note_h = 0.0
        if note_p:
            _, note_h = note_p.wrap(text_w, h_mm * mm)

        # Chia card thành các vùng theo chiều cao thực tế; không dùng KeepInFrame/flow.
        inner_top = self.y(top_mm + 5.8)
        inner_bottom = self.y(top_mm + h_mm - 0.8)
        gap = 0.75 * mm
        value_h = inner_top - inner_bottom - label_h - note_h - 2 * gap
        value_text = str(value)
        value_p = None
        for size in (16, 15, 14, 13, 12, 11, 10):
            value_style = ParagraphStyle(
                f"kpi_value_{size}", fontName=SANS_BOLD, fontSize=size, leading=size * 1.4,
                textColor=_hex(self.theme.c["ink"]), spaceBefore=0, spaceAfter=0,
            )
            candidate = Paragraph(escape(value_text), value_style)
            _, candidate_h = candidate.wrap(text_w, value_h)
            if candidate_h <= value_h + 0.1:
                value_p = candidate
                break
        if value_p is None:
            # Giữ nguyên nội dung và vùng riêng, hạ đến ngưỡng đọc được rồi cho Paragraph wrap.
            value_style = ParagraphStyle(
                "kpi_value_min", fontName=SANS_BOLD, fontSize=10, leading=14,
                textColor=_hex(self.theme.c["ink"]), spaceBefore=0, spaceAfter=0,
            )
            value_p = Paragraph(escape(value_text), value_style)
            _, value_h = value_p.wrap(text_w, max(0, value_h))
        else:
            _, value_h = value_p.wrap(text_w, value_h)

        label_p.drawOn(self.c, self.x(col) + pad, inner_top - label_h)
        value_top = inner_top - label_h - gap
        value_p.drawOn(self.c, self.x(col) + pad, value_top - value_h)
        if note_p:
            note_p.drawOn(self.c, self.x(col) + pad, inner_bottom)

    def section_panel(self, col: int, span: int, top_mm: float, h_mm: float, title: str, items: list,
                      subtitle: str | None = None, variant: str = "default") -> None:
        colors = self.theme.c
        variant_tokens = {
            "default": ("panel_white", "ink"),
            "blue": ("panel_tint", "accent"),
            "aqua": ("panel_aqua", "accent_aqua"),
            "warm": ("panel_warm", "down"),
        }
        fill_token, title_token = variant_tokens.get(variant, variant_tokens["default"])
        self.rounded_panel(col, span, top_mm, h_mm, fill=colors.get(fill_token, colors.get("panel_white", "#FFFFFF")))
        title_color = colors.get(title_token, colors.get("ink", "#14233A"))
        title_style = ParagraphStyle(f"section_{variant}", parent=self.st.section, textColor=_hex(title_color))
        flow = [Paragraph(escape(title), title_style)]
        if subtitle:
            flow.append(Paragraph(escape(subtitle), self.st.caption))
            flow.append(Spacer(1, 3))
        flow += items
        inset = 3.2 * mm
        box_w = max(1, self.w(span) - 2 * inset)
        box_h = (h_mm - 8) * mm
        frame = Frame(self.x(col) + inset, self.y(top_mm + 4 + h_mm - 8), box_w, box_h,
                      leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0, showBoundary=0)
        frame.addFromList([KeepInFrame(box_w, box_h, flow, mode="shrink")], self.c)


# ------------------------------- cover



# ------------------------------- summary



# ------------------------------- fundamental pages





# ------------------------------- valuation



# ------------------------------- technical & risk







# ------------------------------- news





# ------------------------------- verification



def draw_unranked(doc: ProDoc,i:int,n:int)->None:
    top=doc.heading(i,n,"Chưa đủ dữ liệu để xếp hạng","Báo cáo chỉ trình bày dữ liệu hiện có","DATA QUALITY")
    qg=doc.data.m7.get('quality_gate') or {}; reasons=qg.get('reasons') or []
    human=reason_text(reasons, doc.flag_dict) if reasons else "Chưa đủ dữ liệu theo cổng chất lượng."
    doc.section_panel(0,12,top,55,"Lý do",[Paragraph(escape(human),doc.st.body_2)])


def build_pages(doc: ProDoc, cover: bool)->list[Page]:
    if not doc.data.scored:
        return ([Page('cover',draw_cover)] if cover else [])+[Page('unranked',draw_unranked)]
    pages=[]
    if cover: pages.append(Page('cover',draw_cover))
    pages += [
        Page('summary',draw_summary),
        Page('fundamental_performance',draw_fundamental_performance),
        Page('fundamental_structure',draw_fundamental_structure),
        Page('valuation',draw_valuation),
        Page('technical',draw_technical),
        Page('risk',draw_risk),
        Page('news',draw_news),
        Page('verification',draw_verification),
    ]
    return pages


def render(doc: ProDoc,path:str,*,cover:bool,keywords:str)->int:
    pages=build_pages(doc,cover); n=len(pages)
    c=rl_canvas.Canvas(path,pagesize=A4,pageCompression=1,initialFontName="StockSans",initialFontSize=9.5)
    d=doc.data
    c.setTitle(f"{d.ticker}: báo cáo phân tích cổ phiếu, dữ liệu đến {fmt_date(d.as_of)}")
    c.setAuthor("StockInsight AI"); c.setSubject("Báo cáo phân tích cơ hội đầu tư cổ phiếu"); c.setKeywords(keywords); c.setCreator("StockInsight AI")
    doc.c=c
    for i,p in enumerate(pages,1):
        doc.notes_na=[]
        if p.name != "cover":
            _draw_page_backdrop(c, doc.theme)
        p.draw(doc,i,n); c.showPage()
    c.save(); return n


# Page-specific drawing functions live in focused modules; these imports keep the public API stable.
from stockai.m9_report.pages.cover import draw_cover
from stockai.m9_report.pages.overview import (
    draw_summary, draw_fundamental_performance, draw_fundamental_structure, draw_valuation,
)
from stockai.m9_report.pages.market import draw_technical, draw_risk
from stockai.m9_report.pages.context import draw_news, draw_verification
