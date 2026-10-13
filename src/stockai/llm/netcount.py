"""Bộ đếm HTTP LLM thật (dùng chung providers + generate)."""
from __future__ import annotations

import threading

_lock = threading.Lock()
_network_calls = 0
_max_live_calls: int | None = None


def reset_network_call_count() -> None:
    global _network_calls
    with _lock:
        _network_calls = 0


def get_network_call_count() -> int:
    with _lock:
        return _network_calls


def set_max_live_calls(n: int | None) -> None:
    global _max_live_calls
    _max_live_calls = None if n is None else max(0, int(n))


def get_max_live_calls() -> int | None:
    return _max_live_calls


def bump_network_call() -> None:
    """Tăng 1 trước mỗi requests.post; raise nếu vượt trần live."""
    global _network_calls
    with _lock:
        if _max_live_calls is not None and _network_calls >= _max_live_calls:
            raise RuntimeError(f"max_live_calls_reached:{_max_live_calls}")
        _network_calls += 1
