"""Compact DebatePayload cho LLM — không dump prices.rows."""
from __future__ import annotations

import hashlib
import json
import re
from typing import Any

# Trụ cột M7 ↔ module upstream
COMP_TO_MOD = {"F": "m2", "T": "m3", "V": "m4", "S": "m5", "R": "m6"}
MOD_TO_COMP = {v: k for k, v in COMP_TO_MOD.items()}


def _stable_json(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def payload_hash(payload: dict) -> str:
    """Hash ổn định của payload (giữ news_ref_map để khóa cache)."""
    return hashlib.sha256(_stable_json(payload).encode("utf-8")).hexdigest()


def compute_module_polarity(scores: dict | None, cfg: dict) -> dict[str, float]:
    """d_k lấy từ ``compute_score`` contributions (nguồn duy nhất, feature 010).

    Làm tròn 2 chữ số để LLM/template; khi chưa clamp: score − 50 = Σ d_k.
    """
    from stockai.m7_scoring.scoring import compute_score

    scores = scores or {}
    profile = cfg.get("profile") or "long_term"
    try:
        comp = compute_score(
            {k: scores.get(k) for k in ("F", "T", "V", "S", "R")},
            profile,
            cfg,
        )
    except (KeyError, ValueError, TypeError):
        # cfg thiếu (test hẹp) → d_k = 0
        return {k: 0.0 for k in ("F", "T", "V", "S", "R")}
    contrib = comp.get("contributions") or {}
    return {k: round(float(contrib.get(k, 0.0)), 2) for k in ("F", "T", "V", "S", "R")}


def _display_table(cfg: dict) -> dict:
    debate = cfg.get("debate") if isinstance(cfg.get("debate"), dict) else {}
    # cfg có thể là scoring đã merge llm, hoặc llm đầy đủ
    if not debate and isinstance(cfg.get("llm"), dict):
        debate = (cfg["llm"].get("debate") or {}) if isinstance(cfg["llm"].get("debate"), dict) else {}
    table = debate.get("display_metrics") if isinstance(debate, dict) else None
    return table if isinstance(table, dict) else {}


def metric_display_name(key: str, cfg: dict | None = None) -> str:
    """Tên tiếng Việt từ bảng display; fallback bỏ tiền tố mN."""
    table = _display_table(cfg or {})
    spec = table.get(key) if isinstance(table.get(key), dict) else None
    if not spec:
        short = key.split(".", 1)[-1]
        spec = table.get(short) if isinstance(table.get(short), dict) else None
    if spec and isinstance(spec.get("name"), str) and spec["name"].strip():
        return spec["name"].strip()
    return key.split(".", 1)[-1].replace("_", " ")


def format_metric_value(
    key: str,
    value: Any,
    unit: str | None = None,
    cfg: dict | None = None,
) -> str | None:
    """Format số cho văn bản: %, x, 1 decimal — không in raw nhiều chữ số thập phân."""
    if value is None or isinstance(value, bool):
        return None
    if not isinstance(value, (int, float)):
        return str(value)
    table = _display_table(cfg or {})
    spec = table.get(key) if isinstance(table.get(key), dict) else {}
    if not spec:
        short = key.split(".", 1)[-1]
        spec = table.get(short) if isinstance(table.get(short), dict) else {}
    fmt = (spec or {}).get("format")
    decimals = int((spec or {}).get("decimals", 1))
    unit_l = (unit or "").lower()
    if not fmt:
        if unit_l in ("ratio", "%", "pct", "percent"):
            fmt = "pct"
        elif unit_l in ("x", "times", "multiple"):
            fmt = "x"
        else:
            fmt = "number"
    v = float(value)
    if fmt == "pct":
        # ratio kiểu 0.18 → 18,0%; đã là % (vd 18) giữ nguyên nếu |v|>1
        pct = v * 100.0 if abs(v) <= 1.5 and unit_l in ("ratio", "", "index") else v
        if unit_l == "%":
            pct = v
        return f"{pct:.{decimals}f}%".replace(".", ",")
    if fmt == "x":
        return f"{v:.{decimals}f}x".replace(".", ",")
    # Số lớn nguyên (giá VND): bỏ phần thập phân thừa
    if abs(v) >= 1000 and abs(v - round(v)) < 1e-9:
        return f"{int(round(v)):,}".replace(",", ".")
    return f"{v:.{decimals}f}".replace(".", ",")


def normalize_vi_numbers(text: str) -> str:
    """Chuẩn hóa số trong câu: thập phân phẩy, nghìn chấm. Giữ năm YYYY và nhóm nghìn N.NNN.

    Ví dụ: 1.20→1,20; 0.80→0,80; 49.7%→49,7%; 20.150 giữ nguyên.
    """
    if not text:
        return text
    # Phần trăm kiểu Anh trước
    out = re.sub(r"(\d+)\.(\d+)%", r"\1,\2%", text)

    def _dec(m: re.Match[str]) -> str:
        return f"{m.group(1)},{m.group(2)}"

    # Thập phân Anh 1–2 chữ số sau chấm; không đụng nhóm nghìn (đúng 3 số)
    out = re.sub(r"(?<![\d.])(\d+)\.(\d{1,2})(?!\d)", _dec, out)
    return out


def format_contribution(d: float, *, decimals: int = 1) -> str:
    """Đóng góp điểm kiểu +4,4 / -2,2."""
    sign = "+" if d >= 0 else ""
    return f"{sign}{d:.{decimals}f}".replace(".", ",")


def _news_label_from_text(text: str) -> str | None:
    t = (text or "").strip().lower()
    if t.startswith("tích cực") or "| tích cực" in t or t.startswith("positive"):
        return "pos"
    if t.startswith("tiêu cực") or "| tiêu cực" in t or t.startswith("negative"):
        return "neg"
    if "tích cực |" in t or t.startswith("tích cực |"):
        return "pos"
    if "tiêu cực |" in t or t.startswith("tiêu cực |"):
        return "neg"
    # M5 format: "tích cực | title"
    if re.match(r"^tích\s*cực\s*\|", text or "", re.IGNORECASE):
        return "pos"
    if re.match(r"^tiêu\s*cực\s*\|", text or "", re.IGNORECASE):
        return "neg"
    return None


def _news_from_m5_evidence(upstream: dict, *, max_news: int = 6) -> tuple[list[dict], dict[str, str]]:
    """Tin từ upstream m5.evidence (có news_id), gán nK 1-based ổn định.

    Không lấy 12 tin đầu snapshot.news.
    """
    news_items: list[dict] = []
    news_ref_map: dict[str, str] = {}
    seen: set[str] = set()
    evidence = (upstream.get("m5") or {}).get("evidence") or []
    if not isinstance(evidence, list):
        return news_items, news_ref_map
    for ev in evidence:
        if not isinstance(ev, dict):
            continue
        nid = ev.get("news_id")
        if not nid:
            continue
        nid_s = str(nid)
        if nid_s in seen:
            continue
        text = ev.get("text") or ""
        if not isinstance(text, str) or not text.strip():
            continue
        label = _news_label_from_text(text)
        # Bỏ dòng tổng hợp sentiment (không có polarity article)
        if label is None and "|" not in text:
            continue
        seen.add(nid_s)
        ref = f"n{len(news_items) + 1}"
        news_ref_map[ref] = nid_s
        # title: phần sau | nếu có
        title = text
        if "|" in text:
            title = text.split("|", 1)[1].strip()
        item: dict[str, Any] = {
            "ref": ref,
            "id": nid_s,
            "title": title[:200],
        }
        if label:
            item["label"] = label  # pos | neg
        news_items.append(item)
        if len(news_items) >= max_news:
            break
    return news_items, news_ref_map


def _evidence_summaries(upstream: dict, *, max_per_module: int = 2) -> list[str]:
    """Tối đa 2 dòng evidence mỗi module M2–M6."""
    out: list[str] = []
    for mod in ("m2", "m3", "m4", "m5", "m6"):
        n = 0
        for ev in (upstream.get(mod) or {}).get("evidence") or []:
            if n >= max_per_module:
                break
            if not isinstance(ev, dict):
                continue
            t = ev.get("text") or ev.get("claim") or ""
            if isinstance(t, str) and t.strip():
                out.append(f"{mod}: {t.strip()[:160]}")
                n += 1
    return out


def build_debate_payload(
    snapshot: dict,
    upstream: dict,
    cfg: dict,
    *,
    score: float | None = None,
    rating: str | None = None,
    scores: dict | None = None,
    prompt_version: str = "v1",
    max_news: int = 6,
    max_metrics_per_module: int = 12,
) -> dict:
    """Xây payload compact + metrics_allowed + news_ref_map (nK từ M5 evidence).

    MUST NOT include full ``prices.rows``.
    ``module_polarity`` = d_k làm tròn để LLM biết trụ kéo lên/xuống.
    """
    meta = snapshot.get("meta") or {}
    ticker = meta.get("ticker") or ""
    as_of = meta.get("as_of") or ""
    profile = cfg.get("profile") or "long_term"

    # scores F/T/V/S/R: ưu tiên tham số; fallback upstream module scores
    if scores is None:
        scores = {}
        for comp, mod in COMP_TO_MOD.items():
            block = upstream.get(mod) or {}
            if isinstance(block, dict) and block.get("status") != "error":
                scores[comp] = block.get("score")
            else:
                scores[comp] = None

    module_polarity = compute_module_polarity(scores, cfg)

    metrics: dict[str, dict] = {}
    metrics_allowed: list[str] = []
    # Ưu tiên metric “diễn giải” trước các news_*_count của M5
    _mod_pref = {
        "m2": [
            "roe", "roa", "net_income_growth", "revenue_growth", "gross_margin",
            "debt_to_equity", "current_ratio", "interest_coverage", "cfo_to_net_income",
        ],
        "m3": ["rsi14", "rsi_14", "close", "ma20", "ma50", "volume_ratio_20", "macd", "atr_pct"],
        "m4": ["pe", "pb", "price_close", "eps_used", "sector_median_pe", "sector_median_pb", "score_V"],
        "m5": [
            "sentiment_polarity", "sentiment_score", "sentiment_confidence", "sentiment",
            "news_positive_count", "news_negative_count", "news_directional_count",
        ],
        "m6": ["beta", "vol_20d", "volatility", "max_drawdown", "var_95", "cvar_95"],
    }

    def _ordered_metric_names(mod: str, raw: dict) -> list[str]:
        pref = _mod_pref.get(mod, [])
        names: list[str] = []
        for n in pref:
            if n in raw:
                names.append(n)
        for n in raw:
            if isinstance(n, str) and n not in names:
                # M5: bỏ qua hầu hết bộ đếm tin trừ đã ưu tiên
                if mod == "m5" and n.startswith("news_") and n not in pref:
                    continue
                names.append(n)
        return names

    for mod in ("m2", "m3", "m4", "m5", "m6"):
        block = upstream.get(mod) or {}
        raw = block.get("metrics") or {}
        if not isinstance(raw, dict):
            continue
        count = 0
        for name in _ordered_metric_names(mod, raw):
            if count >= max_metrics_per_module:
                break
            if not isinstance(name, str) or not name:
                continue
            m = raw[name]
            key = f"{mod}.{name}"
            entry: dict[str, Any] = {}
            if isinstance(m, dict):
                if "value" in m:
                    entry["value"] = m.get("value")
                if m.get("unit"):
                    entry["unit"] = m.get("unit")
            else:
                entry["value"] = m
            # kèm display sẵn cho LLM/template
            disp = format_metric_value(key, entry.get("value"), entry.get("unit"), cfg)
            if disp:
                entry["display"] = disp
            entry["display_name"] = metric_display_name(key, cfg)
            metrics[key] = entry
            metrics_allowed.append(key)
            count += 1

    news_items, news_ref_map = _news_from_m5_evidence(upstream, max_news=max_news)
    evidence_summaries = _evidence_summaries(upstream, max_per_module=2)

    payload = {
        "ticker": ticker,
        "as_of": as_of,
        "profile": profile,
        "score": score,
        "rating": rating,
        "scores": scores or {},
        "module_polarity": module_polarity,
        "metrics": metrics,
        "metrics_allowed": metrics_allowed,
        "news": news_items,
        "news_ref_map": news_ref_map,
        "evidence_summaries": evidence_summaries,
        "prompt_version": prompt_version,
    }
    assert "prices" not in payload
    return payload


def payload_for_llm(payload: dict) -> dict:
    """Bản gửi LLM — bỏ news_ref_map (nội bộ validator), giữ news[].ref."""
    return {k: v for k, v in payload.items() if k != "news_ref_map"}
