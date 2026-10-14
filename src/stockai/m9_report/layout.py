"""Dàn trang PDF A4 cho M9 bằng reportlab canvas + flowable.

Lưới 12 cột, lề 18 mm, cách cột 6 mm. Không khung thẻ, không đổ bóng; ngăn cách bằng khoảng trắng
và đường kẻ mảnh. Mỗi vùng vẽ qua KeepInFrame(shrink) nên số trang cố định, "Trang x/y" chính xác.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Callable, Sequence
from xml.sax.saxutils import escape

from reportlab.lib.colors import HexColor
from reportlab.lib.enums import TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader, simpleSplit
from reportlab.pdfgen import canvas as rl_canvas
from reportlab.platypus import Frame, KeepInFrame, Paragraph, Spacer, Table, TableStyle

from stockai.m9_report import charts
from stockai.m9_report.data import ReportData, metric, metric_note
from stockai.m9_report.fmt import (
    NA,
    arrow_word,
    fmt_bn_vnd,
    fmt_date,
    fmt_multiple,
    fmt_num,
    fmt_pct_points,
    fmt_pct_ratio,
    fmt_score,
    fmt_signed,
    to_float,
)
from stockai.m9_report.news_cluster import (
    format_news_label,
    news_extra_phrase,
    news_meta_bits,
    select_news_panel,
)
from stockai.m9_report.sector_band import resolve_sector_band
from stockai.m9_report.text import (
    PILLAR_NAMES,
    conclusion_title,
    fundamental_title,
    human_sources,
    listing_sentence,
    news_title,
    point_text,
    reason_text,
    sanitize,
    scoring_method_plain,
    select_data_notes,
    technical_title,
    translate_flags,
    translate_terms,
)
from stockai.m9_report.theme import SANS, SANS_BOLD, SANS_SEMI, SERIF_SEMI, SYMBOLS, Theme

PAGE_W, PAGE_H = A4
PAGE_W_MM = PAGE_W / mm
PAGE_H_MM = PAGE_H / mm

FOOTER_TAIL = "Báo cáo tự động, không phải khuyến nghị đầu tư"


# --------------------------------------------------------------------------- tiện ích


def _hex(c: str) -> HexColor:
    return HexColor(c)


@dataclass
class Styles:
    title: ParagraphStyle
    section: ParagraphStyle
    body: ParagraphStyle
    body_2: ParagraphStyle
    table: ParagraphStyle
    table_r: ParagraphStyle
    table_h: ParagraphStyle
    table_hr: ParagraphStyle
    caption: ParagraphStyle
    bullet: ParagraphStyle


def make_styles(theme: Theme) -> Styles:
    c = theme.c
    t_sz, t_ld = theme.size("page_title")
    s_sz, s_ld = theme.size("section")
    b_sz, b_ld = theme.size("body")
    tb_sz, tb_ld = theme.size("table")
    c_sz, c_ld = theme.size("caption")
    base = dict(textColor=_hex(c["ink"]), alignment=TA_LEFT)
    return Styles(
        title=ParagraphStyle("title", fontName=SERIF_SEMI, fontSize=t_sz, leading=t_ld, **base),
        section=ParagraphStyle("section", fontName=SANS_SEMI, fontSize=s_sz, leading=s_ld, spaceAfter=3, **base),
        body=ParagraphStyle("body", fontName=SANS, fontSize=b_sz, leading=b_ld, **base),
        body_2=ParagraphStyle("body_2", fontName=SANS, fontSize=b_sz, leading=b_ld, textColor=_hex(c["ink_2"])),
        table=ParagraphStyle("table", fontName=SANS, fontSize=tb_sz, leading=tb_ld, **base),
        table_r=ParagraphStyle("table_r", fontName=SANS, fontSize=tb_sz, leading=tb_ld, textColor=_hex(c["ink"]),
                               alignment=TA_RIGHT),
        table_h=ParagraphStyle("table_h", fontName=SANS_SEMI, fontSize=tb_sz, leading=tb_ld,
                               textColor=_hex(c["ink_2"])),
        table_hr=ParagraphStyle("table_hr", fontName=SANS_SEMI, fontSize=tb_sz, leading=tb_ld,
                                textColor=_hex(c["ink_2"]), alignment=TA_RIGHT),
        caption=ParagraphStyle("caption", fontName=SANS, fontSize=c_sz, leading=c_ld, textColor=_hex(c["ink_3"])),
        bullet=ParagraphStyle("bullet", fontName=SANS, fontSize=b_sz, leading=b_ld, textColor=_hex(c["ink"]),
                              leftIndent=9, bulletIndent=0, spaceAfter=2, bulletFontName=SANS),
    )


def esc(s: Any) -> str:
    return escape(sanitize(str(s)))


def sym(ch: str) -> str:
    return f'<font name="{SYMBOLS}">{ch}</font>'


def change_markup(theme: Theme, value: float | None, text: str) -> str:
    """Giá trị tăng/giảm: màu theo quy ước VN, luôn kèm ▲ ▼ và dấu số."""
    v = to_float(value)
    if v is None:
        return NA
    a = arrow_word(v)
    if not a:
        return escape(text)
    color = theme.c["up"] if v > 0 else theme.c["down"]
    return f'<font color="{color}">{sym(a)} {escape(text)}</font>'


def rating_color(theme: Theme, rating: str) -> str:
    if rating in ("Mua", "Mua mạnh"):
        return theme.c["rating_buy"]
    if rating in ("Giảm tỷ trọng", "Bán"):
        return theme.c["rating_sell"]
    return theme.c["rating_hold"]


@dataclass
class Page:
    kind: str
    draw: Callable[["Doc", int, int], None]
    toc_title: str | None = None


@dataclass
class Doc:
    theme: Theme
    st: Styles
    data: ReportData
    rc: dict
    flag_dict: dict
    scoring_cfg: dict
    export_date: date
    c: rl_canvas.Canvas | None = None
    notes_na: list[str] = field(default_factory=list)
    technical_appendix: bool = False

    # ------------------------------------------------------------- vẽ cơ bản
    def x(self, col: int) -> float:
        return self.theme.col_x_mm(col) * mm

    def w(self, span: int) -> float:
        return self.theme.span_mm(span) * mm

    def y(self, top_mm: float) -> float:
        return PAGE_H - top_mm * mm

    def flow(self, col: int, span: int, top_mm: float, h_mm: float, items: list) -> None:
        """Vẽ danh sách flowable trong khung; tràn thì co lại để giữ bố cục cố định."""
        items = [i for i in items if i is not None]
        if not items:
            return
        f = Frame(self.x(col), self.y(top_mm + h_mm), self.w(span), h_mm * mm, leftPadding=0, rightPadding=0,
                  topPadding=0, bottomPadding=0, showBoundary=0)
        f.addFromList([KeepInFrame(self.w(span), h_mm * mm, items, mode="shrink")], self.c)

    def image(self, buf, col: int, span: int, top_mm: float, h_mm: float) -> None:
        self.c.drawImage(ImageReader(buf), self.x(col), self.y(top_mm + h_mm), self.w(span), h_mm * mm,
                         mask=None)

    def hrule(self, top_mm: float, col: int = 0, span: int = 12, color: str | None = None,
              width: float | None = None) -> None:
        c = self.c
        c.setStrokeColor(_hex(color or self.theme.c["rule"]))
        c.setLineWidth(width or float(self.theme.cfg["layout"]["rule_pt"]))
        c.line(self.x(col), self.y(top_mm), self.x(col) + self.w(span), self.y(top_mm))

    def text(self, s: str, x_pt: float, top_mm: float, font: str, size: float, color: str) -> float:
        c = self.c
        c.setFillColor(_hex(color))
        c.setFont(font, size)
        c.drawString(x_pt, self.y(top_mm), sanitize(s))
        from reportlab.pdfbase.pdfmetrics import stringWidth

        return stringWidth(sanitize(s), font, size)

    def rating_mark(self, x_pt: float, base_mm: float, rating: str, size: float) -> float:
        """Ô vuông 3 mm tô màu + chữ khuyến nghị đậm màu mực; trả bề rộng đã vẽ (pt)."""
        c = self.c
        sq = 3 * mm
        c.setFillColor(_hex(rating_color(self.theme, rating)))
        c.setStrokeColor(_hex(rating_color(self.theme, rating)))
        c.rect(x_pt, self.y(base_mm) + size * 0.02, sq, sq, stroke=0, fill=1)
        w = self.text(rating, x_pt + sq + 2.2 * mm, base_mm, SANS_BOLD, size, self.theme.c["ink"])
        return sq + 2.2 * mm + w

    # ------------------------------------------------------------- khối dùng chung
    def p(self, s: str, style: ParagraphStyle | None = None) -> Paragraph:
        return Paragraph(s, style or self.st.body)

    def section(self, s: str) -> Paragraph:
        return Paragraph(esc(s), self.st.section)

    def caption(self, s: str) -> Paragraph:
        return Paragraph(esc(s), self.st.caption)

    def table(self, header: Sequence[str], rows: Sequence[Sequence[str]], widths_mm: Sequence[float],
              right_cols: Sequence[int] = ()) -> Table:
        """Bảng chỉ kẻ ngang mảnh; tiêu đề cột chữ thường nửa đậm mực phụ; số căn phải."""
        st = self.st
        data = []
        hdr = [Paragraph(esc(h), st.table_hr if i in right_cols else st.table_h) for i, h in enumerate(header)]
        data.append(hdr)
        for r in rows:
            data.append([Paragraph(cell, st.table_r if i in right_cols else st.table) for i, cell in enumerate(r)])
        t = Table(data, colWidths=[w * mm for w in widths_mm])
        rule = _hex(self.theme.c["rule"])
        lw = float(self.theme.cfg["layout"]["rule_pt"])
        t.setStyle(TableStyle([
            ("FONT", (0, 0), (-1, -1), SANS, self.theme.size("table")[0]),
            ("LINEBELOW", (0, 0), (-1, 0), lw, _hex(self.theme.c["axis"])),
            ("LINEBELOW", (0, 1), (-1, -1), lw, rule),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (-1, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 2.2),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2.6),
        ]))
        return t

    def bullets(self, items: Sequence[str], style: ParagraphStyle | None = None) -> list[Paragraph]:
        stl = style or self.st.bullet
        return [Paragraph(s, stl, bulletText="\u2022") for s in items]

    # ------------------------------------------------------------- khung trang
    def header(self) -> None:
        d = self.data
        prof = (self.rc.get("profiles") or {}).get(d.profile, d.profile)
        x0 = self.x(0)
        w = self.text("StockAI", x0, 11.5, SANS_SEMI, 8.5, self.theme.c["ink"])
        name = d.company.get("name") or d.ticker
        self.text(f"Báo cáo phân tích {d.ticker}, {name}, khẩu vị {prof}", x0 + w + 3 * mm, 11.5, SANS, 8.5,
                  self.theme.c["ink_3"])
        self.hrule(13.8)

    def footer(self, i: int, n: int) -> None:
        self.hrule(PAGE_H_MM - 13.5)
        s = f"Trang {i}/{n} | Dữ liệu đến {fmt_date(self.data.as_of)} | {FOOTER_TAIL}"
        self.text(s, self.x(0), PAGE_H_MM - 9.8, SANS, 7.5, self.theme.c["ink_3"])

    def page_title(self, s: str, top_mm: float = 19.0) -> float:
        """Vạch nhấn ngắn + câu kết luận serif; trả vị trí đáy (mm)."""
        c = self.c
        c.setStrokeColor(_hex(self.theme.c["accent"]))
        c.setLineWidth(1.4)
        c.line(self.x(0), self.y(top_mm), self.x(0) + self.theme.col_mm() * mm, self.y(top_mm))
        sz, ld = self.theme.size("page_title")
        lines = simpleSplit(sanitize(s), SERIF_SEMI, sz, self.w(12))[:2]
        h_mm = (len(lines) * ld) / mm + 1
        self.flow(0, 12, top_mm + 2.5, h_mm + 1, [Paragraph(esc(s), self.st.title)])
        return top_mm + 2.5 + h_mm

    def title_fits(self, s: str) -> bool:
        sz, _ = self.theme.size("page_title")
        return len(simpleSplit(sanitize(s), SERIF_SEMI, sz, self.w(12))) <= 2

    # ------------------------------------------------------------- n/a có lý do
    def na(self, label: str, reason: str) -> str:
        note = f"{label}: {reason}"
        if note not in self.notes_na:
            self.notes_na.append(note)
        return NA

    def take_na_caption(self) -> Paragraph | None:
        if not self.notes_na:
            return None
        s = "n/a: " + "; ".join(self.notes_na) + "."
        self.notes_na = []
        return self.caption(s)


# --------------------------------------------------------------------------- lý do thiếu dữ liệu


def module_down(mod: dict) -> bool:
    return not mod or mod.get("status") in ("error", "missing", "stub")


def reason_for(doc: Doc, mod_key: str, metric_key: str) -> str:
    d = doc.data
    mod = d.m.get(mod_key) or {}
    flags = set(mod.get("flags") or [])
    table = doc.flag_dict.get("flags") or {}
    specific = {
        ("m4", "pe"): ["m4_pe_not_meaningful", "m4_pe_unavailable"],
        ("m4", "pb"): ["m4_missing_equity", "m4_pb_unavailable"],
        ("m4", "target"): ["m4_insufficient_for_score", "m4_no_valid_price"],
        ("m2", "npl_ratio"): ["m2_missing_npl_ratio"],
        ("m2", "car"): ["m2_missing_car"],
        ("m2", "interest_coverage"): ["m2_missing_interest_coverage"],
        ("m2", "gross_margin"): ["m2_missing_gross_margin"],
        ("m2", "current_ratio"): ["m2_missing_current_ratio"],
        ("m2", "debt_to_equity"): ["m2_missing_debt_to_equity"],
        ("m3", "ma200"): ["m3_insufficient_history_ma200"],
        ("m3", "volume_ratio_20"): ["m3_volume_ratio_unavailable"],
    }.get((mod_key, metric_key), [])
    for f in specific:
        if f in flags and table.get(f):
            return str(table[f]).rstrip(".").lower()[:1] + str(table[f]).rstrip(".")[1:]
    if module_down(mod):
        return f"module {mod_key.upper()} lỗi hoặc thiếu dữ liệu"
    if mod_key == "m4" and metric_key in ("pe", "pb") and to_float(metric(mod, "v_pe_leg" if metric_key == "pe" else "v_pb_leg")) is None:
        return "M4 không tính chỉ số này cho mã"
    return "nguồn chưa cung cấp"


def mval(doc: Doc, mod_key: str, key: str, fmt: Callable[[float], str], label: str) -> str:
    v = metric(doc.data.m.get(mod_key), key)
    if v is None:
        return doc.na(label, reason_for(doc, mod_key, key))
    return escape(fmt(v))


# --------------------------------------------------------------------------- các trang


def ruler_buf(doc: Doc, w_span: int, h_mm: float):
    d = doc.data
    rul = charts.ruler_from_scoring(doc.scoring_cfg)
    prof = doc.rc.get("profiles") or {}
    main = f"{fmt_score(d.score)} điểm"
    if d.rank:
        main += f", hạng {d.rank} trên {d.total} mã"
    other_label = None
    if d.other_profile and d.other_score is not None:
        other_label = f"Khẩu vị {prof.get(d.other_profile, d.other_profile)}: {fmt_score(d.other_score)} điểm"
        if d.other_rank:
            other_label += f", hạng {d.other_rank} trên {d.other_total}"
    return charts.score_ruler(
        doc.theme, doc.theme.span_mm(w_span), h_mm, ruler=rul, score=d.score, main_label=main,
        universe=[s for _, s in d.universe], other_score=d.other_score, other_label=other_label,
    )


def risk_gate_note(doc: Doc) -> str | None:
    d = doc.data
    if "rating_capped_by_risk_gate" not in (d.m7.get("flags") or []):
        return None
    gate = doc.scoring_cfg.get("risk_gate") or {}
    r = to_float((d.m7.get("scores") or {}).get("R"))
    return (f"Điểm rủi ro {fmt_score(r)} từ ngưỡng {fmt_num(gate.get('R_threshold'))} trở lên, "
            f"khuyến nghị bị giới hạn ở mức {gate.get('max_rating', 'Nắm giữ')}.")


def draw_cover(doc: Doc, i: int, n: int) -> None:
    d, th = doc.data, doc.theme
    c = th.c
    x0 = doc.x(0)
    doc.text("StockAI", x0, 24, SANS_SEMI, 11, c["ink"])
    doc.text("Báo cáo phân tích cơ hội đầu tư cổ phiếu", x0, 29.5, SANS, 9.5, c["ink_2"])

    t_sz, _ = th.size("cover_ticker")
    w_tk = doc.text(d.ticker, x0, 112, SANS_BOLD, t_sz, c["ink"])
    if len(d.closes) >= 2:
        spark_w = 62.0
        x_spark = x0 + w_tk + 10 * mm
        buf = charts.sparkline(th, spark_w, 17, close=d.closes)
        c_ = doc.c
        c_.drawImage(ImageReader(buf), x_spark, doc.y(110), spark_w * mm, 17 * mm)
        doc.text(f"Giá đóng cửa 1 năm, đồng/cổ phiếu. Phiên cuối {fmt_num(d.closes[-1])}", x_spark, 114, SANS,
                 7.5, c["ink_3"])
    co_sz, _ = th.size("cover_company")
    doc.text(d.company.get("name") or d.ticker, x0, 126, SERIF_SEMI, co_sz, c["ink"])
    doc.text(listing_sentence(d.company.get("exchange"), d.company.get("sector"), doc.rc), x0, 134, SANS, 9.5,
             c["ink_2"])
    if d.synthetic:
        doc.text("Dữ liệu giả lập dùng để kiểm thử, không dùng cho báo cáo thật.", x0, 141, SANS_SEMI, 9.5,
                 c["down"])

    prof = (doc.rc.get("profiles") or {}).get(d.profile, d.profile)
    if d.scored:
        w = doc.rating_mark(x0, 204, d.rating, 20)
        doc.text(f"{fmt_score(d.score)} điểm", x0 + w + 6 * mm, 204, SANS, 20, c["ink"])
        doc.image(ruler_buf(doc, 12, 34), 0, 12, 209, 34)
        line = f"Khẩu vị đầu tư {prof}."
        if d.rank:
            line += f" Hạng {d.rank} trên {d.total} mã được xếp hạng cùng khẩu vị."
        doc.text(line, x0, 250, SANS, 9.5, c["ink_2"])
        note = risk_gate_note(doc)
        if note:
            doc.text(note, x0, 255.5, SANS, 7.5, c["ink_3"])
    else:
        qg = d.m7.get("quality_gate") or {}
        doc.text("Chưa đủ dữ liệu để xếp hạng", x0, 210, SANS_BOLD, 20, c["ink"])
        doc.text(f"Lý do: {reason_text(qg.get('reasons') or [], doc.flag_dict)}.", x0, 218, SANS, 9.5, c["ink_2"])
        doc.text(f"Khẩu vị đầu tư {prof}. Báo cáo không có điểm và khuyến nghị.", x0, 224, SANS, 9.5, c["ink_2"])

    doc.text(f"Xuất ngày {doc.export_date.strftime('%d/%m/%Y')}. Điểm số mang tính minh họa, chưa hiệu chỉnh "
             "và kiểm định.", x0, PAGE_H_MM - 17.5, SANS, 7.5, c["ink_3"])
    doc.footer(i, n)


def key_rows(doc: Doc) -> list[list[str]]:
    """Bảng số liệu chính: gộp cận dưới/trên vào dòng giá tham chiếu; bỏ KL TB20 để giữ cỡ chữ ≥8pt."""
    d, th = doc.data, doc.theme
    close = metric(d.m.get("m3"), "close") or metric(d.m.get("m4"), "price_close")
    tgt = d.target or {}
    base = to_float(tgt.get("base"))
    bank = bool(d.company.get("is_bank"))
    rows: list[list[str]] = []
    rows.append(["Giá đóng cửa, đồng", fmt_num(close) if close else doc.na("Giá", "thiếu dữ liệu giá")])
    if base is not None:
        bear_s, bull_s = fmt_num(tgt.get("bear")), fmt_num(tgt.get("bull"))
        rows.append([
            "Giá tham chiếu theo bội số ngành, đồng",
            f"{fmt_num(base)} (cận {bear_s}–{bull_s})",
        ])
        if close:
            up = base / close - 1
            rows.append(["So với giá hiện tại", change_markup(th, up, fmt_pct_ratio(up, signed=True))])
    else:
        rows.append(["Giá tham chiếu theo bội số ngành, đồng",
                     doc.na("Giá tham chiếu", reason_for(doc, "m4", "target"))])
    pe_lab = "P/E (tham khảo, ngân hàng định giá theo P/B), lần" if bank else "P/E, lần"
    rows.append([pe_lab, mval(doc, "m4", "pe", lambda v: fmt_num(v, 2), "P/E")])
    rows.append(["P/B, lần", mval(doc, "m4", "pb", lambda v: fmt_num(v, 2), "P/B")])
    rows.append(["ROE", mval(doc, "m2", "roe", fmt_pct_ratio, "ROE")])
    rows.append(["Beta so với VN-Index", mval(doc, "m6", "beta", lambda v: fmt_num(v, 2), "Beta")])
    shares = to_float(d.company.get("shares_outstanding"))
    if shares and close:
        rows.append(["Vốn hóa, tỷ đồng", fmt_bn_vnd(shares * close)])
    else:
        rows.append(["Vốn hóa, tỷ đồng", doc.na("Vốn hóa", "thiếu số cổ phiếu lưu hành")])
    if len(d.closes) >= 2:
        ch = d.closes[-1] / d.closes[0] - 1
        rows.append([f"Thay đổi giá {len(d.closes)} phiên", change_markup(th, ch, fmt_pct_ratio(ch, signed=True))])
    return [[escape(r[0]), r[1]] for r in rows]


def contributions_rows(d: ReportData) -> list[tuple[str, float | None]]:
    contrib = d.m7.get("contributions") or {}
    return [(PILLAR_NAMES[k], to_float(contrib.get(k))) for k in ("F", "T", "V", "S", "R")]


def debate_caption(d: ReportData) -> str | None:
    """Chỉ ghi chú ngắn khi luận điểm do mô hình ngôn ngữ soạn; template thì im lặng."""
    if d.debate_source == "CACHE":
        return "Luận điểm do mô hình ngôn ngữ soạn, đã đối chiếu số liệu."
    return None


def m8_block(doc: Doc, col: int, span: int, top_mm: float, h_mm: float) -> None:
    """Khung kiểm tra dữ liệu: co theo nội dung; câu kết quả + tối đa 3 ghi chú."""
    d = doc.data
    c = doc.c
    status = {"pass": "Đạt", "warn": "Có cảnh báo", "fail": "Không đạt"}.get(str(d.m8.get("status")), NA)
    issues = [i for i in d.m8.get("issues") or [] if isinstance(i, dict)]
    n_warn = sum(1 for i in issues if i.get("severity") in ("warn", "fail", "error"))
    checked = d.m8.get("checked")
    if checked is not None and n_warn == 0:
        head = f"Đạt: {fmt_num(checked)} phép kiểm tra, không có cảnh báo"
    elif checked is not None:
        head = f"{status}: {fmt_num(checked)} phép kiểm tra, {fmt_num(n_warn)} cảnh báo"
    else:
        head = "Chưa có kết quả kiểm tra dữ liệu."
    repl = doc.flag_dict.get("m8_messages") or {}
    notes: list[str] = []
    for it in issues:
        if len(notes) >= 3:
            break
        sev = str(it.get("severity") or "info")
        msg = str(it.get("message") or "")
        for k, v in repl.items():
            msg = msg.replace(k, v)
        # Diễn đạt tiếng người đọc; bỏ khóa kỹ thuật / peers / as_of
        msg = re.sub(r"\b[Pp]eers?\b", "Nhóm so sánh", msg)
        msg = re.sub(r"\bas_of\b", "ngày dữ liệu", msg, flags=re.I)
        msg = re.sub(r"\b[a-z]+(?:_[a-z0-9]+)+\b", "", msg)
        msg = re.sub(r"['\"]", "", msg)
        msg = re.sub(r"\s{2,}", " ", msg).strip(" :;,.")
        if not msg or len(msg) < 8:
            continue
        if not msg.endswith("."):
            msg = msg + "."
        msg = msg[0].upper() + msg[1:]
        notes.append(msg)
    pad = 3.5
    items = [Paragraph(esc("Kiểm tra dữ liệu"), doc.st.section), Paragraph(esc(head), doc.st.table)]
    items += [Paragraph(esc(s), doc.st.caption) for s in notes]
    # Co khung theo nội dung ước lượng
    est_h = 10 + 5 * len(items)
    use_h = min(float(h_mm), max(18.0, float(est_h)))
    c.setFillColor(_hex(doc.theme.c["panel"]))
    c.rect(doc.x(col), doc.y(top_mm + use_h), doc.w(span), use_h * mm, stroke=0, fill=1)
    f = Frame(doc.x(col) + pad * mm, doc.y(top_mm + use_h) + pad * mm * 0.5, doc.w(span) - 2 * pad * mm,
              use_h * mm - 1.4 * pad * mm, leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
    f.addFromList([KeepInFrame(doc.w(span) - 2 * pad * mm, use_h * mm - 1.4 * pad * mm, items, mode="shrink")], c)


def draw_summary(doc: Doc, i: int, n: int, toc: list[tuple[str, int]] | None = None) -> None:
    d, th = doc.data, doc.theme
    c = th.c
    doc.header()
    m4 = d.m.get("m4") or {}
    title = conclusion_title(
        d.ticker, d.bull, d.bear, score=d.score, rating=d.rating, fits=doc.title_fits,
        contributions=d.m7.get("contributions") or {},
        m2=d.m.get("m2") or {}, m3=d.m.get("m3") or {}, m4=m4,
        m5=d.m.get("m5") or {}, m6=d.m.get("m6") or {},
        is_bank=bool(d.company.get("is_bank")), m4_flags=m4.get("flags") or [],
    )
    bottom = doc.page_title(title)
    prof = (doc.rc.get("profiles") or {}).get(d.profile, d.profile)
    sub = f"{d.company.get('name') or d.ticker}. {listing_sentence(d.company.get('exchange'), d.company.get('sector'), doc.rc)} Khẩu vị {prof}."
    doc.flow(0, 12, bottom + 1.5, 6, [Paragraph(esc(sub), doc.st.body_2)])
    top = bottom + 11

    # khuyến nghị + thước nhỏ
    doc.flow(0, 7, top, 7, [doc.section("Khuyến nghị")])
    w = doc.rating_mark(doc.x(0), top + 15, d.rating, 16)
    doc.text(f"{fmt_score(d.score)} điểm trên thang 0 đến 100", doc.x(0) + w + 5 * mm, top + 15, SANS, 11,
             c["ink"])
    doc.image(ruler_buf(doc, 7, 25), 0, 7, top + 19, 25)
    notes = []
    gate = risk_gate_note(doc)
    if gate:
        notes.append(doc.caption(gate))
    if d.synthetic:
        notes.append(Paragraph(esc("Dữ liệu giả lập dùng để kiểm thử, không dùng cho báo cáo thật."),
                               doc.st.table))
    if d.rank:
        notes.append(doc.caption(f"Vạch xám: {d.total} mã được xếp hạng cùng khẩu vị {prof}."))
    doc.flow(0, 7, top + 45, 12, notes)

    # bảng số liệu chính — chú thích một câu; chênh ≥30% chỉ ở trang 3
    rows = key_rows(doc)
    val_w = 30.0
    tbl = doc.table(["Chỉ tiêu", "Giá trị"], rows, [th.span_mm(5) - val_w, val_w], right_cols=[1])
    key_caps = []
    tgt = d.target or {}
    if to_float(tgt.get("base")) is not None:
        key_caps.append("Giá tham chiếu suy ra từ bội số ngành; xem giải thích ở trang 3.")
    doc.flow(7, 5, top, 64, [doc.section("Số liệu chính"), tbl, Spacer(1, 2)]
             + [doc.caption(s) for s in key_caps] + [doc.take_na_caption()])

    top2 = top + 66
    doc.hrule(top2)
    top2 += 4
    doc.flow(0, 5, top2, 7, [doc.section("Đóng góp điểm theo nhóm yếu tố")])
    doc.image(charts.contributions_chart(th, th.span_mm(5), 44, rows=contributions_rows(d)), 0, 5, top2 + 7, 44)
    s_sum = sum(v for _, v in contributions_rows(d) if v is not None)
    cap = f"Tổng: 50 {'+' if s_sum >= 0 else '−'} {fmt_num(abs(s_sum), 1)} = {fmt_score(50 + s_sum)} điểm."
    if d.score is not None and abs((50 + s_sum) - d.score) > 0.05:
        cap += f" Điểm công bố {fmt_score(d.score)} sau khi giới hạn trong khoảng 0 đến 100."
    doc.flow(0, 5, top2 + 52, 6, [Paragraph(esc(cap), doc.st.table_h)])
    doc.flow(0, 5, top2 + 58, 12, [
        doc.caption("Thanh xanh cộng điểm, thanh đỏ trừ điểm so với mức trung tính 50."),
        doc.caption("Tổng có thể lệch 0,1 điểm do làm tròn."),
        doc.caption(f"Nguồn: mô hình chấm điểm, đến {fmt_date(d.as_of)}."),
    ])

    def plist(points: list, empty: str) -> list:
        items = [esc(translate_terms(point_text(p))) for p in points if point_text(p)]
        return doc.bullets(items) if items else [Paragraph(esc(empty), doc.st.body_2)]

    items = [doc.section("Luận điểm chính"), Paragraph("Điểm cộng", doc.st.table_h)]
    items += plist(d.bull, "Không có nhóm yếu tố nào cộng điểm.")
    items += [Spacer(1, 3), Paragraph("Điểm trừ", doc.st.table_h)]
    items += plist(d.bear, "Không có nhóm yếu tố nào trừ điểm.")
    deb = debate_caption(d)
    if deb:
        items += [Spacer(1, 3), doc.caption(deb)]
    doc.flow(5, 7, top2, 66, items)

    top3 = top2 + 70
    doc.hrule(top3)
    top3 += 4
    doc.flow(0, 7, top3, 46, [doc.section("Điểm thành phần"), pillar_table(doc), Spacer(1, 2),
                              doc.caption("Điểm mỗi nhóm thang 0 đến 100; điểm rủi ro cao nghĩa là rủi ro đo được cao.")])
    if toc:
        t_rows = [[esc(t), str(p)] for t, p in toc]
        doc.flow(8, 4, top3, 46, [doc.section("Mục lục"),
                                  doc.table(["Mục", "Trang"], t_rows, [th.span_mm(4) - 12, 12], right_cols=[1])])
    m8_top = PAGE_H_MM - 18 - 28
    m8_block(doc, 0, 12, m8_top, 26)
    doc.footer(i, n)


def pillar_table(doc: Doc) -> Table:
    d = doc.data
    scores = d.m7.get("scores") or {}
    w = d.m7.get("weights") or {}
    contrib = d.m7.get("contributions") or {}
    rows = []
    for k in ("F", "T", "V", "S", "R"):
        wk = to_float(w.get("lambda_R" if k == "R" else k))
        w_txt = (fmt_num(wk, 2) if k == "R" else fmt_num(wk * 100) + "%") if wk is not None else NA
        cv = to_float(contrib.get(k))
        rows.append([PILLAR_NAMES[k], escape(fmt_score(scores.get(k))), escape(w_txt),
                     escape(fmt_signed(cv, 1)) if cv is not None else NA])
    sp = doc.theme.span_mm(7)
    return doc.table(["Nhóm", "Điểm", "Trọng số", "Đóng góp"], rows, [sp - 66, 22, 22, 22],
                     right_cols=[1, 2, 3])


def financial_table(doc: Doc) -> tuple[Table | None, str]:
    d = doc.data
    if not d.annual:
        return None, "Thiếu báo cáo tài chính năm, chưa lập được bảng kết quả kinh doanh."
    bank = bool(d.company.get("is_bank"))
    if bank:
        items = [("total_operating_income", "Tổng thu nhập hoạt động"), ("net_interest_income", "Thu nhập lãi thuần"),
                 ("provision_expense", "Chi phí dự phòng"), ("net_income_parent", "Lợi nhuận cổ đông mẹ"),
                 ("customer_loans", "Cho vay khách hàng"), ("customer_deposits", "Tiền gửi khách hàng"),
                 ("total_equity", "Vốn chủ sở hữu")]
    else:
        items = [("revenue", "Doanh thu thuần"), ("gross_profit", "Lợi nhuận gộp"), ("ebit", "Lợi nhuận hoạt động"),
                 ("net_income_parent", "Lợi nhuận cổ đông mẹ"), ("total_assets", "Tổng tài sản"),
                 ("total_equity", "Vốn chủ sở hữu"), ("cfo", "Dòng tiền kinh doanh")]
    years = [str(a.get("period")) for a in d.annual]
    rows = []
    unit_vnd = str(d.fin_unit or "VND").upper() == "VND"
    for key, label in items:
        vals = [to_float((a.get("items") or {}).get(key)) for a in d.annual]
        if all(v is None for v in vals):
            continue
        rows.append([escape(label)] + [fmt_bn_vnd(v) if unit_vnd else fmt_num(v) for v in vals])
    eps = [to_float((a.get("items") or {}).get("eps")) for a in d.annual]
    if any(v is not None for v in eps):
        rows.append(["EPS công bố, đồng"] + [fmt_num(v) for v in eps])
    shares = to_float(d.company.get("shares_outstanding"))
    if shares and shares > 0:
        adj = []
        for a in d.annual:
            ni = to_float((a.get("items") or {}).get("net_income_parent"))
            adj.append(fmt_num(ni / shares) if ni is not None else NA)
        if any(x != NA for x in adj):
            rows.append(["EPS quy đổi theo số cổ phiếu hiện tại, đồng"] + adj)
    else:
        rows.append(["EPS quy đổi theo số cổ phiếu hiện tại, đồng"] + [NA] * len(years))
    rows.append(["Ngày công bố"] + [fmt_date(a.get("published_at")) + ("*" if a.get("published_at_estimated") else "")
                                    for a in d.annual])
    th = doc.theme
    first = th.span_mm(12) - 22 * len(years)
    unit_label = "tỷ đồng" if unit_vnd else str(d.fin_unit)
    t = doc.table([f"Chỉ tiêu, {unit_label}"] + years, rows, [first] + [22] * len(years),
                  right_cols=list(range(1, len(years) + 1)))
    note = f"Đơn vị: {unit_label}, trừ EPS. "
    note += ("EPS công bố chưa điều chỉnh khi doanh nghiệp phát hành thêm hoặc chia cổ phiếu thưởng, "
             "nên không so sánh được giữa các năm. ")
    if d.fin_estimated:
        note += "* Ngày công bố là ước lượng vì nguồn không cung cấp. "
    note += f"Nguồn: báo cáo tài chính, đến {fmt_date(d.as_of)}."
    return t, note


def m2_rows(doc: Doc) -> list[list[str]]:
    d = doc.data
    m2 = d.m.get("m2") or {}
    bank = bool(d.company.get("is_bank"))
    spec = [("roe", "ROE", fmt_pct_ratio), ("net_income_growth", "Tăng trưởng lợi nhuận ròng", None),
            ("revenue_growth", "Tăng trưởng doanh thu", None)]
    if bank:
        spec += [("nim", "NIM", fmt_pct_ratio), ("cir", "CIR", fmt_pct_ratio),
                 ("loan_to_deposit", "Cho vay trên tiền gửi", fmt_pct_ratio),
                 ("npl_ratio", "Tỷ lệ nợ xấu", fmt_pct_ratio), ("car", "CAR", fmt_pct_ratio)]
    else:
        spec += [("gross_margin", "Biên lợi nhuận gộp", fmt_pct_ratio),
                 ("debt_to_equity", "Nợ vay trên vốn chủ, lần", lambda v: fmt_num(v, 2)),
                 ("interest_coverage", "Khả năng trả lãi, lần", lambda v: fmt_num(v, 1)),
                 ("cfo_to_net_income", "CFO trên lợi nhuận ròng, lần", lambda v: fmt_num(v, 2)),
                 ("current_ratio", "Thanh toán hiện hành, lần", lambda v: fmt_num(v, 2))]
    rows = []
    for key, label, f in spec:
        v = metric(m2, key)
        if v is None:
            cell = doc.na(label, reason_for(doc, "m2", key))
        elif f is None:
            cell = change_markup(doc.theme, v, fmt_pct_ratio(v, signed=True))
        else:
            cell = escape(f(v))
        rows.append([escape(label), cell])
    rows.append(["Điểm cơ bản, 0 đến 100",
                 escape(fmt_score(m2.get("score"))) if to_float(m2.get("score")) is not None
                 else doc.na("Điểm cơ bản", reason_for(doc, "m2", "score"))])
    return rows


def draw_fundamental(doc: Doc, i: int, n: int) -> None:
    d, th = doc.data, doc.theme
    m2, m4 = d.m.get("m2") or {}, d.m.get("m4") or {}
    bank = bool(d.company.get("is_bank"))
    doc.header()
    bottom = doc.page_title(fundamental_title(m2, m4, is_bank=bank, m4_flags=m4.get("flags") or []))
    top = bottom + 5
    tbl, note = financial_table(doc)
    items = [doc.section("Kết quả kinh doanh và bảng cân đối theo năm")]
    items += [tbl, Spacer(1, 2), doc.caption(note)] if tbl is not None else [Paragraph(esc(note), doc.st.body_2)]
    doc.flow(0, 12, top, 62, items)

    top2 = top + 65
    doc.hrule(top2)
    top2 += 4
    rows = m2_rows(doc)
    doc.flow(0, 5, top2, 82, [doc.section("Chỉ số tài chính"),
                              doc.table(["Chỉ số", "Giá trị"], rows, [th.span_mm(5) - 24, 24], right_cols=[1]),
                              Spacer(1, 3), doc.take_na_caption()])

    band = resolve_sector_band(
        d.company.get("sector"),
        pe=metric(m4, "pe"),
        pb=metric(m4, "pb"),
    )
    val_rows = []
    for key, lab in (("pe", "P/E"), ("pb", "P/B")):
        if bank and key == "pe":
            # Vẫn hiện P/E tham khảo nhưng chú thích
            pass
        blk = band.get(key) or {}
        v = metric(m4, key)
        med = metric(m4, f"sector_median_{key}")
        pct = blk.get("percentile")
        pct_lab = f"phân vị {fmt_num(pct, 1)}" if pct is not None else None
        val_rows.append({
            "label": f"{lab}, lần",
            "value": v,
            "median": med,
            "p25": blk.get("p25"),
            "p75": blk.get("p75"),
            "ticker": d.ticker,
            "pct_label": pct_lab,
        })
    doc.flow(5, 7, top2, 7, [doc.section("Định giá so với ngành")])
    doc.image(charts.valuation_chart(th, th.span_mm(7), 40, rows=val_rows), 5, 7, top2 + 7, 40)
    cap_parts = [
        "Chấm xanh: chỉ số của mã; vạch xám: trung vị ngành; dải nhạt: khoảng giữa phân vị 25 và 75. "
        "Phân vị càng cao nghĩa là càng đắt so với các mã cùng ngành."
    ]
    if band.get("used_fallback") or (band.get("pe") or {}).get("market_wide") or (band.get("pb") or {}).get("market_wide"):
        cap_parts.append("Ngành có ít hơn 5 mã đủ dữ liệu nên dùng trung vị toàn thị trường.")
    n_pe, n_pb = band.get("n_pe"), band.get("n_pb")
    if n_pe or n_pb:
        cap_parts.append(f"Số mẫu: P/E {fmt_num(n_pe)}, P/B {fmt_num(n_pb)}.")
    if metric_note(m4, "eps_used") == "ttm_ni":
        cap_parts.append("EPS dùng lợi nhuận 4 quý gần nhất.")
    cap_parts.append(f"Nguồn: chỉ số ngành, đến {fmt_date(d.as_of)}.")
    doc.flow(5, 7, top2 + 48, 16, [doc.caption(" ".join(cap_parts))])
    score_v = to_float(m4.get("score"))
    doc.flow(5, 7, top2 + 65, 14, [Paragraph(
        esc(f"Điểm định giá: {fmt_score(score_v)} trên 100. Điểm cao nghĩa là rẻ hơn ngành.")
        if score_v is not None else esc("Điểm định giá: n/a, chưa đủ dữ liệu để chấm."), doc.st.body)])

    top3 = top2 + 86
    doc.hrule(top3)
    top3 += 4
    doc.flow(0, 12, top3, 7, [doc.section("Giá tham chiếu theo bội số ngành, đồng/cổ phiếu")])
    tgt = d.target or {}
    ff_rows = []
    hi52 = max((to_float(r.get("high")) or 0) for r in d.rows) if d.rows else None
    lo52 = min((to_float(r.get("low")) or float("inf")) for r in d.rows) if d.rows else None
    if hi52 and lo52 and lo52 != float("inf"):
        ff_rows.append({"label": "Biên độ 1 năm", "low": lo52, "high": hi52, "color": "axis", "light": False})
    if to_float(tgt.get("base")) is not None:
        ff_rows.append({"label": "Bội số ngành", "low": tgt.get("bear"), "high": tgt.get("bull"),
                        "mid": tgt.get("base"), "mid_label": "Tham chiếu", "color": "series_1", "light": True})
    close = metric(d.m.get("m3"), "close") or metric(m4, "price_close")
    if ff_rows:
        doc.image(charts.football_field(th, th.span_mm(12), 36, rows=ff_rows, price=close), 0, 12, top3 + 7, 36)
    # Ba ý theo thứ tự: (i) giá + cận, (ii) % chênh, (iii) hạn chế phương pháp; thêm câu ≥30% nếu có
    method = []
    if to_float(tgt.get("base")) is not None:
        method.append(
            f"Giá tham chiếu {fmt_num(tgt.get('base'))} đồng; cận dưới {fmt_num(tgt.get('bear'))} đồng, "
            f"cận trên {fmt_num(tgt.get('bull'))} đồng."
        )
        if close:
            up = to_float(tgt.get("base")) / close - 1
            method.append(
                f"Giá tham chiếu {'cao' if up >= 0 else 'thấp'} hơn giá đóng cửa {fmt_pct_ratio(abs(up))}."
            )
            if abs(up) >= 0.30:
                method.append(
                    "Chênh lệch lớn so với giá thị trường; thường gặp khi doanh nghiệp giao dịch cao hoặc "
                    "thấp hơn nhiều so với trung vị ngành."
                )
        method.append(
            "Giá tham chiếu suy ra từ trung vị P/E, P/B của ngành, chưa tính phần bù hoặc chiết khấu "
            "theo chất lượng doanh nghiệp, không phải dự phóng kết quả kinh doanh."
        )
    else:
        method.append(f"Chưa có giá tham chiếu: {reason_for(doc, 'm4', 'target')}.")
    doc.flow(0, 8, top3 + 45, 18, [Paragraph(esc(" ".join(method)), doc.st.body),
                                   doc.caption(f"Nguồn: định giá theo bội số ngành, đến {fmt_date(d.as_of)}.")])
    doc.footer(i, n)


def draw_technical(doc: Doc, i: int, n: int) -> None:
    d, th = doc.data, doc.theme
    m3, m6 = d.m.get("m3") or {}, d.m.get("m6") or {}
    doc.header()
    bottom = doc.page_title(technical_title(m3, m6))
    top = bottom + 5
    doc.flow(0, 12, top, 7, [doc.section(f"Diễn biến giá {len(d.closes)} phiên gần nhất, đồng/cổ phiếu")])
    if len(d.closes) >= 2:
        series = []
        if d.ma.get("MA20"):
            series.append(("MA20", d.ma["MA20"], "series_2"))
        if d.ma.get("MA50"):
            series.append(("MA50", d.ma["MA50"], "series_3"))
        doc.image(charts.price_chart(th, th.span_mm(12), 70, dates=d.dates, close=d.closes, series=series),
                  0, 12, top + 7, 70)
        doc.flow(0, 12, top + 79, 6, [Paragraph(f"Khối lượng khớp lệnh, {charts.volume_unit(d.volumes)[1]}",
                                                doc.st.table_h)])
        doc.image(charts.volume_chart(th, th.span_mm(12), 24, dates=d.dates, volume=d.volumes), 0, 12, top + 84, 24)
        doc.flow(0, 12, top + 109, 8, [doc.caption(
            f"Giá đã điều chỉnh. MA20 và MA50 là trung bình giá đóng cửa 20 và 50 phiên. "
            f"Nguồn: giá và khối lượng, đến {fmt_date(d.as_of)}.")])
    else:
        doc.flow(0, 12, top + 7, 10, [Paragraph(esc("Thiếu dữ liệu giá, chưa vẽ được biểu đồ."), doc.st.body_2)])

    top2 = top + 120
    doc.hrule(top2)
    top2 += 4
    rows = [
        ["Giá đóng cửa, đồng", mval(doc, "m3", "close", fmt_num, "Giá")],
        ["MA20, đồng", mval(doc, "m3", "ma20", fmt_num, "MA20")],
        ["MA50, đồng", mval(doc, "m3", "ma50", fmt_num, "MA50")],
        ["MA200, đồng", mval(doc, "m3", "ma200", fmt_num, "MA200")],
        ["RSI 14 phiên", mval(doc, "m3", "rsi14", lambda v: fmt_num(v, 1), "RSI14")],
        ["MACD, đồng", mval(doc, "m3", "macd", lambda v: fmt_num(v, 1), "MACD")],
        ["Đường tín hiệu MACD, đồng", mval(doc, "m3", "macd_signal", lambda v: fmt_num(v, 1), "Tín hiệu MACD")],
        ["ATR 14 phiên trên giá", mval(doc, "m3", "atr_pct", fmt_pct_points, "ATR")],
        ["Khối lượng so với TB20, lần", mval(doc, "m3", "volume_ratio_20", lambda v: fmt_num(v, 2), "KL/TB20")],
        ["Điểm kỹ thuật, 0 đến 100", escape(fmt_score(m3.get("score"))) if to_float(m3.get("score")) is not None
         else doc.na("Điểm kỹ thuật", reason_for(doc, "m3", "score"))],
    ]
    doc.flow(0, 6, top2, 70, [doc.section("Chỉ báo kỹ thuật"),
                              doc.table(["Chỉ báo", "Giá trị"], [[escape(r[0]), r[1]] for r in rows],
                                        [th.span_mm(6) - 26, 26], right_cols=[1]),
                              Spacer(1, 3), doc.take_na_caption()])

    def pair(key: str, bkey: str | None, f) -> list[str]:
        a = mval(doc, "m6", key, f, key)
        b = mval(doc, "m6", bkey, f, bkey) if bkey else ""
        return [a, b]

    rrows = [
        ["Biến động năm"] + pair("annualized_volatility", "benchmark_volatility", fmt_pct_points),
        ["Sụt giảm tối đa"] + pair("max_drawdown", "benchmark_max_drawdown", fmt_pct_points),
        ["Beta"] + pair("beta", None, lambda v: fmt_num(v, 2)),
        ["VaR lịch sử 95%, một phiên"] + pair("historical_var_95", None, fmt_pct_points),
        ["CVaR lịch sử 95%, một phiên"] + pair("historical_cvar_95", None, fmt_pct_points),
        ["Số phiên tăng và giảm", (f"{fmt_num(metric(m6, 'positive_sessions'))} và "
                                   f"{fmt_num(metric(m6, 'negative_sessions'))}")
         if metric(m6, "positive_sessions") is not None else doc.na("Số phiên", reason_for(doc, "m6", "x")), ""],
        ["Điểm rủi ro, 0 đến 100", escape(fmt_score(m6.get("score"))) if to_float(m6.get("score")) is not None
         else doc.na("Điểm rủi ro", reason_for(doc, "m6", "score")), ""],
    ]
    obs = metric(m6, "aligned_observations")
    doc.flow(6, 6, top2, 70, [
        doc.section("Đo lường rủi ro"),
        doc.table(["Chỉ tiêu", d.ticker, "VN-Index"], [[escape(r[0]), r[1], r[2]] for r in rrows],
                  [th.span_mm(6) - 44, 22, 22], right_cols=[1, 2]),
        Spacer(1, 3),
        doc.caption(
            f"Điểm rủi ro cao nghĩa là rủi ro đo được cao, kéo điểm tổng xuống. Ước tính từ "
            f"{fmt_num(obs)} phiên lợi suất trùng khớp với VN-Index. VaR và CVaR không phải giới hạn "
            f"thua lỗ tối đa." if obs is not None else "Điểm rủi ro cao nghĩa là rủi ro đo được cao."
        ),
        doc.take_na_caption(),
    ])
    doc.footer(i, n)


def draw_news(doc: Doc, i: int, n: int) -> None:
    d, th = doc.data, doc.theme
    m5 = d.m.get("m5") or {}
    doc.header()
    bottom = doc.page_title(news_title(m5))
    top = bottom + 5
    pos, neg = metric(m5, "news_positive_count"), metric(m5, "news_negative_count")
    doc.flow(0, 5, top, 7, [doc.section("Tâm lý tin tức")])
    left_h = 7.0
    if pos is not None and neg is not None:
        doc.flow(0, 5, top + 7, 5, [doc.caption("Số tin có hướng rõ, tiêu cực bên trái, tích cực bên phải")])
        doc.image(charts.sentiment_chart(th, th.span_mm(5), 16, positive=pos, negative=neg), 0, 5, top + 12, 16)
        left_h = 28.0
    rows = [
        ["Tin liên quan", mval(doc, "m5", "news_relevant_count", fmt_num, "Tin liên quan")],
        ["Tin trung tính", mval(doc, "m5", "news_neutral_count", fmt_num, "Tin trung tính")],
        ["Nguồn tin khác nhau", mval(doc, "m5", "news_distinct_sources", fmt_num, "Nguồn tin")],
        ["Độ phủ tin có hướng, 0 đến 1", mval(doc, "m5", "sentiment_confidence", lambda v: fmt_num(v, 2), "Độ phủ")],
        ["Điểm tin tức, 0 đến 100", escape(fmt_score(m5.get("score"))) if to_float(m5.get("score")) is not None
         else doc.na("Điểm tin tức", reason_for(doc, "m5", "score"))],
    ]
    metrics_top = top + left_h + 1
    metrics_h = 36.0
    doc.flow(0, 5, metrics_top, metrics_h, [
        doc.table(["Chỉ tiêu", "Giá trị"], [[escape(r[0]), r[1]] for r in rows],
                  [th.span_mm(5) - 20, 20], right_cols=[1]),
        Spacer(1, 2),
        doc.caption("Chấm theo từ khóa trên tiêu đề, chưa đọc toàn văn; độ phủ thấp thì "
                    "điểm tin kém tin cậy hơn."),
        doc.take_na_caption(),
    ])
    left_bottom = metrics_top + metrics_h

    clustered = select_news_panel(
        d.news,
        ticker=d.ticker,
        company=d.company,
        as_of=d.as_of,
        max_items=6,
        max_negatives=3,
    )
    news_lines = []
    for it in clustered:
        label = format_news_label(str(it.get("label") or ""))
        title = (it.get("title") or "").strip()
        meta_bits = news_meta_bits(it)
        # markup — không esc() phần này (có thẻ <font>)
        extra = news_extra_phrase(int(it.get("extra_count") or 0), markup=True)
        line = f"<b>{esc(label)}.</b> {esc(title)}{extra}" if label else f"{esc(title)}{extra}"
        if meta_bits:
            line += f'<font color="{th.c["ink_3"]}" size="7.5"> — {esc(", ".join(meta_bits))}</font>'
        news_lines.append(line)
    news_flow = [doc.section("Tin gần đây")]
    bullet_st = ParagraphStyle(
        "news_b", parent=doc.st.bullet, fontSize=8.5, leading=11.5, spaceAfter=1.5,
    )
    if news_lines:
        news_flow += doc.bullets(news_lines, bullet_st)
    else:
        news_flow.append(Paragraph(esc("Không có tin trong cửa sổ dữ liệu."), doc.st.body_2))
    # Cao khung tin theo số dòng (~2 dòng/tin khi tiêu đề dài)
    news_h = min(95.0, max(16.0, 8.0 + 9.5 * max(1, len(news_lines))))
    doc.flow(5, 7, top, news_h, news_flow)
    news_bottom = top + news_h

    # Khối lưu ý / phương pháp / nguồn sát dưới tin (và cột trái) — không để khoảng trống giữa trang
    top2 = max(left_bottom, news_bottom) + 2.5
    doc.hrule(top2)
    top2 += 2.5
    notes = select_data_notes(d.all_flags(), doc.flag_dict, fin_estimated=d.fin_estimated, max_lines=4)
    note_flow = [doc.section("Lưu ý dữ liệu")]
    if notes:
        note_flow += doc.bullets(
            [esc(s) for s in notes],
            ParagraphStyle("bs", parent=doc.st.bullet, fontSize=8.5, leading=11.5),
        )
    else:
        note_flow.append(Paragraph(esc("Không có lưu ý đọc số đặc biệt."), doc.st.body_2))
    remain = max(24.0, PAGE_H_MM - 15 - top2 - (18 if doc.technical_appendix else 2))
    doc.flow(0, 6, top2, remain, note_flow)
    meth = scoring_method_plain(doc.scoring_cfg, d.profile)
    src_lines = [esc(s) for s in human_sources(d.sources, d.as_of)]
    doc.flow(6, 6, top2, remain, [doc.section("Phương pháp chấm điểm"), Paragraph(esc(meth), doc.st.table),
                                  Spacer(1, 3), doc.section("Nguồn dữ liệu")]
             + [Paragraph(s, doc.st.caption) for s in src_lines])

    if doc.technical_appendix:
        top3 = top2 + min(remain, 50)
        if top3 + 10 < PAGE_H_MM - 16:
            doc.hrule(top3)
            tech = list(d.ma_notes)
            tech.append(
                f"Nguồn luận điểm: {'cache' if d.debate_source == 'CACHE' else 'template'}"
                + (f", mô hình {d.debate_model}" if d.debate_model else "") + "."
            )
            tech.append(f"Khẩu vị {d.profile}, dữ liệu đến {fmt_date(d.as_of)}.")
            doc.flow(0, 12, top3 + 3, PAGE_H_MM - 16 - top3 - 3, [Paragraph("Chi tiết kỹ thuật", doc.st.table_h)]
                     + [doc.caption(s) for s in tech])
    doc.footer(i, n)


def draw_unranked(doc: Doc, i: int, n: int) -> None:
    d, th = doc.data, doc.theme
    qg = d.m7.get("quality_gate") or {}
    doc.header()
    bottom = doc.page_title(f"{d.ticker}: chưa đủ dữ liệu để xếp hạng")
    sub = f"{d.company.get('name') or d.ticker}. {listing_sentence(d.company.get('exchange'), d.company.get('sector'), doc.rc)}"
    doc.flow(0, 12, bottom + 1.5, 6, [Paragraph(esc(sub), doc.st.body_2)])
    top = bottom + 10
    reason = reason_text(qg.get("reasons") or [], doc.flag_dict)
    doc.flow(0, 8, top, 16, [
        Paragraph(esc(f"Mã chưa được chấm điểm vì {reason}. Báo cáo chỉ trình bày dữ liệu giá và kết quả kiểm "
                      "chứng, không có điểm và khuyến nghị."), doc.st.body)])
    top += 18
    if len(d.closes) >= 2:
        doc.flow(0, 12, top, 7, [doc.section(f"Diễn biến giá {len(d.closes)} phiên gần nhất, đồng/cổ phiếu")])
        doc.image(charts.price_chart(th, th.span_mm(12), 62, dates=d.dates, close=d.closes, series=[]),
                  0, 12, top + 7, 62)
        doc.image(charts.volume_chart(th, th.span_mm(12), 20, dates=d.dates, volume=d.volumes), 0, 12, top + 70, 20)
        doc.flow(0, 12, top + 91, 6, [doc.caption(f"Trên: giá đóng cửa điều chỉnh. Dưới: khối lượng, "
                                                  f"{charts.volume_unit(d.volumes)[1]}. "
                                                  f"Nguồn: giá và khối lượng, đến {fmt_date(d.as_of)}.")])
        top += 99
    else:
        doc.flow(0, 12, top, 8, [Paragraph(esc("Thiếu dữ liệu giá, chưa vẽ được biểu đồ."), doc.st.body_2)])
        top += 10
    doc.hrule(top)
    top += 4
    rows = []
    if d.closes:
        rows.append(["Giá đóng cửa, đồng", fmt_num(d.closes[-1])])
        hi = max(to_float(r.get("high")) or 0 for r in d.rows)
        lo = min(to_float(r.get("low")) or float("inf") for r in d.rows)
        rows.append([f"Cao nhất {len(d.rows)} phiên, đồng", fmt_num(hi)])
        rows.append([f"Thấp nhất {len(d.rows)} phiên, đồng", fmt_num(lo) if lo != float("inf") else NA])
        vma = sum(d.volumes[-20:]) / min(20, len(d.volumes))
        rows.append(["Khối lượng TB 20 phiên, cổ phiếu", fmt_num(vma)])
        rows.append(["Số phiên có giá", fmt_num(len(d.rows))])
    else:
        rows.append(["Giá đóng cửa, đồng", doc.na("Giá", "thiếu dữ liệu giá")])
    doc.flow(0, 5, top, 50, [doc.section("Dữ liệu giá"),
                             doc.table(["Chỉ tiêu", "Giá trị"], [[escape(a), b] for a, b in rows],
                                       [th.span_mm(5) - 24, 24], right_cols=[1]), doc.take_na_caption()])
    notes = select_data_notes(d.all_flags(), doc.flag_dict, fin_estimated=d.fin_estimated, max_lines=4)
    note_items = [doc.section("Lưu ý dữ liệu")]
    if notes:
        note_items += doc.bullets([esc(s) for s in notes])
    else:
        note_items.append(Paragraph(esc("Không có lưu ý đọc số đặc biệt."), doc.st.body_2))
    doc.flow(5, 7, top, 50, note_items)
    top += 53
    m8_block(doc, 0, 12, top, min(42.0, PAGE_H_MM - 16 - top - 14))
    doc.footer(i, n)


# --------------------------------------------------------------------------- ráp tài liệu


def build_pages(doc: Doc, cover: bool) -> list[Page]:
    pages: list[Page] = []
    if cover:
        pages.append(Page("cover", draw_cover))
    if not doc.data.scored:
        pages.append(Page("unranked", draw_unranked, "Dữ liệu hiện có"))
        return pages
    pages.append(Page("summary", draw_summary, "Tóm tắt khuyến nghị"))
    pages.append(Page("fundamental", draw_fundamental, "Cơ bản và định giá"))
    pages.append(Page("technical", draw_technical, "Kỹ thuật và rủi ro"))
    pages.append(Page("news", draw_news, "Tin tức, lưu ý dữ liệu và phụ lục"))
    return pages


def render(doc: Doc, path: str, *, cover: bool, keywords: str) -> int:
    pages = build_pages(doc, cover)
    n = len(pages)
    c = rl_canvas.Canvas(path, pagesize=A4, pageCompression=1, initialFontName="StockSans",
                         initialFontSize=9.5)
    d = doc.data
    c.setTitle(f"{d.ticker}: báo cáo phân tích, dữ liệu đến {fmt_date(d.as_of)}")
    c.setAuthor("StockAI")
    c.setSubject("Báo cáo phân tích cơ hội đầu tư cổ phiếu, tạo tự động")
    c.setKeywords(keywords)
    c.setCreator("StockAI")
    doc.c = c
    toc = [(p.toc_title, k + 1) for k, p in enumerate(pages) if p.toc_title] if cover else None
    for k, p in enumerate(pages, start=1):
        doc.notes_na = []
        if p.kind == "summary":
            draw_summary(doc, k, n, toc=toc)
        else:
            p.draw(doc, k, n)
        c.showPage()
    c.save()
    return n
