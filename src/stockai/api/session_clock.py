"""Máy trạng thái phiên HOSE/HNX (ICT) — mặc định khi không có kênh session DNSE."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Literal
from zoneinfo import ZoneInfo

ICT = ZoneInfo("Asia/Ho_Chi_Minh")

SessionPhase = Literal[
    "closed",
    "ato",
    "continuous",
    "lunch",
    "atc",
]

# Nghỉ lễ VN tối thiểu (bổ sung theo năm khi cần). Weekend xử lý riêng.
_VN_HOLIDAYS: set[date] = {
    date(2026, 1, 1),
    date(2026, 2, 14),
    date(2026, 2, 15),
    date(2026, 2, 16),
    date(2026, 2, 17),
    date(2026, 2, 18),
    date(2026, 4, 30),
    date(2026, 5, 1),
    date(2026, 9, 2),
}


@dataclass(frozen=True)
class SessionSnapshot:
    """Trạng thái phiên tại một thời điểm ICT."""

    phase: SessionPhase
    exchange: str  # HOSE | HNX
    is_trading_day: bool
    session_fraction: float  # 0..1 phần phiên đã trôi (để prorate khối lượng)
    as_of_ts: str  # ISO ICT


def _parse_hhmm(s: str) -> time:
    h, m = s.split(":")
    return time(int(h), int(m))


# Lịch mặc định HOSE (giống HNX cho mục đích hiển thị phiên)
_DEFAULT_SCHEDULE = {
    "ato_start": "09:00",
    "continuous_am_start": "09:15",
    "lunch_start": "11:30",
    "continuous_pm_start": "13:00",
    "atc_start": "14:30",
    "close": "14:45",
}


def is_holiday(d: date, holidays: set[date] | None = None) -> bool:
    hol = holidays if holidays is not None else _VN_HOLIDAYS
    return d in hol


def is_trading_day(d: date, holidays: set[date] | None = None) -> bool:
    if d.weekday() >= 5:
        return False
    return not is_holiday(d, holidays)


def _combine(d: date, hhmm: str) -> datetime:
    return datetime.combine(d, _parse_hhmm(hhmm), tzinfo=ICT)


def session_fraction_at(now: datetime | None = None) -> float:
    """Tỉ lệ phút giao dịch đã qua / tổng phút phiên (không tính nghỉ trưa)."""
    snap = resolve_session(now)
    return snap.session_fraction


def resolve_session(
    now: datetime | None = None,
    *,
    exchange: str = "HOSE",
    holidays: set[date] | None = None,
    dnse_phase: str | None = None,
) -> SessionSnapshot:
    """Suy phiên từ đồng hồ ICT; nếu có ``dnse_phase`` thì ưu tiên ánh xạ.

    ``dnse_phase``: chuỗi thô từ kênh session (nếu probe xác nhận), ví dụ
    ATO / CONTINUOUS / BREAK / ATC / CLOSED. Chưa đo → luôn None.
    """
    wall = now.astimezone(ICT) if now is not None else datetime.now(ICT)
    ts = wall.isoformat(timespec="seconds")
    d = wall.date()
    trading = is_trading_day(d, holidays)

    if dnse_phase:
        mapped = _map_dnse_phase(dnse_phase)
        if mapped is not None:
            frac = _fraction_for_phase(wall, mapped) if trading else 0.0
            return SessionSnapshot(
                phase=mapped,
                exchange=exchange,
                is_trading_day=trading,
                session_fraction=frac,
                as_of_ts=ts,
            )

    if not trading:
        return SessionSnapshot("closed", exchange, False, 0.0, ts)

    sch = _DEFAULT_SCHEDULE
    tt = wall.time().replace(tzinfo=None)

    ato_s = _parse_hhmm(sch["ato_start"])
    cont_am = _parse_hhmm(sch["continuous_am_start"])
    lunch_s = _parse_hhmm(sch["lunch_start"])
    cont_pm = _parse_hhmm(sch["continuous_pm_start"])
    atc_s = _parse_hhmm(sch["atc_start"])
    close_t = _parse_hhmm(sch["close"])

    if tt < ato_s or tt >= close_t:
        phase: SessionPhase = "closed"
    elif ato_s <= tt < cont_am:
        phase = "ato"
    elif cont_am <= tt < lunch_s:
        phase = "continuous"
    elif lunch_s <= tt < cont_pm:
        phase = "lunch"
    elif cont_pm <= tt < atc_s:
        phase = "continuous"
    else:
        phase = "atc"

    frac = _compute_fraction(wall, sch)
    return SessionSnapshot(phase, exchange, True, frac, ts)


def _map_dnse_phase(raw: str) -> SessionPhase | None:
    s = (raw or "").strip().upper()
    if not s:
        return None
    if "ATO" in s or "OPEN" == s:
        return "ato"
    if "ATC" in s or "CLOSE_AUCTION" in s:
        return "atc"
    if "BREAK" in s or "LUNCH" in s or "INTERMISSION" in s:
        return "lunch"
    if "CONTINUOUS" in s or "CONT" in s or "OPENING" in s:
        return "continuous"
    if "CLOSE" in s or "CLOSED" in s or "END" in s:
        return "closed"
    return None


def _trading_minutes(sch: dict[str, str] = _DEFAULT_SCHEDULE) -> float:
    """Tổng phút giao dịch trong ngày (ATO+liên tục+ATC, trừ lunch)."""
    d = date(2000, 1, 1)
    ato = _combine(d, sch["ato_start"])
    lunch = _combine(d, sch["lunch_start"])
    pm = _combine(d, sch["continuous_pm_start"])
    close = _combine(d, sch["close"])
    am = (lunch - ato).total_seconds() / 60.0
    afternoon = (close - pm).total_seconds() / 60.0
    return max(am + afternoon, 1.0)


def _elapsed_trading_minutes(wall: datetime, sch: dict[str, str] = _DEFAULT_SCHEDULE) -> float:
    d = wall.date()
    ato = _combine(d, sch["ato_start"])
    lunch = _combine(d, sch["lunch_start"])
    pm = _combine(d, sch["continuous_pm_start"])
    close = _combine(d, sch["close"])
    if wall <= ato:
        return 0.0
    if wall >= close:
        return _trading_minutes(sch)
    if wall < lunch:
        return (wall - ato).total_seconds() / 60.0
    if wall < pm:
        return (lunch - ato).total_seconds() / 60.0
    return (lunch - ato).total_seconds() / 60.0 + (wall - pm).total_seconds() / 60.0


def _compute_fraction(wall: datetime, sch: dict[str, str] = _DEFAULT_SCHEDULE) -> float:
    total = _trading_minutes(sch)
    elapsed = _elapsed_trading_minutes(wall, sch)
    return max(0.0, min(1.0, elapsed / total))


def _fraction_for_phase(wall: datetime, phase: SessionPhase) -> float:
    if phase == "closed":
        # sau đóng cửa → 1.0; trước mở cửa → 0.0
        tt = wall.time().replace(tzinfo=None)
        if tt >= _parse_hhmm(_DEFAULT_SCHEDULE["close"]):
            return 1.0
        return 0.0
    return _compute_fraction(wall)


def next_open_hint(now: datetime | None = None) -> str | None:
    """Gợi ý ngắn khi ngoài giờ (không phải lịch đầy đủ)."""
    wall = now.astimezone(ICT) if now is not None else datetime.now(ICT)
    snap = resolve_session(wall)
    if snap.phase != "closed":
        return None
    d = wall.date()
    # tìm ngày giao dịch kế
    for i in range(0, 10):
        cand = d + timedelta(days=i)
        if i == 0 and wall.time().replace(tzinfo=None) < _parse_hhmm("09:00"):
            if is_trading_day(cand):
                return f"{cand.isoformat()} 09:00 ICT"
        if i == 0:
            continue
        if is_trading_day(cand):
            return f"{cand.isoformat()} 09:00 ICT"
    return None


def last_closed_trading_session(
    now: datetime | None = None,
    *,
    holidays: set[date] | None = None,
) -> date:
    """Ngày phiên đã đóng gần nhất (sau 14:45 ICT ngày giao dịch = chính ngày đó)."""
    wall = now.astimezone(ICT) if now is not None else datetime.now(ICT)
    d = wall.date()
    close_t = _parse_hhmm(_DEFAULT_SCHEDULE["close"])
    if is_trading_day(d, holidays) and wall.time().replace(tzinfo=None) >= close_t:
        return d
    for i in range(1, 40):
        cand = d - timedelta(days=i)
        if is_trading_day(cand, holidays):
            return cand
    return d - timedelta(days=1)


def sessions_behind(
    asof: date | str | None,
    now: datetime | None = None,
    *,
    holidays: set[date] | None = None,
) -> int | None:
    """Số phiên giao dịch đã đóng sau ``asof`` tới phiên đóng gần nhất.

    ``0`` = snapshot trùng phiên đóng gần nhất (đủ tươi để dùng làm giá tham chiếu).
    ``None`` nếu ``asof`` không parse được.
    """
    if asof is None:
        return None
    if isinstance(asof, str):
        try:
            asof_d = date.fromisoformat(asof[:10])
        except ValueError:
            return None
    else:
        asof_d = asof
    last = last_closed_trading_session(now, holidays=holidays)
    if asof_d >= last:
        return 0
    n = 0
    d = asof_d
    while d < last:
        d += timedelta(days=1)
        if is_trading_day(d, holidays):
            n += 1
    return n
