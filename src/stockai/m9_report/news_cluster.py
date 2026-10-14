"""Gom tin cùng sự kiện và chọn danh sách hiển thị trang tin PDF."""
from __future__ import annotations

import math
import re
from typing import Any

from stockai.m5_sentiment.run import (
    _ambiguous_identity_ok,
    _cluster_stories,
    _company_alias_hit,
    _is_cw,
    _jaccard,
    _load_m5_cfg,
    _tokens,
    _word_hit,
    classify_title,
    normalize_title,
    parse_date as m5_parse_date,
)
from stockai.m9_report.fmt import fmt_date, parse_date

LABEL_POS = "Tích cực"
LABEL_NEG = "Tiêu cực"
LABEL_NEU = "Trung tính"


def _story_size(ev: dict) -> int | None:
    for k in ("story_size", "cluster_size", "n_same_event"):
        v = ev.get(k)
        if isinstance(v, (int, float)) and int(v) >= 1:
            return int(v)
    return None


def polarity_label(polarity: float) -> str:
    if polarity > 0:
        return LABEL_POS
    if polarity < 0:
        return LABEL_NEG
    return LABEL_NEU


def _label_from_evidence_text(text: str) -> str:
    lab = (text or "").partition("|")[0].strip().lower()
    if "tiêu cực" in lab or "tieu cuc" in lab:
        return LABEL_NEG
    if "tích cực" in lab or "tich cuc" in lab:
        return LABEL_POS
    if "trung tính" in lab or "trung tinh" in lab:
        return LABEL_NEU
    return ""


def cluster_news_for_report(
    evidence: list,
    news_by_id: dict[str, dict],
    *,
    jaccard_thr: float = 0.42,
    max_items: int = 7,
) -> list[dict[str, Any]]:
    """Mỗi cụm một bài đại diện (mới nhất / có hướng rõ); kèm số tin cùng sự kiện.

    Giữ API cũ cho test 012b; panel PDF dùng ``select_news_panel``.
    """
    items: list[dict[str, Any]] = []
    for ev in evidence or []:
        if not isinstance(ev, dict) or not ev.get("news_id"):
            continue
        txt = str(ev.get("text") or "")
        label, _, title = txt.partition("|")
        src = news_by_id.get(str(ev["news_id"])) or {}
        title = (title.strip() or str(src.get("title") or "")).strip()
        if not title:
            continue
        pub = src.get("published_at") or src.get("date")
        items.append(
            {
                "news_id": str(ev["news_id"]),
                "label": label.strip() or "",
                "title": title,
                "source": src.get("source"),
                "published_at": pub,
                "story_size": _story_size(ev),
                "norm": normalize_title(title),
            }
        )

    if not items:
        return []

    if any(it["story_size"] is not None for it in items):
        out: list[dict[str, Any]] = []
        for it in items:
            n_extra = max(0, (it["story_size"] or 1) - 1)
            out.append({**it, "extra_count": n_extra})
            if len(out) >= max_items:
                break
        return out

    def _same_event(a: str, b: str) -> bool:
        ta, tb = set(_tokens(a)), set(_tokens(b))
        if _jaccard(ta, tb) >= jaccard_thr:
            return True
        key = {
            "mua", "đăng", "ký", "con", "trai", "bắt", "đáy", "cổ", "phiếu",
            "hpg", "vcb", "kos", "fpt", "aam", "vvs",
        }
        inter = ta & tb
        if len(inter & key) >= 3:
            return True
        if len(inter) >= 4 and (inter & {"mua", "bán", "đăng", "ký", "bắt"}):
            return True
        return False

    used = [False] * len(items)
    clusters: list[list[dict[str, Any]]] = []
    for i, it in enumerate(items):
        if used[i]:
            continue
        used[i] = True
        members = [it]
        for j in range(i + 1, len(items)):
            if used[j]:
                continue
            other = items[j]
            if _same_event(it["norm"], other["norm"]):
                used[j] = True
                members.append(other)
        clusters.append(members)

    def _pub_key(m: dict) -> str:
        d = parse_date(m.get("published_at"))
        return d.isoformat() if d else ""

    out2: list[dict[str, Any]] = []
    for members in clusters:
        best = max(members, key=lambda m: (_pub_key(m), abs(len(m["title"]))))
        out2.append({**best, "extra_count": max(0, len(members) - 1)})
        if len(out2) >= max_items:
            break
    return out2


def _build_classified_records(
    news_list: list,
    *,
    ticker: str,
    company: dict,
    as_of: str,
    m5_cfg: dict[str, Any],
) -> list[dict[str, Any]]:
    """Lọc và chấm polarity giống đường đi M5 (chỉ tiêu đề, cùng lookback)."""
    lookback = int(m5_cfg.get("lookback_days", 60))
    half_life = float(m5_cfg.get("half_life_days", 14))
    ambiguous = {str(x).upper() for x in (m5_cfg.get("ambiguous_tickers") or [])}
    cw_patterns = list(m5_cfg.get("cw_patterns") or [])
    company_aliases = dict(m5_cfg.get("company_aliases") or {})
    asof_d = m5_parse_date(as_of)
    ticker_raw = str(ticker or "").upper()
    ticker_norm = normalize_title(ticker_raw)
    company_name = normalize_title((company or {}).get("name"))
    cfg = dict(m5_cfg)
    cfg["company_name"] = (company or {}).get("name") or ""

    seen: set[str] = set()
    records: list[dict[str, Any]] = []
    for article in news_list or []:
        if not isinstance(article, dict):
            continue
        published = m5_parse_date(article.get("published_at"))
        if asof_d is None or published is None:
            continue
        age = (asof_d - published).days
        if age < 0 or age > lookback:
            continue
        title = str(article.get("title") or "")
        title_norm = normalize_title(title)
        if not title_norm or title_norm in seen:
            continue
        src = str(article.get("source") or "")
        ticker_match = bool(ticker_norm and _word_hit(title_norm, ticker_norm))
        alias_match = _company_alias_hit(title_norm, ticker_raw, company_aliases, company_name)
        company_match = bool(company_name and len(company_name) >= 6 and company_name in title_norm)
        ticker_raw_hit = bool(ticker_raw and re.search(rf"\b{re.escape(ticker_raw)}\b", title))
        if not (ticker_match or ticker_raw_hit or alias_match or company_match):
            continue
        if _is_cw(title_norm, cw_patterns):
            continue
        if ticker_raw in ambiguous and not _ambiguous_identity_ok(
            title,
            title_norm,
            ticker_raw,
            source=src,
            aliases=company_aliases,
            company_name_norm=company_name,
        ):
            continue
        seen.add(title_norm)
        polarity, _matches, cmeta = classify_title(title, ticker_raw, source=src, m5_cfg=cfg)
        weight = math.exp(-math.log(2) * age / half_life)
        records.append(
            {
                "id": str(article.get("id") or ""),
                "title": title,
                "date": str(published),
                "published_at": article.get("published_at") or str(published),
                "age": age,
                "polarity": float(polarity),
                "weight": weight,
                "source": src,
                "meta": cmeta,
            }
        )
    return records


def select_news_panel(
    news_list: list,
    *,
    ticker: str,
    company: dict | None = None,
    as_of: str,
    cfg: dict | None = None,
    max_items: int = 6,
    max_negatives: int = 3,
) -> list[dict[str, Any]]:
    """Chọn tối đa ``max_items`` sự kiện khác nhau cho panel tin.

    - Gom cụm theo cùng ngưỡng M5; mỗi cụm một đại diện (ngày mới nhất).
    - Gồm tin trung tính.
    - Bắt buộc lấy tin tiêu cực nếu có (tối đa ``max_negatives``); không chỉ hiện tin tích cực
      khi còn tin tiêu cực.
    - Sắp xếp kết quả theo ngày mới → cũ.
    """
    m5_cfg, _ = _load_m5_cfg(cfg if isinstance(cfg, dict) else {})
    try:
        jaccard_thr = float(m5_cfg.get("story_jaccard_threshold", 0.6))
        story_window = int(m5_cfg.get("story_window_days", 3))
    except (TypeError, ValueError):
        jaccard_thr, story_window = 0.6, 3

    records = _build_classified_records(
        news_list,
        ticker=ticker,
        company=company or {},
        as_of=as_of,
        m5_cfg=m5_cfg,
    )
    if not records:
        return []

    stories = _cluster_stories(records, jaccard_thr=jaccard_thr, window_days=story_window)

    def _pub_key(s: dict) -> str:
        d = parse_date(s.get("published_at") or s.get("date"))
        return d.isoformat() if d else ""

    items: list[dict[str, Any]] = []
    for s in stories:
        members = s.get("members") or [s]
        best = max(members, key=lambda m: (_pub_key(m), abs(len(str(m.get("title") or "")))))
        pol = float(s.get("polarity") or 0.0)
        # Nếu cụm có thành viên tiêu cực, ưu tiên nhãn tiêu cực (không nuốt tin xấu)
        if any(float(m.get("polarity") or 0.0) < 0 for m in members):
            pol = min(float(m.get("polarity") or 0.0) for m in members)
            neg_members = [m for m in members if float(m.get("polarity") or 0.0) < 0]
            best = max(neg_members, key=lambda m: (_pub_key(m), abs(len(str(m.get("title") or "")))))
        items.append(
            {
                "news_id": str(best.get("id") or ""),
                "label": polarity_label(pol),
                "title": str(best.get("title") or "").strip(),
                "source": best.get("source"),
                "published_at": best.get("published_at") or best.get("date"),
                "polarity": pol,
                "extra_count": max(0, int(s.get("story_size") or len(members)) - 1),
                "norm": normalize_title(str(best.get("title") or "")),
            }
        )

    items = [it for it in items if it.get("title")]
    if not items:
        return []

    negatives = [it for it in items if it["polarity"] < 0]
    negatives = sorted(negatives, key=lambda it: _pub_key(it), reverse=True)[: max(0, int(max_negatives))]
    neg_ids = {it["news_id"] or it["norm"] for it in negatives}

    others = [
        it for it in items
        if (it["news_id"] or it["norm"]) not in neg_ids
    ]
    others = sorted(others, key=lambda it: _pub_key(it), reverse=True)

    slots = max(0, int(max_items) - len(negatives))
    chosen = list(negatives) + others[:slots]
    chosen.sort(key=lambda it: _pub_key(it), reverse=True)
    return chosen[: int(max_items)]


def news_extra_phrase(extra_count: int, *, markup: bool = False) -> str:
    """Hậu tố ' (và N tin cùng sự kiện)' khi N>0.

    ``markup=True`` bọc ngoặc trong ``<font>`` và giữ khoảng trắng trước thẻ — Paragraph không dính chữ.
    """
    n = int(extra_count or 0)
    if n <= 0:
        return ""
    body = f"(và {n} tin cùng sự kiện)"
    if markup:
        return f' <font size="8.5">{body}</font>'
    return f" {body}"


def news_meta_bits(item: dict[str, Any]) -> list[str]:
    return [b for b in (item.get("source"), fmt_date(item.get("published_at"), na="")) if b]


def format_news_label(label: str) -> str:
    """Chuẩn hoá nhãn panel: Tích cực / Tiêu cực / Trung tính."""
    raw = (label or "").strip()
    mapped = _label_from_evidence_text(raw + " |")
    if mapped:
        return mapped
    if not raw:
        return LABEL_NEU
    # capitalize từng từ tiếng Việt đơn giản
    return raw[:1].upper() + raw[1:] if raw else LABEL_NEU
