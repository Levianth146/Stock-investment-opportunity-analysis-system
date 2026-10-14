"""Câu chữ tất định cho M9: tiêu đề kết luận, rút gọn luận điểm, dịch cờ.

Không sinh số mới: mọi con số trong câu đều chép từ luận điểm M7 hoặc metrics module.
"""
from __future__ import annotations

import re
from typing import Any, Callable, Iterable

from stockai.m9_report.fmt import (
    MINUS,
    fmt_multiple,
    fmt_num,
    fmt_pct_points,
    fmt_pct_ratio,
    fmt_score,
    to_float,
)

PILLAR_NAMES = {
    "F": "Cơ bản",
    "T": "Kỹ thuật",
    "V": "Định giá",
    "S": "Tin tức",
    "R": "Rủi ro",
}

# Cụm từ ngắn cho tiêu đề theo nhóm yếu tố (không chữ F/T/V/S/R)
_BULL_PHRASE = {
    "F": "cơ bản cộng",
    "T": "kỹ thuật cộng",
    "V": "định giá cộng",
    "S": "tin tức cộng",
    "R": "rủi ro thấp cộng",
}
_BEAR_PHRASE = {
    "F": "cơ bản trừ",
    "T": "kỹ thuật trừ",
    "V": "định giá trừ",
    "S": "tin tức trừ",
    "R": "rủi ro cao trừ",
}

# Tên chỉ số tiếng Anh/khóa kỹ thuật trong luận điểm mẫu -> thuật ngữ tiếng Việt
_TERMS: list[tuple[str, str]] = [
    (r"\bannualized volatility\b", "biến động năm"),
    (r"\bnet income growth\b", "tăng trưởng lợi nhuận ròng"),
    (r"\brevenue growth\b", "tăng trưởng doanh thu"),
    (r"\bgross margin\b", "biên lợi nhuận gộp"),
    (r"\bdebt to equity\b", "nợ trên vốn chủ"),
    (r"\bdebt to assets\b", "nợ trên tài sản"),
    (r"\binterest coverage\b", "khả năng trả lãi"),
    (r"\bcfo to net income\b", "CFO trên lợi nhuận ròng"),
    (r"\bcurrent ratio\b", "thanh toán hiện hành"),
    (r"\bloan to deposit\b", "LDR"),
    (r"\bmax drawdown\b", "sụt giảm tối đa"),
    (r"\bhistorical var 95\b", "VaR 95%"),
    (r"\bvolume ratio 20\b", "khối lượng so với TB20"),
    (r"\batr pct\b", "ATR%"),
    (r"\brsi14\b", "RSI14"),
    (r"\bmacd\b", "MACD"),
    (r"\bclose\b", "giá đóng cửa"),
    (r"\broe\b", "ROE"),
    (r"\bnim\b", "NIM"),
    (r"\bcir\b", "CIR"),
    (r"\bnpl ratio\b", "tỷ lệ nợ xấu"),
    (r"\bcar\b", "CAR"),
    (r"\(pe: ", "(P/E "),
    (r"\(pb: ", "(P/B "),
    (r"nguồn EPS=TTM", "EPS 4 quý gần nhất"),
    (r"nguồn EPS=ttm_ni", "EPS 4 quý gần nhất"),
]

# Mẫu mới: "Cơ bản hỗ trợ điểm (+3,8): ROE …" hoặc cũ có trụ/(F)
_TEMPLATE_RE = re.compile(
    r"^(?:[A-Z0-9]{1,6}:\s*)?(?:trụ\s+)?"
    r"(?P<label>cơ bản|kỹ thuật|định giá|tin tức|rủi ro)"
    r"(?:\s*\((?P<k>[FTVSR])\))?\s+"
    r"(?P<verb>hỗ trợ|gây áp lực lên)\s+điểm\s*"
    r"\((?P<inner>[^)]*?)(?P<c>[+\-\u2212]?[\d.,]+)(?:\s*điểm)?\)\s*:?\s*(?P<rest>.*)$",
    re.S | re.I,
)

_LABEL_TO_K = {
    "cơ bản": "F",
    "kỹ thuật": "T",
    "định giá": "V",
    "tin tức": "S",
    "rủi ro": "R",
}


def translate_terms(text: str) -> str:
    """Thay tên chỉ số tiếng Anh bằng thuật ngữ tiếng Việt; bỏ ký tự cấm trong báo cáo."""
    out = str(text or "")
    for pat, rep in _TERMS:
        out = re.sub(pat, rep, out, flags=re.I)
    out = re.sub(r"(?<=[\s(])-(?=\d)", MINUS, out)
    return sanitize(out)


def sanitize(text: str) -> str:
    """Bỏ các ký tự bị cấm theo quy chuẩn trình bày (mũi tên, chấm giữa, gạch dài nối chuỗi)."""
    s = str(text or "")
    s = s.replace("\u2192", " sang ").replace("->", " sang ")
    s = s.replace(" \u00b7 ", ", ").replace("\u00b7", ", ")
    s = s.replace(" \u2014 ", ", ").replace("\u2014", ", ")
    s = re.sub(r"\s{2,}", " ", s)
    return s.strip()


def point_text(p: Any) -> str:
    if isinstance(p, dict):
        return str(p.get("text") or "").strip()
    if isinstance(p, str):
        return p.strip()
    return ""


def is_substantive(p: Any) -> bool:
    """Luận điểm có căn cứ: có refs tới metric/tin; luận điểm 'không có yếu tố...' bị loại."""
    if not isinstance(p, dict):
        return False
    refs = p.get("refs")
    txt = point_text(p)
    if not txt or txt.startswith("[quality_gate]") or re.match(r"^(?:[A-Z0-9]{1,6}:\s*)?Không có\b", txt):
        return False
    return isinstance(refs, list) and len(refs) > 0


def _first_detail(rest: str, pillar: str) -> str:
    """Lấy chi tiết số đầu tiên của luận điểm mẫu; tin tức thì bỏ (tiêu đề tin quá dài)."""
    if pillar == "S":
        return ""
    rest = rest.strip()
    if not rest:
        return ""
    first = re.split(r"\.\s", rest, maxsplit=1)[0].rstrip(".")
    first = re.sub(r"\s*\([^)]*\)", "", first)
    first = first.split(", ")[0]
    first = first.replace(" = ", " ")
    return translate_terms(first).strip()


def _cut_words(s: str, limit: int) -> str:
    if len(s) <= limit:
        return s
    cut = s[:limit]
    if ", " in cut:
        cut = cut[: cut.rfind(", ")]
    elif " " in cut:
        cut = cut[: cut.rfind(" ")]
    return cut.rstrip(",;: ")


def shorten_point(p: Any, side: str, *, with_detail: bool = True, limit: int = 70) -> str:
    """Rút gọn tất định một luận điểm Bull/Bear (giữ số, bỏ chữ thừa)."""
    txt = point_text(p)
    if not txt:
        return ""
    m = _TEMPLATE_RE.match(txt)
    if m:
        k = m.group("k") or _LABEL_TO_K.get((m.group("label") or "").lower(), "F")
        c = to_float(m.group("c").replace(MINUS, "-").replace(".", "").replace(",", "."))
        phrase = (_BULL_PHRASE if side == "bull" else _BEAR_PHRASE).get(k, "")
        # Tiêu đề trang 2 không đưa số điểm đóng góp
        head = phrase.rstrip(" cộng trừ").strip() if phrase else ""
        if side == "bull":
            head = {"F": "cơ bản", "T": "kỹ thuật", "V": "định giá", "S": "tin tức", "R": "rủi ro thấp"}.get(k, head)
        else:
            head = {"F": "cơ bản", "T": "kỹ thuật", "V": "định giá", "S": "tin tức", "R": "rủi ro cao"}.get(k, head)
        detail = _first_detail(m.group("rest"), k) if with_detail else ""
        if detail:
            return detail
        return head
    # Văn bản tự do (LLM): bỏ tiền tố mã, lấy câu đầu, cắt theo từ
    t = re.sub(r"^[A-Z0-9]{1,6}:\s*", "", txt)
    t = re.split(r"(?<=[^\d])\.\s", t, maxsplit=1)[0].rstrip(".")
    t = translate_terms(t)
    if len(t) > 1 and t[0].isupper() and t[1].islower():
        t = t[0].lower() + t[1:]
    return _cut_words(t, limit if with_detail else max(30, limit // 2))


def _mv(mod: dict | None, name: str) -> Any:
    if not isinstance(mod, dict):
        return None
    m = (mod.get("metrics") or {}).get(name) if isinstance(mod.get("metrics"), dict) else None
    if isinstance(m, dict):
        return m.get("value")
    return None


def _cap(s: str) -> str:
    return s[:1].upper() + s[1:] if s else s


def _phrase_for_pillar(
    pillar: str,
    *,
    m2: dict,
    m3: dict,
    m4: dict,
    m5: dict,
    m6: dict,
    is_bank: bool,
    m4_flags: Iterable[str] = (),
) -> str:
    """Một cụm tiếng Việt từ metrics (không số điểm) cho tiêu đề trang 2."""
    if pillar == "F":
        parts: list[str] = []
        g = to_float(_mv(m2, "net_income_growth"))
        if g is not None:
            parts.append(f"lợi nhuận ròng {'tăng' if g >= 0 else 'giảm'} {fmt_pct_ratio(abs(g))}")
        roe = to_float(_mv(m2, "roe"))
        if roe is not None and not parts:
            parts.append(f"ROE {fmt_pct_ratio(roe)}")
        elif roe is not None and len(parts) == 1:
            parts.append(f"ROE {fmt_pct_ratio(roe)}")
        return ", ".join(parts)
    if pillar == "V":
        use_pb = is_bank or "m4_bank_primary_pb" in set(m4_flags)
        key, med_key, label = ("pb", "sector_median_pb", "P/B") if use_pb else ("pe", "sector_median_pe", "P/E")
        x, med = to_float(_mv(m4, key)), to_float(_mv(m4, med_key))
        if x is not None and med is not None:
            rel = "thấp hơn" if x < med else "cao hơn"
            return f"{label} {rel} trung vị ngành"
        return ""
    if pillar == "T":
        close = to_float(_mv(m3, "close"))
        ma20, ma50 = to_float(_mv(m3, "ma20")), to_float(_mv(m3, "ma50"))
        if close is not None and ma20 is not None and ma50 is not None:
            pos20 = "trên" if close >= ma20 else "dưới"
            pos50 = "trên" if close >= ma50 else "dưới"
            if pos20 == pos50:
                return f"giá {pos20} MA20 và MA50"
            return f"giá {pos20} MA20, {pos50} MA50"
        rsi = to_float(_mv(m3, "rsi14"))
        if rsi is not None:
            return f"RSI14 {fmt_num(rsi, 1)}"
        return ""
    if pillar == "S":
        pos = to_float(_mv(m5, "news_positive_count"))
        neg = to_float(_mv(m5, "news_negative_count"))
        if pos is not None and neg is not None:
            if pos > neg:
                return "tin tức thiên tích cực"
            if neg > pos:
                return "tin tức thiên tiêu cực"
            return "tin tức cân bằng"
        return ""
    if pillar == "R":
        beta = to_float(_mv(m6, "beta"))
        vol = to_float(_mv(m6, "annualized_volatility"))
        bits = []
        if beta is not None:
            bits.append(f"beta {fmt_num(beta, 2)}")
        if vol is not None:
            bits.append(f"biến động năm {fmt_pct_points(vol)}")
        return ", ".join(bits)
    return ""


def investment_takeaway_title(
    ticker: str,
    *,
    contributions: dict | None = None,
    m2: dict | None = None,
    m3: dict | None = None,
    m4: dict | None = None,
    m5: dict | None = None,
    m6: dict | None = None,
    is_bank: bool = False,
    m4_flags: Iterable[str] = (),
    fits: Callable[[str], bool] | None = None,
) -> str | None:
    """Tiêu đề trang 2 kiểu takeaway: chọn F/V/T/S theo |đóng góp|; chỉ dùng R khi hết nhóm khác."""
    contrib = contributions or {}
    m2, m3, m4, m5, m6 = m2 or {}, m3 or {}, m4 or {}, m5 or {}, m6 or {}
    fits = fits or (lambda s: len(s) <= 140)

    def _d(k: str) -> float | None:
        return to_float(contrib.get(k))

    primary = ["F", "V", "T", "S"]
    pos = [(k, _d(k)) for k in primary if _d(k) is not None and (_d(k) or 0) > 0]
    neg = [(k, _d(k)) for k in primary if _d(k) is not None and (_d(k) or 0) < 0]
    pos.sort(key=lambda x: abs(x[1] or 0), reverse=True)
    neg.sort(key=lambda x: abs(x[1] or 0), reverse=True)
    if not pos and _d("R") is not None and (_d("R") or 0) > 0:
        pos = [("R", _d("R"))]
    if not neg and _d("R") is not None and (_d("R") or 0) < 0:
        neg = [("R", _d("R"))]

    def phrase(k: str) -> str:
        return _phrase_for_pillar(
            k, m2=m2, m3=m3, m4=m4, m5=m5, m6=m6, is_bank=is_bank, m4_flags=m4_flags
        )

    pos_p = phrase(pos[0][0]) if pos else ""
    neg_p = phrase(neg[0][0]) if neg else ""
    # Ghép thêm một cụm phụ nếu còn chỗ (vd F + T)
    if pos and len(pos) > 1 and pos[0][0] != "T":
        extra = phrase(pos[1][0]) if pos[1][0] in ("T", "V", "F") else ""
        # Chỉ gắn thêm kỹ thuật vào phía dương khi vẫn còn chỗ với "nhưng"
        pass

    if pos_p and neg_p:
        s = f"{ticker}: {pos_p} nhưng {neg_p}"
    elif pos_p:
        s = f"{ticker}: {pos_p}"
    elif neg_p:
        s = f"{ticker}: {neg_p}"
    else:
        return None
    s = sanitize(s)
    # Không được chứa số điểm kiểu "62,2 điểm" / "+5,1"
    if re.search(r"\d+,\d+\s*điểm|[+\-\u2212]\d+,\d+", s):
        return None
    if fits(s):
        return s
    # Rút gọn: chỉ giữ cụm chính
    if pos_p and neg_p:
        short = sanitize(f"{ticker}: {pos_p} nhưng {neg_p.split(',')[0]}")
        if fits(short):
            return short
    return s if fits(s) else _cut_words(s, 120)


def conclusion_title(
    ticker: str,
    bull: list,
    bear: list,
    *,
    score: Any = None,
    rating: str | None = None,
    fits: Callable[[str], bool] | None = None,
    contributions: dict | None = None,
    m2: dict | None = None,
    m3: dict | None = None,
    m4: dict | None = None,
    m5: dict | None = None,
    m6: dict | None = None,
    is_bank: bool = False,
    m4_flags: Iterable[str] = (),
) -> str:
    """Câu kết luận trang 2: ưu tiên takeaway từ F/V/T/S; không đưa số điểm vào tiêu đề."""
    fits = fits or (lambda s: len(s) <= 120)
    take = investment_takeaway_title(
        ticker,
        contributions=contributions,
        m2=m2,
        m3=m3,
        m4=m4,
        m5=m5,
        m6=m6,
        is_bank=is_bank,
        m4_flags=m4_flags,
        fits=fits,
    )
    if take:
        return take

    b = next((x for x in bull or [] if is_substantive(x)), None)
    r = next((x for x in bear or [] if is_substantive(x)), None)

    def build(detail_b: bool, detail_r: bool) -> str:
        if b is not None and r is not None:
            return f"{ticker}: {shorten_point(b, 'bull', with_detail=detail_b)}, nhưng {shorten_point(r, 'bear', with_detail=detail_r)}"
        # Trung tính: không nhét số điểm vào tiêu đề
        neutral = f"{ticker}: tóm tắt dữ liệu phân tích"
        if rating and to_float(score) is None:
            neutral = f"{ticker}: mức {rating}"
        side = b if b is not None else r
        if side is None:
            return neutral
        return f"{ticker}: {shorten_point(side, 'bull' if b is not None else 'bear', with_detail=detail_b and detail_r)}"

    for db, dr in ((True, True), (True, False), (False, True), (False, False)):
        s = sanitize(build(db, dr))
        if fits(s) and not re.search(r"\d+,\d+\s*điểm", s):
            return s
    return sanitize(build(False, False))


def fundamental_title(m2: dict, m4: dict, *, is_bank: bool, m4_flags: Iterable[str] = ()) -> str:
    """Câu kết luận trang cơ bản và định giá, chỉ từ metrics M2/M4."""
    parts: list[str] = []
    g = to_float(_mv(m2, "net_income_growth"))
    if g is not None:
        parts.append(f"lợi nhuận ròng {'tăng' if g >= 0 else 'giảm'} {fmt_pct_ratio(abs(g))}")
    roe = to_float(_mv(m2, "roe"))
    if roe is not None:
        parts.append(f"ROE {fmt_pct_ratio(roe)}")
    use_pb = is_bank or "m4_bank_primary_pb" in set(m4_flags)
    key, med_key, label = ("pb", "sector_median_pb", "P/B") if use_pb else ("pe", "sector_median_pe", "P/E")
    x, med = to_float(_mv(m4, key)), to_float(_mv(m4, med_key))
    if x is not None and med is not None:
        rel = "thấp hơn" if x < med else "cao hơn"
        parts.append(f"{label} {fmt_multiple(x)} {rel} trung vị ngành {fmt_multiple(med)}")
    if not parts:
        return "Cơ bản và định giá: chưa đủ dữ liệu để kết luận"
    return _cap(", ".join(parts))


def technical_title(m3: dict, m6: dict) -> str:
    """Câu kết luận trang kỹ thuật và rủi ro."""
    close = to_float(_mv(m3, "close"))
    ma20, ma50 = to_float(_mv(m3, "ma20")), to_float(_mv(m3, "ma50"))
    parts: list[str] = []
    if close is not None and ma20 is not None and ma50 is not None:
        pos20 = "trên" if close >= ma20 else "dưới"
        pos50 = "trên" if close >= ma50 else "dưới"
        where = f"{pos20} MA20 và MA50" if pos20 == pos50 else f"{pos20} MA20, {pos50} MA50"
        parts.append(f"Giá {fmt_num(close)} đồng nằm {where}")
    rsi = to_float(_mv(m3, "rsi14"))
    if rsi is not None:
        parts.append(f"RSI14 {fmt_num(rsi, 1)}")
    vol = to_float(_mv(m6, "annualized_volatility"))
    if vol is not None:
        parts.append(f"biến động năm {fmt_pct_points(vol)}")
    beta = to_float(_mv(m6, "beta"))
    if beta is not None:
        parts.append(f"beta {fmt_num(beta, 2)}")
    if not parts:
        return "Kỹ thuật và rủi ro: chưa đủ dữ liệu để kết luận"
    return _cap(", ".join(parts))


def news_title(m5: dict) -> str:
    rel = to_float(_mv(m5, "news_relevant_count"))
    pos = to_float(_mv(m5, "news_positive_count"))
    neg = to_float(_mv(m5, "news_negative_count"))
    neu = to_float(_mv(m5, "news_neutral_count"))
    if rel is None or pos is None or neg is None:
        return "Tin tức và lưu ý dữ liệu"
    s = f"{fmt_num(rel)} tin liên quan: {fmt_num(pos)} tích cực, {fmt_num(neg)} tiêu cực"
    if neu is not None:
        s += f", {fmt_num(neu)} trung tính"
    return s


def flag_key(flag: str) -> str:
    return str(flag).split(":", 1)[0]


def translate_flags(flags: Iterable[str], flag_dict: dict) -> tuple[list[str], list[str]]:
    """Trả (câu tiếng Việt đã dịch, cờ chưa có trong từ điển). Giữ thứ tự, bỏ trùng."""
    table = flag_dict.get("flags") or {}
    known: list[str] = []
    unknown: list[str] = []
    seen: set[str] = set()
    for f in flags or []:
        if not isinstance(f, str) or not f:
            continue
        if f in seen:
            continue
        seen.add(f)
        sent = table.get(f) or table.get(flag_key(f))
        if sent:
            if sent not in known:
                known.append(str(sent))
        else:
            unknown.append(f)
    return known, unknown


# Cờ được phép hiện ở «Lưu ý dữ liệu» (tối đa 4 dòng, chỉ ảnh hưởng cách đọc số)
_DATA_NOTE_ALLOW = {
    "quality_tier_limited",
    "quality_news_few",
    "quality_low_liquidity",
    "m5_heuristic_headline_only",
    "m5_low_directional_coverage",
    "m5_insufficient_news",
    "universe_membership_current_not_point_in_time",
    "m6_historical_risk_estimate",
    "m4_sector_fallback",
    "m4_peer_group_small",
    "bank_nim_cir_derived_approx",
}


def select_data_notes(
    flags: Iterable[str],
    flag_dict: dict,
    *,
    fin_estimated: bool = False,
    max_lines: int = 4,
) -> list[str]:
    """Tối đa 4 dòng lưu ý đọc số; bỏ dòng xử lý nội bộ."""
    known, _ = translate_flags(
        [f for f in flags or [] if flag_key(f) in _DATA_NOTE_ALLOW],
        flag_dict,
    )
    out: list[str] = []
    if fin_estimated:
        out.append("Ngày công bố báo cáo tài chính là ước lượng khi nguồn không cung cấp.")
    for s in known:
        if s not in out:
            out.append(s)
        if len(out) >= max_lines:
            break
    return out[:max_lines]


def reason_text(reasons: Iterable[str], flag_dict: dict) -> str:
    """Lý do của cổng chất lượng thành một câu ngắn."""
    table = flag_dict.get("reasons") or {}
    parts = [str(table.get(r) or r.replace("_", " ")) for r in reasons or [] if isinstance(r, str)]
    if not parts:
        return "dữ liệu chưa đạt ngưỡng chất lượng tối thiểu"
    return ", ".join(parts)


def listing_sentence(exchange: str | None, sector: str | None, rc: dict) -> str:
    """'Niêm yết trên HOSE, ngành Tài nguyên cơ bản.'"""
    ex = (rc.get("exchanges") or {}).get(str(exchange or "").upper()) or (exchange or None)
    sec = (rc.get("sectors") or {}).get(str(sector or "")) or sector
    if ex and sec:
        return f"Niêm yết trên {ex}, ngành {sec}."
    if ex:
        return f"Niêm yết trên {ex}, chưa có thông tin ngành."
    if sec:
        return f"Ngành {sec}, chưa có thông tin sàn niêm yết."
    return "Chưa có thông tin sàn niêm yết và ngành."


def human_sources(sources: list[dict], as_of: str) -> list[str]:
    """Gom nguồn theo loại, một dòng tiếng người đọc."""
    names = " ".join(str(s.get("name") or s.get("id") or "") for s in sources).lower()
    lines: list[str] = []
    if "quote" in names or "giá" in names or "vci" in names or "price" in names:
        lines.append(f"Giá và khối lượng: VCI, qua thư viện vnstock, giá đã điều chỉnh.")
    if "finance" in names or "income" in names or "bctc" in names or "financial" in names:
        lines.append("Báo cáo tài chính: VCI.")
    if "news" in names or "google" in names:
        lines.append("Tin tức: Google News và các báo điện tử.")
    lines.append("Chỉ số ngành: tính từ các mã trong danh sách theo dõi.")
    # Tránh trùng
    uniq: list[str] = []
    for s in lines:
        if s not in uniq:
            uniq.append(s)
    return uniq


def scoring_method_plain(scoring_cfg: dict, profile: str) -> str:
    """Phương pháp chấm điểm tối đa 4 câu, không công thức ký hiệu."""
    _ = profile  # khẩu vị chỉ ảnh hưởng trọng số bảng, không đổi câu ngưỡng
    gate = scoring_cfg.get("risk_gate") or {}
    max_r = gate.get("max_rating", "Nắm giữ")
    _ = scoring_cfg  # giữ chữ ký; ngưỡng đọc cố định theo yêu cầu báo cáo
    return (
        "Điểm tổng bắt đầu từ 50 (mức trung tính). "
        "Mỗi nhóm yếu tố cộng hoặc trừ điểm tùy cao hay thấp hơn 50, theo trọng số trong bảng; "
        "rủi ro cao thì trừ điểm. "
        "Điểm giới hạn từ 0 đến 100. "
        f"Ngưỡng khuyến nghị: Bán dưới 30, Giảm tỷ trọng từ 30, Nắm giữ từ 45, Mua từ 60, "
        f"Mua mạnh từ 75; rủi ro rất cao giới hạn khuyến nghị ở {max_r}."
    )
