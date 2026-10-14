"""Quét tiêu đề 30 ngày / ~235 mã: lexicon = 0 nhưng có hint → top 60 bigram/trigram.

Chỉ IN ra để người dùng duyệt — KHÔNG tự thêm vào lexicon.
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from stockai.m5_sentiment.run import (  # noqa: E402
    _load_m5_cfg,
    classify_title,
    normalize_title,
    parse_date,
)

SNAP = ROOT / "data" / "snapshots_ext"
HINTS = [
    "tăng",
    "giảm",
    "lãi",
    "lỗ",
    "vượt",
    "thanh tra",
    "cổ tức",
    "điều tra",
    "phạt",
    "thầu",
    "hợp đồng",
    "mua",
    "bán",
    "ròng",
    "khuyến nghị",
    "dự báo",
]


def _tier(snap: dict) -> str | None:
    for f in (snap.get("meta") or {}).get("flags") or []:
        if isinstance(f, str) and f.startswith("quality_tier_"):
            return f.replace("quality_tier_", "")
    return None


def _ngrams(tokens: list[str], n: int) -> list[str]:
    return [" ".join(tokens[i : i + n]) for i in range(len(tokens) - n + 1)]


def main() -> None:
    cfg, _ = _load_m5_cfg({})
    lookback = 30  # cửa sổ quét gap (khác default score 60)
    big = Counter()
    tri = Counter()
    scanned = 0
    gap = 0

    for path in sorted(SNAP.glob("*.json")):
        try:
            snap = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if _tier(snap) not in ("full", "limited"):
            continue
        as_of = parse_date((snap.get("meta") or {}).get("as_of"))
        ticker = str((snap.get("meta") or {}).get("ticker") or "").upper()
        if not as_of or not ticker:
            continue
        for art in snap.get("news") or []:
            if not isinstance(art, dict):
                continue
            pub = parse_date(art.get("published_at"))
            if pub is None or pub > as_of:
                continue
            age = (as_of - pub).days
            if age > lookback:
                continue
            title = str(art.get("title") or "")
            scanned += 1
            pol, _, _ = classify_title(
                title, ticker, source=str(art.get("source") or ""), m5_cfg=cfg
            )
            if pol != 0:
                continue
            norm = normalize_title(title)
            if not any(h in norm for h in HINTS):
                continue
            gap += 1
            toks = [t for t in norm.split() if t and not re.fullmatch(r"\d+", t)]
            # bỏ mã 3 chữ đơn
            toks = [t for t in toks if not re.fullmatch(r"[a-z]{3}", t)]
            for g in _ngrams(toks, 2):
                big[g] += 1
            for g in _ngrams(toks, 3):
                tri[g] += 1

    print(f"scanned_titles={scanned} lexicon_zero_with_hint={gap} lookback={lookback}")
    print("--- TOP 60 bigrams ---")
    for i, (g, c) in enumerate(big.most_common(60), 1):
        print(f"{i:2}. {c:5}  {g}")
    print("--- TOP 60 trigrams ---")
    for i, (g, c) in enumerate(tri.most_common(60), 1):
        print(f"{i:2}. {c:5}  {g}")
    print(
        "\n(CHỈ đề xuất — không tự thêm lexicon. Duyệt rồi bảo N5 cập nhật tay.)"
    )


if __name__ == "__main__":
    main()
