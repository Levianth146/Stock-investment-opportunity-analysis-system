"""Dynamic executive and fundamental detail pages. All values come from ReportData."""
from __future__ import annotations

from reportlab.lib.units import mm

from stockai.m9_report import charts, professional_charts as pcharts
from stockai.m9_report.data import metric
from stockai.m9_report.fmt import fmt_date, fmt_num, fmt_pct_points, fmt_pct_ratio, fmt_score, to_float
from stockai.m9_report.layout import contributions_rows
from stockai.m9_report.pages.insight_components import (
    Box, PageCanvas, CARD_GAP, COLUMN_GAP, status_kind, status_label,
)


def number(value, suffix="", decimals=0):
    return "N/A" if to_float(value) is None else fmt_num(value, decimals)+suffix


def score(value):
    return number(value, "/100", 1)


def positive_price(value):
    parsed = to_float(value)
    return parsed if parsed is not None and parsed > 0 else None


def live_price(data):
    """Giá trực tiếp/chốt phiên do API truyền vào; None nếu không có (khi đó dùng giá EOD)."""
    q = (getattr(data, "live", None) or {}).get("quote") or {}
    return positive_price(q.get("price"))


def live_labels(data):
    """(nhãn KPI, ghi chú) cho ô giá: phân biệt trực tiếp trong phiên với chốt phiên tạm tính."""
    live = getattr(data, "live", None) or {}
    q = live.get("quote") or {}
    stamp = _stamp(live.get("captured_at"))
    if positive_price(q.get("price")) is None:
        return "Giá đóng cửa", f"EOD {fmt_date(getattr(data, 'as_of', None))}"
    if q.get("state") == "live" or q.get("basis") == "live":
        return "Giá trực tiếp", stamp
    return "Giá chốt phiên", f"{stamp} · tạm tính"


def _stamp(iso):
    if not isinstance(iso, str) or len(iso) < 16:
        return ""
    return f"{fmt_date(iso[:10])} {iso[11:16]}"


def draw_live_strip(pc, data):
    """Dải dữ liệu thời gian thực ở góc phải tiêu đề (trang tóm tắt đã kín nên không thêm panel)."""
    x, w = pc.x + pc.width * 0.52, pc.width * 0.48
    live = getattr(data, "live", None) or {}
    if not live:
        pc.text(f"Giá đóng cửa EOD {fmt_date(getattr(data, 'as_of', None))}; không có dữ liệu trực tiếp tại thời điểm xuất.",
                Box(x, 27, w, 12), size=7.2, max_lines=2, color="muted")
        return
    stamp = _stamp(live.get("captured_at"))
    pc.text("Dữ liệu thời gian thực tại thời điểm xuất" + (f" · {stamp}" if stamp else ""),
            Box(x, 25, w, 5), size=7.2, max_lines=1, bold=True, color="muted")
    idx = live.get("index") or {}
    br = live.get("breadth") or {}
    parts = []
    if to_float(idx.get("price")) is not None:
        chg = to_float(idx.get("change_pct"))
        pct = "" if chg is None else f" ({'+' if chg >= 0 else ''}{fmt_num(chg, 2)}%)"
        parts.append(f"{idx.get('name') or 'VN-Index'} {fmt_num(idx['price'], 2)}{pct}")
    if br:
        parts.append(f"Tăng {fmt_num(br.get('up'), 0)} · Giảm {fmt_num(br.get('down'), 0)} · Đứng {fmt_num(br.get('flat'), 0)}")
    q = live.get("quote") or {}
    vol = to_float(q.get("volume"))
    if vol is not None:
        parts.append(f"KL {fmt_num(vol, 0)}")
    if parts:
        pc.text(" · ".join(parts), Box(x, 30.5, w, 5), size=7.2, max_lines=1, color="muted")
    pc.text(f"Điểm tính theo EOD {fmt_date(getattr(data, 'as_of', None))}, không đổi theo giá trong phiên.",
            Box(x, 35.5, w, 8), size=7, max_lines=2, color="muted")


def target_values(data):
    # Prefer the M7 presentation target; use M4 only when M7 has none.
    target = data.target
    return target if target is not None else (data.m.get("m4") or {}).get("target") or {}


def price_markers(target, current):
    """Use one numeric scale for every available positive marker; never fabricate bounds."""
    values = [(label, positive_price(value)) for label, value in (
        ("Bear", target.get("bear")), ("Base", target.get("base")),
        ("Hiện tại", current), ("Bull", target.get("bull")),
    )]
    values = [(label, value) for label, value in values if value is not None]
    if not values:
        return []
    low, high = min(v for _, v in values), max(v for _, v in values)
    span = high-low
    return [(label, value, 0.5 if span == 0 else 0.06+0.88*(value-low)/span)
            for label, value in values]


def news_rows(data):
    m5 = data.m.get("m5") or {}
    rows = []
    direct_score = to_float(m5.get("score"))
    if direct_score is not None:
        rows.append(("Điểm tin tức M5", score(direct_score)))
    else:
        rows.append(("Tin tức M5", "Chưa đủ dữ liệu"))
        if "S_missing_used_neutral" in (data.m7.get("flags") or []):
            neutral = to_float((data.m7.get("scores") or {}).get("S"))
            if neutral is not None:
                rows.append(("M7 trung tính", score(neutral)))
    for key, label in (
        ("news_story_count", "Stories liên quan"),
        ("news_distinct_sources", "Nguồn phân biệt"),
        ("sentiment_confidence", "Confidence M5"),
    ):
        value = metric(m5, key)
        if value is not None:
            rows.append((label, fmt_num(value, 2 if key == "sentiment_confidence" else 0)))
    rows.append(("Kiểm chứng M8", status_label(data.m8)))
    if isinstance(data.m8.get("issues"), list):
        count = sum(1 for issue in data.m8["issues"] if isinstance(issue, dict)
                    and str(issue.get("severity", "")).lower() in ("warn", "warning"))
        rows.append(("Cảnh báo M8", fmt_num(count)))
    return rows


GENERAL_METRICS = (
    ("gross_margin", "Biên gộp", "pct"),
    ("debt_to_equity", "D/E", "x"),
    ("debt_to_assets", "Nợ/Tài sản", "pct"),
    ("interest_coverage", "Khả năng trả lãi", "x"),
    ("cfo_to_net_income", "CFO/LNST", "x"),
    ("current_ratio", "Current ratio", "x"),
)
BANK_METRICS = (
    ("nim", "NIM", "pct"), ("cir", "CIR", "pct"),
    ("loan_to_deposit", "Cho vay / huy động", "pct"),
    ("npl_ratio", "Tỷ lệ nợ xấu", "pct"), ("car", "CAR", "pct"),
)


def metric_text(module, key, kind):
    value = metric(module, key)
    if value is None:
        return "N/A"
    return fmt_pct_ratio(value) if kind == "pct" else number(value, "x", 2)


def financial_health_metrics(module, bank):
    definitions = BANK_METRICS if bank else GENERAL_METRICS
    return [(key, label, metric_text(module, key, kind)) for key, label, kind in definitions
            if metric(module, key) is not None]


def ratio_rows(module, bank):
    available_keys = module.get("metrics") or {}
    return [(label, metric_text(module, key, kind))
            for key, label, kind in (BANK_METRICS if bank else GENERAL_METRICS)
            if key in available_keys]


def conclusion_bullets(module, bank):
    bullets = []
    if to_float(module.get("score")) is not None:
        bullets.append(f"Điểm cơ bản F đạt {score(module['score'])}; trạng thái M2: {status_label(module)}.")
    parts = []
    for key, label in (("roe", "ROE"), ("net_income_growth", "Tăng trưởng LNST")):
        value = metric(module, key)
        if value is not None:
            parts.append(f"{label} {fmt_pct_ratio(value)}"+(" YoY" if key.endswith("growth") else ""))
    if parts:
        bullets.append("; ".join(parts)+".")
    growth = metric(module, "revenue_growth")
    if growth is not None:
        bullets.append(f"Tăng trưởng doanh thu {fmt_pct_ratio(growth)} YoY.")
    groups = [BANK_METRICS[:3], BANK_METRICS[3:]] if bank else [GENERAL_METRICS[1:4], GENERAL_METRICS[4:]]
    for group in groups:
        parts = [f"{label} {metric_text(module, key, kind)}" for key, label, kind in group
                 if metric(module, key) is not None]
        if parts:
            bullets.append("; ".join(parts)+".")
    if bank:
        missing = [label for key, label, _ in BANK_METRICS
                   if key in (module.get("metrics") or {}) and metric(module, key) is None]
        if missing and len(bullets) < 5:
            bullets.append("M2 chưa có số liệu: "+", ".join(missing)+".")
    return bullets[:5] or [f"M2: {status_label(module)}. Chưa có chỉ tiêu định lượng để kết luận."]


def annual_observations(periods, revenue, profit, label):
    observations = []
    valid_rev = [(period, value) for period, value in zip(periods, revenue) if value is not None]
    valid_ni = [(period, value) for period, value in zip(periods, profit) if value is not None]
    if valid_rev:
        period, value = max(valid_rev, key=lambda item: item[1])
        observations.append(f"{label} cao nhất trong {len(valid_rev)} năm có dữ liệu hiển thị: "
                            f"{fmt_num(value,1)} nghìn tỷ đồng ({period}).")
    if valid_ni:
        ymax, vmax = max(valid_ni, key=lambda item: item[1])
        ymin, vmin = min(valid_ni, key=lambda item: item[1])
        observations.append(f"LNST cao nhất {fmt_num(vmax,1)} nghìn tỷ đồng ({ymax}); "
                            f"thấp nhất {fmt_num(vmin,1)} nghìn tỷ đồng ({ymin}).")
    if len(periods) >= 2 and revenue[-1] is not None and revenue[-2] is not None:
        relation = "cao hơn" if revenue[-1] > revenue[-2] else "thấp hơn" if revenue[-1] < revenue[-2] else "bằng"
        observations.append(f"{label} {periods[-1]} {relation} {periods[-2]}.")
    return observations or ["Chưa có chuỗi BCTC năm đủ để trình bày điểm nhấn."]


def _series(rows, revenue_key):
    periods, revenue, profit = [], [], []
    for row in sorted(rows, key=lambda row: str(row.get("period", ""))):
        items = row.get("items") or {}
        rv = to_float(items.get(revenue_key))
        ni = to_float(items.get("net_income_parent"))
        if ni is None:
            ni = to_float(items.get("net_income"))
        periods.append(str(row.get("period", "")))
        revenue.append(None if rv is None else rv/1e12)
        profit.append(None if ni is None else ni/1e12)
    return periods, revenue, profit


def _range(pc, box, target, current):
    markers = price_markers(target, current)
    if not markers:
        pc.text("Chưa có khoảng giá hợp lệ.", box, size=7.5, color="muted", max_lines=2)
        return
    pc.c.setStrokeColor(pc.color("line")); pc.c.setLineWidth(1.5)
    pc.c.line(box.x*mm, pc.doc.y(box.y+2), (box.x+box.w)*mm, pc.doc.y(box.y+2))
    colors = {"Bear": "danger", "Base": "caution", "Hiện tại": "blue", "Bull": "support"}
    # Price markers follow the numeric scale. Labels use a separate 2x2 legend,
    # so equal/nearby prices never cause label collisions.
    for label, value, position in markers:
        pc.c.setFillColor(pc.color(colors[label]))
        pc.c.circle((box.x+position*box.w)*mm, pc.doc.y(box.y+2), 0.85*mm, fill=1, stroke=0)
    columns = Box(box.x, box.y+5, box.w, 15).columns(2, gap=1)
    for index, (label, value, _) in enumerate(markers):
        col = columns[index%2]
        top = box.y+5+(index//2)*7.6
        pc.text(label, Box(col.x, top, col.w, 3), size=6.7, minimum=6.1,
                color=colors[label], name=f"range.{label}.label")
        pc.text(fmt_num(value), Box(col.x, top+3, col.w, 3.4), size=7.5, minimum=6.2,
                bold=True, name=f"range.{label}.value")


def _quick_position(pc, data):
    content = pc.panel(Box(pc.x, 195, pc.width, 74), "Định vị đầu tư nhanh",
                       subtitle="Tín hiệu chính từ định giá, kỹ thuật, rủi ro, tin tức và kiểm chứng.",
                       variant="blue", name="position")
    cards = Box(content.x, 211, content.w, 55).columns(3, CARD_GAP)
    a, b, c = cards
    pc.panel(a, "Định giá nhanh (M4)", variant="purple", title_size=8.6, name="position.valuation")
    pc.panel(b, "Kỹ thuật & rủi ro", variant="teal", title_size=8.6, name="position.technical")
    pc.panel(c, "Tin tức & kiểm chứng", variant="purple", title_size=8.6, name="position.news")
    m3, m4, m5, m6 = [data.m.get(key) or {} for key in ("m3", "m4", "m5", "m6")]
    target, current = target_values(data), positive_price(data.close)
    base = positive_price(target.get("base"))
    if to_float(m4.get("score")) is None and base is None:
        pc.text("Chưa đủ dữ liệu định giá", Box(a.x+3, 223, a.w-6, 13),
                size=9, max_lines=3, color="muted")
        pc.text(status_label(m4), Box(a.x+3, 244, a.w-6, 7),
                size=8, color=status_kind(status_label(m4)), max_lines=2)
    else:
        rows = [("Điểm V", score(m4.get("score"))),
                ("Giá cơ sở", number(base, " đ")), ("Giá đóng cửa EOD", number(current, " đ"))]
        if base is not None and current is not None:
            rows.append(("Base / hiện tại", fmt_pct_ratio(base/current-1, signed=True)))
        pc.rows(Box(a.x+2, 221, a.w-4, 18), rows, size=7.3, value_fraction=0.49, name="valuation.rows")
        pc.text("M4: "+status_label(m4), Box(a.x+3, 239.2, a.w-6, 3.3),
                size=6.6, minimum=6.3, color=status_kind(status_label(m4)))
        _range(pc, Box(a.x+3, 243, a.w-6, 20), target, current)
    for y, label, value, color in ((221, "Điểm kỹ thuật T", m3.get("score"), "teal"),
                                    (230, "Điểm rủi ro R", m6.get("score"), "caution")):
        pc.rows(Box(b.x+2, y, b.w-4, 4.5), [(label, score(value))],
                size=7.4, value_fraction=0.36, name=label)
        pc.bar(Box(b.x+3, y+4.6, b.w-6, 1.5), value, color)
    pc.text("R càng cao: rủi ro càng lớn", Box(b.x+3, 237, b.w-6, 3.2),
            size=6.4, minimum=6.1, color="muted")
    risk_rows = []
    for module, key, label, kind in (
        (m3, "rsi14", "RSI (14)", "number"), (m6, "beta", "Beta", "beta"),
        (m6, "annualized_volatility", "Biến động năm hóa", "pct"),
        (m6, "max_drawdown", "Max drawdown", "pct"),
    ):
        value = metric(module, key)
        if value is not None:
            risk_rows.append((label, fmt_pct_points(value) if kind == "pct" else fmt_num(value, 2 if kind == "beta" else 1)))
    pc.rows(Box(b.x+2, 241, b.w-4, 22), risk_rows, size=7.3, value_fraction=0.34, name="risk.rows")
    pc.rows(Box(c.x+2, 221, c.w-4, 42), news_rows(data), size=7.2,
            value_fraction=0.55, name="news.rows")


def _status_strip(pc, data):
    box = Box(pc.x, 273, pc.width, 15)
    content = pc.panel(box, name="status")
    title_width = 32
    pc.text("Tình trạng dữ liệu\ncác module", Box(content.x, box.y+3.5, title_width-2, 8),
            size=8, bold=True, max_lines=2)
    slots = Box(content.x+title_width, box.y+2.4, content.w-title_width, 11).columns(6, 1.5)
    for slot, key in zip(slots, ("m2", "m3", "m4", "m5", "m6", "m8")):
        module = data.m8 if key == "m8" else data.m.get(key) or {}
        status = status_label(module)
        pc.text(key.upper(), Box(slot.x, slot.y, slot.w, 3.5), size=7.4, bold=True, align="center")
        pc.text(status, Box(slot.x, slot.y+4.1, slot.w, 7.2), size=7.1, minimum=6,
                bold=True, color=status_kind(status), align="center", max_lines=2,
                name=f"status.{key}")


def draw_summary(doc, i, n):
    data, pc = doc.data, PageCanvas(doc, i)
    profile = (doc.rc.get("profiles") or {}).get(data.profile, data.profile)
    pc.heading(i, n, "Tổng quan đầu tư", f"{data.company.get('name') or data.ticker} - hồ sơ {profile}",
               "INVESTMENT SNAPSHOT")
    eod_close = positive_price(data.close)
    close = live_price(data) or eod_close
    price_label, price_note = live_labels(data)
    base = positive_price(target_values(data).get("base"))
    gap = base/close-1 if base is not None and close is not None else None
    kpis = Box(pc.x, 48, pc.width, 25).columns(4)
    for index, (box, label, value, note, color) in enumerate(zip(
        kpis, ("Khuyến nghị", "Điểm tổng hợp", price_label, "Giá cơ sở"),
        (data.rating, score(data.score), number(close, " đ"), number(base, " đ")),
        (f"Điểm {score(data.score)}", "", price_note, "So với hiện tại "+fmt_pct_ratio(gap, signed=True) if gap is not None else "M4: "+status_label(data.m.get("m4") or {})),
        ("danger" if any(t in data.rating.casefold() for t in ("giảm", "bán")) else "blue", "blue", "teal", "caution"),
    )):
        pc.kpi(box, label, value, note, accent=color, name=f"kpi.{index}")
    left_width = pc.width*0.46
    left = Box(pc.x, 77, left_width, 66)
    right = Box(pc.x+left_width+COLUMN_GAP, 77, pc.width-left_width-COLUMN_GAP, 66)
    chart = pc.panel(left, "Đóng góp vào điểm tổng hợp", variant="blue", title_size=9.5)
    pc.text("Thanh dương hỗ trợ, thanh âm gây áp lực so với mức trung tính 50.",
            Box(chart.x, 87, chart.w, 8), size=7.2, max_lines=2, color="muted")
    pc.image(charts.contributions_chart(doc.theme, chart.w, 44, rows=contributions_rows(data)),
             Box(chart.x, 96, chart.w, 43))
    for y, title, evidence, variant in (
        (77, "Các yếu tố hỗ trợ điểm số", data.bull, "support"),
        (112, "Các yếu tố gây áp lực điểm số", data.bear, "danger"),
    ):
        content = pc.panel(Box(right.x, y, right.w, 31), title, variant=variant, title_size=9.2)
        items = [str(item.get("text", "")) if isinstance(item, dict) else str(item) for item in evidence[:3]]
        pc.bullets(items or ["Không có yếu tố nổi bật trong kết quả hiện tại."], content,
                   size=7.6, minimum=7, max_items=3, name=variant)
    scores = data.m7.get("scores") or {}
    table_w = pc.width*0.37
    content = pc.panel(Box(pc.x, 147, table_w, 44), "Điểm thành phần", title_size=9.4)
    pc.rows(content, [("Nhóm", "Điểm")]+[(lab, number(scores.get(key), "", 1))
            for key, lab in (("F", "Cơ bản"), ("T", "Kỹ thuật"), ("V", "Định giá"), ("S", "Tin tức"), ("R", "Rủi ro"))],
            header=True, size=7.8, name="components")
    content = pc.panel(Box(pc.x+table_w+COLUMN_GAP, 147, pc.width-table_w-COLUMN_GAP, 44),
                       "Tóm tắt đầu tư", title_size=9.5)
    view = []
    for key, label in (("F", "Nền tảng cơ bản"), ("V", "Điểm định giá"), ("T", "Điểm kỹ thuật")):
        if to_float(scores.get(key)) is not None:
            view.append(f"{label} {score(scores[key])}.")
    if to_float(scores.get("R")) is not None:
        view.append(f"Điểm rủi ro R {score(scores['R'])}; R càng cao nghĩa là rủi ro càng lớn.")
    pc.bullets(view, content, size=8.3, max_items=4, name="summary")
    draw_live_strip(pc, data)
    _quick_position(pc, data)
    _status_strip(pc, data)


def draw_fundamental_performance(doc, i, n):
    data, pc = doc.data, PageCanvas(doc, i)
    module = data.m.get("m2") or {}
    bank = bool(data.company.get("is_bank"))
    pc.heading(i, n, "Nền tảng tài chính", "Hiệu quả kinh doanh và các chỉ tiêu cơ bản", "M2 - FUNDAMENTAL")
    boxes = Box(pc.x, 48, pc.width, 25).columns(4)
    labels = ("Điểm cơ bản F", "ROE", "NIM", "CIR") if bank else ("Điểm cơ bản F", "ROE", "Tăng trưởng LNST", "Tăng trưởng doanh thu")
    keys = ("roe", "nim", "cir") if bank else ("roe", "net_income_growth", "revenue_growth")
    values = [score(module.get("score"))]+[fmt_pct_ratio(metric(module, key), na="N/A") for key in keys]
    notes = ["M2: "+status_label(module), "Hiệu quả sinh lời", "Biên lãi ròng" if bank else "YoY - M2", "Chi phí / thu nhập" if bank else "YoY - M2"]
    for index, (box, label, value, note) in enumerate(zip(boxes, labels, values, notes)):
        pc.kpi(box, label, value, note, accent=("blue", "blue", "support", "caution")[index], name=f"kpi.{index}")
    revenue_key, revenue_label = ("net_interest_income", "Thu nhập lãi thuần") if bank else ("revenue", "Doanh thu")
    periods, rev, ni = _series(data.annual, revenue_key)
    chart_w = pc.width*0.57
    chart_box = Box(pc.x, 77, chart_w, 58)
    content = pc.panel(chart_box, revenue_label+" và LNST", variant="blue", title_size=9.7)
    if periods and any(v is not None for v in rev+ni):
        pc.image(pcharts.annual_revenue_profit(doc.theme, content.w, 44, periods,
                 [float("nan") if v is None else v for v in rev],
                 [float("nan") if v is None else v for v in ni], label_a=revenue_label, legend_above=True),
                 Box(content.x, 88, content.w, 43))
    else:
        pc.text("Chưa có chuỗi BCTC năm.", content, max_lines=2, color="muted")
    content = pc.panel(Box(pc.x+chart_w+COLUMN_GAP, 77, pc.width-chart_w-COLUMN_GAP, 58),
                       "Điểm nhấn từ dữ liệu", variant="support", title_size=9.3)
    pc.bullets(annual_observations(periods, rev, ni, revenue_label), content,
               size=8, minimum=7.4, max_items=3, name="highlights")
    periods, rev, ni = _series(data.quarterly, revenue_key)
    quarterly_w = pc.width*0.63
    content = pc.panel(Box(pc.x, 139, quarterly_w, 57), "8 quý gần nhất", variant="blue")
    if periods and any(v is not None for v in rev+ni):
        pc.image(pcharts.annual_revenue_profit(doc.theme, content.w, 43, periods,
                 [float("nan") if v is None else v for v in rev],
                 [float("nan") if v is None else v for v in ni], label_a=revenue_label, legend_above=True),
                 Box(content.x, 150, content.w, 42))
    else:
        pc.text("Chưa có chuỗi BCTC quý.", content, max_lines=2, color="muted")
    content = pc.panel(Box(pc.x+quarterly_w+COLUMN_GAP, 139, pc.width-quarterly_w-COLUMN_GAP, 57),
                       "Chỉ tiêu M2 sử dụng", title_size=9.2)
    pc.rows(content, [("Chỉ tiêu", "Giá trị")]+ratio_rows(module, bank), size=7.4,
            value_fraction=0.4, header=True, name="ratios")
    health = pc.panel(Box(pc.x, 200, pc.width, 42), "Sức khỏe tài chính",
                      subtitle="Các chỉ tiêu M2 có số liệu; bố cục điều chỉnh theo loại doanh nghiệp.",
                      variant="blue", name="health")
    metrics = financial_health_metrics(module, bank)
    if metrics:
        boxes = Box(health.x, 217, health.w, 22).columns(len(metrics), CARD_GAP)
        for index, (box, (key, label, value)) in enumerate(zip(boxes, metrics)):
            pc.panel(box, name="health."+key)
            pc.text(label, Box(box.x+2, box.y+2.4, box.w-4, 7),
                    size=7.5, minimum=6.5, max_lines=2, color="muted", name="health."+key+".label")
            pc.text(value, Box(box.x+2, box.y+11, box.w-4, 7),
                    size=12.3, minimum=8.2, bold=True, name="health."+key+".value")
    else:
        pc.text("M2: "+status_label(module)+". Chưa có chỉ tiêu phù hợp.", health, max_lines=3, color="muted")
    content = pc.panel(Box(pc.x, 246, pc.width, 43), "Kết luận nền tảng",
                       subtitle="Tóm tắt định lượng từ các chỉ tiêu thực tế do M2 cung cấp.",
                       variant="support", name="conclusion")
    pc.bullets(conclusion_bullets(module, bank), content, size=8.2,
               minimum=7.3, max_items=5, name="conclusion")
