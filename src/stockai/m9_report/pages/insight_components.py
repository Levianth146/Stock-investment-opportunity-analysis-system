"""Bounded ReportLab components used only by investment snapshot and fundamental pages."""
from __future__ import annotations
from dataclasses import dataclass
from xml.sax.saxutils import escape
from reportlab.lib.colors import HexColor
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader
from reportlab.platypus import Paragraph
from stockai.m9_report.fmt import to_float
from stockai.m9_report.layout import sanitize
from stockai.m9_report.theme import SANS, SANS_BOLD

COLUMN_GAP = 3.5
CARD_GAP = 2.0
CARD_PADDING = 3.0
SECTION_GAP = 4.0
RADIUS = 3.2
PAGE_BOTTOM = 289.0


@dataclass(frozen=True)
class Box:
    x: float
    y: float
    w: float
    h: float

    def inset(self, pad: float = CARD_PADDING) -> "Box":
        return Box(self.x+pad, self.y+pad, self.w-2*pad, self.h-2*pad)

    def columns(self, count: int, gap: float = COLUMN_GAP) -> list["Box"]:
        width = (self.w-gap*(count-1))/count
        return [Box(self.x+i*(width+gap), self.y, width, self.h) for i in range(count)]


def status_label(module: dict) -> str:
    return str(module.get("status") or "unavailable").replace("_", " ").upper()


def status_kind(label: str) -> str:
    value = label.casefold()
    if any(s in value for s in ("warn", "partial", "limited")):
        return "caution"
    if any(s in value for s in ("fail", "error")):
        return "danger"
    return "support" if value in ("ok", "pass") else "muted"


class PageCanvas:
    def __init__(self, doc, page: int):
        self.doc, self.c, self.page = doc, doc.c, page
        self.x, self.width = doc.x(0)/mm, doc.w(12)/mm
        self.colors = {
            "ink": doc.theme.c["ink"], "muted": doc.theme.c["ink_3"],
            "line": doc.theme.c.get("panel_border", "#D7EAF6"),
            "white": "#FFFFFF", "blue": doc.theme.c["series_1"],
            "support": "#087D59", "danger": "#C72E3A", "caution": "#B36B08",
            "purple": "#7650B6", "teal": "#087D72",
        }
        self.fills = {
            "white": "#FFFFFF", "blue": "#F2F9FF", "support": "#EFFAF6",
            "danger": "#FFF3F4", "caution": "#FFF8ED", "purple": "#F7F3FF",
            "muted": "#F1F4F7", "teal": "#EFFAF8",
        }
        if not hasattr(doc, "_insight_regions"):
            doc._insight_regions = []

    def color(self, token: str):
        return HexColor(self.colors.get(token, token))

    def panel(self, box: Box, title: str = "", *, variant: str = "white",
              subtitle: str = "", title_size: float = 10.2, name: str = "") -> Box:
        c = self.c
        c.setFillColor(HexColor(self.fills.get(variant, variant)))
        c.setStrokeColor(self.color("line")); c.setLineWidth(0.65)
        c.roundRect(box.x*mm, self.doc.y(box.y+box.h), box.w*mm, box.h*mm,
                    RADIUS*mm, fill=1, stroke=1)
        self.doc._insight_regions.append({
            "page": self.page, "name": name or title, "kind": "panel",
            "box": (box.x, box.y, box.w, box.h),
        })
        if title:
            self.text(title, Box(box.x+CARD_PADDING, box.y+2.7, box.w-2*CARD_PADDING, 5.5),
                      size=title_size, minimum=8, bold=True,
                      color=variant if variant in self.colors and variant not in ("white", "muted") else "ink",
                      name=(name or title)+".title")
        offset = 10.0 if title else CARD_PADDING
        if subtitle:
            self.text(subtitle, Box(box.x+CARD_PADDING, box.y+8.6, box.w-2*CARD_PADDING, 5.5),
                      size=7.3, minimum=6.8, color="muted", max_lines=2,
                      name=(name or title)+".subtitle")
            offset = 15.7
        return Box(box.x+CARD_PADDING, box.y+offset, box.w-2*CARD_PADDING,
                   box.h-offset-CARD_PADDING)

    def text(self, value, box: Box, *, size: float = 8.5, minimum: float = 7.2,
             color: str = "ink", bold: bool = False, max_lines: int = 1,
             align: str = "left", name: str = "") -> float:
        """Wrap, then shrink, then ellipsize within a measured explicit box."""
        text = sanitize(str(value if value is not None else "N/A"))
        minimum = min(minimum, box.h*mm/1.5)
        font = SANS_BOLD if bold else SANS
        alignment = {"left": 0, "center": 1, "right": 2}[align]

        def candidate(content, font_size):
            style = ParagraphStyle(
                "insight_text", fontName=font, fontSize=font_size, leading=font_size*1.42,
                textColor=self.color(color), alignment=alignment,
                splitLongWords=True, spaceBefore=0, spaceAfter=0,
            )
            paragraph = Paragraph(escape(content), style)
            _, height = paragraph.wrap(max(1, box.w*mm), max(1, box.h*mm))
            drawn_height = height+font_size*0.08
            fits = drawn_height <= box.h*mm+0.01 and height <= max_lines*style.leading+0.01
            return paragraph, drawn_height, fits

        sizes, current = [], size
        while current > minimum:
            sizes.append(current); current -= 0.4
        sizes.append(minimum)
        for font_size in sizes:
            paragraph, height, fits = candidate(text, font_size)
            if fits:
                break
        if not fits:
            lo, hi = 0, len(text)
            while lo < hi:
                mid = (lo+hi+1)//2
                if candidate(text[:mid].rstrip()+"...", minimum)[2]:
                    lo = mid
                else:
                    hi = mid-1
            text = text[:lo].rstrip()+"..."
            paragraph, height, _ = candidate(text, minimum)
            font_size = minimum
        paragraph.drawOn(self.c, box.x*mm, self.doc.y(box.y)-height)
        self.doc._insight_regions.append({
            "page": self.page, "name": name, "kind": "text", "text": text,
            "box": (box.x, box.y, box.w, box.h), "height": height/mm, "size": font_size,
        })
        return height/mm

    def bullets(self, items: list[str], box: Box, *, size: float = 8.1,
                minimum: float = 7.3, max_items: int = 3, color: str = "ink", name: str = ""):
        selected = items[:max_items]
        if not selected:
            return

        def heights(font_size, texts):
            style = ParagraphStyle("insight_measure", fontName=SANS,
                                   fontSize=font_size, leading=font_size*1.42)
            return [(Paragraph(escape(sanitize(t)), style).wrap((box.w-3)*mm, 999)[1]+font_size*0.08)/mm for t in texts]

        font_size = size
        while font_size > minimum and sum(heights(font_size, selected))+0.9*(len(selected)-1) > box.h:
            font_size = max(minimum, font_size-0.4)
        while len(selected) > 1 and sum(heights(font_size, selected))+0.9*(len(selected)-1) > box.h:
            selected.pop()
        used = 0.0
        for index, (item, height) in enumerate(zip(selected, heights(font_size, selected))):
            height = min(height+0.1, box.h-used)
            self.c.setFillColor(self.color(color))
            self.c.circle((box.x+0.8)*mm, self.doc.y(box.y+used+1.6), 0.5*mm, fill=1, stroke=0)
            self.text(item, Box(box.x+3, box.y+used, box.w-3, height),
                      size=font_size, minimum=minimum, max_lines=20, color=color,
                      name=f"{name}.{index}")
            used += height+0.9

    def kpi(self, box: Box, label: str, value: str, note: str = "",
            *, accent: str = "blue", name: str = ""):
        self.panel(box, variant="white", name=name)
        self.c.setStrokeColor(self.color(accent)); self.c.setLineWidth(2.7)
        self.c.setLineCap(1)
        self.c.line((box.x+3.5)*mm, self.doc.y(box.y+3.4),
                    (box.x+9.4)*mm, self.doc.y(box.y+3.4))
        self.c.setLineCap(0)
        width = box.w-7
        self.text(label.upper(), Box(box.x+3.5, box.y+5.2, width, 7.0),
                  size=7.1, minimum=6.6, max_lines=2, color="muted", name=name+".label")
        self.text(value, Box(box.x+3.5, box.y+12.5, width, 7.0),
                  size=15, minimum=9, bold=True, name=name+".value")
        if note:
            self.text(note, Box(box.x+3.5, box.y+20.4, width, 3.9),
                      size=6.9, minimum=6.3, color="muted", name=name+".note")

    def rows(self, box: Box, rows: list[tuple[str, str]], *, size: float = 8,
             value_fraction: float = 0.37, name: str = "", header: bool = False):
        if not rows:
            self.text("Chưa có số liệu M2 phù hợp.", box, max_lines=3, color="muted")
            return
        height = box.h/len(rows)
        for index, (label, value) in enumerate(rows):
            y = box.y+index*height
            if header and index == 0:
                self.c.setFillColor(HexColor("#EAF1F7"))
                self.c.rect(box.x*mm, self.doc.y(y+height), box.w*mm, height*mm, fill=1, stroke=0)
            self.text(label, Box(box.x+1, y+0.6, box.w*(1-value_fraction)-2, height-0.7),
                      size=size, minimum=6.6, max_lines=2, bold=header and index == 0,
                      name=f"{name}.{index}.label")
            self.text(value, Box(box.x+box.w*(1-value_fraction), y+0.6,
                                 box.w*value_fraction-1, height-0.7),
                      size=size, minimum=6.5, max_lines=2, bold=True, align="right",
                      name=f"{name}.{index}.value")
            self.c.setStrokeColor(self.color("line")); self.c.setLineWidth(0.35)
            self.c.line(box.x*mm, self.doc.y(y+height), (box.x+box.w)*mm, self.doc.y(y+height))

    def bar(self, box: Box, score, color: str = "blue"):
        self.c.setFillColor(HexColor("#E9EFF4"))
        self.c.roundRect(box.x*mm, self.doc.y(box.y+box.h), box.w*mm, box.h*mm,
                         box.h*mm/2, fill=1, stroke=0)
        value = to_float(score)
        if value is not None and value > 0:
            self.c.setFillColor(self.color(color))
            self.c.roundRect(box.x*mm, self.doc.y(box.y+box.h),
                             box.w*min(100, max(0, value))/100*mm, box.h*mm,
                             min(box.h, box.w*value/100)*mm/2, fill=1, stroke=0)

    def image(self, buf, box: Box):
        self.c.drawImage(ImageReader(buf), box.x*mm, self.doc.y(box.y+box.h),
                         box.w*mm, box.h*mm)

    def heading(self, i: int, n: int, title: str, subtitle: str, kicker: str):
        self.text("STOCKINSIGHT AI", Box(self.x, 6.9, 50, 4), size=8.2,
                  bold=True, color="blue", name="header.brand")
        name = self.doc.data.company.get("name") or self.doc.data.ticker
        self.text(f"{self.doc.data.ticker} | {name} | Trang {i}/{n}",
                  Box(self.x+51, 6.9, self.width-51, 4), size=8, minimum=6.6,
                  align="right", name="header.context")
        self.c.setStrokeColor(self.color("line")); self.c.setLineWidth(0.6)
        self.c.line(self.x*mm, self.doc.y(13.4), (self.x+self.width)*mm, self.doc.y(13.4))
        self.text(kicker, Box(self.x, 17, self.width, 5), size=7.5, color="muted")
        self.text(title, Box(self.x, 23.2, self.width, 12.0), size=23, minimum=18, bold=True)
        self.text(subtitle, Box(self.x, 37.1, self.width, 8.7),
                  size=10, minimum=8.4, max_lines=2, color="muted")
