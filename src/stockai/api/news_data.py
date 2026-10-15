"""Article archive for the news UI; never infer reliability or price impacts."""
from __future__ import annotations

import hashlib
import html
import re
from typing import Any

from stockai.m5_sentiment.run import (
    _load_m5_cfg, classify_title, load_universe_tickers, normalize_title, parse_date,
)


def news_archive(snapshot: dict[str, Any], asof: str, symbol: str) -> list[dict[str, Any]]:
    cutoff = parse_date(asof)
    if cutoff is None:
        return []
    cfg = _load_m5_cfg({})[0]
    cfg["company_name"] = (snapshot.get("company") or {}).get("name", "")
    universe = load_universe_tickers()
    seen: set[str] = set()
    articles = []
    for row in snapshot.get("news") or []:
        if not isinstance(row, dict):
            continue
        day = parse_date(row.get("published_at"))
        title = html.unescape(str(row.get("title") or "")).strip()
        key = normalize_title(title)
        if day is None or day > cutoff or not key or key in seen:
            continue
        seen.add(key)
        source = str(row.get("source") or "Không rõ nguồn")
        polarity, matches, _ = classify_title(title, symbol, source=source, m5_cfg=cfg)
        url = str(row.get("url") or "")
        mentions = sorted(set(re.findall(r"\b[A-Z][A-Z0-9]{1,5}\b", title)) & universe)
        articles.append({
            "id": str(row.get("id") or hashlib.sha256(key.encode()).hexdigest()[:16]),
            "title": title,
            "summary": html.unescape(re.sub(r"<[^>]*>", "", str(row.get("summary") or ""))),
            "published_at": str(row.get("published_at")), "date": day.isoformat(),
            "source": source, "url": url if url.startswith(("https://", "http://")) else None,
            "label": "pos" if polarity > 0 else "neg" if polarity < 0 else "neutral",
            "polarity": polarity, "matches": matches, "tickers": mentions,
        })
    return sorted(articles, key=lambda row: row["published_at"], reverse=True)
