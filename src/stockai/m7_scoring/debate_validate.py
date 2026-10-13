"""Validator refs + độ dài luận điểm debate M7 (Q2:B) + dấu module_polarity + số."""
from __future__ import annotations

import re
from typing import Any, Literal

from stockai.llm.payload import MOD_TO_COMP

RefKind = Literal["metric", "news", "invalid"]

_METRIC_RE = re.compile(r"^m[0-9]+\.[A-Za-z0-9_]+$")
_NEWS_RE = re.compile(r"^n[0-9]+$")
# Heuristic cấm giá mục tiêu / target do LLM bịa (conservative)
_TARGET_BAN_RE = re.compile(
    r"(giá\s*mục\s*tiêu|target\s*price|định\s*giá\s*mục\s*tiêu)",
    re.IGNORECASE,
)
# Số trong text: 12,5% | 7.3x | 12.5 | 1.2345
_NUM_TOKEN_RE = re.compile(
    r"(?<![A-Za-z0-9_])(-?\d+(?:[.,]\d+)?)(x|%)?(?![A-Za-z0-9_])",
    re.IGNORECASE,
)


def classify_ref(ref: str) -> RefKind:
    """Phân loại chuỗi ref: metric | news | invalid."""
    if not isinstance(ref, str):
        return "invalid"
    if _METRIC_RE.match(ref):
        return "metric"
    if _NEWS_RE.match(ref):
        return "news"
    return "invalid"


def resolve_metric_ref(ref: str, metrics_allowed: set[str] | list[str], upstream: dict | None = None) -> bool:
    """True nếu metric nằm trong allow-list hoặc upstream[mN].metrics."""
    if classify_ref(ref) != "metric":
        return False
    allowed = set(metrics_allowed or [])
    if ref in allowed:
        return True
    if not upstream:
        return False
    try:
        mod, name = ref.split(".", 1)
    except ValueError:
        return False
    block = upstream.get(mod)
    if not isinstance(block, dict):
        return False
    metrics = block.get("metrics") or {}
    return name in metrics


def resolve_news_ref(ref: str, news_ref_map: dict[str, str] | None) -> bool:
    """True nếu nK có trong news_ref_map."""
    if classify_ref(ref) != "news":
        return False
    return bool(news_ref_map) and ref in news_ref_map


def is_ref_grounded(
    ref: str,
    *,
    metrics_allowed: set[str] | list[str],
    news_ref_map: dict[str, str] | None,
    upstream: dict | None = None,
) -> bool:
    """Regex + resolve; fail nếu invalid hoặc không resolve."""
    kind = classify_ref(ref)
    if kind == "metric":
        return resolve_metric_ref(ref, metrics_allowed, upstream)
    if kind == "news":
        return resolve_news_ref(ref, news_ref_map)
    return False


def _module_of_metric_ref(ref: str) -> str | None:
    if classify_ref(ref) != "metric":
        return None
    return ref.split(".", 1)[0]


def _primary_metric_ref(refs: list) -> str | None:
    """Ref metric đầu tiên = primary basis của luận điểm."""
    for r in refs:
        if isinstance(r, str) and classify_ref(r) == "metric":
            return r
    return None


def _polarity_sign_error(
    side: str,
    primary_ref: str | None,
    module_polarity: dict[str, float] | None,
) -> str | None:
    """Bull trích metric module d<0 (primary) → lỗi; Bear ngược lại."""
    if not primary_ref or not module_polarity:
        return None
    mod = _module_of_metric_ref(primary_ref)
    if not mod:
        return None
    comp = MOD_TO_COMP.get(mod)
    if not comp:
        return None
    d = module_polarity.get(comp)
    if not isinstance(d, (int, float)):
        return None
    if side == "bull" and d < 0:
        return f"bull primary {primary_ref} thuộc module {comp} d={d}<0"
    if side == "bear" and d > 0:
        return f"bear primary {primary_ref} thuộc module {comp} d={d}>0"
    return None


def _collect_payload_number_forms(payload_metrics: dict | None, news: list | None) -> set[str]:
    """Tập chuỗi số chấp nhận được (raw + % + x + comma/dot)."""
    forms: set[str] = set()

    def _add_num(v: float) -> None:
        # nhiều dạng gần đúng
        for prec in (0, 1, 2, 3, 4):
            s = f"{v:.{prec}f}"
            forms.add(s)
            forms.add(s.replace(".", ","))
            forms.add(f"{s}%")
            forms.add(f"{s.replace('.', ',')}%")
            forms.add(f"{s}x")
            forms.add(f"{s.replace('.', ',')}x")
            # pct từ ratio
            pct = v * 100.0
            sp = f"{pct:.{prec}f}"
            forms.add(sp)
            forms.add(sp.replace(".", ","))
            forms.add(f"{sp}%")
            forms.add(f"{sp.replace('.', ',')}%")

    if isinstance(payload_metrics, dict):
        for entry in payload_metrics.values():
            if isinstance(entry, dict):
                val = entry.get("value")
                if isinstance(val, (int, float)):
                    _add_num(float(val))
                for key in ("display", "display_name", "name"):
                    disp = entry.get(key)
                    if isinstance(disp, str) and disp.strip():
                        forms.add(disp.strip())
                        forms.add(disp.strip().replace(",", "."))
                        # Cho phép số nằm trong tên (vd RSI(14) → 14)
                        for m in _NUM_TOKEN_RE.finditer(disp):
                            raw = m.group(1)
                            forms.add(raw)
                            forms.add(raw.replace(",", "."))
                            forms.add(raw.replace(".", ","))
            elif isinstance(entry, (int, float)):
                _add_num(float(entry))
    return forms


def _numbers_in_text_ok(text: str, allowed_forms: set[str], scores: dict | None = None) -> list[str]:
    """Mỗi số trong text phải khớp payload (cho phép %/x và scores F/T/V/S/R)."""
    if not text:
        return []
    # bổ sung scores vào allowed
    forms = set(allowed_forms)
    if isinstance(scores, dict):
        for v in scores.values():
            if isinstance(v, (int, float)):
                for prec in (0, 1, 2):
                    s = f"{float(v):.{prec}f}"
                    forms.add(s)
                    forms.add(s.replace(".", ","))

    errs: list[str] = []
    for m in _NUM_TOKEN_RE.finditer(text):
        raw = m.group(1)
        suffix = (m.group(2) or "").lower()
        # bỏ số năm kiểu 2025, 2026
        if re.fullmatch(r"20\d{2}", raw.replace(",", "").split(".")[0]):
            continue
        # độ lệch kiểu +3,76 / -8.91 trong ngoặc template — cho phép gần module_polarity
        token = raw + suffix
        token_alt = raw.replace(",", ".") + suffix
        candidates = {
            token,
            token_alt,
            raw,
            raw.replace(",", "."),
            raw.replace(".", ","),
            f"{raw}%",
            f"{raw.replace(',', '.')}%",
            f"{raw.replace('.', ',')}%",
            f"{raw}x",
            f"{raw.replace(',', '.')}x",
            f"{raw.replace('.', ',')}x",
        }
        if forms and not (candidates & forms):
            # thử so khớp số gần đúng với một value trong forms (parse float)
            try:
                num = float(raw.replace(",", "."))
            except ValueError:
                errs.append(f"số lạ '{token}'")
                continue
            ok = False
            for f in forms:
                fm = _NUM_TOKEN_RE.search(f)
                if not fm:
                    continue
                try:
                    fv = float(fm.group(1).replace(",", "."))
                except ValueError:
                    continue
                if abs(fv - num) < 0.051 or abs(fv - num * 100) < 0.51 or abs(fv * 100 - num) < 0.51:
                    ok = True
                    break
            if not ok:
                errs.append(f"số không khớp payload '{token}'")
    return errs


def _item_errors(
    item: Any,
    side: str,
    idx: int,
    *,
    metrics_allowed: set[str] | list[str],
    news_ref_map: dict[str, str] | None,
    upstream: dict | None,
    payload_numbers: set[str] | None,
    module_polarity: dict[str, float] | None,
    payload_metrics: dict | None,
    scores: dict | None,
    news_items: list | None,
) -> list[str]:
    errs: list[str] = []
    where = f"{side}[{idx}]"
    if not isinstance(item, dict):
        return [f"{where}: không phải object"]
    text = item.get("text")
    if not isinstance(text, str) or not text.strip():
        errs.append(f"{where}: text rỗng")
    else:
        if _TARGET_BAN_RE.search(text):
            errs.append(f"{where}: text chứa pattern giá mục tiêu bị cấm")
        if payload_numbers is not None or payload_metrics is not None:
            forms = payload_numbers or _collect_payload_number_forms(payload_metrics, news_items)
            for ne in _numbers_in_text_ok(text, forms, scores=scores):
                errs.append(f"{where}: {ne}")
    refs = item.get("refs")
    if not isinstance(refs, list) or len(refs) == 0:
        errs.append(f"{where}: refs thiếu hoặc rỗng")
        return errs
    for j, ref in enumerate(refs):
        if not isinstance(ref, str) or not ref:
            errs.append(f"{where}.refs[{j}]: không phải chuỗi")
            continue
        if not is_ref_grounded(
            ref,
            metrics_allowed=metrics_allowed,
            news_ref_map=news_ref_map,
            upstream=upstream,
        ):
            errs.append(f"{where}.refs[{j}]: ungrounded '{ref}'")
    # Sign check qua module_polarity (primary metric)
    primary = _primary_metric_ref(refs)
    sign_err = _polarity_sign_error(side, primary, module_polarity)
    if sign_err:
        errs.append(f"{where}: polarity_sign {sign_err}")
    # News: Bull không nên primary-cậy tin neg và ngược lại (nếu có label trong payload)
    if isinstance(news_items, list) and isinstance(text, str):
        label_by_ref = {
            n["ref"]: n.get("label")
            for n in news_items
            if isinstance(n, dict) and isinstance(n.get("ref"), str)
        }
        for ref in refs:
            if classify_ref(ref) != "news":
                continue
            lab = label_by_ref.get(ref)
            if side == "bull" and lab == "neg":
                errs.append(f"{where}: bull dùng tin tiêu cực {ref}")
            if side == "bear" and lab == "pos":
                errs.append(f"{where}: bear dùng tin tích cực {ref}")
    return errs


def validate_debate_sides(
    bull: Any,
    bear: Any,
    *,
    metrics_allowed: set[str] | list[str],
    news_ref_map: dict[str, str] | None,
    upstream: dict | None = None,
    payload_numbers: set[str] | None = None,
    module_polarity: dict[str, float] | None = None,
    payload_metrics: dict | None = None,
    scores: dict | None = None,
    news_items: list | None = None,
    min_items: int = 2,
    max_items: int = 4,
) -> list[str]:
    """Kiểm tra scored path: mỗi phía 2–4 item; text + refs grounded + polarity.

    Trả về danh sách lỗi (rỗng = hợp lệ).
    """
    errs: list[str] = []
    for side, items in (("bull", bull), ("bear", bear)):
        if not isinstance(items, list):
            errs.append(f"{side}: phải là list")
            continue
        n = len(items)
        if n < min_items or n > max_items:
            errs.append(f"{side}: cần {min_items}–{max_items} luận điểm, có {n}")
        for i, item in enumerate(items):
            errs.extend(
                _item_errors(
                    item,
                    side,
                    i,
                    metrics_allowed=metrics_allowed,
                    news_ref_map=news_ref_map,
                    upstream=upstream,
                    payload_numbers=payload_numbers,
                    module_polarity=module_polarity,
                    payload_metrics=payload_metrics,
                    scores=scores,
                    news_items=news_items,
                )
            )
    return errs


def repair_debate_sides(
    bull: Any,
    bear: Any,
    *,
    metrics_allowed: set[str] | list[str],
    news_ref_map: dict[str, str] | None,
    upstream: dict | None = None,
    module_polarity: dict[str, float] | None = None,
    payload_metrics: dict | None = None,
    scores: dict | None = None,
    news_items: list | None = None,
    min_items: int = 2,
    max_items: int = 4,
) -> tuple[list[dict], list[dict], list[str]]:
    """Bỏ item lỗi polarity/số nếu vẫn còn đủ min_items mỗi phía; trả (bull, bear, errs).

    Không bịa nội dung mới — chỉ cắt item không đạt validator.
    """
    out_bull = list(bull) if isinstance(bull, list) else []
    out_bear = list(bear) if isinstance(bear, list) else []

    # Bỏ dần item lỗi khi còn dư (≥ min_items)
    for _ in range(4):
        repaired_b: list[dict] = []
        repaired_r: list[dict] = []
        for side, src, dst in (("bull", out_bull, repaired_b), ("bear", out_bear, repaired_r)):
            for i, item in enumerate(src):
                if not isinstance(item, dict):
                    continue
                ie = _item_errors(
                    item,
                    side,
                    i,
                    metrics_allowed=metrics_allowed,
                    news_ref_map=news_ref_map,
                    upstream=upstream,
                    payload_numbers=None,
                    module_polarity=module_polarity,
                    payload_metrics=payload_metrics,
                    scores=scores,
                    news_items=news_items,
                )
                if ie and len(src) > min_items and (len(dst) + len(src) - i - 1) >= min_items:
                    continue
                dst.append(item)
            del dst[max_items:]
        out_bull, out_bear = repaired_b, repaired_r
        errs = validate_debate_sides(
            out_bull,
            out_bear,
            metrics_allowed=metrics_allowed,
            news_ref_map=news_ref_map,
            upstream=upstream,
            module_polarity=module_polarity,
            payload_metrics=payload_metrics,
            scores=scores,
            news_items=news_items,
            min_items=min_items,
            max_items=max_items,
        )
        if not errs:
            break
    return out_bull, out_bear, errs


def ungrounded_refs_in_item(
    item: dict,
    *,
    metrics_allowed: set[str] | list[str],
    news_ref_map: dict[str, str] | None,
    upstream: dict | None = None,
) -> list[str]:
    """Danh sách ref không grounded (thiếu refs → ['<missing>'])."""
    refs = item.get("refs")
    if not isinstance(refs, list) or len(refs) == 0:
        return ["<missing>"]
    bad: list[str] = []
    for ref in refs:
        if not isinstance(ref, str) or not is_ref_grounded(
            ref,
            metrics_allowed=metrics_allowed,
            news_ref_map=news_ref_map,
            upstream=upstream,
        ):
            bad.append(str(ref))
    return bad
