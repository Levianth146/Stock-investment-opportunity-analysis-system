"""Biểu đồ cho layout báo cáo chuyên nghiệp M9.

Mọi chuỗi đều nhận từ ReportData (snapshot M1) hoặc output M2-M6; module này chỉ trực quan hóa,
không tạo dữ liệu tài chính mới hay gọi mạng.
"""
from __future__ import annotations

import io
from typing import Sequence

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import FancyBboxPatch
from matplotlib.ticker import FuncFormatter, MaxNLocator

from stockai.m9_report.fmt import fmt_num
from stockai.m9_report.theme import Theme


def _fig(w_mm: float, h_mm: float):
    return plt.figure(figsize=(w_mm / 25.4, h_mm / 25.4), dpi=140)


def _png(fig, theme: Theme) -> io.BytesIO:
    buf = io.BytesIO()
    bg = theme.c.get("chart_bg", "#FFFFFF")
    fig.savefig(buf, format="png", dpi=int(theme.cfg["charts"].get("dpi", 220)), facecolor=bg,
                bbox_inches="tight", pad_inches=0.02)
    plt.close(fig)
    buf.seek(0)
    return buf


def _style(ax, theme: Theme, *, ygrid: bool = True):
    c = theme.c
    ax.set_facecolor(theme.c.get("chart_bg", "#FFFFFF"))
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color(c["rule"])
    ax.spines["bottom"].set_color(c["rule"])
    ax.tick_params(colors=c["ink_3"], labelsize=7, length=2.5)
    if ygrid:
        ax.grid(axis="y", color=c["rule"], linewidth=0.6, alpha=0.7)
        ax.set_axisbelow(True)


def _bn_tick(x, _):
    return f"{x:.0f}".replace("-", "-")


def _pct_tick(x, _):
    return f"{x:.0f}%"


def annual_revenue_profit(theme: Theme, w_mm: float, h_mm: float, years: Sequence[str], revenue: Sequence[float],
                          profit: Sequence[float], *, label_a: str = "Doanh thu", label_b: str = "LNST",
                          legend_above: bool = False) -> io.BytesIO:
    c = theme.c
    fig = _fig(w_mm, h_mm)
    ax = fig.add_axes([0.11, 0.18, 0.84, 0.61 if legend_above else 0.73])
    _style(ax, theme)
    x = np.arange(len(years)); width = 0.34
    ax.bar(x - width/2, revenue, width, color=c["series_1"], label=label_a)
    ax.bar(x + width/2, profit, width, color=c["series_3"], label=label_b)
    ax.set_xticks(x); ax.set_xticklabels(years)
    ax.yaxis.set_major_locator(MaxNLocator(5)); ax.yaxis.set_major_formatter(FuncFormatter(_bn_tick))
    ax.set_ylabel("Nghìn tỷ đồng", fontsize=7, color=c["ink_3"])
    ax.legend(frameon=False, fontsize=7, ncols=2, loc="upper left",
              **({"bbox_to_anchor": (0, 1.28)} if legend_above else {}))
    return _png(fig, theme)


def quarterly_revenue_profit(theme: Theme, w_mm: float, h_mm: float, periods: Sequence[str], revenue: Sequence[float],
                             profit: Sequence[float]) -> io.BytesIO:
    return annual_revenue_profit(theme, w_mm, h_mm, periods, revenue, profit)


def lines_chart(theme: Theme, w_mm: float, h_mm: float, xlabels: Sequence[str], series: Sequence[tuple[str, Sequence[float], str]],
                *, ylabel: str = "Nghìn tỷ đồng") -> io.BytesIO:
    c = theme.c
    fig = _fig(w_mm, h_mm)
    ax = fig.add_axes([0.12, 0.18, 0.82, 0.72])
    _style(ax, theme)
    for label, vals, ck in series:
        ax.plot(range(len(xlabels)), vals, marker="o", markersize=3, linewidth=1.5, color=c[ck], label=label)
    ax.set_xticks(range(len(xlabels))); ax.set_xticklabels(xlabels)
    ax.yaxis.set_major_locator(MaxNLocator(5)); ax.yaxis.set_major_formatter(FuncFormatter(_bn_tick))
    ax.set_ylabel(ylabel, fontsize=7, color=c["ink_3"])
    ax.legend(frameon=False, fontsize=6.8, ncols=min(3, len(series)), loc="upper left")
    return _png(fig, theme)


def cashflow_chart(theme: Theme, w_mm: float, h_mm: float, years: Sequence[str], cfo: Sequence[float], cfi: Sequence[float],
                   cff: Sequence[float]) -> io.BytesIO:
    c = theme.c
    fig = _fig(w_mm, h_mm)
    ax = fig.add_axes([0.12, 0.18, 0.82, 0.72]); _style(ax, theme)
    x = np.arange(len(years)); width = 0.24
    ax.axhline(0, color=c["axis"], linewidth=0.7)
    ax.bar(x-width, cfo, width, label="CFO", color=c["series_1"])
    ax.bar(x, cfi, width, label="CFI", color=c["series_2"])
    ax.bar(x+width, cff, width, label="CFF", color=c["series_3"])
    ax.set_xticks(x); ax.set_xticklabels(years)
    ax.yaxis.set_major_locator(MaxNLocator(5)); ax.yaxis.set_major_formatter(FuncFormatter(_bn_tick))
    ax.set_ylabel("Nghìn tỷ đồng", fontsize=7, color=c["ink_3"])
    ax.legend(frameon=False, fontsize=7, ncols=3, loc="upper left")
    return _png(fig, theme)


def valuation_compare(theme: Theme, w_mm: float, h_mm: float, *, ticker: str, value: float | None,
                      median: float | None, label: str, benchmark_label: str) -> io.BytesIO:
    c = theme.c
    fig = _fig(w_mm, h_mm)
    ax = fig.add_axes([0.08, 0.20, 0.88, 0.68]); ax.axis("off")
    vals = [value or 0, median or 0]
    maxv = max(vals + [1]) * 1.15
    ys = [0.67, 0.28]
    cols = [c["series_1"], c["axis"]]
    labs = [ticker, benchmark_label]
    for y, v, col, lab in zip(ys, vals, cols, labs):
        ax.add_patch(FancyBboxPatch((0.20, y-0.06), 0.70, 0.12, boxstyle="round,pad=0.01,rounding_size=0.025",
                                    facecolor="#E8EDF3", edgecolor="none"))
        ax.add_patch(FancyBboxPatch((0.20, y-0.06), 0.70*(v/maxv), 0.12,
                                    boxstyle="round,pad=0.01,rounding_size=0.025", facecolor=col, edgecolor="none"))
        ax.text(0.01, y, lab, va="center", fontsize=8, color=c["ink"], fontproperties=theme.mpl["semibold"])
        ax.text(0.94, y, f"{v:.2f}x" if v else "n/a", va="center", ha="right", fontsize=9, color=c["ink"],
                fontproperties=theme.mpl["semibold"])
    ax.text(0.01, 0.95, label, va="top", fontsize=9, color=c["ink"], fontproperties=theme.mpl["semibold"])
    return _png(fig, theme)


def target_scale(theme: Theme, w_mm: float, h_mm: float, *, bear: float | None, base: float | None,
                 current: float | None, bull: float | None) -> io.BytesIO:
    c = theme.c
    vals = [("Bear", bear, c["down"]), ("Base", base, c["series_1"]), ("Giá hiện tại", current, c["ink"]),
            ("Bull", bull, c["series_3"])]
    nums = [float(v) for _, v, _ in vals if v is not None]
    fig = _fig(w_mm, h_mm)
    ax = fig.add_axes([0.05, 0.08, 0.90, 0.82]); ax.axis("off"); ax.set_xlim(0, 1); ax.set_ylim(0, 1)
    if not nums:
        return _png(fig, theme)
    lo, hi = min(nums), max(nums); span = hi-lo or max(abs(hi), 1)*0.1
    lo -= span*0.08; hi += span*0.08
    def xn(v): return 0.06 + 0.88*(v-lo)/(hi-lo)
    ax.plot([0.06, 0.94], [0.42, 0.42], color="#DCE6F1", linewidth=6, solid_capstyle="round")
    for idx, (lab, v, col) in enumerate(vals):
        if v is None: continue
        x = xn(float(v))
        ax.scatter([x], [0.42], s=75, color=col, edgecolors="white", linewidth=1.2, zorder=5)
        top = idx % 2 == 0
        ax.text(x, 0.70 if top else 0.12, lab, ha="center", va="center", fontsize=7, color=col,
                fontproperties=theme.mpl["semibold"])
        ax.text(x, 0.57 if top else 0.25, fmt_num(v), ha="center", va="center", fontsize=8, color=c["ink"],
                fontproperties=theme.mpl["semibold"])
    return _png(fig, theme)


def price_ma_chart(theme: Theme, w_mm: float, h_mm: float, *, dates: Sequence[str], close: Sequence[float],
                   ma20: Sequence[float | None], ma50: Sequence[float | None], ma200: Sequence[float | None]) -> io.BytesIO:
    c = theme.c
    fig = _fig(w_mm, h_mm)
    ax = fig.add_axes([0.08, 0.15, 0.88, 0.75]); _style(ax, theme)
    x = np.arange(len(close))
    ax.plot(x, close, color=c["ink"], linewidth=1.15, label="Giá đóng cửa")
    for vals, lab, ck in ((ma20, "MA20", "series_1"), (ma50, "MA50", "series_3"), (ma200, "MA200", "series_2")):
        xs=[i for i,v in enumerate(vals) if v is not None]; ys=[v for v in vals if v is not None]
        if xs: ax.plot(xs, ys, linewidth=1.1, color=c[ck], label=lab)
    if len(dates):
        ticks=np.linspace(0,len(dates)-1,min(6,len(dates))).astype(int)
        ax.set_xticks(ticks); ax.set_xticklabels([dates[i][5:7]+"/"+dates[i][:4] for i in ticks])
    ax.yaxis.set_major_locator(MaxNLocator(6)); ax.yaxis.set_major_formatter(FuncFormatter(lambda x,_: f"{x:,.0f}".replace(",",".")))
    ax.set_ylabel("VND", fontsize=7, color=c["ink_3"])
    ax.legend(frameon=False, fontsize=7, ncols=4, loc="upper left")
    return _png(fig, theme)


def rsi_chart(theme: Theme, w_mm: float, h_mm: float, *, dates: Sequence[str], rsi: Sequence[float | None]) -> io.BytesIO:
    c=theme.c; fig=_fig(w_mm,h_mm); ax=fig.add_axes([0.09,0.18,0.87,0.72]); _style(ax,theme)
    xs=[i for i,v in enumerate(rsi) if v is not None]; ys=[v for v in rsi if v is not None]
    if xs: ax.plot(xs,ys,color=c["series_1"],linewidth=1.3)
    ax.axhline(70,color=c["down"],linestyle="--",linewidth=0.8); ax.axhline(30,color=c["up"],linestyle="--",linewidth=0.8)
    ax.fill_between(range(len(rsi)),70,100,color=c["down"],alpha=0.05); ax.fill_between(range(len(rsi)),0,30,color=c["up"],alpha=0.05)
    ax.set_ylim(0,100); ax.set_yticks([0,30,50,70,100]); ax.yaxis.set_major_formatter(FuncFormatter(_pct_tick))
    if dates:
        ticks=np.linspace(0,len(dates)-1,min(5,len(dates))).astype(int); ax.set_xticks(ticks); ax.set_xticklabels([dates[i][5:7]+"/"+dates[i][:4] for i in ticks])
    return _png(fig,theme)


def macd_chart(theme: Theme, w_mm: float, h_mm: float, *, dates: Sequence[str], macd: Sequence[float | None],
               signal: Sequence[float | None], hist: Sequence[float | None]) -> io.BytesIO:
    c=theme.c; fig=_fig(w_mm,h_mm); ax=fig.add_axes([0.10,0.18,0.86,0.72]); _style(ax,theme)
    xs=np.arange(len(dates)); hv=np.array([0 if v is None else v for v in hist],dtype=float)
    ax.bar(xs,hv,color=[c["series_3"] if v>=0 else c["down"] for v in hv],width=0.75,alpha=0.75,label="Histogram")
    for vals,lab,ck in ((macd,"MACD","series_1"),(signal,"Signal","series_2")):
        xx=[i for i,v in enumerate(vals) if v is not None]; yy=[v for v in vals if v is not None]
        if xx: ax.plot(xx,yy,color=c[ck],linewidth=1.15,label=lab)
    ax.axhline(0,color=c["axis"],linewidth=0.7)
    if dates:
        ticks=np.linspace(0,len(dates)-1,min(5,len(dates))).astype(int); ax.set_xticks(ticks); ax.set_xticklabels([dates[i][5:7]+"/"+dates[i][:4] for i in ticks])
    ax.yaxis.set_major_locator(MaxNLocator(5)); ax.legend(frameon=False,fontsize=7,ncols=3,loc="upper left")
    return _png(fig,theme)


def drawdown_chart(theme: Theme, w_mm: float, h_mm: float, *, dates: Sequence[str], close: Sequence[float]) -> io.BytesIO:
    c=theme.c; fig=_fig(w_mm,h_mm); ax=fig.add_axes([0.09,0.18,0.87,0.72]); _style(ax,theme)
    peak=-float("inf"); dds=[]
    for p in close:
        peak=max(peak,p); dds.append((p/peak-1)*100 if peak>0 else 0)
    x=np.arange(len(dds)); ax.plot(x,dds,color=c["down"],linewidth=1.3); ax.fill_between(x,dds,0,color=c["down"],alpha=0.12)
    ax.axhline(0,color=c["axis"],linewidth=0.7); ax.yaxis.set_major_formatter(FuncFormatter(_pct_tick))
    if dates:
        ticks=np.linspace(0,len(dates)-1,min(6,len(dates))).astype(int); ax.set_xticks(ticks); ax.set_xticklabels([dates[i][5:7]+"/"+dates[i][:4] for i in ticks])
    return _png(fig,theme)


def sessions_donut(theme: Theme, w_mm: float, h_mm: float, *, positive: float, negative: float) -> io.BytesIO:
    c=theme.c; fig=_fig(w_mm,h_mm); ax=fig.add_axes([0.08,0.08,0.84,0.84]); ax.axis("equal"); ax.axis("off")
    vals=[max(0,positive),max(0,negative)]; total=sum(vals)
    if total<=0: vals=[1,0]; total=1
    ax.pie(vals,colors=[c["series_3"],c["down"]],startangle=90,counterclock=False,
           wedgeprops={"width":0.28,"edgecolor":"white"})
    ax.text(0,0.08,fmt_num(total),ha="center",va="center",fontsize=15,color=c["ink"],fontproperties=theme.mpl["bold"])
    ax.text(0,-0.15,"phiên",ha="center",va="center",fontsize=8,color=c["ink_3"])
    return _png(fig,theme)


def sentiment_distribution(theme: Theme, w_mm: float, h_mm: float, *, positive: float, neutral: float, negative: float) -> io.BytesIO:
    c=theme.c; fig=_fig(w_mm,h_mm); ax=fig.add_axes([0.18,0.14,0.76,0.76]); _style(ax,theme,ygrid=False)
    labels=["Tích cực","Trung tính","Tiêu cực"]; vals=[positive,neutral,negative]
    cols=[c["series_3"],c["axis"],c["down"]]
    y=np.arange(3); ax.barh(y,vals,color=cols,height=0.42); ax.set_yticks(y); ax.set_yticklabels(labels); ax.invert_yaxis(); ax.xaxis.set_major_locator(MaxNLocator(integer=True)); ax.grid(axis="x",color=c["rule"],linewidth=0.6,alpha=0.6)
    for yi,v in zip(y,vals): ax.text(v+max(vals+[1])*0.02,yi,fmt_num(v),va="center",fontsize=8,color=c["ink"])
    return _png(fig,theme)
