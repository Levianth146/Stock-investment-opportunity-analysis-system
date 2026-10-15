from __future__ import annotations

from xml.sax.saxutils import escape
from reportlab.platypus import Paragraph
from stockai.m9_report import charts
from stockai.m9_report import professional_charts as pcharts
from stockai.m9_report.data import metric
from stockai.m9_report.fmt import fmt_num, fmt_pct_ratio, fmt_score, to_float
from stockai.m9_report.layout import contributions_rows
from stockai.m9_report.theme import SANS, SANS_BOLD, SANS_SEMI
from stockai.m9_report.professional_layout import ProDoc, _clean_point, _period_rows, _value, _vnd_tril



def draw_fundamental_structure(doc: ProDoc, i:int,n:int)->None:
    d=doc.data; m2=d.m.get("m2") or {}; bank=bool(d.company.get("is_bank")); top=doc.heading(i,n,"Cấu trúc tài chính & dòng tiền","Bảng cân đối, thanh khoản và chất lượng dòng tiền","M1 + M2")
    if bank:
        doc.kpi(0,3,top,27,"NIM",fmt_pct_ratio(metric(m2,"nim")))
        doc.kpi(3,3,top,27,"CIR",fmt_pct_ratio(metric(m2,"cir")))
        doc.kpi(6,3,top,27,"Cho vay / huy động",fmt_pct_ratio(metric(m2,"loan_to_deposit")))
        doc.kpi(9,3,top,27,"Tỷ lệ nợ xấu",fmt_pct_ratio(metric(m2,"npl_ratio")))
    else:
        doc.kpi(0,3,top,27,"D/E",f"{fmt_num(metric(m2,'debt_to_equity'),2)}x")
        doc.kpi(3,3,top,27,"Nợ/Tài sản",fmt_pct_ratio(metric(m2,"debt_to_assets")))
        doc.kpi(6,3,top,27,"Current ratio",f"{fmt_num(metric(m2,'current_ratio'),2)}x")
        doc.kpi(9,3,top,27,"Khả năng trả lãi",f"{fmt_num(metric(m2,'interest_coverage'),2)}x")
    years,ai=_period_rows(d.annual); y=top+33
    def vals(k): return [_vnd_tril(_value(x,k)) or 0 for x in ai]
    doc.section_panel(0,7,y,60,"Quy mô tài sản, vốn chủ sở hữu và nợ phải trả",[], variant="blue")
    if years: doc.image(pcharts.lines_chart(doc.theme,doc.theme.span_mm(7)-8,44,years,[('Tổng tài sản',vals('total_assets'),'series_1'),('VCSH',vals('total_equity'),'series_3'),('Nợ phải trả',vals('total_liabilities'),'series_2')]),0,7,y+12,44)
    if bank:
        doc.section_panel(7,5,y,60,"Cho vay và tiền gửi khách hàng",[], variant="blue")
        if years: doc.image(pcharts.lines_chart(doc.theme,doc.theme.span_mm(5)-8,44,years,[('Cho vay',vals('customer_loans'),'series_1'),('Tiền gửi',vals('customer_deposits'),'series_3')]),7,5,y+12,44)
    else:
        doc.section_panel(7,5,y,60,"Thanh khoản ngắn hạn",[], variant="blue")
        if years: doc.image(pcharts.lines_chart(doc.theme,doc.theme.span_mm(5)-8,44,years,[('Tài sản NH',vals('current_assets'),'series_1'),('Nợ NH',vals('current_liabilities'),'series_2'),('Tồn kho',vals('inventory'),'series_3')]),7,5,y+12,44)
    y2=y+66
    ni=[_vnd_tril(_value(x,'net_income_parent','net_income')) or 0 for x in ai]; cfo=vals('cfo')
    if bank:
        nii=vals('net_interest_income')
        doc.section_panel(0,6,y2,59,"Thu nhập lãi thuần và lợi nhuận",[], variant="blue")
        if years: doc.image(pcharts.annual_revenue_profit(doc.theme,doc.theme.span_mm(6)-8,42,years,nii,ni,label_a='Thu nhập lãi thuần',label_b='LNST'),0,6,y2+12,42)
        nim=[(_value(x,'nim') or 0)*100 for x in ai]; cir=[(_value(x,'cir') or 0)*100 for x in ai]
        doc.section_panel(6,6,y2,59,"NIM và CIR theo năm",[], variant="blue")
        if years: doc.image(pcharts.lines_chart(doc.theme,doc.theme.span_mm(6)-8,42,years,[('NIM',nim,'series_3'),('CIR',cir,'series_2')],ylabel="%"),6,6,y2+12,42)
    else:
        doc.section_panel(0,6,y2,59,"LNST và dòng tiền kinh doanh",[], variant="blue")
        if years: doc.image(pcharts.annual_revenue_profit(doc.theme,doc.theme.span_mm(6)-8,42,years,cfo,ni,label_a='CFO',label_b='LNST'),0,6,y2+12,42)
        doc.section_panel(6,6,y2,59,"Ba dòng tiền chính",[])
        if years: doc.image(pcharts.cashflow_chart(doc.theme,doc.theme.span_mm(6)-8,42,years,cfo,vals('cfi'),vals('cff')),6,6,y2+12,42)
    # table raw latest annual - no forecast
    y3=y2+65
    rows=[]
    for yr,it in zip(years,ai):
        if bank:
            rows.append([yr,fmt_num(_vnd_tril(_value(it,'net_interest_income')),1),fmt_num(_vnd_tril(_value(it,'net_income_parent','net_income')),1),fmt_num(_vnd_tril(_value(it,'customer_loans')),1),fmt_num(_vnd_tril(_value(it,'customer_deposits')),1),fmt_pct_ratio(_value(it,'nim')),fmt_pct_ratio(_value(it,'cir'))])
        else:
            rows.append([yr,fmt_num(_vnd_tril(_value(it,'revenue')),1),fmt_num(_vnd_tril(_value(it,'net_income_parent','net_income')),1),fmt_num(_vnd_tril(_value(it,'total_assets')),1),fmt_num(_vnd_tril(_value(it,'total_equity')),1),fmt_num(_vnd_tril(_value(it,'cfo')),1),fmt_num(_value(it,'eps'))])
    if bank:
        table=doc.table(["Năm","Thu nhập lãi thuần","LNST","Cho vay","Tiền gửi","NIM","CIR"],rows,[16,29,24,26,26,18,18],right_cols=[1,2,3,4,5,6])
        caption=Paragraph("Đơn vị: nghìn tỷ đồng, trừ NIM và CIR (%).",doc.st.caption)
    else:
        table=doc.table(["Năm","Doanh thu","LNST","Tài sản","VCSH","CFO","EPS"],rows,[16,27,24,25,25,24,20],right_cols=[1,2,3,4,5,6])
        caption=Paragraph("Đơn vị: nghìn tỷ đồng, trừ EPS (đồng/cổ phiếu).",doc.st.caption)
    doc.section_panel(0,12,y3,48,"Bảng số liệu lịch sử",[table,caption])


def draw_valuation(doc: ProDoc,i:int,n:int)->None:
    d=doc.data; m4=d.m.get('m4') or {}; top=doc.heading(i,n,"Định giá tương đối","So sánh P/E và P/B với mức tham chiếu của mô hình","M4 - VALUATION")
    flags=set(m4.get('flags') or []); bench='Trung vị thị trường' if 'm4_sector_fallback' in flags else 'Trung vị ngành'
    pe=metric(m4,'pe'); pb=metric(m4,'pb'); mpe=metric(m4,'sector_median_pe'); mpb=metric(m4,'sector_median_pb')
    doc.kpi(0,3,top,27,"Điểm định giá V",f"{fmt_score(m4.get('score'))}/100")
    doc.kpi(3,3,top,27,"P/E",f"{fmt_num(pe,2)}x",f"{bench}: {fmt_num(mpe,2)}x")
    doc.kpi(6,3,top,27,"P/B",f"{fmt_num(pb,2)}x",f"{bench}: {fmt_num(mpb,2)}x")
    n_pe=to_float(metric(m4,'sector_n_pe')); n_pb=to_float(metric(m4,'sector_n_pb'))
    sample=f"{fmt_num(n_pe)} / {fmt_num(n_pb)}" if n_pe is not None or n_pb is not None else "n/a"
    doc.kpi(9,3,top,27,"Mẫu so sánh",sample,"P/E / P/B")
    y=top+33
    doc.section_panel(0,6,y,63,"P/E so với mức tham chiếu",[], variant="blue")
    doc.image(pcharts.valuation_compare(doc.theme,doc.theme.span_mm(6)-8,40,ticker=d.ticker,value=pe,median=mpe,label='P/E',benchmark_label=bench),0,6,y+12,40)
    note_pe=(f"P/E của {d.ticker} thấp hơn {bench.lower()}, hỗ trợ định giá." if pe is not None and mpe is not None and pe<mpe else f"P/E của {d.ticker} cao hơn {bench.lower()}, tạo áp lực lên định giá.") if pe is not None and mpe is not None else "Chưa đủ dữ liệu để so sánh P/E."
    doc.flow(0,6,y+50,10,[Paragraph(escape(note_pe),doc.st.body)])
    doc.section_panel(6,6,y,63,"P/B so với mức tham chiếu",[], variant="blue")
    doc.image(pcharts.valuation_compare(doc.theme,doc.theme.span_mm(6)-8,40,ticker=d.ticker,value=pb,median=mpb,label='P/B',benchmark_label=bench),6,6,y+12,40)
    note_pb=(f"P/B của {d.ticker} thấp hơn {bench.lower()}, hỗ trợ định giá." if pb is not None and mpb is not None and pb<mpb else f"P/B của {d.ticker} cao hơn {bench.lower()}, tạo áp lực lên định giá.") if pb is not None and mpb is not None else "Chưa đủ dữ liệu để so sánh P/B."
    doc.flow(6,6,y+50,10,[Paragraph(escape(note_pb),doc.st.body)])
    y2=y+69; tgt=d.target or {}; close=d.close; base=to_float(tgt.get('base'))
    doc.section_panel(0,12,y2,58,"Khoảng giá định giá",[], variant="blue")
    doc.image(pcharts.target_scale(doc.theme,doc.theme.span_mm(12)-8,33,bear=to_float(tgt.get('bear')),base=base,current=close,bull=to_float(tgt.get('bull'))),0,12,y2+14,33)
    if base and close:
        diff=base/close-1
        line=f"Giá cơ sở {fmt_num(base)} đồng {'cao' if diff>=0 else 'thấp'} hơn giá hiện tại {fmt_num(close)} đồng {fmt_pct_ratio(abs(diff))}."
        doc.flow(0,12,y2+47,8,[Paragraph(escape(line),doc.st.body)])
    y3=y2+64
    notes=[f"Điểm V đạt {fmt_score(m4.get('score'))}/100.",note_pe,note_pb]
    if base and close: notes.append(f"Giá cơ sở của M4/M7 là {fmt_num(base)} đồng, so với giá hiện tại {fmt_num(close)} đồng.")
    rel=m4.get('target_reliability') if isinstance(m4.get('target_reliability'),dict) else None
    if rel and rel.get('level')=='low' and rel.get('reason'): notes.append(str(rel['reason']))
    dcf=m4.get('dcf') if isinstance(m4.get('dcf'),dict) else None
    if dcf:
        if dcf.get('status')=='ok' and to_float(dcf.get('per_share')):
            used='đã đưa vào giá mục tiêu' if dcf.get('usable_for_target') else 'chưa đưa vào giá mục tiêu do lệch xa giá thị trường'
            notes.append(f"DCF (FCFF) cho {fmt_num(dcf.get('per_share'))} đồng/cp, WACC {fmt_pct_ratio(dcf.get('wacc'))}, tăng trưởng dài hạn {fmt_pct_ratio(dcf.get('terminal_growth'))}; {used}.")
        else:
            notes.append("DCF: "+str(dcf.get('reason') or 'không áp dụng hoặc chưa đủ dữ liệu')+".")
    doc.section_panel(0,12,y3,44,"Nhận định định giá",doc.bullets([escape(x) for x in notes[:5]]), variant="aqua")


from stockai.m9_report.pages.snapshot_pages import draw_summary, draw_fundamental_performance
