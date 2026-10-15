from __future__ import annotations

from xml.sax.saxutils import escape
from reportlab.platypus import Paragraph
from stockai.m9_report import professional_charts as pcharts
from stockai.m9_report.data import ReportData, metric
from stockai.m9_report.fmt import fmt_num, fmt_pct_points, fmt_score
from stockai.m9_report.professional_layout import ProDoc



def draw_technical(doc: ProDoc,i:int,n:int)->None:
    d=doc.data; m3=d.m.get('m3') or {}; top=doc.heading(i,n,"Phân tích kỹ thuật","Diễn biến giá và các chỉ báo kỹ thuật","M3 - TECHNICAL")
    doc.kpi(0,3,top,27,"Điểm kỹ thuật T",f"{fmt_score(m3.get('score'))}/100")
    doc.kpi(3,3,top,27,"RSI 14",fmt_num(metric(m3,'rsi14'),1))
    doc.kpi(6,3,top,27,"Volume ratio",f"{fmt_num(metric(m3,'volume_ratio_20'),2)}x")
    doc.kpi(9,3,top,27,"ATR",fmt_pct_points(metric(m3,'atr_pct')))
    y=top+33
    doc.section_panel(0,12,y,76,f"Giá đóng cửa và đường trung bình - {len(d.closes)} phiên",[], variant="blue")
    doc.image(pcharts.price_ma_chart(doc.theme,doc.theme.span_mm(12)-8,58,dates=d.dates,close=d.closes,ma20=d.ma.get('MA20') or [],ma50=d.ma.get('MA50') or [],ma200=d.ma.get('MA200') or []),0,12,y+12,58)
    y2=y+82
    doc.section_panel(0,6,y2,61,"RSI 14",[], variant="blue")
    if _series_match(d,'rsi14','rsi14'):
        doc.image(pcharts.rsi_chart(doc.theme,doc.theme.span_mm(6)-8,43,dates=d.dates,rsi=d.tech_series['rsi14']),0,6,y2+12,43)
    else:
        doc.flow(0,6,y2+20,20,[Paragraph("Không hiển thị chuỗi RSI vì giá trị cuối không khớp output M3.",doc.st.body_2)])
    doc.section_panel(6,6,y2,61,"MACD",[], variant="blue")
    if _series_match(d,'macd','macd') and _series_match(d,'macd_signal','macd_signal'):
        doc.image(pcharts.macd_chart(doc.theme,doc.theme.span_mm(6)-8,43,dates=d.dates,macd=d.tech_series['macd'],signal=d.tech_series['macd_signal'],hist=d.tech_series['macd_histogram']),6,6,y2+12,43)
    else:
        doc.flow(6,6,y2+20,20,[Paragraph("Không hiển thị chuỗi MACD vì giá trị cuối không khớp output M3.",doc.st.body_2)])
    y3=y2+67
    close=metric(m3,'close'); ma20=metric(m3,'ma20'); ma50=metric(m3,'ma50'); ma200=metric(m3,'ma200'); rsi=metric(m3,'rsi14'); vr=metric(m3,'volume_ratio_20')
    notes=[]
    if all(v is not None for v in (close,ma20,ma50,ma200)):
        pos=sum(close>v for v in (ma20,ma50,ma200)); notes.append(f"Giá hiện tại {fmt_num(close)} đồng nằm trên {pos}/3 đường MA20, MA50 và MA200.")
    if rsi is not None: notes.append(f"RSI 14 ở mức {fmt_num(rsi,1)}; ngưỡng 30 và 70 được hiển thị trực tiếp trên đồ thị.")
    if vr is not None: notes.append(f"Volume ratio 20 phiên là {fmt_num(vr,2)}x.")
    doc.section_panel(0,12,y3,38,"Nhận định kỹ thuật",doc.bullets([escape(x) for x in notes]), variant="aqua")


def draw_risk(doc: ProDoc,i:int,n:int)->None:
    d=doc.data; m6=d.m.get('m6') or {}; top=doc.heading(i,n,"Phân tích rủi ro","Biến động, drawdown và thước đo rủi ro thị trường","M6 - RISK")
    doc.kpi(0,3,top,27,"Điểm rủi ro R",f"{fmt_score(m6.get('score'))}/100","R càng cao, rủi ro càng lớn",accent=doc.theme.c['down'])
    doc.kpi(3,3,top,27,"Biến động năm hóa",fmt_pct_points(metric(m6,'annualized_volatility')))
    doc.kpi(6,3,top,27,"Beta",fmt_num(metric(m6,'beta'),2),"So với VN-Index")
    doc.kpi(9,3,top,27,"Max drawdown",fmt_pct_points(metric(m6,'max_drawdown')))
    y=top+33
    doc.section_panel(0,8,y,68,"Drawdown trong cửa sổ rủi ro",[], variant="blue")
    doc.image(pcharts.drawdown_chart(doc.theme,doc.theme.span_mm(8)-8,50,dates=d.dates,close=d.closes),0,8,y+12,50)
    doc.section_panel(8,4,y,68,"Số phiên tăng/giảm",[], variant="blue")
    pos=metric(m6,'positive_sessions') or 0; neg=metric(m6,'negative_sessions') or 0
    doc.image(pcharts.sessions_donut(doc.theme,doc.theme.span_mm(4)-8,38,positive=pos,negative=neg),8,4,y+13,38)
    doc.flow(8,4,y+51,12,[Paragraph(escape(f"Phiên tăng: {fmt_num(pos)} | Phiên giảm: {fmt_num(neg)}"),doc.st.body)])
    y2=y+74
    risk_rows=[
        ["Biến động năm hóa",fmt_pct_points(metric(m6,'annualized_volatility'))],
        ["Beta",fmt_num(metric(m6,'beta'),2)],
        ["Max drawdown",fmt_pct_points(metric(m6,'max_drawdown'))],
        ["VaR 95% - 1 phiên",fmt_pct_points(metric(m6,'historical_var_95'))],
        ["CVaR 95% - 1 phiên",fmt_pct_points(metric(m6,'historical_cvar_95'))],
    ]
    doc.section_panel(0,5,y2,58,"Các thước đo rủi ro",[doc.table(["Chỉ tiêu","Giá trị"],risk_rows,[doc.theme.span_mm(5)-30,30],right_cols=[1])])
    notes=[f"Điểm rủi ro R là {fmt_score(m6.get('score'))}/100.",f"Beta {fmt_num(metric(m6,'beta'),2)} phản ánh độ nhạy của {d.ticker} so với VN-Index.",f"Max drawdown trong cửa sổ là {fmt_pct_points(metric(m6,'max_drawdown'))}.","VaR và CVaR là ước tính lịch sử một phiên, không phải mức lỗ tối đa chắc chắn."]
    doc.section_panel(5,7,y2,58,"Nhận định rủi ro",doc.bullets([escape(x) for x in notes]), variant="warm")


def _series_match(d: ReportData, key: str, m3_key: str, tol=0.02) -> bool:
    vals=d.tech_series.get(key) or []; last=next((v for v in reversed(vals) if v is not None),None); ref=metric(d.m.get('m3'),m3_key)
    if last is None or ref is None: return False
    return abs(last-ref) <= max(tol,abs(ref)*1e-6)
