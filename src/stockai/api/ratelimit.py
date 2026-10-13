"""Giới hạn tần suất gọi LLM live (toàn cục + theo IP + trần ngày UTC)."""
from __future__ import annotations

import json
import threading
import time
from collections import OrderedDict, deque
from datetime import datetime, timezone
from pathlib import Path


class SlidingWindowLimiter:
    """Đếm sự kiện trong cửa sổ ``window_sec`` giây."""

    def __init__(self, *, max_events: int, window_sec: float = 3600.0) -> None:
        self.max_events = max(0, int(max_events))
        self.window_sec = float(window_sec)
        self._events: deque[float] = deque()
        self._lock = threading.Lock()

    def _prune(self, now: float) -> None:
        cutoff = now - self.window_sec
        while self._events and self._events[0] < cutoff:
            self._events.popleft()

    def remaining(self) -> int:
        with self._lock:
            self._prune(time.monotonic())
            return max(0, self.max_events - len(self._events))

    def allow(self) -> bool:
        """True nếu còn ngân sách; ghi nhận 1 sự kiện khi cho phép."""
        with self._lock:
            now = time.monotonic()
            self._prune(now)
            if self.max_events <= 0:
                return False
            if len(self._events) >= self.max_events:
                return False
            self._events.append(now)
            return True

    def would_allow(self) -> bool:
        with self._lock:
            self._prune(time.monotonic())
            if self.max_events <= 0:
                return False
            return len(self._events) < self.max_events

    def is_empty_after_prune(self) -> bool:
        """True nếu không còn sự kiện trong cửa sổ (sau khi dọn)."""
        with self._lock:
            self._prune(time.monotonic())
            return len(self._events) == 0


class DebateRateLimiter:
    """Ghép limiter toàn cục + theo IP + trần ngày (UTC) cho POST debate live."""

    def __init__(
        self,
        *,
        max_per_hour: int = 10,
        max_per_ip_per_hour: int = 3,
        max_per_day: int = 15,
        window_sec: float = 3600.0,
        budget_path: Path | str | None = None,
        max_tracked_ips: int = 5000,
    ) -> None:
        self.global_limiter = SlidingWindowLimiter(
            max_events=max_per_hour, window_sec=window_sec
        )
        self.max_per_ip = max(0, int(max_per_ip_per_hour))
        self.max_per_day = max(0, int(max_per_day))
        self.window_sec = float(window_sec)
        self.max_tracked_ips = max(1, int(max_tracked_ips))
        self.budget_path = Path(budget_path) if budget_path is not None else None
        self._by_ip: OrderedDict[str, SlidingWindowLimiter] = OrderedDict()
        self._lock = threading.Lock()
        # Bộ nhớ khi chưa có budget_path (test / fallback)
        self._mem_day: str | None = None
        self._mem_count: int = 0

    @staticmethod
    def _utc_day() -> str:
        return datetime.now(timezone.utc).strftime("%Y-%m-%d")

    def _load_daily_unlocked(self) -> tuple[str, int]:
        today = self._utc_day()
        if self.budget_path is None:
            if self._mem_day != today:
                self._mem_day = today
                self._mem_count = 0
            return today, self._mem_count
        path = self.budget_path
        if not path.is_file():
            return today, 0
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, TypeError):
            return today, 0
        if not isinstance(data, dict):
            return today, 0
        day = str(data.get("day") or "")
        try:
            count = int(data.get("count") or 0)
        except (TypeError, ValueError):
            count = 0
        if day != today:
            return today, 0
        return today, max(0, count)

    def _save_daily_unlocked(self, day: str, count: int) -> None:
        if self.budget_path is None:
            self._mem_day = day
            self._mem_count = count
            return
        path = self.budget_path
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                json.dumps({"day": day, "count": int(count)}, ensure_ascii=False, indent=1),
                encoding="utf-8",
            )
        except OSError:
            # Vẫn giữ bộ nhớ để không vượt trần trong process hiện tại
            self._mem_day = day
            self._mem_count = count

    def _daily_would_allow_unlocked(self) -> bool:
        if self.max_per_day <= 0:
            return False
        _, count = self._load_daily_unlocked()
        return count < self.max_per_day

    def _daily_record_unlocked(self) -> bool:
        """Ghi nhận 1 lần gọi mạng trong ngày UTC. False nếu đã chạm trần."""
        if self.max_per_day <= 0:
            return False
        day, count = self._load_daily_unlocked()
        if count >= self.max_per_day:
            return False
        self._save_daily_unlocked(day, count + 1)
        return True

    def _cleanup_by_ip_unlocked(self) -> None:
        """Dọn limiter IP rỗng; nếu vượt max_tracked_ips thì đuổi IP cũ nhất."""
        empty = [ip for ip, lim in self._by_ip.items() if lim.is_empty_after_prune()]
        for ip in empty:
            del self._by_ip[ip]
        while len(self._by_ip) > self.max_tracked_ips:
            self._by_ip.popitem(last=False)

    def _get_ip_limiter_unlocked(self, ip: str) -> SlidingWindowLimiter:
        """Lấy/tạo limiter IP. Không dọn empty ngay sau khi tạo (tránh xóa entry mới)."""
        if ip in self._by_ip:
            return self._by_ip[ip]
        lim = SlidingWindowLimiter(max_events=self.max_per_ip, window_sec=self.window_sec)
        self._by_ip[ip] = lim
        # Entry mới ở cuối OrderedDict — đuổi cũ nhất nếu vượt trần
        while len(self._by_ip) > self.max_tracked_ips:
            self._by_ip.popitem(last=False)
        return self._by_ip[ip]

    def cleanup_by_ip(self) -> None:
        """Dọn `_by_ip` công khai (test / bảo trì)."""
        with self._lock:
            self._cleanup_by_ip_unlocked()

    def tracked_ip_count(self) -> int:
        with self._lock:
            return len(self._by_ip)

    def budget_ok(self, client_ip: str) -> bool:
        ip = (client_ip or "unknown").strip() or "unknown"
        if not self.global_limiter.would_allow():
            return False
        with self._lock:
            self._cleanup_by_ip_unlocked()
            if not self._daily_would_allow_unlocked():
                return False
            ip_lim = self._get_ip_limiter_unlocked(ip)
        return ip_lim.would_allow()

    def try_acquire(self, client_ip: str) -> tuple[bool, str | None]:
        """Thử giữ 1 slot live (ghi nhận khi sắp gọi mạng). Trả (ok, lý do nếu từ chối)."""
        ip = (client_ip or "unknown").strip() or "unknown"
        if not self.global_limiter.would_allow():
            return False, "rate_limit_global"
        with self._lock:
            self._cleanup_by_ip_unlocked()
            if not self._daily_would_allow_unlocked():
                return False, "rate_limit_daily"
            ip_lim = self._get_ip_limiter_unlocked(ip)
            if not ip_lim.would_allow():
                return False, "rate_limit_ip"
            # Giữ cả ba (best-effort; race nhỏ chấp nhận cho demo local)
            if not self.global_limiter.allow():
                return False, "rate_limit_global"
            if not ip_lim.allow():
                return False, "rate_limit_ip"
            if not self._daily_record_unlocked():
                return False, "rate_limit_daily"
            return True, None
