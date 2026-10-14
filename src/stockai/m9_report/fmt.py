"""Định dạng số và ngày theo vi-VN: 20.150 (phân cách nghìn), 28,5% (thập phân dấu phẩy)."""
from __future__ import annotations

import math
from datetime import date, datetime
from typing import Any

NA = "n/a"
MINUS = "\u2212"  # dấu trừ chuẩn, không dùng gạch nối


def to_float(x: Any) -> float | None:
    """Ép về float hữu hạn; None/NaN/inf/chuỗi rác trả None."""
    if isinstance(x, bool) or x is None:
        return None
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


def fmt_num(x: Any, decimals: int = 0, *, na: str = NA) -> str:
    """20150 -> '20.150'; 7.3275 (2) -> '7,33'; âm dùng dấu trừ chuẩn."""
    v = to_float(x)
    if v is None:
        return na
    s = f"{abs(v):,.{decimals}f}"
    s = s.replace(",", "\x00").replace(".", ",").replace("\x00", ".")
    if round(v, decimals) == 0:
        return s
    return (MINUS + s) if v < 0 else s


def fmt_signed(x: Any, decimals: int = 1, *, na: str = NA) -> str:
    """Luôn có dấu: +4,4 / −2,2 / 0,0."""
    v = to_float(x)
    if v is None:
        return na
    body = fmt_num(abs(v), decimals)
    if round(v, decimals) == 0:
        return body
    return ("+" if v > 0 else MINUS) + body


def fmt_pct_ratio(x: Any, decimals: int = 1, *, signed: bool = False, na: str = NA) -> str:
    """Tỷ lệ 0,285 -> '28,5%'."""
    v = to_float(x)
    if v is None:
        return na
    return (fmt_signed(v * 100, decimals) if signed else fmt_num(v * 100, decimals)) + "%"


def fmt_pct_points(x: Any, decimals: int = 1, *, signed: bool = False, na: str = NA) -> str:
    """Giá trị đã là phần trăm 27,11 -> '27,1%'."""
    v = to_float(x)
    if v is None:
        return na
    return (fmt_signed(v, decimals) if signed else fmt_num(v, decimals)) + "%"


def fmt_multiple(x: Any, decimals: int = 2, *, na: str = NA) -> str:
    """Bội số định giá: '7,33 lần'."""
    v = to_float(x)
    if v is None:
        return na
    return f"{fmt_num(v, decimals)} lần"


def fmt_bn_vnd(x: Any, decimals: int = 0, *, na: str = NA) -> str:
    """Đồng -> tỷ đồng (chỉ số, chưa kèm đơn vị)."""
    v = to_float(x)
    if v is None:
        return na
    return fmt_num(v / 1e9, decimals)


def fmt_score(x: Any, *, na: str = NA) -> str:
    return fmt_num(x, 1, na=na)


def parse_date(s: Any) -> date | None:
    if isinstance(s, datetime):
        return s.date()
    if isinstance(s, date):
        return s
    if not isinstance(s, str) or len(s) < 10:
        return None
    try:
        return datetime.strptime(s[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def fmt_date(s: Any, *, na: str = NA) -> str:
    """'2026-10-08' -> '08/10/2026'."""
    d = parse_date(s)
    return d.strftime("%d/%m/%Y") if d else na


def arrow_word(x: Any) -> str:
    """Ký hiệu tăng/giảm: ▲ cho dương, ▼ cho âm, rỗng nếu 0 hoặc thiếu."""
    v = to_float(x)
    if v is None or v == 0:
        return ""
    return "\u25b2" if v > 0 else "\u25bc"
