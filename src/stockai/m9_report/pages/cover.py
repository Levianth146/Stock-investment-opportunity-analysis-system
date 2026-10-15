from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING
from xml.sax.saxutils import escape

from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.utils import simpleSplit
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.platypus import Paragraph
from reportlab.lib.styles import ParagraphStyle

from stockai.m9_report.fmt import fmt_date
from stockai.m9_report.theme import ROOT, SANS, SANS_BOLD, SANS_SEMI

PAGE_W, PAGE_H = A4

if TYPE_CHECKING:
    from stockai.m9_report.professional_layout import ProDoc


def _palette(doc: ProDoc) -> dict[str, str]:
    defaults = {
        "navy": "#082A55", "blue": "#126BC5", "blue_light": "#4CAAE8",
        "cyan_soft": "#DDF5FB", "green": "#18A66B", "green_soft": "#E8F8F1",
        "orange": "#F59E0B", "red": "#D65A50", "text": "#102A43",
        "muted": "#61758A", "background": "#F9FCFF", "white": "#FFFFFF",
        "line": "#D9E4EE", "sky": "#E8F6FC", "sky_deep": "#B9E1F2",
        "city": "#75B7D8", "city_dark": "#3B85B5", "water": "#C7EAF4",
        "teal": "#148D88", "gold": "#F5C77A", "panel": "#F4FAFD",
    }
    return {**defaults, **(doc.rc.get("cover_palette") or {})}


def _py(top_mm: float) -> float:
    return PAGE_H - top_mm * mm


def _fill(c, color: str) -> None:
    c.setFillColor(HexColor(color))


def _stroke(c, color: str, width: float = 0.7) -> None:
    c.setStrokeColor(HexColor(color))
    c.setLineWidth(width)


def _round_box(c, x: float, top: float, width: float, height: float, radius: float,
               fill: str, stroke: str | None = None, line_width: float = 0.7) -> None:
    if stroke:
        _stroke(c, stroke, line_width)
    else:
        c.setStrokeColor(HexColor(fill))
    _fill(c, fill)
    c.roundRect(x*mm, _py(top+height), width*mm, height*mm, radius*mm, fill=1, stroke=1 if stroke else 0)


def _generic_hero_asset() -> Path | None:
    for path in (
        ROOT / "assets" / "report" / "equity_research_cover_hero.png",
        ROOT / "assets" / "branding" / "generic_equity_cover.png",
    ):
        if path.is_file():
            return path
    return None


def _draw_city_hero(c, p: dict[str, str]) -> None:
    """Ticker-neutral skyline, river waves and faint market-chart overlay."""
    c.saveState()
    _fill(c, p["sky"])
    path = c.beginPath()
    path.moveTo(102*mm, _py(40)); path.curveTo(139*mm, _py(28), 174*mm, _py(48), PAGE_W, _py(29))
    path.lineTo(PAGE_W, _py(222)); path.curveTo(174*mm, _py(213), 138*mm, _py(203), 102*mm, _py(222)); path.close()
    c.drawPath(path, fill=1, stroke=0)
    _fill(c, "#FFF4DA")
    c.circle(178*mm, _py(151), 20*mm, fill=1, stroke=0)
    skyline = [(118,159,18,52),(137,148,20,64),(159,166,15,47),
               (175,132,24,81),(194,110,16,103),(207,150,13,60)]
    for idx, (x, top, w, h) in enumerate(skyline):
        _fill(c, p["city_dark"] if idx in (1,4) else p["city"])
        c.roundRect(x*mm, _py(top+h), w*mm, h*mm, 1.1*mm, fill=1, stroke=0)
        _stroke(c, p["white"], 0.45)
        for wy in range(top+7, top+h-4, 10):
            for wx in range(x+4, x+w-2, 6):
                c.line(wx*mm, _py(wy), wx*mm, _py(wy+2.2))
    _stroke(c, p["white"], 1.4); c.line(105*mm, _py(196), PAGE_W, _py(196))
    _stroke(c, p["blue_light"], 0.8); c.line(111*mm, _py(200), PAGE_W, _py(200))
    for x in (122,145,171,198):
        c.line(x*mm, _py(196), x*mm, _py(210))
    candles = [(111,82,13),(122,77,18),(133,73,14),(144,67,20),(155,62,14),
               (166,58,22),(177,51,18),(188,47,24),(199,42,20),(208,37,21)]
    for i, (x, top, height) in enumerate(candles):
        color = p["blue_light"] if i % 3 else p["teal"]
        _stroke(c, color, 0.7); c.line((x+2)*mm, _py(top-5), (x+2)*mm, _py(top+height+5))
        _fill(c, color); c.rect(x*mm, _py(top+height), 4*mm, height*mm, fill=1, stroke=0)
    _stroke(c, p["white"], 1.25)
    line = c.beginPath(); line.moveTo(106*mm, _py(102))
    for x, y in ((124,94),(143,87),(161,82),(178,71),(195,61),(210,50)):
        line.lineTo(x*mm, _py(y))
    c.drawPath(line, fill=0, stroke=1)
    for top, color, lift in ((191,p["water"],8),(199,p["sky_deep"],7),(207,p["white"],6)):
        _fill(c, color); wave = c.beginPath(); wave.moveTo(97*mm, _py(top))
        wave.curveTo(131*mm,_py(top-lift),164*mm,_py(top+lift),PAGE_W,_py(top-2))
        wave.lineTo(PAGE_W,_py(226)); wave.lineTo(97*mm,_py(226)); wave.close()
        c.drawPath(wave, fill=1, stroke=0)
    c.restoreState()


def _draw_hero(c, p: dict[str, str]) -> None:
    hero = _generic_hero_asset()
    if hero:
        try:
            c.drawImage(str(hero), 99*mm, _py(224), 111*mm, 194*mm,
                        preserveAspectRatio=True, anchor="c", mask="auto")
            return
        except Exception:
            pass
    _draw_city_hero(c, p)


def _draw_brand(c, p: dict[str, str]) -> None:
    x, base = 11, _py(14)
    _fill(c, p["blue"])
    for i, height in enumerate((3.2,5.3,7.4,9.4)):
        c.roundRect((x+i*2.4)*mm, base, 1.5*mm, height*mm, 0.45*mm, fill=1, stroke=0)
    c.setFont(SANS_BOLD, 10.7); _fill(c, p["navy"])
    c.drawString(23*mm, _py(13.2), "STOCKINSIGHT AI")


def _fit_size(text: str, font: str, preferred: float, max_width: float, floor: float = 7) -> float:
    width = stringWidth(text, font, 1)
    return max(floor, min(preferred, max_width / max(width, 0.001)))


def _draw_header(c, doc: ProDoc, p: dict[str, str]) -> None:
    _draw_brand(c, p)
    _stroke(c, p["line"], 0.65); c.line(58*mm, _py(7.5), 58*mm, _py(16.5))
    c.setFont(SANS_SEMI, 8.2); _fill(c, p["muted"])
    c.drawString(64*mm, _py(13.2), "E Q U I T Y   R E S E A R C H")
    label = f"Ngày phát hành: {doc.export_date.strftime('%d/%m/%Y')}"
    c.setFont(SANS, _fit_size(label, SANS, 9.2, 67*mm, 7)); _fill(c, p["muted"])
    c.drawRightString(199*mm, _py(13.2), label)
    _stroke(c, p["line"], 0.7); c.line(11*mm, _py(21), 199*mm, _py(21))


def _wrap_fit(text: str, font: str, preferred: float, minimum: float,
              max_width: float, max_lines: int = 2) -> tuple[float, list[str]]:
    size = preferred
    while size > minimum:
        lines = simpleSplit(text, font, size, max_width)
        if len(lines) <= max_lines:
            return size, lines
        size = round(size-0.5, 2)
    return minimum, simpleSplit(text, font, minimum, max_width)


def _company_name(company: dict, ticker: str) -> str:
    for key in ("legal_name", "full_name", "company_full_name", "name"):
        value = company.get(key)
        if value and str(value).strip():
            return str(value).strip()
    return ticker


def _rating_color(rating: str, p: dict[str, str]) -> tuple[str, str]:
    value = rating.casefold()
    if any(term in value for term in ("mua", "buy", "tích cực")):
        return p["green"], p["green_soft"]
    if any(term in value for term in ("giảm", "bán", "sell", "reduce")):
        return p["red"], "#FCEFED"
    return p["blue"], p["cyan_soft"]


def _draw_title(c, p: dict[str, str]) -> None:
    c.setFont(SANS_BOLD, 49); _fill(c, p["navy"]); c.drawString(11*mm, _py(54), "BÁO CÁO")
    second = "PHÂN TÍCH CỔ PHIẾU"
    c.setFont(SANS_BOLD, _fit_size(second, SANS_BOLD, 36, 139*mm, 26)); _fill(c, p["blue"])
    c.drawString(11*mm, _py(73), second)
    c.setFont(SANS_SEMI, 10.5); _fill(c, p["muted"])
    c.drawString(11*mm, _py(84), "S T O C K   R E S E A R C H   R E P O R T")
    _fill(c, p["green"]); c.roundRect(11*mm, _py(92), 12*mm, 1.1*mm, 0.5*mm, fill=1, stroke=0)
    desc = "Phân tích dữ liệu doanh nghiệp, định giá, kỹ thuật, tin tức và rủi ro để hỗ trợ quá trình đánh giá cổ phiếu."
    style = ParagraphStyle("cover_description", fontName=SANS, fontSize=9.4, leading=13.3,
                           textColor=HexColor(p["muted"]), spaceAfter=0)
    para = Paragraph(escape(desc), style); para.wrapOn(c, 101*mm, 25*mm); para.drawOn(c, 11*mm, _py(119))


def _draw_calendar_icon(c, x: float, top: float, color: str, p: dict[str, str]) -> None:
    cy = _py(top+5); _fill(c, p["cyan_soft"]); c.circle(x*mm, cy, 5*mm, fill=1, stroke=0)
    _stroke(c, color, 1.0); c.roundRect((x-2.3)*mm,cy-2.5*mm,4.6*mm,4.5*mm,0.6*mm,fill=0,stroke=1)
    c.line((x-2.3)*mm,cy+1.2*mm,(x+2.3)*mm,cy+1.2*mm)
    c.line((x-1.2)*mm,cy+3*mm,(x-1.2)*mm,cy+1.2*mm); c.line((x+1.2)*mm,cy+3*mm,(x+1.2)*mm,cy+1.2*mm)


def _draw_document_icon(c, x: float, top: float, color: str, p: dict[str, str]) -> None:
    cy = _py(top+5); _fill(c, p["cyan_soft"]); c.circle(x*mm, cy, 5*mm, fill=1, stroke=0)
    _stroke(c, color, 1.0); c.roundRect((x-2.1)*mm,cy-2.7*mm,4.2*mm,5.3*mm,0.5*mm,fill=0,stroke=1)
    for dy in (-1.2,0.1,1.4):
        c.line((x-1.1)*mm,cy+dy*mm,(x+1.2)*mm,cy+dy*mm)


def _draw_company_card(doc: ProDoc, p: dict[str, str]) -> None:
    d, c = doc.data, doc.c
    x, top, width, height = 11, 132, 115, 102
    _round_box(c,x+1.2,top+1.3,width,height,5,"#EAF1F6")
    _round_box(c,x,top,width,height,5,p["white"],p["line"],0.65)
    ticker = str(d.ticker or "N/A")
    c.setFont(SANS_BOLD,_fit_size(ticker,SANS_BOLD,43,96*mm,20)); _fill(c,p["navy"])
    c.drawString((x+7)*mm,_py(154),ticker)
    company = _company_name(d.company or {},ticker)
    name_size,name_lines = _wrap_fit(company,SANS_BOLD,15.3,10.2,101*mm,2)
    c.setFont(SANS_BOLD,name_size); _fill(c,p["navy"])
    for row,line in enumerate(name_lines[:2]):
        c.drawString((x+7)*mm,_py(165.5+row*(name_size*0.39)),line)
    company_data = d.company or {}
    sector = str(company_data.get("sector") or company_data.get("industry") or "").strip()
    exchange = str(company_data.get("exchange") or "").strip()
    sector_label = f"Ngành: {sector}" if sector else ""
    if exchange:
        sector_label = f"{sector_label}   |   {exchange}" if sector_label else exchange
    sector_size,sector_lines = _wrap_fit(sector_label,SANS,9.3,7.1,101*mm,2) if sector_label else (9.3,[])
    c.setFont(SANS,sector_size); _fill(c,p["muted"])
    for row,line in enumerate(sector_lines[:2]):
        c.drawString((x+7)*mm,_py(179+row*(sector_size*0.42)),line)
    _stroke(c,p["line"],0.65); c.line((x+7)*mm,_py(186),(x+width-7)*mm,_py(186))
    rating = str(d.rating or "Không xếp hạng")
    rating_fg,rating_bg = _rating_color(rating,p)
    _round_box(c,x+5,189,width-10,20.5,3.2,rating_bg)
    _fill(c,rating_fg)
    for i,bar_h in enumerate((3.3,5,7.2)):
        c.roundRect((x+10+i*2.4)*mm,_py(204),1.5*mm,bar_h*mm,0.4*mm,fill=1,stroke=0)
    c.setFont(SANS,8.2); _fill(c,p["muted"]); c.drawString((x+20)*mm,_py(197),"Khuyến nghị:")
    c.setFont(SANS_BOLD,_fit_size(rating,SANS_BOLD,13.4,(width-31)*mm,8.3)); _fill(c,rating_fg)
    c.drawString((x+20)*mm,_py(205.3),rating)
    _draw_calendar_icon(c,x+12,213,p["blue"],p); _draw_document_icon(c,x+64,213,p["teal"],p)
    c.setFont(SANS,7.7); _fill(c,p["muted"])
    c.drawString((x+20)*mm,_py(215),"Ngày định giá:"); c.drawString((x+72)*mm,_py(215),"Ngày phát hành:")
    c.setFont(SANS_BOLD,9.2); _fill(c,p["text"])
    c.drawString((x+20)*mm,_py(223),fmt_date(d.as_of) if d.as_of else "—")
    c.drawString((x+72)*mm,_py(223),doc.export_date.strftime("%d/%m/%Y"))


def _draw_module_icon(c, cx: float, cy_top: float, kind: int, color: str, pale: str) -> None:
    cy = _py(cy_top); _fill(c,pale); c.circle(cx*mm,cy,7.2*mm,fill=1,stroke=0)
    _stroke(c,color,1.25); _fill(c,color)
    if kind == 0:
        for i,h in enumerate((4,7,10)):
            c.roundRect((cx-4+i*3)*mm,cy-4.2*mm,1.8*mm,h*mm,0.4*mm,fill=1,stroke=0)
    elif kind == 1:
        c.ellipse((cx-4)*mm,cy-4*mm,(cx+4)*mm,cy+4*mm,fill=0,stroke=1)
        c.line(cx*mm,cy,cx*mm,cy+4*mm); c.line(cx*mm,cy,(cx+3.2)*mm,cy-2*mm)
    elif kind == 2:
        c.rect((cx-4)*mm,cy-3.5*mm,8*mm,6.8*mm,fill=0,stroke=1)
        c.line((cx-2.8)*mm,cy-2*mm,(cx-0.2)*mm,cy+0.1*mm); c.line((cx-0.2)*mm,cy+0.1*mm,(cx+2.8)*mm,cy+2.2*mm)
    elif kind == 3:
        for dx,dy in ((-2.6,0),(2.6,0),(0,2.8)):
            c.circle((cx+dx)*mm,cy+dy*mm,1.7*mm,fill=1,stroke=0)
        c.arc((cx-4.7)*mm,cy-3.8*mm,(cx+4.7)*mm,cy+3.5*mm,5,170)
    else:
        c.circle(cx*mm,cy,4.1*mm,fill=0,stroke=1)
        path=c.beginPath(); path.moveTo((cx-2.1)*mm,cy); path.lineTo((cx-0.5)*mm,cy-1.8*mm); path.lineTo((cx+2.5)*mm,cy+2*mm)
        c.drawPath(path,fill=0,stroke=1)


def _draw_modules(c,p:dict[str,str])->None:
    modules=(("Phân tích","doanh nghiệp",p["blue"],p["cyan_soft"]),
             ("Định giá","cổ phiếu",p["green"],p["green_soft"]),
             ("Phân tích","kỹ thuật",p["blue_light"],"#EAF5FC"),
             ("Tin tức &","sentiment",p["teal"],"#E7F7F4"),
             ("Rủi ro","",p["orange"],"#FFF3DE"))
    left,width=10,190; cell=width/len(modules)
    for i,(line1,line2,color,pale) in enumerate(modules):
        cx=left+cell*(i+0.5); _draw_module_icon(c,cx,245,i,color,pale)
        c.setFont(SANS_SEMI,8.2); _fill(c,p["text"]); c.drawCentredString(cx*mm,_py(257),line1)
        if line2: c.drawCentredString(cx*mm,_py(262),line2)
        _fill(c,color); c.roundRect((cx-3.4)*mm,_py(268),6.8*mm,0.8*mm,0.4*mm,fill=1,stroke=0)
        if i<len(modules)-1:
            _stroke(c,p["line"],0.6); x=left+cell*(i+1); c.line(x*mm,_py(240),x*mm,_py(266))


def _draw_footer(c,p:dict[str,str])->None:
    _stroke(c,p["line"],0.7); c.line(11*mm,_py(276),199*mm,_py(276))
    c.setFont(SANS_BOLD,8.8); _fill(c,p["navy"]); c.drawString(12*mm,_py(283),"Bộ phận phân tích StockInsight AI")
    disclaimer="Báo cáo phục vụ mục đích học thuật và minh họa hệ thống; không phải khuyến nghị đầu tư."
    style=ParagraphStyle("cover_disclaimer",fontName=SANS,fontSize=7.3,leading=9.4,
                         textColor=HexColor(p["muted"]),alignment=0,spaceAfter=0)
    para=Paragraph(escape(disclaimer),style); para.wrapOn(c,119*mm,14*mm); para.drawOn(c,79*mm,_py(289))


def draw_cover(doc: ProDoc, i: int, n: int) -> None:
    """Draw the fixed, ticker-neutral equity-research cover as page one of M9."""
    c,p=doc.c,_palette(doc)
    _fill(c,p["background"]); c.rect(0,0,PAGE_W,PAGE_H,fill=1,stroke=0)
    _draw_hero(c,p); _draw_header(c,doc,p); _draw_title(c,p)
    _draw_company_card(doc,p); _draw_modules(c,p); _draw_footer(c,p)
