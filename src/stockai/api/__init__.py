"""Feature 011 — FastAPI layer đọc kết quả pipeline cho web demo."""
from __future__ import annotations

__all__ = ["create_app"]


def create_app(*args, **kwargs):
    from stockai.api.app import create_app as _create

    return _create(*args, **kwargs)
