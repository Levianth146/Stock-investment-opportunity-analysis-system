from __future__ import annotations

import re
from xml.sax.saxutils import escape
from reportlab.platypus import Paragraph, Spacer
from stockai.m9_report import professional_charts as pcharts
from stockai.m9_report.data import metric
from stockai.m9_report.fmt import fmt_date, fmt_num, fmt_score, to_float
from stockai.m9_report.news_cluster import select_news_panel
from stockai.m9_report.text import reason_text, translate_flags
from stockai.m9_report.theme import SANS_SEMI
from stockai.m9_report.professional_layout import ProDoc



def draw_verification(doc: ProDoc,i:int,n:int)->None:
    d=doc.data; top=doc.heading(i,n,"Kiểm chứng & phương pháp","Các giới hạn dữ liệu và cách đọc kết quả","M8 - VERIFICATION")
    status={'pass':'Đạt','warn':'Có cảnh báo','fail':'Không đạt'}.get(str(d.m8.get('status')),str(d.m8.get('status') or 'n/a'))
    issues=[x for x in d.m8.get('issues') or [] if isinstance(x,dict)]
    n_warn=sum(1 for x in issues if str(x.get('severity')).lower() in ('warn','fail','error','fatal'))
    doc.kpi(0,4,top,28,"Kết quả kiểm chứng",status,f"{fmt_num(d.m8.get('checked'))} phép kiểm")
    doc.kpi(4,4,top,28,"Cảnh báo nghiêm trọng",fmt_num(n_warn))
    doc.kpi(8,4,top,28,"Ngày dữ liệu",fmt_date(d.as_of))
    y=top+34
    issue_items=[]
    if issues:
        for it in issues[:8]:
            sev=str(it.get('severity') or 'info').upper(); msg=str(it.get('message') or '')
            msg=re.sub(r"\bPeers?\b","Nhóm so sánh",msg,flags=re.I)
            msg=re.sub(r"\bas_of\b","ngày dữ liệu",msg,flags=re.I)
            issue_items.append(Paragraph(f'<font name="{SANS_SEMI}">{escape(sev)}</font> - {escape(msg)}',doc.st.body))
            issue_items.append(Spacer(1,3))
    else: issue_items=[Paragraph("Không có issue được M8 ghi nhận.",doc.st.body_2)]
    qflags=[f for f in d.all_flags() if str(f).startswith('quality_')]
    known,_=translate_flags(qflags,doc.flag_dict)
    for msg in known[:5]:
        issue_items.append(Paragraph(f'<font name="{SANS_SEMI}">LƯU Ý</font> - {escape(msg)}',doc.st.body))
        issue_items.append(Spacer(1,3))
    doc.section_panel(0,7,y,88,"Kiểm tra dữ liệu",issue_items, variant="warm" if n_warn else "aqua")
    scores=d.m7.get('scores') or {}; weights=d.m7.get('weights') or {}
    method=[]
    qg=d.m7.get('quality_gate') or {}
    if qg.get('tier') == 'limited' or 'quality_tier_limited' in d.snapshot_flags:
        method.append("Mã được chấm điểm có giới hạn do chất lượng dữ liệu; xem các lưu ý kiểm chứng bên trái.")
    method += [
        f"Điểm tổng hợp M7: {fmt_score(d.score)}/100, khuyến nghị {d.rating}.",
        f"F/T/V/S/R lần lượt: {fmt_score(scores.get('F'))} / {fmt_score(scores.get('T'))} / {fmt_score(scores.get('V'))} / {fmt_score(scores.get('S'))} / {fmt_score(scores.get('R'))}.",
        "R càng cao nghĩa là rủi ro càng lớn và được dùng như thành phần điều chỉnh điểm tổng hợp.",
        "Báo cáo không tự tạo forecast, consensus hoặc chỉ tiêu ngoài các module trước; DCF (nếu có) lấy từ M4.",
    ]
    doc.section_panel(7,5,y,88,"Cách đọc báo cáo",doc.bullets([escape(x) for x in method]), variant="blue")
    y2=y+94
    src=[]
    for s in d.sources[:10]:
        name=str(s.get('name') or s.get('source_id') or s.get('id') or 'Nguồn dữ liệu')
        url=str(s.get('url') or '')
        src.append(Paragraph(escape(name + (f" - {url}" if url else "")),doc.st.caption))
    doc.section_panel(0,12,y2,70,"Nguồn & lưu ý",src+[Spacer(1,4),Paragraph("Báo cáo phục vụ mục đích học thuật và minh họa hệ thống; không phải khuyến nghị đầu tư.",doc.st.body_2)], variant="aqua")


def draw_news(doc: ProDoc,i:int,n:int)->None:
    d=doc.data; m5=d.m.get('m5') or {}; top=doc.heading(i,n,"Tin tức & Sentiment","Phân loại tiêu đề tin và mức độ hỗ trợ từ M5","M5 - NEWS & SENTIMENT")
    score=to_float(m5.get('score')); s_txt=f"{fmt_score(score)}/100" if score is not None else "Chưa đủ dữ liệu"
    doc.kpi(0,3,top,27,"Điểm tin tức S",s_txt,"M7 dùng 50 trung tính" if score is None and 'S_missing_used_neutral' in (d.m7.get('flags') or []) else "")
    doc.kpi(3,3,top,27,"Story liên quan",fmt_num(metric(m5,'news_relevant_count')))
    doc.kpi(6,3,top,27,"Nguồn dữ liệu",fmt_num(metric(m5,'news_distinct_sources')))
    conf=metric(m5,'sentiment_confidence'); doc.kpi(9,3,top,27,"Confidence",fmt_num(conf,2) if conf is not None else "Không chấm")
    y=top+33
    pos=metric(m5,'news_positive_count') or 0; neu=metric(m5,'news_neutral_count') or 0; neg=metric(m5,'news_negative_count') or 0
    doc.section_panel(0,6,y,60,"Phân loại story",[], variant="blue")
    doc.image(pcharts.sentiment_distribution(doc.theme,doc.theme.span_mm(6)-8,42,positive=pos,neutral=neu,negative=neg),0,6,y+12,42)
    scope=[f"{fmt_num(metric(m5,'news_relevant_count'))} story liên quan.",f"{fmt_num(metric(m5,'news_distinct_sources'))} nguồn tin khác nhau."]
    lb=_lookback_from_evidence(m5)
    if lb: scope.append(f"Cửa sổ phân tích: {lb} ngày.")
    if 'm5_heuristic_headline_only' in (m5.get('flags') or []): scope.append("M5 dùng heuristic/lexicon trên tiêu đề, không phân tích toàn văn bài báo.")
    if score is None and 'S_missing_used_neutral' in (d.m7.get('flags') or []): scope.append("M5 không đủ điều kiện chấm S; M7 dùng mức trung tính 50 khi tổng hợp điểm.")
    doc.section_panel(6,6,y,60,"M5 xử lý gì?",doc.bullets([escape(x) for x in scope]), variant="aqua")
    y2=y+66
    panel=select_news_panel(d.news,ticker=d.ticker,company=d.company,as_of=d.as_of,max_items=6,max_negatives=3)
    items=[]
    for idx,it in enumerate(panel,1):
        lab=str(it.get('label') or ''); title=str(it.get('title') or '')
        src=str(it.get('source') or ''); dt=fmt_date(it.get('published_at'),na='')
        color=doc.theme.c['series_3'] if lab=='Tích cực' else (doc.theme.c['down'] if lab=='Tiêu cực' else doc.theme.c['ink_3'])
        items.append(Paragraph(f'<font name="{SANS_SEMI}" color="{color}">{idx}. {escape(lab)}</font>  {escape(title)}<br/><font size="7" color="{doc.theme.c["ink_3"]}">{escape(" | ".join(x for x in (src,dt) if x))}</font>',doc.st.body))
        items.append(Spacer(1,4))
    if not items: items=[Paragraph("Không có tiêu đề phù hợp để hiển thị trong cửa sổ dữ liệu.",doc.st.body_2)]
    doc.section_panel(0,12,y2,108,"Các tiêu đề được M5 sử dụng / phân loại",items,"Mỗi dòng là một story đại diện sau bước lọc và gom sự kiện.", variant="blue")


def _lookback_from_evidence(m5: dict) -> str | None:
    for ev in m5.get('evidence') or []:
        t=str(ev.get('text') or '') if isinstance(ev,dict) else str(ev)
        m=re.search(r'lookback=(\d+)d',t)
        if m: return m.group(1)
    return None
