"""Biểu đồ matplotlib cho M9: PNG 300 dpi, đúng kích thước khung, cùng phông với PDF.

Quy ước chung: một trục y mỗi biểu đồ, lưới ngang mảnh, không lưới dọc, không viền khung,
nhãn trực tiếp ở đầu mút, chỉ ghi giá trị ở điểm cuối hoặc cực trị.
"""
from __future__ import annotations

import io
from dataclasses import dataclass
from typing import Any, Sequence

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyBboxPatch, Rectangle  # noqa: E402
from matplotlib.ticker import FuncFormatter, MaxNLocator  # noqa: E402

from stockai.m9_report.fmt import fmt_num, fmt_signed, to_float  # noqa: E402
from stockai.m9_report.theme import Theme  # noqa: E402

MM = 1 / 25.4
TICK_PT = 7.5
LABEL_PT = 7.5


@dataclass
class Ruler:
    """Ngưỡng và nhãn vùng của thước điểm (đọc từ config/scoring.yaml)."""

    thresholds: list[float]
    labels: list[str]


def ruler_from_scoring(scoring_cfg: dict) -> Ruler:
    """ratings: [{min, label}] giảm dần -> ngưỡng tăng dần + nhãn vùng từ thấp tới cao."""
    rows = [r for r in (scoring_cfg.get("ratings") or []) if isinstance(r, dict) and "min" in r]
    rows = sorted(rows, key=lambda r: float(r["min"]))
    thresholds = [float(r["min"]) for r in rows if float(r["min"]) > 0]
    labels = [str(r.get("label")) for r in rows]
    return Ruler(thresholds=thresholds, labels=labels)


def _fig(w_mm: float, h_mm: float):
    fig = plt.figure(figsize=(w_mm * MM, h_mm * MM), dpi=100)
    fig.patch.set_facecolor("#FFFFFF")
    return fig


def _png(fig, theme: Theme) -> io.BytesIO:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=int(theme.cfg["charts"]["dpi"]), facecolor="#FFFFFF")
    plt.close(fig)
    buf.seek(0)
    return buf


def _style(ax, theme: Theme, *, ygrid: bool = True, xaxis: bool = True) -> None:
    c = theme.c
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_visible(xaxis)
    ax.spines["bottom"].set_color(c["axis"])
    ax.spines["bottom"].set_linewidth(0.6)
    ax.tick_params(axis="both", colors=c["ink_2"], labelsize=TICK_PT, length=0, pad=3)
    ax.tick_params(axis="x", length=2.5 if xaxis else 0, color=c["axis"], width=0.5)
    ax.grid(False)
    if ygrid:
        ax.yaxis.grid(True, color=c["rule"], linewidth=0.5, linestyle="-")
    ax.set_axisbelow(True)
    ax.set_facecolor("#FFFFFF")


def _vi_tick(decimals: int = 0):
    return FuncFormatter(lambda v, _pos: fmt_num(v, decimals))


# --------------------------------------------------------------------------- thước điểm


def score_ruler(
    theme: Theme,
    w_mm: float,
    h_mm: float,
    *,
    ruler: Ruler,
    score: float | None,
    main_label: str,
    universe: Sequence[float] = (),
    other_score: float | None = None,
    other_label: str | None = None,
) -> io.BytesIO:
    """Thước 0-100: vạch ngưỡng, nhãn vùng, vạch mảnh cho mọi mã cùng profile, dấu mã đang xem."""
    c = theme.c
    fig = _fig(w_mm, h_mm)
    pad = 1.5 / w_mm * 100
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(-pad * 1.2, 100 + pad * 1.2)
    ax.set_ylim(0, 1)
    ax.axis("off")

    y_bar = 0.52
    bar_h = 0.05 if h_mm > 22 else 0.07
    ax.add_patch(Rectangle((0, y_bar - bar_h / 2), 100, bar_h, color=c["rule"], lw=0, zorder=1))
    for s in universe:
        v = to_float(s)
        if v is None:
            continue
        ax.plot([v, v], [y_bar - bar_h * 1.3, y_bar + bar_h * 1.3], color=c["axis"], lw=0.4, zorder=2,
                solid_capstyle="butt")
    for t in ruler.thresholds:
        ax.plot([t, t], [y_bar - bar_h * 2.0, y_bar + bar_h * 2.0], color=c["ink_2"], lw=0.8, zorder=3,
                solid_capstyle="butt")
    y_num = y_bar - bar_h * 2.0 - 0.04
    for t in [0.0, *ruler.thresholds, 100.0]:
        ha = "left" if t <= 0 else ("right" if t >= 100 else "center")
        ax.text(t, y_num, fmt_num(t), ha=ha, va="top", fontsize=TICK_PT, color=c["ink_3"])
    edges = [0.0, *ruler.thresholds, 100.0]
    y_zone = y_num - 0.14
    char_mm = LABEL_PT * 0.52 / 72 * 25.4
    # Xen kẽ hai hàng nhãn để không xuống dòng chồng chữ khi vùng hẹp
    for i, lab in enumerate(ruler.labels):
        if i + 1 >= len(edges):
            break
        mid = (edges[i] + edges[i + 1]) / 2
        zone_mm = (edges[i + 1] - edges[i]) / 100 * w_mm
        short = lab
        if len(lab) * char_mm > zone_mm * 0.95:
            # Rút gọn thay vì wrap nhiều dòng (tránh chồng nhãn)
            short_map = {
                "Giảm tỷ trọng": "Giảm tỷ trọng",
                "Nắm giữ": "Nắm giữ",
                "Mua mạnh": "Mua mạnh",
            }
            short = short_map.get(lab, lab)
            if len(short) * char_mm > zone_mm * 0.98 and " " in short:
                # Hàng xen kẽ thay vì xuống dòng trong cùng ô
                short = short.replace("Giảm tỷ trọng", "Giảm\u00a0tỷ\u00a0trọng")
        y_lab = y_zone - (0.11 if i % 2 else 0.0)
        ax.text(mid, y_lab, short, ha="center", va="top", fontsize=LABEL_PT, color=c["ink_2"],
                linespacing=1.05)

    def _ha(x: float, label: str, size: float) -> str:
        """Căn nhãn theo bề rộng ước tính để không tràn mép thước."""
        half = len(label) * size * 0.55 / 72 * 25.4 / 2
        pos = x / 100 * w_mm
        if pos < half:
            return "left"
        if w_mm - pos < half:
            return "right"
        return "center"

    if to_float(other_score) is not None:
        o = float(other_score)
        ax.scatter([o], [y_bar], s=22, facecolor="#FFFFFF", edgecolor=c["ink_2"], linewidths=1.0, zorder=5)
        if other_label:
            ax.text(o, 0.97, other_label, ha=_ha(o, other_label, LABEL_PT), va="top", fontsize=LABEL_PT,
                    color=c["ink_2"])
    if to_float(score) is not None:
        s = float(score)
        ax.plot([s, s], [y_bar - bar_h * 2.6, y_bar + bar_h * 2.6], color=c["series_1"], lw=1.6, zorder=6,
                solid_capstyle="round")
        ax.scatter([s], [y_bar], s=46, facecolor=c["series_1"], edgecolor="#FFFFFF", linewidths=2.0, zorder=7)
        ax.text(s, y_bar + bar_h * 2.6 + 0.04, main_label, ha=_ha(s, main_label, 8.5), va="bottom",
                color=c["ink"], fontproperties=_sized(theme.mpl["semibold"], 8.5))
    return _png(fig, theme)


def _sized(fp, size: float):
    f = fp.copy()
    f.set_size(size)
    return f


# --------------------------------------------------------------------------- giá và khối lượng


def _month_ticks(dates: Sequence[str], max_ticks: int = 7) -> tuple[list[int], list[str]]:
    idx: list[int] = []
    labs: list[str] = []
    last = None
    for i, d in enumerate(dates):
        ym = d[:7]
        if ym != last:
            if last is not None:
                idx.append(i)
                labs.append(f"{d[5:7]}/{d[:4]}")
            last = ym
    if len(idx) > max_ticks:
        step = -(-len(idx) // max_ticks)
        idx, labs = idx[::step], labs[::step]
    return idx, labs


def _spread_labels(ys: list[float], min_gap: float) -> list[float]:
    """Dàn nhãn đầu mút theo chiều dọc để không đè nhau (giữ thứ tự)."""
    order = sorted(range(len(ys)), key=lambda i: ys[i])
    out = list(ys)
    for k in range(1, len(order)):
        a, b = order[k - 1], order[k]
        if out[b] - out[a] < min_gap:
            out[b] = out[a] + min_gap
    return out


def price_chart(
    theme: Theme,
    w_mm: float,
    h_mm: float,
    *,
    dates: Sequence[str],
    close: Sequence[float],
    series: Sequence[tuple[str, Sequence[float | None], str]] = (),
) -> io.BytesIO:
    """Giá đóng cửa (chuỗi 1) + các đường MA; nhãn trực tiếp ở đầu mút, đánh dấu cao nhất và thấp nhất."""
    c = theme.c
    lw = float(theme.cfg["charts"]["line_pt"])
    fig = _fig(w_mm, h_mm)
    right_pad = 26 / w_mm
    top = 0.86 if series else 0.95
    ax = fig.add_axes([0.075, 0.10, 1 - 0.075 - right_pad, top - 0.10])
    _style(ax, theme)
    x = list(range(len(close)))
    ax.plot(x, close, color=c["series_1"], lw=lw, solid_capstyle="round", solid_joinstyle="round",
            label="Giá đóng cửa", zorder=4)
    lo = min(close)
    hi = max(close)
    for name, vals, color in series:
        xs = [i for i, v in zip(x, vals) if v is not None]
        ys = [v for v in vals if v is not None]
        if xs:
            ax.plot(xs, ys, color=c[color], lw=lw * 0.8, solid_capstyle="round", label=name, zorder=3)
            lo, hi = min(lo, min(ys)), max(hi, max(ys))
    span = hi - lo if hi > lo else max(hi, 1) * 0.1
    ax.set_ylim(lo - span * 0.12, hi + span * 0.14)
    ax.fill_between(x, close, lo - span * 0.12, color=c["series_1"], alpha=0.10, lw=0, zorder=2)
    ax.set_xlim(0, len(close) - 1)
    ax.yaxis.set_major_formatter(_vi_tick())
    ax.yaxis.set_major_locator(MaxNLocator(5))
    ti, tl = _month_ticks(dates)
    ax.set_xticks(ti)
    ax.set_xticklabels(tl)

    # cực trị của giá đóng cửa
    i_hi = max(range(len(close)), key=lambda i: close[i])
    i_lo = min(range(len(close)), key=lambda i: close[i])
    for i, word, va, dy in ((i_hi, "Cao nhất", "bottom", span * 0.03), (i_lo, "Thấp nhất", "top", -span * 0.03)):
        ax.scatter([i], [close[i]], s=14, facecolor=c["series_1"], edgecolor="#FFFFFF", linewidths=1.0, zorder=6)
        ha = "left" if i < len(close) * 0.15 else ("right" if i > len(close) * 0.85 else "center")
        ax.text(i, close[i] + dy, f"{word} {fmt_num(close[i])}", ha=ha, va=va, fontsize=LABEL_PT,
                color=c["ink"], zorder=7)

    # nhãn đầu mút
    ends: list[tuple[str, float, str]] = [("Giá", close[-1], "series_1")]
    for name, vals, color in series:
        last = next((v for v in reversed(list(vals)) if v is not None), None)
        if last is not None:
            ends.append((name, last, color))
    ylim = ax.get_ylim()
    placed = _spread_labels([e[1] for e in ends], (ylim[1] - ylim[0]) * 0.075)
    x_end = len(close) - 1
    for (name, val, color), yl in zip(ends, placed):
        ax.scatter([x_end], [val], s=14, facecolor=c[color], edgecolor="#FFFFFF", linewidths=1.0, zorder=8,
                   clip_on=False)
        xt = x_end + len(close) * 0.02
        if abs(yl - val) > 1e-9:
            ax.plot([x_end, xt], [val, yl], color=c["axis"], lw=0.5, clip_on=False, zorder=5)
        ax.text(xt + len(close) * 0.005, yl, f"{name} {fmt_num(val)}", ha="left", va="center",
                fontsize=LABEL_PT, color=c["ink"], clip_on=False)
    if series:
        leg = ax.legend(loc="lower left", bbox_to_anchor=(0.0, 1.01), frameon=False, fontsize=LABEL_PT,
                        ncol=len(series) + 1, handlelength=1.6, borderaxespad=0.0, labelcolor=c["ink"])
        for line in leg.get_lines():
            line.set_linewidth(lw)
    return _png(fig, theme)


def volume_unit(volume: Sequence[float]) -> tuple[float, str]:
    """Chọn đơn vị khối lượng: triệu cổ phiếu, hoặc nghìn cổ phiếu khi mã thanh khoản thấp."""
    peak = max((float(v or 0) for v in volume), default=0.0)
    return (1e6, "triệu cổ phiếu") if peak >= 1e6 else (1e3, "nghìn cổ phiếu")


def volume_chart(theme: Theme, w_mm: float, h_mm: float, *, dates: Sequence[str],
                 volume: Sequence[float]) -> io.BytesIO:
    """Khối lượng (đơn vị theo volume_unit), cột xám mảnh, tách riêng dưới biểu đồ giá."""
    c = theme.c
    fig = _fig(w_mm, h_mm)
    right_pad = 26 / w_mm
    ax = fig.add_axes([0.075, 0.22, 1 - 0.075 - right_pad, 0.70])
    _style(ax, theme)
    div, _ = volume_unit(volume)
    vals = [float(v or 0) / div for v in volume]
    ax.bar(range(len(vals)), vals, width=0.72, color=c["axis"], lw=0)
    ax.set_xlim(-0.5, len(vals) - 0.5)
    ax.yaxis.set_major_locator(MaxNLocator(3))
    ax.yaxis.set_major_formatter(_vi_tick(0 if max(vals or [0]) >= 10 else 1))
    ti, tl = _month_ticks(dates)
    ax.set_xticks(ti)
    ax.set_xticklabels(tl)
    if vals:
        ax.text(len(vals) - 1 + len(vals) * 0.02, vals[-1], f"Phiên cuối {fmt_num(vals[-1], 1)}", ha="left",
                va="center", fontsize=LABEL_PT, color=c["ink"], clip_on=False)
    return _png(fig, theme)


def sparkline(theme: Theme, w_mm: float, h_mm: float, *, close: Sequence[float]) -> io.BytesIO:
    """Đường giá thu nhỏ không trục cho trang bìa."""
    c = theme.c
    fig = _fig(w_mm, h_mm)
    ax = fig.add_axes([0.02, 0.08, 0.96, 0.84])
    ax.axis("off")
    ax.plot(range(len(close)), close, color=c["series_1"], lw=float(theme.cfg["charts"]["line_pt"]),
            solid_capstyle="round", solid_joinstyle="round")
    ax.scatter([len(close) - 1], [close[-1]], s=14, facecolor=c["series_1"], edgecolor="#FFFFFF",
               linewidths=1.0, zorder=5, clip_on=False)
    return _png(fig, theme)


# --------------------------------------------------------------------------- đóng góp điểm


def contributions_chart(
    theme: Theme,
    w_mm: float,
    h_mm: float,
    *,
    rows: Sequence[tuple[str, float | None]],
) -> io.BytesIO:
    """Thanh ngang gốc 50: dương xanh, âm đỏ, giá trị có dấu ở đầu thanh."""
    c = theme.c
    fig = _fig(w_mm, h_mm)
    ax = fig.add_axes([0.26, 0.14, 0.66, 0.84])
    _style(ax, theme, ygrid=False)
    vals = [to_float(v) or 0.0 for _, v in rows]
    m = max([abs(v) for v in vals] + [5.0])
    lim = m * 1.7
    ax.set_xlim(50 - lim, 50 + lim)
    n = len(rows)
    ax.set_ylim(-0.6, n - 0.4)
    ax.invert_yaxis()
    for i, ((label, raw), v) in enumerate(zip(rows, vals)):
        ax.add_patch(Rectangle((50 - lim, i - 0.32), 2 * lim, 0.64, color=c["contrib_mid"], lw=0, zorder=1))
        if to_float(raw) is None:
            ax.text(50 + lim * 0.04, i, "n/a", va="center", ha="left", fontsize=LABEL_PT, color=c["ink_3"])
            continue
        color = c["contrib_pos"] if v >= 0 else c["contrib_neg"]
        ax.add_patch(FancyBboxPatch((min(50, 50 + v), i - 0.22), abs(v), 0.44,
                                    boxstyle="round,pad=0,rounding_size=0.08", color=color, lw=0, zorder=3,
                                    mutation_aspect=1 / max(lim, 1) * 4))
        ha = "left" if v >= 0 else "right"
        ax.text(50 + v + (lim * 0.03 if v >= 0 else -lim * 0.03), i, fmt_signed(v, 1), va="center", ha=ha,
                fontsize=LABEL_PT, color=c["ink"], zorder=4)
    ax.axvline(50, color=c["ink_2"], lw=0.8, zorder=5)
    ax.set_yticks(range(n))
    ax.set_yticklabels([r[0] for r in rows])
    ax.tick_params(axis="y", colors=c["ink"])
    ticks = [50 - round(m), 50, 50 + round(m)]
    ax.set_xticks(ticks)
    ax.xaxis.set_major_formatter(_vi_tick())
    return _png(fig, theme)


# --------------------------------------------------------------------------- định giá


def valuation_chart(
    theme: Theme,
    w_mm: float,
    h_mm: float,
    *,
    rows: Sequence[dict[str, Any]],
) -> io.BytesIO:
    """Mỗi chỉ số một hàng: dải p25-p75 (nếu M4 có), vạch trung vị, chấm của mã có nhãn."""
    c = theme.c
    fig = _fig(w_mm, h_mm)
    n = max(1, len(rows))
    h_each = 0.94 / n
    for k, r in enumerate(rows):
        bottom = 0.03 + (n - 1 - k) * h_each
        ax = fig.add_axes([0.17, bottom, 0.79, h_each])
        ax.axis("off")
        ax.set_ylim(0, 1)
        vals = [to_float(r.get(k2)) for k2 in ("value", "median", "p25", "p75")]
        present = [v for v in vals if v is not None]
        fig.text(0.0, bottom + h_each * 0.5, r["label"], ha="left", va="center", color=c["ink"],
                 fontproperties=_sized(theme.mpl["semibold"], 8.5))
        if not present:
            ax.text(0.0, 0.5, "n/a", transform=ax.transAxes, ha="left", va="center", fontsize=LABEL_PT,
                    color=c["ink_3"])
            continue
        lo = min(0.0, min(present) * 1.1)
        hi = max(present) * 1.18
        ax.set_xlim(lo, hi)
        y0 = 0.5
        ax.plot([lo, hi], [y0, y0], color=c["axis"], lw=0.6, solid_capstyle="butt", zorder=1)
        ax.text(lo, y0 - 0.10, fmt_num(lo), ha="left", va="top", fontsize=LABEL_PT, color=c["ink_3"])
        p25, p75 = to_float(r.get("p25")), to_float(r.get("p75"))
        if p25 is not None and p75 is not None:
            ax.add_patch(Rectangle((p25, y0 - 0.09), p75 - p25, 0.18, color=c["rule"], lw=0, zorder=2))
        med = to_float(r.get("median"))
        if med is not None:
            ax.plot([med, med], [y0 - 0.16, y0 + 0.16], color=c["ink_2"], lw=1.2, zorder=3)
            ax.text(med, y0 - 0.22, f"Trung vị ngành {fmt_num(med, 2)}", ha="center", va="top",
                    fontsize=LABEL_PT, color=c["ink_2"])
        v = to_float(r.get("value"))
        if v is not None:
            ax.scatter([v], [y0], s=44, facecolor=c["series_1"], edgecolor="#FFFFFF", linewidths=1.5, zorder=4)
            txt = f"{r.get('ticker', '')} {fmt_num(v, 2)}"
            if r.get("pct_label"):
                txt += f", {r['pct_label']}"
            ax.text(v, y0 + 0.20, txt, ha="center", va="bottom", fontsize=LABEL_PT, color=c["ink"], zorder=5)
    return _png(fig, theme)


def football_field(
    theme: Theme,
    w_mm: float,
    h_mm: float,
    *,
    rows: Sequence[dict[str, Any]],
    price: float | None,
) -> io.BytesIO:
    """Dải giá theo phương pháp trên trục giá; vạch dọc là giá hiện tại; base có dấu riêng."""
    c = theme.c
    fig = _fig(w_mm, h_mm)
    ax = fig.add_axes([0.20, 0.14, 0.74, 0.72])
    _style(ax, theme, ygrid=False)
    vals: list[float] = []
    for r in rows:
        vals += [v for v in (to_float(r.get("low")), to_float(r.get("high")), to_float(r.get("mid"))) if v is not None]
    if to_float(price) is not None:
        vals.append(float(price))
    if not vals:
        ax.axis("off")
        return _png(fig, theme)
    lo, hi = min(vals), max(vals)
    span = hi - lo if hi > lo else hi * 0.2
    ax.set_xlim(lo - span * 0.22, hi + span * 0.22)
    n = len(rows)
    ax.set_ylim(-0.7, n - 0.3)
    ax.invert_yaxis()
    for i, r in enumerate(rows):
        a, b = to_float(r.get("low")), to_float(r.get("high"))
        if a is None or b is None:
            ax.text(lo, i, "n/a", va="center", fontsize=LABEL_PT, color=c["ink_3"])
            continue
        color = c[r.get("color", "series_1")]
        ax.add_patch(Rectangle((a, i - 0.17), b - a, 0.34, color=color, alpha=0.35 if r.get("light") else 0.85,
                               lw=0, zorder=2))
        ax.text(a - span * 0.015, i, fmt_num(a), ha="right", va="center", fontsize=LABEL_PT, color=c["ink"])
        ax.text(b + span * 0.015, i, fmt_num(b), ha="left", va="center", fontsize=LABEL_PT, color=c["ink"])
        mid = to_float(r.get("mid"))
        if mid is not None:
            ax.scatter([mid], [i], marker="D", s=26, facecolor=c["ink"], edgecolor="#FFFFFF", linewidths=1.0,
                       zorder=4)
            ax.text(mid, i - 0.27, f"{r.get('mid_label', 'Cơ sở')} {fmt_num(mid)}", ha="center", va="bottom",
                    fontsize=LABEL_PT, color=c["ink"], zorder=5)
    if to_float(price) is not None:
        ax.axvline(float(price), color=c["ink_2"], lw=0.8, zorder=3)
        ax.text(float(price), -0.72, f"Giá hiện tại {fmt_num(price)}", ha="center", va="bottom",
                fontsize=LABEL_PT, color=c["ink_2"], clip_on=False)
    ax.set_yticks(range(n))
    ax.set_yticklabels([r["label"] for r in rows])
    ax.tick_params(axis="y", colors=c["ink"])
    ax.xaxis.set_major_locator(MaxNLocator(5))
    ax.xaxis.set_major_formatter(_vi_tick())
    return _png(fig, theme)


# --------------------------------------------------------------------------- tâm lý tin tức


def sentiment_chart(theme: Theme, w_mm: float, h_mm: float, *, positive: float | None,
                    negative: float | None) -> io.BytesIO:
    """Cột đếm tin tích cực (xanh, bên phải) và tiêu cực (đỏ, bên trái) hai bên điểm giữa."""
    c = theme.c
    fig = _fig(w_mm, h_mm)
    ax = fig.add_axes([0.0, 0.0, 1.0, 1.0])
    ax.axis("off")
    p = to_float(positive) or 0.0
    q = to_float(negative) or 0.0
    m = max(p, q, 1.0) * 1.06
    ax.set_xlim(-m, m)
    ax.set_ylim(-0.6, 0.6)
    yb = -0.22
    ax.add_patch(Rectangle((0, yb - 0.17), p, 0.34, color=c["up"], lw=0))
    ax.add_patch(Rectangle((-q, yb - 0.17), q, 0.34, color=c["down"], lw=0))
    ax.plot([0, 0], [yb - 0.30, 0.50], color=c["ink_2"], lw=0.8)
    ax.text(m * 0.06, 0.18, f"\u25b2 {fmt_num(p)} tích cực", ha="left", va="center", fontsize=LABEL_PT,
            color=c["ink"])
    ax.text(-m * 0.06, 0.18, f"\u25bc {fmt_num(q)} tiêu cực", ha="right", va="center", fontsize=LABEL_PT,
            color=c["ink"])
    return _png(fig, theme)
