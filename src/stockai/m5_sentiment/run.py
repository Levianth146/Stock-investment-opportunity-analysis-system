"""News sentiment score (S) using a transparent Vietnamese/English keyword baseline."""
from __future__ import annotations

POSITIVE_TERMS = (
    "tăng trưởng", "tăng mạnh", "lợi nhuận tăng", "doanh thu tăng", "vượt kế hoạch",
    "khởi sắc", "tích cực", "bứt phá", "mở rộng", "hưởng lợi", "cổ tức", "record profit",
    "profit rises", "revenue growth", "upgrade", "positive outlook", "expansion",
)
NEGATIVE_TERMS = (
    "thua lỗ", "lỗ ròng", "lợi nhuận giảm", "doanh thu giảm", "suy giảm", "tiêu cực",
    "nợ xấu", "vi phạm", "bị phạt", "đình chỉ", "kiện", "hủy niêm yết", "cắt giảm",
    "không đạt", "rủi ro", "khó khăn", "loss", "profit falls", "downgrade",
    "investigation", "default", "fine", "lawsuit",
)


def _classify(text: str) -> int:
    lowered = text.casefold()
    positive = sum(term in lowered for term in POSITIVE_TERMS)
    negative = sum(term in lowered for term in NEGATIVE_TERMS)
    return 1 if positive > negative else -1 if negative > positive else 0


def run(snapshot: dict, upstream: dict, cfg: dict) -> dict:
    out = {"module": "m5", "status": "partial", "score": None, "metrics": {}, "evidence": [], "flags": []}
    articles = [
        article for article in snapshot.get("news", [])
        if article.get("published_at", "")[:10] <= snapshot.get("meta", {}).get("as_of", "")
    ]
    articles.sort(key=lambda article: article.get("published_at", ""), reverse=True)
    if len(articles) < 3:
        out.update(status="partial", evidence=[], flags=["fewer_than_three_news_items"])
        return out

    classified = []
    for article in articles:
        text = " ".join((article.get("title") or "", article.get("summary") or ""))
        classified.append((article, _classify(text)))
    positive = sum(sentiment > 0 for _, sentiment in classified)
    negative = sum(sentiment < 0 for _, sentiment in classified)
    neutral = len(classified) - positive - negative
    classifiable = positive + negative
    score = 50 + 50 * (positive - negative) / classifiable if classifiable else None
    out["score"] = round(score, 2) if score is not None and classifiable >= 3 else None
    out["status"] = "ok" if len(classified) >= 10 and classifiable >= 3 else "partial"
    out["flags"] = []
    if len(classified) < 10:
        out["flags"].append("news_sample_smaller_than_ten_items")
    if classifiable < 3:
        out["flags"].append("fewer_than_three_classifiable_news_items")
    out["metrics"] = {
        "articles": {"value": len(classified), "unit": "items", "note": "Tin có ngày công bố không sau ngày phân tích."},
        "positive": {"value": positive, "unit": "items"},
        "negative": {"value": negative, "unit": "items"},
        "neutral": {"value": neutral, "unit": "items"},
        "classifiable_articles": {"value": classifiable, "unit": "items"},
        "sentiment_score": {"value": round(score, 2) if out["score"] is not None else None, "unit": "0-100", "note": "Từ khóa; không phải mô hình ngôn ngữ."},
    }
    out["evidence"] = []
    for article, sentiment in classified:
        if sentiment:
            label = "Tích cực" if sentiment > 0 else "Tiêu cực"
            out["evidence"].append({
                "text": f"Tin {label}: {article.get('title', '')}",
                "news_id": article.get("id", ""),
            })
        if len(out["evidence"]) >= 6:
            break
    return out
