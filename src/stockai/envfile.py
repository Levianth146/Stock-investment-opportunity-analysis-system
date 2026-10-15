"""Đọc ``.env`` dùng chung (LLM + DNSE) — không ghi đè biến đã có, không log giá trị."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable

_REPO_ROOT = Path(__file__).resolve().parents[2]


def _strip_bom(text: str) -> str:
    if text.startswith("\ufeff"):
        return text[1:]
    return text


def parse_dotenv_text(text: str) -> dict[str, str]:
    """Parse nội dung .env: khoảng trắng quanh ``=``, quotes, ``export``, CRLF, BOM, ``#``.

    Không trả/ghi giá trị vào log. Bỏ dòng trống và comment.
    """
    text = _strip_bom(text.replace("\r\n", "\n").replace("\r", "\n"))
    out: dict[str, str] = {}
    for raw in text.split("\n"):
        s = raw.strip()
        if not s or s.startswith("#"):
            continue
        if s.lower().startswith("export "):
            s = s[7:].lstrip()
        if "=" not in s:
            continue
        name, _, val = s.partition("=")
        name = name.strip()
        if not name or not all(c.isalnum() or c == "_" for c in name):
            continue
        val = val.strip()
        if len(val) >= 2 and val[0] == val[-1] and val[0] in ("'", '"'):
            val = val[1:-1]
        if val:
            out[name] = val
    return out


def load_dotenv(
    env_path: str | Path | None = None,
    *,
    keys: Iterable[str] | None = None,
) -> dict[str, bool]:
    """Nạp biến từ ``.env`` vào ``os.environ`` nếu chưa có.

    Trả map ``tên → đã nạp (True) / bỏ qua vì đã có hoặc thiếu (False)``.
    Không bao giờ ghi đè biến đã tồn tại (kể cả chuỗi rỗng được coi là "đã có"
    chỉ khi ``os.environ.get(name)`` truthy — thiếu/trống thì được nạp).
    """
    path = Path(env_path) if env_path else _REPO_ROOT / ".env"
    wanted = set(keys) if keys is not None else None
    loaded: dict[str, bool] = {}
    if not path.is_file():
        if wanted:
            for k in wanted:
                loaded[k] = False
        return loaded
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError:
        if wanted:
            for k in wanted:
                loaded[k] = False
        return loaded
    parsed = parse_dotenv_text(raw)
    names = wanted if wanted is not None else set(parsed)
    for name in names:
        if os.environ.get(name):
            loaded[name] = False
            continue
        val = parsed.get(name)
        if val:
            os.environ[name] = val
            loaded[name] = True
        else:
            loaded[name] = False
    return loaded


def repo_dotenv_path() -> Path:
    """Đường dẫn ``<repo>/.env`` mặc định."""
    return _REPO_ROOT / ".env"
