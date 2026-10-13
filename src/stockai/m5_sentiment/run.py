"""m5 - điểm S (sentiment) từ tiêu đề tin.

Chữ ký: run(snapshot, upstream, cfg) -> dict đã validate module_out.
Chỉ chấm tiêu đề; lexicon heuristic; không LLM.
Chuẩn hóa: NFC + lower + gộp khoảng trắng/dấu câu; GIỮ dấu tiếng Việt và đ.
"""
from __future__ import annotations

import math
import re
import unicodedata
from collections import Counter
from copy import deepcopy
from datetime import date, datetime
from pathlib import Path
from typing import Any

import yaml

from stockai.contracts.schemas import validate

_ROOT = Path(__file__).resolve().parents[3]
_SENTIMENT_YAML = _ROOT / "config" / "sentiment.yaml"
_LEXICON_YAML = _ROOT / "config" / "sentiment_lexicon.yaml"
_ALIASES_YAML = _ROOT / "config" / "news_aliases.yaml"
_UNIVERSE_TXT = _ROOT / "config" / "universe_hose_hnx.txt"

_DEFAULT_M5: dict[str, Any] = {
    "llm_enabled": False,
    "lookback_days": 60,
    "half_life_days": 14,
    "min_relevant_news": 3,
    "min_directional_news": 2,
    "ambiguous_tickers": ["CEO", "HCM", "VND", "AAA"],
    "brokerage_tickers": [
        "SSI",
        "VND",
        "HCM",
        "VCI",
        "MBS",
        "SHS",
        "BSI",
        "FTS",
        "CTS",
        "VIX",
        "ORS",
        "BVS",
        "TVS",
        "AGR",
        "APS",
        "BSC",
        "VDS",
    ],
    "brokerage_market_themes": [
        "chứng khoán",
        "thị trường",
        "vn-index",
        "vnindex",
        "rung lắc",
        "nghỉ lễ",
    ],
    "score": {
        "base": 50,
        "scale": 35,
        "conf_dir_cap": 12,
        "conf_coverage_ref": 0.35,
    },
    "evidence_max_headlines": 6,
    "multi_ticker_threshold": 3,
    "multi_ticker_weight": 0.3,
    "weak_subject_weight": 0.3,
    "flow_weight_multiplier": 0.5,
    "story_jaccard_threshold": 0.6,
    "story_window_days": 3,
    "news_stale_days": 14,
    "subject_lead_tokens": 6,
    "negation_window_tokens": 3,
    "flip_window_tokens": 3,
    "market_summary_ticker_action_weight": 0.6,
    "market_summary_ticker_action_window": 4,
}

_DEFAULT_LEXICON: dict[str, Any] = {
    "positive": {
        "lợi nhuận tăng": 1.3,
        "doanh thu tăng": 1.1,
        "vượt kế hoạch": 1.3,
        "ký hợp đồng": 0.8,
        "khởi sắc": 0.8,
        "phục hồi": 0.8,
        "trúng thầu": 1.1,
    },
    "negative": {
        "thua lỗ": -1.4,
        "lợi nhuận giảm": -1.2,
        "doanh thu giảm": -1.0,
        "điều tra": -0.9,
        "vi phạm": -1.2,
        "bán tháo": -1.4,
        "lao dốc": -1.3,
        "giảm liên tiếp": -1.0,
        "kỷ lục buồn": -1.2,
        "chuỗi phiên giảm": -1.1,
        "chuỗi ngày giảm": -1.1,
        "giảm điểm": -0.7,
    },
    "announcements_positive": {},
    "announcements_negative": {},
    "flow_positive": {"khối ngoại mua ròng": 0.8, "tự doanh mua ròng": 0.7},
    "flow_negative": {"khối ngoại bán ròng": -0.8, "tự doanh bán ròng": -0.7},
    "force_neutral": [
        "phát hành cổ phiếu thưởng",
        "cổ phiếu thưởng",
        "phát hành cổ phiếu để trả cổ tức",
        "phát hành cổ phiếu trả cổ tức",
        "phát hành cp để trả cổ tức",
        "phát hành cp trả cổ tức",
        "cổ phiếu để trả cổ tức",
        "cổ phiếu trả cổ tức",
        "cổ tức bằng cổ phiếu",
        "cổ tức bằng cp",
        "phcp để trả cổ tức",
        "đính chính",
        "quản trị rủi ro",
        "giải trình",
    ],
    "negation_phrases": [
        "chấm dứt",
        "thoát khỏi",
        "không còn",
        "thoát",
        "hết",
        "chưa",
        "không",
        "tránh",
    ],
    "market_summary_markers": [
        "vn-index",
        "vnindex",
        "phiên ngày",
        "thị trường chứng khoán ngày",
    ],
    "market_summary_ticker_action_phrases": [
        "ngược dòng",
        "tăng trần",
        "giảm sàn",
        "dư bán sàn",
        "kịch biên độ",
        "kịch trần",
        "tăng mạnh",
        "giảm mạnh",
        "hụt hơi",
        "lao dốc",
        "hit the ceiling",
        "surged",
        "plunged",
    ],
    "research_issuer_markers": [
        "research",
        "securities",
        "chứng khoán",
        "dự báo của",
    ],
    "flip_objects": [
        "nợ vay",
        "nợ",
        "chi phí",
        "lỗ",
        "nợ xấu",
    ],
}

_DEFAULT_ALIASES: dict[str, Any] = {
    "finance_keywords": [
        "cổ phiếu",
        "chứng khoán",
        "doanh thu",
        "lợi nhuận",
        "giao dịch",
        "cổ đông",
        "hose",
        "hnx",
        "hợp đồng",
        "trúng thầu",
        "mua ròng",
        "bán ròng",
    ],
    "cw_patterns": [r"chứng quyền", r"\bcw\b", r"warrant"],
    "company_aliases": {
        "CEO": ["ceo group", "tập đoàn ceo"],
        "HCM": ["chứng khoán hcm", "saigon securities"],
        "VND": ["vndirect", "chứng khoán vndirect"],
        "AAA": ["an phát", "an phát holdings"],
    },
}

_UNIVERSE_CACHE: set[str] | None = None


def _deep_merge(base: dict, overlay: dict) -> dict:
    out = deepcopy(base)
    for k, v in (overlay or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def _safe_load_yaml(path: Path) -> tuple[dict, bool]:
    try:
        if path.is_file():
            raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            return dict(raw) if isinstance(raw, dict) else {}, False
    except (OSError, yaml.YAMLError, TypeError):
        return {}, True
    return {}, True


def load_universe_tickers(path: Path | None = None) -> set[str]:
    """Đọc mã từ universe_hose_hnx.txt (không đoán mọi cụm 3 chữ IN HOA)."""
    global _UNIVERSE_CACHE
    if path is None and _UNIVERSE_CACHE is not None:
        return _UNIVERSE_CACHE
    p = path or _UNIVERSE_TXT
    codes: set[str] = set()
    try:
        if p.is_file():
            for line in p.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                for tok in line.split():
                    t = tok.strip().upper()
                    if re.fullmatch(r"[A-Z]{3}", t):
                        codes.add(t)
    except OSError:
        pass
    if path is None:
        _UNIVERSE_CACHE = codes
    return codes


def _float_dict(raw: object) -> dict[str, float]:
    if not isinstance(raw, dict):
        return {}
    out: dict[str, float] = {}
    for k, v in raw.items():
        try:
            out[str(k)] = float(v)
        except (TypeError, ValueError):
            continue
    return out


def _str_list(raw: object) -> list[str]:
    if isinstance(raw, list):
        return [str(x) for x in raw if x]
    return []


def _load_m5_cfg(cfg: dict | None) -> tuple[dict[str, Any], bool]:
    """Gộp cfg.m5 + sentiment.yaml (+ lexicon/aliases); thiếu → defaulted."""
    defaulted = False
    file_raw, miss = _safe_load_yaml(_SENTIMENT_YAML)
    defaulted = defaulted or miss
    file_m5 = dict(file_raw.get("m5") or file_raw)

    lex_raw, miss_lex = _safe_load_yaml(_LEXICON_YAML)
    defaulted = defaulted or miss_lex
    alias_raw, miss_alias = _safe_load_yaml(_ALIASES_YAML)
    defaulted = defaulted or miss_alias

    merged = _deep_merge(_DEFAULT_M5, file_m5)
    overlay = cfg.get("m5") if isinstance(cfg, dict) and isinstance(cfg.get("m5"), dict) else {}
    flat_keys = (
        "lookback_days",
        "half_life_days",
        "min_relevant_news",
        "min_directional_news",
        "ambiguous_tickers",
        "brokerage_tickers",
        "brokerage_market_themes",
        "llm_enabled",
        "evidence_max_headlines",
        "multi_ticker_threshold",
        "multi_ticker_weight",
        "weak_subject_weight",
        "flow_weight_multiplier",
        "story_jaccard_threshold",
        "story_window_days",
        "news_stale_days",
        "subject_lead_tokens",
        "negation_window_tokens",
        "flip_window_tokens",
        "market_summary_ticker_action_weight",
        "market_summary_ticker_action_window",
    )
    if isinstance(cfg, dict):
        for k in flat_keys:
            if k in cfg and k not in overlay:
                overlay[k] = cfg[k]
        if isinstance(cfg.get("score"), dict) and "score" not in overlay:
            overlay["score"] = cfg["score"]
    merged = _deep_merge(merged, overlay)

    # File lexicon ghi đè từng nhóm (không merge cụm với default — tránh khớp kép).
    if miss_lex:
        defaulted = True
        lex_src = _DEFAULT_LEXICON
    else:
        lex_src = dict(_DEFAULT_LEXICON)
        for key in (
            "positive",
            "negative",
            "announcements_positive",
            "announcements_negative",
            "flow_positive",
            "flow_negative",
            "force_neutral",
            "negation_phrases",
            "market_summary_markers",
            "market_summary_ticker_action_phrases",
            "research_issuer_markers",
            "flip_objects",
        ):
            if key in lex_raw and lex_raw[key] is not None:
                lex_src[key] = lex_raw[key]

    for key in (
        "positive",
        "negative",
        "announcements_positive",
        "announcements_negative",
        "flow_positive",
        "flow_negative",
    ):
        merged[f"lexicon_{key}"] = _float_dict(lex_src.get(key))
        if key in ("positive", "negative") and not merged[f"lexicon_{key}"]:
            defaulted = True

    merged["force_neutral"] = _str_list(lex_src.get("force_neutral"))
    merged["negation_phrases"] = _str_list(lex_src.get("negation_phrases"))
    merged["market_summary_markers"] = _str_list(lex_src.get("market_summary_markers"))
    merged["market_summary_ticker_action_phrases"] = _str_list(
        lex_src.get("market_summary_ticker_action_phrases")
    )
    merged["research_issuer_markers"] = _str_list(lex_src.get("research_issuer_markers"))
    merged["flip_objects"] = _str_list(lex_src.get("flip_objects"))

    aliases = _deep_merge(_DEFAULT_ALIASES, alias_raw if alias_raw else {})
    if miss_alias:
        defaulted = True
    merged["finance_keywords"] = list(aliases.get("finance_keywords") or [])
    merged["cw_patterns"] = list(aliases.get("cw_patterns") or [])
    merged["company_aliases"] = dict(aliases.get("company_aliases") or {})
    merged["brokerage_tickers"] = [
        str(x).upper() for x in (merged.get("brokerage_tickers") or []) if x
    ]
    merged["brokerage_market_themes"] = list(merged.get("brokerage_market_themes") or [])
    merged["universe"] = load_universe_tickers()
    return merged, defaulted


def normalize_title(value: object) -> str:
    """NFC + lowercase; chỉ gộp khoảng trắng/dấu câu; GIỮ dấu tiếng Việt và đ."""
    text = unicodedata.normalize("NFC", str(value or "")).lower()
    # Giữ chữ/số Unicode (gồm có dấu, đ); thay mọi ký tự khác bằng khoảng trắng.
    text = re.sub(r"[^\w]+", " ", text, flags=re.UNICODE)
    text = text.replace("_", " ")
    return " ".join(text.split())


def parse_date(value: object) -> date | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).date()
    except (ValueError, TypeError):
        try:
            return date.fromisoformat(str(value)[:10])
        except (ValueError, TypeError):
            return None


def _tokens(text: str) -> list[str]:
    return [t for t in text.split() if t]


def _word_hit(haystack: str, needle: str) -> bool:
    if not needle:
        return False
    return bool(re.search(r"(?<!\w)" + re.escape(needle) + r"(?!\w)", haystack, flags=re.UNICODE))


def _phrase_span(tokens: list[str], phrase_norm: str) -> list[tuple[int, int]]:
    """Vị trí (start, end exclusive) của cụm trong danh sách token."""
    ptoks = _tokens(phrase_norm)
    if not ptoks:
        return []
    n, m = len(tokens), len(ptoks)
    spans: list[tuple[int, int]] = []
    for i in range(n - m + 1):
        if tokens[i : i + m] == ptoks:
            spans.append((i, i + m))
    return spans


def _has_negation_before(
    tokens: list[str],
    start: int,
    negation_norms: list[str],
    window: int,
) -> bool:
    if start <= 0 or window <= 0:
        return False
    left = tokens[max(0, start - window) : start]
    left_text = " ".join(left)
    # Ưu tiên cụm dài hơn (thoát khỏi trước thoát; không còn trước không).
    for neg in sorted(negation_norms, key=len, reverse=True):
        if not neg:
            continue
        ntoks = _tokens(neg)
        if not ntoks:
            continue
        if len(ntoks) == 1:
            if ntoks[0] in left:
                return True
        else:
            if _word_hit(left_text, neg):
                return True
    return False


def _matching_phrases(text: str, dictionary: dict[str, float]) -> list[tuple[str, float, str]]:
    """Trả (phrase gốc, weight, phrase_norm)."""
    hits: list[tuple[str, float, str]] = []
    for phrase, weight in dictionary.items():
        p = normalize_title(phrase)
        if p and _word_hit(text, p):
            hits.append((phrase, float(weight), p))
    return hits


def _is_vci_source(source: object) -> bool:
    s = str(source or "").strip().lower()
    if not s:
        return False
    return "vnstock" in s or s.endswith("/vci") or s == "vci" or "vnstock/vci" in s


def _is_market_summary(title_norm: str, markers: list[str]) -> bool:
    return any(normalize_title(m) and normalize_title(m) in title_norm for m in markers)


def _ticker_price_action_near(
    title_norm: str,
    ticker: str,
    action_phrases: list[str],
    window: int = 4,
) -> bool:
    """True nếu cụm hành động giá nằm trong cửa sổ token quanh mã (gắn mã này).

    Cửa sổ: token sau mã trong [1..window] (cụm có thể kéo dài quá window nếu
    bắt đầu trong cửa sổ). Chỉ nhìn sau mã — tránh khớp 'thanh khoản giảm mạnh, VIC…'.
    """
    t_norm = normalize_title(ticker)
    if not t_norm or window <= 0:
        return False
    tokens = _tokens(title_norm)
    action_norms = [
        normalize_title(p) for p in action_phrases if p and normalize_title(p)
    ]
    # Ưu tiên cụm dài hơn khi quét.
    action_norms.sort(key=lambda x: len(_tokens(x)), reverse=True)
    for i, tok in enumerate(tokens):
        if tok != t_norm:
            continue
        # Vùng sau mã: tối đa `window` token bắt đầu cụm.
        lo = i + 1
        hi = min(len(tokens), i + 1 + window)
        if hi <= lo:
            continue
        region = tokens[lo:hi]
        region_text = " ".join(region)
        for phrase in action_norms:
            pt = _tokens(phrase)
            if not pt:
                continue
            if len(pt) == 1:
                if pt[0] in region:
                    return True
            else:
                # Cụm bắt đầu trong cửa sổ (có thể kéo dài ra ngoài).
                for start in range(lo, hi):
                    end = start + len(pt)
                    if end <= len(tokens) and tokens[start:end] == pt:
                        return True
                if _word_hit(region_text, phrase):
                    return True
    return False


def _ticker_leads_with_colon(title_raw: str, ticker: str) -> bool:
    """Mã dẫn đầu dạng 'VIC: ...'."""
    t = str(ticker or "").upper()
    raw = str(title_raw or "").lstrip()
    return bool(re.match(rf"^{re.escape(t)}\s*:", raw, flags=re.IGNORECASE))


def _subject_weight(
    title_raw: str,
    title_norm: str,
    ticker: str,
    *,
    lead_tokens: int,
    weak_weight: float,
    research_markers: list[str],
) -> float:
    """1.0 nếu mã là chủ thể; 0 nếu issuer Research/CTCK; else weak_weight."""
    t = str(ticker or "").upper()
    t_norm = normalize_title(t)
    if not t_norm:
        return weak_weight

    tokens = _tokens(title_norm)
    lead_n = max(1, int(lead_tokens))

    # Issuer báo cáo: Research / Securities / chứng khoán X / dự báo của X
    research_hit = False
    for marker in research_markers:
        mn = normalize_title(marker)
        if not mn:
            continue
        # "SSI Research", "chứng khoán SSI", "dự báo của SSI"
        if mn in ("research", "securities"):
            if t_norm in tokens:
                idx = tokens.index(t_norm)
                # token kế bên là research/securities
                neigh = []
                if idx + 1 < len(tokens):
                    neigh.append(tokens[idx + 1])
                if idx > 0:
                    neigh.append(tokens[idx - 1])
                if mn in neigh or f"{t_norm} {mn}" in title_norm or f"{mn} {t_norm}" in title_norm:
                    research_hit = True
                    break
        else:
            # chứng khoán X / dự báo của X
            if _word_hit(title_norm, f"{mn} {t_norm}"):
                research_hit = True
                break
    if research_hit:
        return 0.0

    # Chủ thể mạnh
    if tokens[:lead_n] and t_norm in tokens[:lead_n]:
        return 1.0
    if re.search(rf"\(\s*{re.escape(t)}\s*\)", str(title_raw or ""), flags=re.IGNORECASE):
        return 1.0
    if _ticker_leads_with_colon(title_raw, t):
        return 1.0
    # sau cổ phiếu / mã / CP
    for prefix in ("cổ phiếu", "mã", "cp"):
        pn = normalize_title(prefix)
        if _word_hit(title_norm, f"{pn} {t_norm}"):
            return 1.0
    if t_norm in tokens:
        return weak_weight
    return weak_weight


def _universe_tickers_in_title(title_raw: str, universe: set[str]) -> set[str]:
    codes = re.findall(r"\b[A-Z]{3}\b", str(title_raw or ""))
    return {c for c in codes if c in universe}


def _is_cw(title_norm: str, patterns: list[str]) -> bool:
    for pat in patterns:
        try:
            if re.search(pat, title_norm, flags=re.IGNORECASE):
                return True
        except re.error:
            if normalize_title(pat) in title_norm:
                return True
    return False


def _company_alias_hit(title_norm: str, ticker: str, aliases: dict, company_name_norm: str) -> bool:
    if company_name_norm and len(company_name_norm) >= 6 and company_name_norm in title_norm:
        return True
    for alias in aliases.get(ticker.upper(), []) or []:
        an = normalize_title(alias)
        if an and an in title_norm:
            return True
    return False


def _strict_ticker_forms(title_raw: str, title_norm: str, ticker: str) -> bool:
    """Khớp chặt: 'cổ phiếu X' / 'mã X' / 'CP X' / '(X)'."""
    t = str(ticker or "").upper()
    t_norm = normalize_title(t)
    if not t_norm:
        return False
    for prefix in ("cổ phiếu", "mã", "cp"):
        pn = normalize_title(prefix)
        if _word_hit(title_norm, f"{pn} {t_norm}"):
            return True
    if re.search(rf"\(\s*{re.escape(t)}\s*\)", str(title_raw or ""), flags=re.IGNORECASE):
        return True
    return False


def _firm_role_ticker_hit(title_norm: str, ticker: str) -> bool:
    """Dạng nội bộ/HĐQT: (vai trò)[+≤3 từ] + TICKER.

    Chỉ dùng cho ambiguous HCM/VND/AAA — không áp cho CEO (chức danh).
    """
    t_norm = normalize_title(ticker)
    if not t_norm:
        return False
    # Vai trò (đã normalize); cụm dài trước để khớp Hội đồng quản trị trước thành viên.
    roles = [
        normalize_title("Hội đồng quản trị"),
        normalize_title("Tổng giám đốc"),
        normalize_title("Chủ tịch"),
        normalize_title("lãnh đạo"),
        normalize_title("thành viên"),
        normalize_title("HĐQT"),
    ]
    tokens = _tokens(title_norm)
    n = len(tokens)
    for role in roles:
        rtoks = _tokens(role)
        if not rtoks:
            continue
        m = len(rtoks)
        for i in range(n - m + 1):
            if tokens[i : i + m] != rtoks:
                continue
            # Sau vai trò: 0..3 từ rồi mã.
            after = i + m
            for gap in range(0, 4):
                j = after + gap
                if j < n and tokens[j] == t_norm:
                    return True
    return False


def _ambiguous_identity_ok(
    title_raw: str,
    title_norm: str,
    ticker: str,
    *,
    source: str,
    aliases: dict,
    company_name_norm: str,
) -> bool:
    """Ambiguous: chỉ chấp nhận dạng chặt / VCI 'X:' / tên-alias — KHÔNG chỉ vì finance kw.

    HCM/VND/AAA thêm dạng HĐQT/lãnh đạo[+≤3 từ]+TICKER. CEO không dùng dạng này
    (tránh 'CEO <công ty>' bị nhận nhầm là mã CEO).
    """
    if _strict_ticker_forms(title_raw, title_norm, ticker):
        return True
    if _ticker_leads_with_colon(title_raw, ticker) and _is_vci_source(source):
        return True
    if _company_alias_hit(title_norm, ticker, aliases, company_name_norm):
        return True
    ticker_u = str(ticker or "").upper()
    if ticker_u in {"HCM", "VND", "AAA"} and _firm_role_ticker_hit(title_norm, ticker_u):
        return True
    return False


def _has_brokerage_market_theme(title_norm: str, themes: list[str]) -> bool:
    return any(normalize_title(t) and normalize_title(t) in title_norm for t in themes if t)


def _flip_object_near(
    tokens: list[str],
    start: int,
    end: int,
    flip_object_norms: list[str],
    window: int,
) -> bool:
    """True nếu flip_object nằm TRƯỚC cụm hướng trong cửa sổ window token.

    Chỉ nhìn bên trái — 'nợ vay giảm mạnh' → đảo; 'giảm sàn giữa áp lực…' không đảo.
    """
    if window < 0 or not flip_object_norms:
        return False
    # Ưu tiên cụm dài hơn (nợ vay trước nợ; nợ xấu trước nợ).
    ordered = sorted(flip_object_norms, key=lambda x: len(_tokens(x)), reverse=True)
    left_from = max(0, start - window)
    if start <= left_from:
        return False
    region = tokens[left_from:start]
    region_text = " ".join(region)
    for obj in ordered:
        if not obj:
            continue
        otoks = _tokens(obj)
        if not otoks:
            continue
        if len(otoks) == 1:
            if otoks[0] in region:
                return True
        else:
            if _word_hit(region_text, obj):
                return True
    return False


def classify_title(
    title_raw: str,
    ticker: str,
    *,
    source: str = "",
    m5_cfg: dict[str, Any] | None = None,
) -> tuple[float, list[str], dict[str, Any]]:
    """Chấm một tiêu đề → (polarity [-1,1], matches, meta).

    polarity đã nhân subject/market/multi/flow; 0 = trung tính / bỏ hướng.
    """
    cfg = m5_cfg or _load_m5_cfg({})[0]
    title_norm = normalize_title(title_raw)
    meta: dict[str, Any] = {
        "title_norm": title_norm,
        "subject_weight": 1.0,
        "multi_ticker": False,
        "market_summary": False,
        "brokerage_market": False,
        "vci": False,
        "negation_flipped": False,
        "object_flipped": False,
    }
    if not title_norm:
        return 0.0, [], meta

    # force_neutral
    for phrase in cfg.get("force_neutral") or []:
        if normalize_title(phrase) and _word_hit(title_norm, normalize_title(phrase)):
            return 0.0, [], meta

    # Market summary → weight 0 trừ khi mã dẫn "X:" hoặc cụm hành động gắn mã.
    market_markers = list(cfg.get("market_summary_markers") or [])
    action_phrases = list(cfg.get("market_summary_ticker_action_phrases") or [])
    action_window = int(cfg.get("market_summary_ticker_action_window", 4))
    action_weight = float(cfg.get("market_summary_ticker_action_weight", 0.6))
    market_summary_ticker_action = False
    if _is_market_summary(title_norm, market_markers) and not _ticker_leads_with_colon(
        title_raw, ticker
    ):
        meta["market_summary"] = True
        if _ticker_price_action_near(
            title_norm, ticker, action_phrases, window=action_window
        ):
            # Giữ tin hướng: weight 0.6 thay vì 0 (vd DXG ngược dòng trong tóm tắt TT).
            market_summary_ticker_action = True
            meta["market_summary_ticker_action"] = True
            meta["subject_weight"] = action_weight
        else:
            # Chỉ nhắc mã trong danh sách kéo chỉ số → giữ rule cũ (weight 0).
            meta["subject_weight"] = 0.0
            return 0.0, ["market_summary"], meta

    is_vci = _is_vci_source(source)
    meta["vci"] = is_vci

    ticker_u = str(ticker or "").upper()
    company_aliases = dict(cfg.get("company_aliases") or {})
    company_name_norm = normalize_title(cfg.get("company_name") or "")
    brokerage = {str(x).upper() for x in (cfg.get("brokerage_tickers") or [])}
    themes = list(cfg.get("brokerage_market_themes") or [])
    # CTCK + chủ đề thị trường chung + không tên/alias công ty → weight 0 (kể cả "MBS:").
    if (
        ticker_u in brokerage
        and not is_vci
        and _has_brokerage_market_theme(title_norm, themes)
        and not _company_alias_hit(title_norm, ticker_u, company_aliases, company_name_norm)
    ):
        meta["brokerage_market"] = True
        meta["subject_weight"] = 0.0
        return 0.0, ["brokerage_market"], meta

    if market_summary_ticker_action:
        subject_w = action_weight
    else:
        subject_w = _subject_weight(
            title_raw,
            title_norm,
            ticker,
            lead_tokens=int(cfg.get("subject_lead_tokens", 6)),
            weak_weight=float(cfg.get("weak_subject_weight", 0.3)),
            research_markers=list(cfg.get("research_issuer_markers") or []),
        )
    meta["subject_weight"] = subject_w
    if subject_w == 0.0:
        return 0.0, ["research_issuer"], meta

    positive = dict(cfg.get("lexicon_positive") or {})
    negative = dict(cfg.get("lexicon_negative") or {})
    ann_pos = dict(cfg.get("lexicon_announcements_positive") or {})
    ann_neg = dict(cfg.get("lexicon_announcements_negative") or {})
    flow_pos = dict(cfg.get("lexicon_flow_positive") or {})
    flow_neg = dict(cfg.get("lexicon_flow_negative") or {})
    flow_mult = float(cfg.get("flow_weight_multiplier", 0.5))
    neg_window = int(cfg.get("negation_window_tokens", 3))
    flip_window = int(cfg.get("flip_window_tokens", 3))
    negation_norms = [normalize_title(p) for p in (cfg.get("negation_phrases") or []) if p]
    flip_norms = [normalize_title(p) for p in (cfg.get("flip_objects") or []) if p]
    # Tập phrase_norm thuộc nhóm negative gốc (để biết khi nào áp dụng flip_objects).
    neg_phrase_norms = {normalize_title(p) for p in negative} | {
        normalize_title(p) for p in ann_neg
    }

    if is_vci:
        # Chỉ announcements; mặc định trung tính
        dict_pos, dict_neg = ann_pos, ann_neg
        flow_pos, flow_neg = {}, {}
    else:
        dict_pos, dict_neg = positive, negative

    hits = (
        [(p, w, pn, "pos") for p, w, pn in _matching_phrases(title_norm, dict_pos)]
        + [(p, w, pn, "neg") for p, w, pn in _matching_phrases(title_norm, dict_neg)]
        + [
            (p, w * flow_mult, pn, "flow_pos")
            for p, w, pn in _matching_phrases(title_norm, flow_pos)
        ]
        + [
            (p, w * flow_mult, pn, "flow_neg")
            for p, w, pn in _matching_phrases(title_norm, flow_neg)
        ]
    )

    # Bỏ "ký hợp đồng" khi có "người có liên quan".
    if "người có liên quan" in title_norm:
        hits = [h for h in hits if normalize_title(h[0]) != normalize_title("ký hợp đồng")]

    if not hits:
        return 0.0, [], meta

    tokens = _tokens(title_norm)
    # Ưu tiên cụm dài hơn khi chồng span — tránh khớp kép "khối ngoại mua ròng" + "mua ròng".
    candidates: list[tuple[int, int, str, float, str]] = []
    for phrase, weight, phrase_norm, _kind in hits:
        for start, end in _phrase_span(tokens, phrase_norm):
            candidates.append((start, end, phrase, weight, phrase_norm))
    candidates.sort(key=lambda x: (x[1] - x[0], x[0]), reverse=True)
    chosen: list[tuple[int, int, str, float, str]] = []
    occupied: set[int] = set()
    for start, end, phrase, weight, phrase_norm in candidates:
        span_idx = set(range(start, end))
        if span_idx & occupied:
            continue
        occupied |= span_idx
        chosen.append((start, end, phrase, weight, phrase_norm))

    signed = 0.0
    matches: list[str] = []
    flipped = False
    object_flipped = False
    for start, end, phrase, weight, phrase_norm in chosen:
        w = weight
        if _has_negation_before(tokens, start, negation_norms, neg_window):
            w = -w
            flipped = True
        # Đảo chiều theo đối tượng: cụm âm gần flip_object → dương.
        elif (
            phrase_norm in neg_phrase_norms
            and w < 0
            and _flip_object_near(tokens, start, end, flip_norms, flip_window)
        ):
            w = -w
            object_flipped = True
        signed += w
        matches.append(phrase)

    meta["negation_flipped"] = flipped
    meta["object_flipped"] = object_flipped
    polarity = max(-1.0, min(1.0, signed / 1.5))

    # Multi-ticker list → ×0.3 (không loại)
    universe = set(cfg.get("universe") or load_universe_tickers())
    thr = int(cfg.get("multi_ticker_threshold", 3))
    found = _universe_tickers_in_title(title_raw, universe)
    if len(found) >= thr:
        meta["multi_ticker"] = True
        polarity *= float(cfg.get("multi_ticker_weight", 0.3))

    polarity *= subject_w
    # Làm tròn gần 0 về 0 để tránh nhiễu
    if abs(polarity) < 1e-9:
        polarity = 0.0
    return max(-1.0, min(1.0, polarity)), matches, meta


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0


def _cluster_stories(
    records: list[dict],
    *,
    jaccard_thr: float,
    window_days: int,
) -> list[dict]:
    """Gom story theo Jaccard token ≥ ngưỡng trong cửa sổ ngày; mỗi story một đơn vị."""
    if not records:
        return []
    ordered = sorted(records, key=lambda r: (r["age"], r["title"]))
    clusters: list[dict] = []
    used = [False] * len(ordered)

    for i, rec in enumerate(ordered):
        if used[i]:
            continue
        used[i] = True
        members = [rec]
        tok_i = set(_tokens(normalize_title(rec["title"])))
        for j in range(i + 1, len(ordered)):
            if used[j]:
                continue
            other = ordered[j]
            if abs(rec["age"] - other["age"]) > window_days:
                continue
            tok_j = set(_tokens(normalize_title(other["title"])))
            if _jaccard(tok_i, tok_j) >= jaccard_thr:
                used[j] = True
                members.append(other)
                tok_i |= tok_j
        # Đại diện: |polarity|*weight lớn nhất
        best = max(members, key=lambda m: (abs(m["polarity"]) * m["weight"], -m["age"]))
        outlets = {str(m.get("source") or "") for m in members if m.get("source")}
        story = dict(best)
        story["outlet_count"] = max(1, len(outlets) if outlets else len(members))
        story["story_size"] = len(members)
        story["members"] = members
        clusters.append(story)
    return clusters


def make_metric(value: float | int | None, unit: str, note: str | None = None) -> dict:
    out: dict[str, Any] = {
        "value": float(value) if value is not None else None,
        "unit": unit,
    }
    if note:
        out["note"] = note
    return out


def run(snapshot: dict, upstream: dict, cfg: dict) -> dict:
    cfg = cfg if isinstance(cfg, dict) else {}
    snapshot = snapshot if isinstance(snapshot, dict) else {}
    meta = snapshot.get("meta") or {}
    company = snapshot.get("company") or {}

    m5_cfg, config_defaulted = _load_m5_cfg(cfg)
    flags: list[str] = ["m5_heuristic_headline_only"]
    if config_defaulted:
        flags.append("m5_config_defaulted")
    if m5_cfg.get("llm_enabled") is True:
        flags.append("m5_llm_ignored")

    try:
        lookback = int(m5_cfg.get("lookback_days", 60))
        half_life = float(m5_cfg.get("half_life_days", 14))
        min_relevant = int(m5_cfg.get("min_relevant_news", 3))
        min_directional = int(m5_cfg.get("min_directional_news", 2))
        multi_thr = int(m5_cfg.get("multi_ticker_threshold", 3))
        evidence_max = int(m5_cfg.get("evidence_max_headlines", 6))
        score_cfg = m5_cfg.get("score") or {}
        base = float(score_cfg.get("base", 50))
        scale = float(score_cfg.get("scale", 35))
        conf_dir_cap = float(score_cfg.get("conf_dir_cap", 12))
        conf_cov_ref = float(score_cfg.get("conf_coverage_ref", 0.35))
        stale_days = int(m5_cfg.get("news_stale_days", 14))
        jaccard_thr = float(m5_cfg.get("story_jaccard_threshold", 0.6))
        story_window = int(m5_cfg.get("story_window_days", 3))
    except (TypeError, ValueError):
        lookback, half_life, min_relevant, min_directional = 60, 14.0, 3, 2
        multi_thr, evidence_max = 3, 6
        base, scale, conf_dir_cap, conf_cov_ref = 50.0, 35.0, 12.0, 0.35
        stale_days, jaccard_thr, story_window = 14, 0.6, 3
        flags.append("m5_invalid_config_defaulted")

    lookback = max(1, min(365, lookback))
    half_life = max(1.0, min(365.0, half_life))
    min_relevant = max(1, min(100, min_relevant))
    min_directional = max(1, min(100, min_directional))
    evidence_max = max(1, min(20, evidence_max))

    ambiguous = {str(x).upper() for x in (m5_cfg.get("ambiguous_tickers") or [])}
    cw_patterns = list(m5_cfg.get("cw_patterns") or [])
    company_aliases = dict(m5_cfg.get("company_aliases") or {})
    universe = set(m5_cfg.get("universe") or load_universe_tickers())
    multi_w = float(m5_cfg.get("multi_ticker_weight", 0.3))

    as_of = parse_date(meta.get("as_of"))
    ticker_raw = str(meta.get("ticker") or "").upper()
    ticker = normalize_title(ticker_raw)
    company_name = normalize_title(company.get("name"))
    # classify_title dùng company_name khi chấm brokerage_market.
    m5_cfg = dict(m5_cfg)
    m5_cfg["company_name"] = company.get("name") or ""

    raw_news = snapshot.get("news")
    if not isinstance(raw_news, list):
        raw_news = []
        flags.append("m5_news_missing")

    if as_of is None:
        flags.append("m5_invalid_as_of")
    if meta.get("synthetic") is True:
        flags.append("m5_synthetic_data")

    counts: Counter[str] = Counter()
    seen: set[str] = set()
    records: list[dict] = []
    sources_seen: set[str] = set()

    for article in raw_news:
        counts["input"] += 1
        if not isinstance(article, dict):
            counts["invalid"] += 1
            continue
        published = parse_date(article.get("published_at"))
        if as_of is None or published is None:
            counts["invalid_date"] += 1
            continue
        age = (as_of - published).days
        if age < 0:
            counts["future"] += 1
            continue
        if age > lookback:
            counts["old"] += 1
            continue

        title = str(article.get("title") or "")
        title_norm = normalize_title(title)
        if not title_norm:
            counts["invalid"] += 1
            continue

        src = str(article.get("source") or "")

        ticker_match = bool(ticker and _word_hit(title_norm, ticker))
        alias_match = _company_alias_hit(title_norm, ticker_raw, company_aliases, company_name)
        company_match = bool(
            company_name and len(company_name) >= 6 and company_name in title_norm
        )
        # Cũng khớp ticker IN HOA trên tiêu đề gốc
        ticker_raw_hit = bool(
            ticker_raw and re.search(rf"\b{re.escape(ticker_raw)}\b", title)
        )
        identity_ok = ticker_match or ticker_raw_hit or alias_match or company_match
        if not identity_ok:
            counts["offtopic"] += 1
            continue

        if _is_cw(title_norm, cw_patterns):
            counts["offtopic"] += 1
            continue

        # Ambiguous: bắt buộc dạng chặt / VCI "X:" / alias — không chỉ finance keyword.
        if ticker_raw in ambiguous:
            if not _ambiguous_identity_ok(
                title,
                title_norm,
                ticker_raw,
                source=src,
                aliases=company_aliases,
                company_name_norm=company_name,
            ):
                counts["offtopic"] += 1
                continue

        if title_norm in seen:
            counts["duplicate"] += 1
            continue
        seen.add(title_norm)

        if src:
            sources_seen.add(src)

        polarity, matches, cmeta = classify_title(
            title, ticker_raw, source=src, m5_cfg=m5_cfg
        )
        # Multi-ticker đã nhân trong classify; vẫn giữ tin (không drop)
        if cmeta.get("multi_ticker"):
            counts["multi_ticker"] += 1

        weight = math.exp(-math.log(2) * age / half_life)
        records.append(
            {
                "id": str(article.get("id") or ""),
                "title": title,
                "date": str(published),
                "age": age,
                "polarity": polarity,
                "weight": weight,
                "matches": matches,
                "source": src,
                "outlet_count": 1,
                "meta": cmeta,
            }
        )

    # Story clustering
    stories = _cluster_stories(
        records, jaccard_thr=jaccard_thr, window_days=story_window
    )
    if any(s.get("story_size", 1) > 1 for s in stories):
        flags.append("m5_story_clustered")

    directional = [r for r in stories if r["polarity"] != 0]
    positive_n = sum(1 for r in directional if r["polarity"] > 0)
    negative_n = sum(1 for r in directional if r["polarity"] < 0)
    neutral_n = len(stories) - len(directional)

    newest_age: float | None = None
    if stories:
        newest_age = float(min(r["age"] for r in stories))

    distinct_sources = float(len(sources_seen))

    metrics = {
        "news_input_count": make_metric(counts["input"], "articles"),
        "news_relevant_count": make_metric(len(stories), "articles"),
        "news_directional_count": make_metric(len(directional), "articles"),
        "news_positive_count": make_metric(positive_n, "articles"),
        "news_negative_count": make_metric(negative_n, "articles"),
        "news_neutral_count": make_metric(neutral_n, "articles"),
        "news_duplicate_count": make_metric(counts["duplicate"], "articles"),
        "news_future_excluded": make_metric(counts["future"], "articles"),
        "news_old_excluded": make_metric(counts["old"], "articles"),
        "news_offtopic_excluded": make_metric(counts["offtopic"], "articles"),
        "news_distinct_sources": make_metric(distinct_sources, "sources"),
        "news_newest_age_days": make_metric(newest_age, "days"),
        "news_story_count": make_metric(len(stories), "stories"),
        "news_multi_ticker_weighted": make_metric(counts["multi_ticker"], "articles"),
    }

    if counts["offtopic"]:
        flags.append("m5_off_topic_filtered")
    if newest_age is not None and newest_age > stale_days:
        flags.append("m5_news_stale")
    if len(stories) > 0 and distinct_sources <= 1:
        flags.append("m5_single_source")

    sufficient = (
        as_of is not None
        and meta.get("synthetic") is not True
        and len(stories) >= min_relevant
        and len(directional) >= min_directional
    )

    score: float | None = None
    if sufficient:
        weight_sum = sum(r["weight"] for r in directional) or 1.0
        weighted = sum(r["weight"] * r["polarity"] for r in directional) / weight_sum
        coverage = len(directional) / max(1, len(stories))
        confidence = min(1.0, len(directional) / conf_dir_cap, coverage / conf_cov_ref)
        score = round(max(0.0, min(100.0, base + scale * weighted * confidence)), 2)
        metrics["sentiment_confidence"] = make_metric(
            confidence, "index", "Heuristic coverage, not calibrated probability"
        )
        metrics["sentiment_polarity"] = make_metric(weighted, "index", "Range -1 to 1")
        metrics["sentiment_score"] = make_metric(score, "points")
        if coverage < conf_cov_ref:
            flags.append("m5_low_directional_coverage")
        status = "ok"
    else:
        flags.append("m5_insufficient_news")
        status = "partial"

    if counts["future"]:
        flags.append("m5_future_news_excluded")
    if counts["duplicate"]:
        flags.append("m5_duplicate_news_excluded")
    if counts["invalid_date"]:
        flags.append("m5_invalid_news_dates")

    evidence: list[dict] = [
        {
            "text": (
                f"Sentiment theo tiêu đề đến {meta.get('as_of')}; "
                f"{len(stories)} story liên quan "
                f"({positive_n} tích cực, {negative_n} tiêu cực, {neutral_n} trung tính); "
                f"lookback={lookback}d half_life={half_life}d; "
                f"nguồn phân biệt={int(distinct_sources)}. "
                "Lexicon heuristic, chỉ tiêu đề, không xác minh toàn văn."
            )
        }
    ]
    # Xếp theo |polarity|×weight (polarity đã gồm subject/multi). Multi-ticker
    # (weight cấu hình < 0.5) chỉ vào evidence khi hết tin khác.
    def _ev_rank(r: dict) -> tuple[float, int]:
        return (abs(float(r["polarity"])) * float(r["weight"]), -int(r["age"]))

    primary = [r for r in directional if not r.get("meta", {}).get("multi_ticker")]
    multi_weak = [
        r
        for r in directional
        if r.get("meta", {}).get("multi_ticker") and multi_w < 0.5
    ]
    multi_strong = [
        r
        for r in directional
        if r.get("meta", {}).get("multi_ticker") and multi_w >= 0.5
    ]
    ranked_primary = sorted(primary + multi_strong, key=_ev_rank, reverse=True)
    ranked_multi = sorted(multi_weak, key=_ev_rank, reverse=True)
    if ranked_primary:
        evidence_pool = ranked_primary[:evidence_max]
        if len(evidence_pool) < evidence_max:
            evidence_pool = evidence_pool + ranked_multi[: evidence_max - len(evidence_pool)]
    else:
        evidence_pool = ranked_multi[:evidence_max]

    for article in evidence_pool:
        label = "tích cực" if article["polarity"] > 0 else "tiêu cực"
        item: dict[str, Any] = {
            "text": f"{label} | {article['title']}"
        }
        if article["id"]:
            item["news_id"] = article["id"]
        evidence.append(item)

    out = {
        "module": "m5",
        "status": status,
        "score": score,
        "metrics": metrics,
        "evidence": evidence,
        "flags": list(dict.fromkeys(flags)),
    }
    errors = validate(out, "module_out")
    if errors:
        raise ValueError("M5 schema errors: " + "; ".join(errors))
    return out
