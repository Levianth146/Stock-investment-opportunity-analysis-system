"""Vẽ radar 6 trụ cột từ điểm tổng hợp p; không sửa dữ liệu/điểm nguồn.

Chạy từ scripts/: python 11_radar.py
Xuất radar năm cuối và chuỗi năm riêng từng ngân hàng, PNG/SVG/PDF.
"""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path

from common import OUT, load_yaml
os.environ.setdefault("MPLCONFIGDIR", str(OUT / "radar" / ".matplotlib"))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
import numpy as np
import pandas as pd

PILLARS = ["K", "S", "T", "O", "C", "D"]
LABELS = ["Khách hàng", "Chiến lược", "Công nghệ", "Vận hành", "Văn hóa", "Dữ liệu"]
COLORS = {"agribank": "#B04735", "mb": "#245CC4", "tcb": "#D53D42",
          "bidv": "#087C83", "vcb": "#16734A"}
ANGLES = np.arange(6) * 2 * math.pi / 6


def values(group):
    """Yêu cầu đủ đúng 6 điểm trụ cột, không thay ô thiếu bằng 0."""
    if len(group) != 6 or set(group.pillar) != set(PILLARS):
        raise ValueError("Mỗi ngân hàng/năm phải có đủ 6 trụ cột duy nhất")
    result = pd.to_numeric(group.set_index("pillar").loc[PILLARS, "p"], errors="coerce").to_numpy()
    if not np.isfinite(result).all() or ((result < 0) | (result > 100)).any():
        raise ValueError("Điểm trụ cột phải hữu hạn, trong khoảng 0–100")
    return result


def style(axis, title, compact=False):
    axis.set_theta_offset(math.pi / 2)
    axis.set_theta_direction(-1)
    axis.set_xticks(ANGLES, LABELS, fontsize=10 if compact else 12)
    axis.tick_params(axis="x", pad=15)
    axis.set_ylim(0, 100)
    axis.set_yticks([25, 50, 75, 100])
    axis.set_yticklabels(["25", "50", "75", "100"], fontsize=8, color="#697582")
    axis.set_rlabel_position(15)
    axis.grid(color="#CFD8E0", linewidth=.8)
    axis.spines["polar"].set_color("#B9C6D0")
    axis.set_facecolor("#FCFDFE")
    axis.set_title(title, fontsize=13 if compact else 17, fontweight="bold", pad=28)


def line(axis, scores, color, label=None, fill=False, annotate=False, width=2.3):
    axis.plot(np.r_[ANGLES, ANGLES[0]], np.r_[scores, scores[0]], color=color,
              linewidth=width, marker="o", markersize=4, label=label)
    if fill:
        axis.fill(np.r_[ANGLES, ANGLES[0]], np.r_[scores, scores[0]], color=color, alpha=.12)
    if annotate:
        for angle, score in zip(ANGLES, scores):
            axis.annotate(f"{score:.1f}", (angle, score), xytext=(0, 8), textcoords="offset points",
                          ha="center", fontsize=9, color=color, fontweight="bold",
                          bbox=dict(facecolor="white", edgecolor="none", alpha=.85, pad=1))


def save(figure, stem, pdf):
    figure.savefig(stem.with_suffix(".png"), dpi=220, bbox_inches="tight", facecolor="white")
    figure.savefig(stem.with_suffix(".svg"), bbox_inches="tight", facecolor="white")
    pdf.savefig(figure, bbox_inches="tight", facecolor="white")
    plt.close(figure)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scores", default=str(OUT / "scores.csv"))
    parser.add_argument("--years", help="Ví dụ 2024,2025; mặc định mọi năm trong bảng điểm")
    args = parser.parse_args()
    data = pd.read_csv(args.scores, encoding="utf-8-sig")
    if args.years:
        years = [int(y) for y in args.years.split(",")]
        data = data[data.year.isin(years)].copy()
    if data.empty or data.duplicated(["bank", "year", "pillar"]).any():
        raise ValueError("Bảng điểm trống hoặc trùng ngân hàng/năm/trụ cột")
    config = load_yaml("banks.yaml")
    banks = [b for b in config["banks"] if b in set(data.bank)]
    years = sorted(data.year.unique())
    latest = int(max(years))
    vectors = {(b, int(y)): values(g) for (b, y), g in data.groupby(["bank", "year"])}
    if any((b, latest) not in vectors for b in banks):
        raise ValueError("Năm cuối phải có điểm cho toàn bộ ngân hàng được vẽ")
    output = OUT / "radar"
    output.mkdir(exist_ok=True)
    plt.rcParams.update({"font.family": "DejaVu Sans", "svg.fonttype": "none"})
    footnote = "Điểm tổng hợp p của 6 trụ cột • thang 0–100 • sau cổng Bước 0"
    with PdfPages(output / "radar_banks.pdf") as pdf:
        figure, axes = plt.subplots(2, 3, figsize=(15, 11), subplot_kw={"projection": "polar"})
        figure.subplots_adjust(wspace=.65, hspace=.65, top=.85, bottom=.10)
        figure.suptitle(f"CHUYỂN ĐỔI SỐ NGÂN HÀNG — {latest}", fontsize=21, fontweight="bold", y=.97)
        for axis, bank in zip(axes.flat, banks):
            style(axis, config["banks"][bank]["name"], compact=True)
            line(axis, vectors[bank, latest], COLORS.get(bank, "#245CC4"), fill=True, annotate=True)
        axes.flat[-1].set_axis_off()
        axes.flat[-1].text(.5, .65, "Cùng 6 trụ cột\nCùng thang điểm 0–100\n\nDBI chủ đạo + DTI bổ trợ\nTrụ cột thiếu DTI dùng DBI thuần",
                           transform=axes.flat[-1].transAxes, ha="center", va="center", fontsize=13, color="#445465")
        figure.text(.5, .025, footnote, ha="center", fontsize=11, color="#596979")
        save(figure, output / f"radar_{latest}_all_banks", pdf)
        for bank in banks:
            name = config["banks"][bank]["name"]
            figure, axis = plt.subplots(figsize=(8, 8), subplot_kw={"projection": "polar"})
            figure.subplots_adjust(left=.18, right=.82, top=.82, bottom=.16)
            style(axis, f"{name} — {latest}")
            line(axis, vectors[bank, latest], COLORS.get(bank, "#245CC4"), fill=True, annotate=True)
            figure.text(.5, .04, footnote, ha="center", fontsize=9, color="#596979")
            save(figure, output / f"radar_{bank}_{latest}", pdf)
            figure, axis = plt.subplots(figsize=(9, 9), subplot_kw={"projection": "polar"})
            figure.subplots_adjust(left=.18, right=.82, top=.83, bottom=.22)
            style(axis, f"{name} — {min(years)}–{latest}")
            palette = plt.get_cmap("viridis")(np.linspace(.12, .85, len(years)))
            for year, color in zip(years, palette):
                if (bank, int(year)) in vectors:
                    line(axis, vectors[bank, int(year)], color, label=str(year), fill=year == latest,
                         width=2.5 if year == latest else 1.5)
            axis.legend(loc="upper center", bbox_to_anchor=(.5, -.15), ncol=3, frameon=False)
            figure.text(.5, .025, "Thang 0–100; bộ DTI được giữ thay đổi theo năm sau Bước 0.\nĐọc thay đổi điểm cùng độ phủ dữ liệu; không suy ra mức cải thiện chỉ từ diện tích radar.",
                         ha="center", fontsize=9, color="#596979")
            save(figure, output / f"radar_{bank}_{min(years)}_{latest}", pdf)
    manifest = dict(source_file=args.scores, source_sha256=hashlib.sha256(Path(args.scores).read_bytes()).hexdigest(),
                    value_column="p", pillars=PILLARS, years=list(map(int, years)), scale=[0, 100], banks=banks)
    (output / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8-sig")
    data[["bank", "year", "pillar", "pillar_name", "p"]].to_csv(output / "radar_values.csv", index=False, encoding="utf-8-sig")
    print(f"Đã vẽ radar {len(banks)} ngân hàng: {output}")


if __name__ == "__main__":
    main()
