"""M9 - xuất báo cáo PDF A4 tiếng Việt kiểu báo cáo phân tích của công ty chứng khoán (feature 012).

Bản đầy đủ: trang bìa (tùy chọn) + 4 trang: tóm tắt khuyến nghị, cơ bản và định giá, kỹ thuật và rủi ro,
tin tức, lưu ý dữ liệu và phụ lục. Mã không xếp hạng (quality_gate.scored = false): 1 trang dữ liệu hiện có,
không có điểm và khuyến nghị.

Mọi số lấy từ result M7, module_out M2-M6, validation M8 và snapshot. Không gọi LLM, không gọi mạng.
cfg tùy chọn: out_dir, cover, export_date (YYYY-MM-DD), universe_scores [(mã, điểm)], api_cache_dir,
other_profile {m7, universe_scores}, debate {source, bull, bear, model}, report_cfg_path.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path

import yaml

from stockai.m9_report.data import build_report_data
from stockai.m9_report.fmt import parse_date
from stockai.m9_report.layout import Doc, make_styles, render
from stockai.m9_report.theme import ROOT, build_theme, load_flag_dict, load_report_cfg


def _scoring_cfg(cfg: dict) -> dict:
    if isinstance(cfg.get("ratings"), list):
        return cfg
    p = ROOT / "config" / "scoring.yaml"
    try:
        raw = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    except OSError:
        raw = {}
    return raw if isinstance(raw, dict) else {}


def run(snapshot: dict, upstream: dict, cfg: dict) -> dict:
    rc = load_report_cfg(cfg.get("report_cfg_path"))
    theme = build_theme(rc)
    data = build_report_data(snapshot, upstream, cfg, price_days=int(rc["charts"].get("price_days", 252)))
    export = parse_date(cfg.get("export_date")) or date.today()
    tech = bool(cfg.get("technical_appendix") or cfg.get("technical"))
    doc = Doc(
        theme=theme,
        st=make_styles(theme),
        data=data,
        rc=rc,
        flag_dict=load_flag_dict(),
        scoring_cfg=_scoring_cfg(cfg),
        export_date=export,
        technical_appendix=tech,
    )
    cover = bool(cfg["cover"]) if "cover" in cfg else bool(rc.get("cover", True))
    out_dir = Path(cfg.get("out_dir") or rc.get("out_dir") or "reports")
    out = out_dir / f"{data.ticker}_{data.as_of}_{data.profile}.pdf"
    out.parent.mkdir(parents=True, exist_ok=True)
    # Từ khóa máy đọc trong metadata: trạng thái xếp hạng (không hiển thị trong trang)
    status = "ranked" if data.scored else "NOT RANKED"
    keywords = f"stockai, report, {data.ticker}, {data.profile}, ranking_status={status}"
    pages = render(doc, str(out), cover=cover, keywords=keywords)
    return {
        "pdf_path": str(out),
        "pages": pages,
        "ranked": data.scored,
        "debate_source": data.debate_source,
        "font_source": theme.fonts.source,
    }
