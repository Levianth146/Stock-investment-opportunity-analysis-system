"""Nạp cấu hình M4 từ config/valuation.yaml + overlay cfg.m4.

Thiếu file/khóa → safe defaults + token m4_config_defaulted (gắn ở run).
Khóa as_of / ngưỡng nghiệp vụ đọc từ YAML — không hard-code chỉ trong Python.
"""
from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml

_ROOT = Path(__file__).resolve().parents[3]
_VALUATION_YAML = _ROOT / "config" / "valuation.yaml"

_DEFAULT_M4: dict[str, Any] = {
    "sector_stats_path": "data/valuation_sector_stats.json",
    "stale_calendar_days": 7,
    "stale_financials_days": 200,
    "pe_max_exclude": 100,
    "winsor": {"low_pct": 0.05, "high_pct": 0.95},
    "min_sector_n": 5,
    "weights": {
        "bank": {"pe": 0.0, "pb": 1.0},
        "default": {"pe": 0.5, "pb": 0.5},
        "by_sector": {},
    },
    "scoring": "percentile_inverted",
    "target_bands": {"bull_mult": 1.15, "bear_mult": 0.85},
    "enable_dcf": False,
    "dcf": {},
}


def deep_merge(base: dict, overlay: dict) -> dict:
    """Gộp dict sâu; overlay thắng khi không phải dict lồng."""
    out = deepcopy(base)
    for k, v in (overlay or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def load_m4_cfg(cfg: dict | None = None) -> tuple[dict[str, Any], bool]:
    """Trả (merged_cfg, defaulted). Overlay cfg.m4 lên file yaml."""
    defaulted = False
    file_m4: dict[str, Any] = {}
    try:
        if _VALUATION_YAML.is_file():
            raw = yaml.safe_load(_VALUATION_YAML.read_text(encoding="utf-8")) or {}
            file_m4 = dict(raw.get("m4") or {})
            if not file_m4:
                defaulted = True
        else:
            defaulted = True
    except (OSError, yaml.YAMLError, TypeError):
        defaulted = True
        file_m4 = {}

    merged = deep_merge(_DEFAULT_M4, file_m4)
    cfg = cfg if isinstance(cfg, dict) else {}
    overlay = cfg.get("m4") if isinstance(cfg.get("m4"), dict) else {}
    if overlay:
        merged = deep_merge(merged, overlay)
    if not file_m4 and not overlay:
        defaulted = True
    return merged, defaulted


def resolve_path(path_str: str) -> Path:
    """Đường dẫn tuyệt đối; relative tính từ root repo."""
    p = Path(path_str)
    if p.is_absolute():
        return p
    return _ROOT / p
