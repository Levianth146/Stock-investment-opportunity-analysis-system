"""Template fallback xác định cho debate Bull/Bear (không gọi LLM).

Luận điểm theo độ lệch trụ cột: d_k = w_k*(score_k-50); d_R = -λ*(R-50).
Bull = d>0 (mạnh nhất trước); Bear = d<0. Không in raw key mN.name / số kiểu Anh.
"""
from __future__ import annotations

import re
from typing import Any

from stockai.llm.payload import (
    COMP_TO_MOD,
    format_contribution,
    format_metric_value,
    metric_display_name,
    normalize_vi_numbers,
)

# Metric ưu tiên theo module khi chọn dẫn chứng
_PREF_METRICS: dict[str, list[str]] = {
    "m2": [
        "roe",
        "roa",
        "net_income_growth",
        "revenue_growth",
        "gross_margin",
        "debt_to_equity",
        "current_ratio",
    ],
    "m3": ["rsi14", "rsi_14", "close", "ma20", "ma50", "volume_ratio_20", "macd"],
    "m4": ["pe", "pb", "price_close", "sector_median_pe", "sector_median_pb"],
    "m5": ["sentiment_polarity", "sentiment_score", "sentiment"],
    "m6": [
        "beta",
        "annualized_volatility",
        "vol_20d",
        "volatility",
        "max_drawdown",
        "var_95",
    ],
}

# Metric không dùng làm dẫn chứng văn bản
_SKIP_METRIC_NAMES = {
    "aligned_observations",
    "observations",
    "invalid_price_rows",
    "future_rows_excluded",
    "benchmark_future_rows_excluded",
    "news_input_count",
    "news_relevant_count",
    "news_duplicate_count",
    "news_future_excluded",
    "news_old_excluded",
    "news_offtopic_excluded",
    "news_newest_age_days",
    "news_multi_ticker_weighted",
    "sector_stats_version",
    "sector_n_pe",
    "sector_n_pb",
    "v_pe_leg",
    "v_pb_leg",
}

_COMP_VI = {"F": "cơ bản (F)", "T": "kỹ thuật (T)", "V": "định giá (V)", "S": "tin tức (S)", "R": "rủi ro (R)"}

# Cụm tiếng Anh máy móc thường gặp trong evidence M4 — nhẹ hóa khi chép vào template
_EVID_EN_REPLACEMENTS = (
    (re.compile(r"\bso median ngành\b", re.I), "so với trung vị ngành"),
    (re.compile(r"\bso median\b", re.I), "so với trung vị"),
    (re.compile(r"\bnguồn EPS=ttm_ni\b", re.I), "nguồn EPS=TTM"),
)


def _cfg_debate(cfg: dict | None) -> dict:
    cfg = cfg or {}
    if isinstance(cfg.get("debate"), dict):
        return cfg
    if isinstance(cfg.get("llm"), dict) and isinstance(cfg["llm"].get("debate"), dict):
        return {**cfg, "debate": cfg["llm"]["debate"]}
    return cfg


def _polarity(payload: dict) -> dict[str, float]:
    mp = payload.get("module_polarity") or {}
    out: dict[str, float] = {}
    for k in ("F", "T", "V", "S", "R"):
        v = mp.get(k)
        if isinstance(v, (int, float)):
            out[k] = float(v)
    return out


def _sorted_side(polarity: dict[str, float], *, bull: bool) -> list[tuple[str, float]]:
    items = []
    for k, d in polarity.items():
        if bull and d > 0:
            items.append((k, d))
        elif (not bull) and d < 0:
            items.append((k, d))
    # Bull: mạnh nhất trước (d lớn); Bear: lệch âm mạnh nhất trước (d nhỏ hơn)
    items.sort(key=lambda x: x[1], reverse=bull)
    return items


def _metric_entry(payload: dict, key: str) -> dict | None:
    m = (payload.get("metrics") or {}).get(key)
    return m if isinstance(m, dict) else None


def _metric_bad_for_bull(name: str, value: Any) -> bool:
    """Tránh đưa chỉ số tăng trưởng âm vào Bull dù nhầm lẫn."""
    if not isinstance(value, (int, float)):
        return False
    n = name.lower()
    if "growth" in n and float(value) < 0:
        return True
    if n in ("debt_to_equity", "debt_to_assets", "max_drawdown", "var_95"):
        # nợ / drawdown / VaR: không dùng làm dẫn chứng Bull (kể cả khi trụ R hỗ trợ)
        return True
    return False


def _metric_bad_for_bear(name: str, value: Any) -> bool:
    if not isinstance(value, (int, float)):
        return False
    n = name.lower()
    # tăng trưởng dương mạnh không phải dẫn chứng Bear
    if "growth" in n and float(value) > 0:
        return True
    return False


def _pick_metrics_for_module(
    payload: dict,
    mod: str,
    *,
    for_bull: bool,
    limit: int = 2,
    cfg: dict | None = None,
) -> list[tuple[str, str, str]]:
    """Trả list (key, display_name, display_value) phù hợp phía."""
    cfg = _cfg_debate(cfg)
    allowed = set(payload.get("metrics_allowed") or [])
    metrics = payload.get("metrics") or {}
    pref = _PREF_METRICS.get(mod, [])
    ordered: list[str] = []
    for name in pref:
        key = f"{mod}.{name}"
        if key in metrics and key in allowed:
            ordered.append(key)
    for key in metrics:
        if isinstance(key, str) and key.startswith(f"{mod}.") and key not in ordered and key in allowed:
            ordered.append(key)
    out: list[tuple[str, str, str]] = []
    for key in ordered:
        entry = _metric_entry(payload, key)
        if not entry:
            continue
        val = entry.get("value")
        name = key.split(".", 1)[-1]
        if name in _SKIP_METRIC_NAMES or name.endswith("_excluded") or "excluded" in name:
            continue
        if for_bull and _metric_bad_for_bull(name, val):
            continue
        if (not for_bull) and _metric_bad_for_bear(name, val):
            continue
        disp = entry.get("display") or format_metric_value(key, val, entry.get("unit"), cfg)
        if not disp:
            continue
        dname = entry.get("display_name") or metric_display_name(key, cfg)
        # Nếu display_name vẫn là raw snake/space Anh → lấy lại từ bảng config
        raw_fallback = name.replace("_", " ")
        if dname in (name, raw_fallback) or ("_" in str(dname) and str(dname).islower()):
            dname = metric_display_name(key, cfg)
        out.append((key, str(dname), str(disp)))
        if len(out) >= limit:
            break
    return out


def _polish_evidence_body(body: str) -> str:
    """Làm sạch evidence trước khi đưa vào text: bỏ raw key, chuẩn số, nhẹ hóa cụm Anh."""
    body = re.sub(r"\bm[0-9]+\.[A-Za-z0-9_]+\b", "", body).strip(" ;,")
    for pat, repl in _EVID_EN_REPLACEMENTS:
        body = pat.sub(repl, body)
    return normalize_vi_numbers(body)


def _evidence_lines(payload: dict, mod: str, *, for_bull: bool) -> list[str]:
    """Ưu tiên evidence tiếng Việt đã format số (đặc biệt M4)."""
    lines: list[str] = []
    for s in payload.get("evidence_summaries") or []:
        if not isinstance(s, str) or not s.startswith(f"{mod}:"):
            continue
        body = s.split(":", 1)[-1].strip()
        if not body:
            continue
        # Bỏ evidence tiếng Anh máy móc ít giá trị
        if body.startswith("Financial statement") or body.startswith("Technical indicators"):
            continue
        if body.startswith("Quantitative risk"):
            continue
        # M5: lọc polarity tin — template S ưu tiên news riêng, evidence title dễ trùng
        low = body.lower()
        if mod == "m5":
            if for_bull and not (low.startswith("tích cực") or "tích cực |" in low):
                if low.startswith("tiêu cực") or low.startswith("sentiment theo"):
                    continue
            if (not for_bull) and not (low.startswith("tiêu cực") or "tiêu cực |" in low):
                if low.startswith("tích cực") or low.startswith("sentiment theo"):
                    continue
        # M4: evidence “P/E thấp hơn” là tích cực định giá — không dùng cho Bear
        if mod == "m4":
            if for_bull and "cao hơn" in low and ("p/e" in low or "p/b" in low):
                continue
            if (not for_bull) and "thấp hơn" in low and ("p/e" in low or "p/b" in low):
                continue
        lines.append(_polish_evidence_body(body))
    return lines


def _news_for_side(payload: dict, *, for_bull: bool, limit: int = 1) -> list[dict]:
    """Tin chỉ khi label khớp phía (pos→Bull, neg→Bear) và S lệch đúng hướng."""
    pol = _polarity(payload)
    d_s = pol.get("S", 0.0)
    if for_bull and d_s <= 0:
        return []
    if (not for_bull) and d_s >= 0:
        return []
    want = "pos" if for_bull else "neg"
    out: list[dict] = []
    for n in payload.get("news") or []:
        if not isinstance(n, dict):
            continue
        if n.get("label") != want:
            continue
        out.append(n)
        if len(out) >= limit:
            break
    return out


def _news_line(n: dict, *, for_bull: bool, max_chars: int = 110) -> str:
    """Một dòng tin: Tin tích cực/tiêu cực: «tiêu đề» (không lặp title)."""
    title = (n.get("title") or "").strip()
    # Bỏ prefix polarity nếu title vẫn còn
    title = re.sub(r"^(tích\s*cực|tiêu\s*cực)\s*\|\s*", "", title, flags=re.I).strip()
    if len(title) > max_chars:
        title = title[: max_chars - 1] + "…"
    label = "tích cực" if for_bull else "tiêu cực"
    return f"Tin {label}: «{title}»"


def _refs_mentioned(text: str, candidates: list[str], news: list[dict]) -> list[str]:
    """Chỉ giữ ref đã được nhắc trong câu (qua tên hiển thị / title), không padding."""
    refs: list[str] = []
    for c in candidates:
        if c and c not in refs:
            refs.append(c)
    for n in news:
        ref = n.get("ref")
        title = (n.get("title") or "")[:40]
        if isinstance(ref, str) and title and title[:20] in text:
            if ref not in refs:
                refs.append(ref)
        elif isinstance(ref, str) and ref in text:
            if ref not in refs:
                refs.append(ref)
    return refs[:3]


def _score_phrase(payload: dict, comps: list[str]) -> str:
    scores = payload.get("scores") or {}
    parts = []
    for c in comps:
        v = scores.get(c)
        if isinstance(v, (int, float)):
            parts.append(f"{c}={v:.1f}".replace(".", ","))
        else:
            parts.append(f"{c}=N/A")
    return "; ".join(parts)


def _head_phrase(ticker: str, comp: str, d: float, *, for_bull: bool) -> str:
    """Câu mở: đóng góp ±X,X điểm; trụ R nói rủi ro thấp/cao hơn TB."""
    label = _COMP_VI.get(comp, comp)
    direction = "hỗ trợ" if for_bull else "gây áp lực lên"
    contrib = format_contribution(d, decimals=1)
    if comp == "R":
        # d_R > 0 ↔ R thấp ↔ rủi ro thấp hơn TB; d_R < 0 ↔ rủi ro cao hơn TB
        risk = "rủi ro thấp hơn mức trung bình" if d > 0 else "rủi ro cao hơn mức trung bình"
        return f"{ticker}: trụ {label} {direction} điểm ({risk}, đóng góp {contrib} điểm)."
    return f"{ticker}: trụ {label} {direction} điểm (đóng góp {contrib} điểm)."


def _finalize_text(text: str) -> str:
    text = re.sub(r"\bm[0-9]+\.[A-Za-z0-9_]+\b", "", text)
    text = normalize_vi_numbers(text)
    text = re.sub(r"\s{2,}", " ", text).strip()
    return text


def _honest_empty(side: str, payload: dict, cfg: dict | None = None) -> dict:
    """Một luận điểm trung thực khi không có trụ lệch đúng hướng."""
    scores = payload.get("scores") or {}
    comps = ["F", "T", "V", "S", "R"]
    score_txt = _score_phrase(payload, comps)
    if side == "bull":
        text = (
            f"Không có yếu tố tích cực nổi bật so với mức trung tính: "
            f"các trụ cột đều kéo điểm xuống hoặc trung tính ({score_txt})."
        )
    else:
        text = (
            f"Không có yếu tố tiêu cực nổi bật: "
            f"các trụ cột không lệch xuống so với mức trung tính ({score_txt})."
        )
    refs: list[str] = []
    allowed = set(payload.get("metrics_allowed") or [])
    for_bull = side == "bull"
    for c in comps:
        mod = COMP_TO_MOD[c]
        picked = _pick_metrics_for_module(payload, mod, for_bull=for_bull, limit=1, cfg=cfg)
        if not picked:
            for key in payload.get("metrics_allowed") or []:
                if not key.startswith(f"{mod}.") or key not in allowed:
                    continue
                entry = _metric_entry(payload, key)
                name = key.split(".", 1)[-1]
                val = entry.get("value") if entry else None
                if for_bull and _metric_bad_for_bull(name, val):
                    continue
                if (not for_bull) and _metric_bad_for_bear(name, val):
                    continue
                picked = [(key, "", "")]
                break
        if picked:
            refs.append(picked[0][0])
    if not refs and allowed:
        for key in list(allowed):
            name = key.split(".", 1)[-1]
            entry = _metric_entry(payload, key)
            val = entry.get("value") if entry else None
            if for_bull and _metric_bad_for_bull(name, val):
                continue
            refs.append(key)
            if len(refs) >= 2:
                break
    return {"text": _finalize_text(text), "refs": refs[:5]}


def _item_from_component(
    payload: dict,
    comp: str,
    d: float,
    *,
    for_bull: bool,
    cfg: dict | None,
) -> dict | None:
    mod = COMP_TO_MOD[comp]
    ticker = payload.get("ticker") or "?"
    news = _news_for_side(payload, for_bull=for_bull, limit=1) if comp == "S" else []
    metrics = _pick_metrics_for_module(payload, mod, for_bull=for_bull, limit=2, cfg=cfg)
    evid = _evidence_lines(payload, mod, for_bull=for_bull)

    metric_refs: list[str] = []
    parts: list[str] = []
    used_news: list[dict] = []

    head = _head_phrase(ticker, comp, d, for_bull=for_bull)

    # S + tin: chỉ in title một lần theo mẫu Tin tích cực/tiêu cực: «…»
    if comp == "S" and news:
        n0 = news[0]
        title = (n0.get("title") or "").strip()
        if title:
            parts.append(_news_line(n0, for_bull=for_bull))
            used_news.append(n0)
    elif evid:
        body = evid[0]
        # M5 evidence dạng "tích cực | title" mà không có news object — tránh lặp
        if mod == "m5" and "|" in body:
            left, _, right = body.partition("|")
            if "tích cực" in left.lower() or "tiêu cực" in left.lower():
                fake = {"title": right.strip(), "ref": None}
                parts.append(_news_line(fake, for_bull=for_bull))
            else:
                parts.append(body)
        else:
            parts.append(body)
        for key, dname, dval in metrics:
            if dname and dname.lower() in body.lower():
                metric_refs.append(key)
            elif dval and dval in body:
                metric_refs.append(key)
    elif metrics:
        bits = [f"{dname} {dval}" for _, dname, dval in metrics]
        parts.append(", ".join(bits))
        metric_refs.extend(k for k, _, _ in metrics)
    else:
        return None

    text = head + " " + parts[0]

    if comp == "S" and used_news:
        refs = [n["ref"] for n in used_news if isinstance(n.get("ref"), str)]
        for key, dname, dval in metrics:
            if dname and dname.lower() in text.lower():
                refs.append(key)
        refs = refs[:3]
    else:
        refs = _refs_mentioned(text, metric_refs, used_news)
        if not refs and metrics:
            key, dname, dval = metrics[0]
            text = f"{text} ({dname}: {dval})."
            refs = [key]

    if not refs:
        return None
    return {"text": _finalize_text(text), "refs": refs}


def build_template_debate(payload: dict, *, cfg: dict | None = None) -> tuple[list[dict], list[dict], list[str]]:
    """Sinh bull/bear deterministic từ payload + module_polarity.

    Cùng snapshot+upstream+cfg (→ cùng payload) → cùng text.
    """
    cfg = _cfg_debate(cfg)
    polarity = _polarity(payload)
    bull_comps = _sorted_side(polarity, bull=True)
    bear_comps = _sorted_side(polarity, bull=False)

    bull: list[dict] = []
    bear: list[dict] = []

    for comp, d in bull_comps:
        if len(bull) >= 3:
            break
        item = _item_from_component(payload, comp, d, for_bull=True, cfg=cfg)
        if item:
            if "net_income_growth" in item["text"] and any(
                "net_income_growth" in r for r in item["refs"]
            ):
                entry = _metric_entry(payload, "m2.net_income_growth")
                if entry and isinstance(entry.get("value"), (int, float)) and entry["value"] < 0:
                    continue
            bull.append(item)

    for comp, d in bear_comps:
        if len(bear) >= 3:
            break
        item = _item_from_component(payload, comp, d, for_bull=False, cfg=cfg)
        if item:
            bear.append(item)

    if not bull:
        bull = [_honest_empty("bull", payload, cfg)]
    if not bear:
        bear = [_honest_empty("bear", payload, cfg)]

    def _pad(side_items: list[dict], comps: list[tuple[str, float]], *, for_bull: bool) -> list[dict]:
        if len(side_items) >= 2 or not comps:
            return side_items
        for comp, d in comps[1:]:
            item = _item_from_component(payload, comp, d, for_bull=for_bull, cfg=cfg)
            if item and item["text"] != side_items[0]["text"]:
                side_items.append(item)
                return side_items
        comp0, d0 = comps[0]
        mod = COMP_TO_MOD[comp0]
        extras = _pick_metrics_for_module(payload, mod, for_bull=for_bull, limit=3, cfg=cfg)
        if len(extras) >= 2:
            key, dname, dval = extras[1]
            ticker = payload.get("ticker") or "?"
            text = _finalize_text(
                f"{ticker}: thêm dẫn chứng trụ {_COMP_VI.get(comp0, comp0)} — {dname} {dval}."
            )
            side_items.append({"text": text, "refs": [key]})
        return side_items

    bull = _pad(bull, bull_comps, for_bull=True)
    bear = _pad(bear, bear_comps, for_bull=False)

    flags = ["debate_fallback_template", "m7_debate_fallback_used"]
    return bull, bear, flags
