"""Nguồn tin bổ sung cho M1 (chỉ N2 sửa). vnstock chỉ trả ~50 tin gần nhất, không có URL bài -> bổ sung bằng RSS.

- Google News RSS theo mã, chia cửa sổ ~30 ngày bằng after:/before: để phủ cả 12 tháng; có tiêu đề + URL + nguồn + ngày.
- Feed RSS tự chọn (config news_rss), lọc theo mã.
Chỉ dùng thư viện chuẩn (urllib + xml). Lỗi mạng không làm sập M1: trả về danh sách rỗng và gắn cờ.
"""
from __future__ import annotations

import re
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime
from urllib.parse import quote
from urllib.request import Request, urlopen

GOOGLE_RSS = "https://news.google.com/rss/search?q={q}&hl=vi&gl=VN&ceid=VN:vi"
_UA = "Mozilla/5.0 (compatible; stockai-m1/1.0)"


def http_get(url: str, timeout: float = 20.0) -> bytes:
    with urlopen(Request(url, headers={"User-Agent": _UA}), timeout=timeout) as r:  # noqa: S310
        return r.read()


def _clean(s: str | None) -> str:
    s = re.sub(r"<[^>]+>", " ", s or "")
    return re.sub(r"\s+", " ", s).strip()


def parse_rss(xml: bytes | str) -> list[dict]:
    """RSS 2.0 -> [{title, link, publish_date(ISO), summary, source}]. Bỏ mục thiếu tiêu đề hoặc ngày."""
    root = ET.fromstring(xml)
    out = []
    for it in root.iter("item"):
        title = _clean(it.findtext("title"))
        pub = it.findtext("pubDate")
        try:
            dt = parsedate_to_datetime(pub) if pub else None
        except (TypeError, ValueError):
            dt = None
        if not title or dt is None:
            continue
        src_el = it.find("source")
        source = _clean(src_el.text) if src_el is not None and src_el.text else ""
        if source and title.endswith(" - " + source):        # Google News gắn tên báo vào cuối tiêu đề
            title = title[: -len(source) - 3]
        elif not source and " - " in title:
            title, source = title.rsplit(" - ", 1)
        if dt.tzinfo is not None:                            # về giờ Việt Nam rồi bỏ tzinfo
            dt = (dt + timedelta(hours=7 - dt.utcoffset().total_seconds() / 3600)).replace(tzinfo=None)
        out.append({"title": title.strip(), "link": (it.findtext("link") or "").strip(), "publish_date": dt.strftime("%Y-%m-%dT%H:%M:%S"),
                    "summary": _clean(it.findtext("description"))[:300], "source": source or "rss"})
    return out


def relevant(row: dict, ticker: str) -> bool:
    return re.search(rf"(?<![A-Za-z0-9]){re.escape(ticker)}(?![A-Za-z0-9])", f"{row['title']} {row['summary']}") is not None


def windows(start: str, as_of: str, days: int) -> list[tuple[str, str]]:
    a, end = datetime.strptime(start, "%Y-%m-%d"), datetime.strptime(as_of, "%Y-%m-%d") + timedelta(days=1)
    out = []
    while a < end:
        b = min(a + timedelta(days=days), end)
        out.append((a.strftime("%Y-%m-%d"), b.strftime("%Y-%m-%d")))
        a = b
    return out


def google_news(ticker: str, start: str, as_of: str, cfg: dict, fetch=http_get) -> tuple[list[dict], list[str]]:
    rows, flags, errors = [], [], 0
    days = int(cfg.get("news_google_window_days", 30))
    for a, b in windows(start, as_of, days):
        q = quote(f'"{ticker}" cổ phiếu after:{a} before:{b}')
        try:
            rows += [r for r in parse_rss(fetch(GOOGLE_RSS.format(q=q))) if relevant(r, ticker)]
        except Exception:  # noqa: BLE001
            errors += 1
        time.sleep(float(cfg.get("news_google_interval_sec", 1.0)) if fetch is http_get else 0)
    if errors:
        flags.append(f"news_google_errors:{errors}_windows")
    return rows, flags


def feed_news(ticker: str, feeds: list[str], fetch=http_get) -> tuple[list[dict], list[str]]:
    rows, flags = [], []
    for u in feeds:
        try:
            rows += [r for r in parse_rss(fetch(u)) if relevant(r, ticker)]
        except Exception as e:  # noqa: BLE001
            flags.append(f"news_rss_error:{str(e)[:60]}")
    return rows, flags
