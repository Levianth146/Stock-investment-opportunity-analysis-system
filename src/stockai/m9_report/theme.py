"""Token thiết kế + đăng ký phông cho M9 (reportlab và matplotlib dùng chung một bộ phông).

Token đọc từ config/report.yaml; thiếu khóa thì dùng giá trị mặc định bên dưới.
Phông ưu tiên Noto (assets/fonts, giấy phép OFL); không có thì dùng DejaVu đi kèm matplotlib.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[3]

DEFAULTS: dict[str, Any] = {
    "cover": True,
    "out_dir": "reports",
    "colors": {
        "paper": "#FFFFFF",
        "ink": "#14233A",
        "ink_2": "#4F5B6B",
        "ink_3": "#6B7684",
        "rule": "#DADFE5",
        "axis": "#B8C0CA",
        "panel": "#F4F6F8",
        "series_1": "#2A78D6",
        "accent": "#184F95",
        "series_2": "#EB6834",
        "series_3": "#1BAF7A",
        "up": "#006300",
        "down": "#C62F2F",
        "contrib_pos": "#2A78D6",
        "contrib_neg": "#E34948",
        "contrib_mid": "#F0EFEC",
        "rating_buy": "#2A78D6",
        "rating_hold": "#8A939E",
        "rating_sell": "#C62F2F",
    },
    "fonts": {
        "dir": "assets/fonts",
        "sans": "NotoSans-Regular.ttf",
        "sans_semibold": "NotoSans-SemiBold.ttf",
        "sans_bold": "NotoSans-Bold.ttf",
        "serif": "NotoSerif-Regular.ttf",
        "serif_semibold": "NotoSerif-SemiBold.ttf",
        "symbols": "NotoSansSymbols2-Regular.ttf",
    },
    "sizes": {
        "cover_ticker": [64, 68],
        "cover_company": [20, 25],
        "page_title": [17, 21],
        "section": [11, 14],
        "body": [9.5, 14],
        "table": [8.5, 12],
        "caption": [7.5, 10],
    },
    "layout": {"margin_mm": 18, "columns": 12, "gutter_mm": 6, "rule_pt": 0.5},
    "charts": {"dpi": 300, "line_pt": 1.5, "price_days": 252},
    "sectors": {},
    "exchanges": {"HSX": "HOSE", "HOSE": "HOSE", "HNX": "HNX", "UPCOM": "UPCoM"},
    "profiles": {"long_term": "dài hạn", "swing": "lướt sóng"},
}

# Tên phông nội bộ trong PDF
SANS = "StockSans"
SANS_SEMI = "StockSans-SemiBold"
SANS_BOLD = "StockSans-Bold"
SERIF = "StockSerif"
SERIF_SEMI = "StockSerif-SemiBold"
SYMBOLS = "StockSymbols"


def _deep_merge(base: dict, extra: dict) -> dict:
    out = copy.deepcopy(base)
    for k, v in (extra or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


@lru_cache(maxsize=4)
def _load_yaml(path: str) -> dict:
    p = Path(path)
    if not p.is_file():
        return {}
    raw = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    return raw if isinstance(raw, dict) else {}


def load_report_cfg(path: str | Path | None = None) -> dict:
    """Đọc config/report.yaml rồi trộn vào giá trị mặc định."""
    p = Path(path) if path else ROOT / "config" / "report.yaml"
    return _deep_merge(DEFAULTS, _load_yaml(str(p)))


def load_flag_dict(path: str | Path | None = None) -> dict:
    """Đọc config/report_flags.yaml (flags, reasons, m8_messages)."""
    p = Path(path) if path else ROOT / "config" / "report_flags.yaml"
    raw = _load_yaml(str(p))
    return {
        "flags": dict(raw.get("flags") or {}),
        "reasons": dict(raw.get("reasons") or {}),
        "m8_messages": dict(raw.get("m8_messages") or {}),
    }


@dataclass
class FontSet:
    """Đường dẫn TTF thực dùng; source = 'noto' hoặc 'dejavu'."""

    sans: str
    sans_semibold: str
    sans_bold: str
    serif: str
    serif_semibold: str
    symbols: str | None
    source: str
    notes: list[str] = field(default_factory=list)


def _dejavu_dir() -> Path:
    import matplotlib

    return Path(matplotlib.get_data_path()) / "fonts" / "ttf"


def resolve_fonts(cfg: dict | None = None) -> FontSet:
    """Chọn bộ phông Noto nếu đủ file, ngược lại DejaVu."""
    fc = (cfg or load_report_cfg())["fonts"]
    d = Path(fc.get("dir") or "assets/fonts")
    d = d if d.is_absolute() else ROOT / d
    keys = ("sans", "sans_semibold", "sans_bold", "serif", "serif_semibold")
    paths = {k: d / str(fc.get(k) or "") for k in keys}
    sym = d / str(fc.get("symbols") or "")
    if all(p.is_file() for p in paths.values()):
        return FontSet(
            **{k: str(v) for k, v in paths.items()},
            symbols=str(sym) if sym.is_file() else None,
            source="noto",
        )
    dj = _dejavu_dir()
    return FontSet(
        sans=str(dj / "DejaVuSans.ttf"),
        sans_semibold=str(dj / "DejaVuSans-Bold.ttf"),
        sans_bold=str(dj / "DejaVuSans-Bold.ttf"),
        serif=str(dj / "DejaVuSerif.ttf"),
        serif_semibold=str(dj / "DejaVuSerif-Bold.ttf"),
        symbols=str(dj / "DejaVuSans.ttf"),
        source="dejavu",
        notes=["Thiếu phông Noto trong assets/fonts, dùng DejaVu đi kèm matplotlib."],
    )


_RL_REGISTERED: dict[str, str] = {}


def register_reportlab_fonts(fonts: FontSet) -> None:
    """Đăng ký TTF vào reportlab (TTF luôn được nhúng dạng subset vào PDF)."""
    from reportlab.lib.fonts import addMapping
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    wanted = {
        SANS: fonts.sans,
        SANS_SEMI: fonts.sans_semibold,
        SANS_BOLD: fonts.sans_bold,
        SERIF: fonts.serif,
        SERIF_SEMI: fonts.serif_semibold,
        SYMBOLS: fonts.symbols or fonts.sans,
    }
    for name, path in wanted.items():
        if _RL_REGISTERED.get(name) == path:
            continue
        pdfmetrics.registerFont(TTFont(name, path))
        _RL_REGISTERED[name] = path
    addMapping(SANS, 0, 0, SANS)
    addMapping(SANS, 1, 0, SANS_SEMI)
    addMapping(SANS, 0, 1, SANS)
    addMapping(SANS, 1, 1, SANS_SEMI)


_MPL_REGISTERED: set[str] = set()


def setup_matplotlib(fonts: FontSet) -> dict[str, Any]:
    """Nạp TTF vào matplotlib, trả FontProperties theo vai trò."""
    import matplotlib

    matplotlib.use("Agg")
    from matplotlib import font_manager

    for p in (fonts.sans, fonts.sans_semibold, fonts.sans_bold, fonts.serif_semibold, fonts.symbols):
        if p and p not in _MPL_REGISTERED:
            font_manager.fontManager.addfont(p)
            _MPL_REGISTERED.add(p)
    fam = font_manager.FontProperties(fname=fonts.sans).get_name()
    families = [fam]
    if fonts.symbols:
        sym_fam = font_manager.FontProperties(fname=fonts.symbols).get_name()
        if sym_fam not in families:
            families.append(sym_fam)
    matplotlib.rcParams["font.family"] = families
    matplotlib.rcParams["axes.unicode_minus"] = True
    matplotlib.rcParams["pdf.fonttype"] = 42
    return {
        "family": families,
        "regular": font_manager.FontProperties(fname=fonts.sans),
        "semibold": font_manager.FontProperties(fname=fonts.sans_semibold),
        "bold": font_manager.FontProperties(fname=fonts.sans_bold),
    }


@dataclass
class Theme:
    """Gói token + phông cho một lần render."""

    cfg: dict
    fonts: FontSet
    mpl: dict[str, Any]

    @property
    def c(self) -> dict[str, str]:
        return self.cfg["colors"]

    def size(self, role: str) -> tuple[float, float]:
        s = self.cfg["sizes"].get(role) or [9.5, 14]
        return float(s[0]), float(s[1])

    @property
    def margin_mm(self) -> float:
        return float(self.cfg["layout"]["margin_mm"])

    @property
    def gutter_mm(self) -> float:
        return float(self.cfg["layout"]["gutter_mm"])

    @property
    def columns(self) -> int:
        return int(self.cfg["layout"]["columns"])

    def col_mm(self, page_w_mm: float = 210.0) -> float:
        content = page_w_mm - 2 * self.margin_mm
        return (content - (self.columns - 1) * self.gutter_mm) / self.columns

    def span_mm(self, n: int, page_w_mm: float = 210.0) -> float:
        """Bề rộng n cột của lưới (gồm các khoảng cách cột bên trong)."""
        return n * self.col_mm(page_w_mm) + (n - 1) * self.gutter_mm

    def col_x_mm(self, i: int, page_w_mm: float = 210.0) -> float:
        """Tọa độ trái (mm, tính từ mép trái giấy) của cột thứ i (0-based)."""
        return self.margin_mm + i * (self.col_mm(page_w_mm) + self.gutter_mm)


def build_theme(cfg: dict | None = None) -> Theme:
    rc = cfg if cfg is not None else load_report_cfg()
    fonts = resolve_fonts(rc)
    register_reportlab_fonts(fonts)
    mpl = setup_matplotlib(fonts)
    return Theme(cfg=rc, fonts=fonts, mpl=mpl)
