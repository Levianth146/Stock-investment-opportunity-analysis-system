"""M7 - Bull/Bear qua LLM (N5): payload → generate_json → validate → retry → template.

Quy tắc: LLM chỉ dùng số/metric/news trong payload; KHÔNG tự đặt giá mục tiêu.
Chữ ký ``run_debate(snapshot, upstream, cfg) -> (bull, bear)`` giữ tương thích ``run.py``.
Flags debate được gắn vào ``cfg["_debate_flags"]`` để ``run.py`` hợp vào ``result.flags``.
"""
from __future__ import annotations

import copy
import json
import time
from typing import Any, Callable

from stockai.llm.generate import generate_json, load_dotenv_keys, load_llm_cfg
from stockai.llm.payload import build_debate_payload, payload_for_llm, payload_hash
from stockai.m7_scoring.debate_template import build_template_debate
from stockai.m7_scoring.debate_validate import validate_debate_sides
from stockai.m7_scoring.scoring import compute_score, to_rating

# Hook test: thay generate_json
_generate_fn: Callable[..., dict] | None = None


def set_generate_fn(fn: Callable[..., dict] | None) -> None:
    """Gắn/mock ``generate_json`` cho pytest (None = dùng thật)."""
    global _generate_fn
    _generate_fn = fn


def _build_prompt(payload_llm: dict, *, feedback: str | None = None) -> str:
    """Prompt tiếng Việt + cấm bịa số / target / refs ngoài allow-list."""
    allowed = payload_llm.get("metrics_allowed") or []
    news_refs = [n.get("ref") for n in (payload_llm.get("news") or []) if isinstance(n, dict)]
    polarity = payload_llm.get("module_polarity") or {}
    body = json.dumps(payload_llm, ensure_ascii=False, indent=2)
    fb = f"\nLỗi lần trước (sửa đúng): {feedback}\n" if feedback else ""
    return (
        "Bạn là chuyên gia phân tích chứng khoán Việt Nam. "
        "Viết luận điểm Bull và Bear bằng tiếng Việt dựa CHỈ trên JSON payload.\n"
        "CẤM tuyệt đối:\n"
        "- Bịa số không có trong payload\n"
        "- Tự đặt giá mục tiêu / target price\n"
        "- Dùng refs ngoài allow-list\n"
        "- In raw key kiểu m2.roe trong text (dùng display_name / display)\n"
        "- Bull trích dẫn trụ/module có module_polarity d<0 làm luận điểm chính\n"
        "- Bear trích dẫn trụ/module có d>0 làm luận điểm chính\n"
        "- Bull dùng tin label=neg; Bear dùng tin label=pos\n"
        f"module_polarity (d_k): {polarity}\n"
        f"Allow-list metric refs: {allowed}\n"
        f"Allow-list news refs: {news_refs}\n"
        "Mỗi ref metric dạng mN.name (vd m4.pe); news dạng nK (vd n1).\n"
        "Trong text dùng tên tiếng Việt và số đã format (%, x, 1 chữ số thập phân).\n"
        "Trả về đúng một JSON object:\n"
        '{"bull":[{"text":"...","refs":["m4.pe","n1"]}],'
        '"bear":[{"text":"...","refs":["m6.beta"]}]}\n'
        "Mỗi phía đúng 2 đến 4 luận điểm; mỗi item text không rỗng và refs không rỗng.\n"
        f"{fb}"
        f"PAYLOAD:\n{body}\n"
    )


def _score_context(snapshot: dict, upstream: dict, cfg: dict) -> tuple[float | None, str, dict]:
    """Tính lại score/rating deterministic (không đổi scoring.py)."""
    def sc(m: str):
        o = upstream.get(m)
        return None if (o is None or o.get("status") == "error") else o.get("score")

    profile = cfg.get("profile") or "long_term"
    try:
        comp = compute_score(
            {"F": sc("m2"), "T": sc("m3"), "V": sc("m4"), "S": sc("m5"), "R": sc("m6")},
            profile,
            cfg,
        )
        rating, _ = to_rating(comp["score"], comp["scores"]["R"], cfg)
        return comp["score"], rating, comp["scores"]
    except Exception:
        return None, "N/A", {"F": None, "T": None, "V": None, "S": None, "R": None}


def _merge_flags(cfg: dict, flags: list[str]) -> None:
    existing = list(cfg.get("_debate_flags") or [])
    for f in flags:
        if f and f not in existing:
            existing.append(f)
    cfg["_debate_flags"] = existing


def _merge_llm_cfg(cfg: dict, llm_cfg: dict) -> dict:
    """Deep-ish merge debate + display_metrics từ cfg['llm']."""
    if not isinstance(cfg.get("llm"), dict):
        return llm_cfg
    base = dict(llm_cfg)
    debate = dict(base.get("debate") or {})
    incoming = cfg["llm"]
    if isinstance(incoming.get("debate"), dict):
        debate.update(incoming["debate"])
    else:
        # cho phép truyền phẳng các khóa debate
        for k in ("max_llm_attempts", "prompt_version", "cache_dir", "providers", "temperature"):
            if k in incoming:
                debate[k] = incoming[k]
    base["debate"] = debate
    return base


def run_debate(snapshot: dict, upstream: dict, cfg: dict) -> tuple[list[dict], list[dict]]:
    """Orchestrate debate: cache/LLM/validate/retry/template.

    Nhánh quality_gate unscored được xử lý ở ``run.py`` (không gọi hàm này).
    """
    load_dotenv_keys()
    llm_cfg = _merge_llm_cfg(cfg, load_llm_cfg())

    debate_cfg = llm_cfg.get("debate") or {}
    prompt_version = str(debate_cfg.get("prompt_version") or "v1")
    max_attempts = int(debate_cfg.get("max_llm_attempts") or 3)
    max_seconds = float(debate_cfg.get("max_seconds_per_ticker") or 60)
    t0 = time.monotonic()

    # Đưa display_metrics / pricing vào cfg để payload format đúng
    cfg_for_payload = dict(cfg)
    if "debate" not in cfg_for_payload and debate_cfg:
        cfg_for_payload["debate"] = debate_cfg

    score, rating, scores = _score_context(snapshot, upstream, cfg)
    payload = build_debate_payload(
        snapshot,
        upstream,
        cfg_for_payload,
        score=score,
        rating=rating,
        scores=scores,
        prompt_version=prompt_version,
    )
    metrics_allowed = payload.get("metrics_allowed") or []
    news_ref_map = payload.get("news_ref_map") or {}
    module_polarity = payload.get("module_polarity") or {}
    p_hash = payload_hash(payload)
    payload_llm = payload_for_llm(payload)

    flags: list[str] = []
    feedback: str | None = None
    gen = _generate_fn or generate_json
    cost_usd = 0.0

    # Không có khóa và không mock → bỏ vòng LLM (tránh timeout khi chỉ fallback)
    import os as _os

    _any_key = bool(
        _os.environ.get("GEMINI_API_KEY", "").strip()
        or _os.environ.get("ZAI_API_KEY", "").strip()
    )
    _using_mock = _generate_fn is not None
    if not _any_key and not _using_mock:
        flags.append("debate_llm_unavailable")
        flags.append("llm_missing_key_gemini")
        flags.append("llm_missing_key_glm")
        attempts = 0
    else:
        attempts = max(1, max_attempts)

    for attempt in range(attempts):
        elapsed = time.monotonic() - t0
        remaining = max_seconds - elapsed
        if remaining <= 1.0:
            flags.append("debate_timeout_per_ticker")
            feedback = feedback or "max_seconds_per_ticker"
            break
        try:
            prompt = _build_prompt(payload_llm, feedback=feedback)
            # Cắt timeout HTTP theo thời gian còn lại của mã
            call_cfg = copy.deepcopy(llm_cfg)
            dsec = call_cfg.setdefault("debate", {})
            if isinstance(dsec, dict):
                base_to = float(dsec.get("timeout_sec") or 45)
                dsec["timeout_sec"] = max(1.0, min(base_to, remaining - 0.5))
            raw = gen(
                prompt,
                None,
                cfg=call_cfg,
                cache_key_parts={
                    "ticker": payload.get("ticker") or "",
                    "as_of": payload.get("as_of") or "",
                    "prompt_version": prompt_version,
                    "payload_hash": p_hash,
                    "model": "debate",
                },
                use_cache=(attempt == 0),  # chỉ cache hit ở lần đầu
            )
            meta = raw.pop("_meta", {}) if isinstance(raw, dict) else {}
            if isinstance(meta, dict):
                flags.extend(meta.get("flags") or [])
                if meta.get("cache_hit"):
                    flags.append("debate_cache_hit")
                try:
                    cost_usd += float(meta.get("cost_usd") or 0.0)
                except (TypeError, ValueError):
                    pass
            bull = raw.get("bull") if isinstance(raw, dict) else None
            bear = raw.get("bear") if isinstance(raw, dict) else None
            errs = validate_debate_sides(
                bull,
                bear,
                metrics_allowed=metrics_allowed,
                news_ref_map=news_ref_map,
                upstream=upstream,
                module_polarity=module_polarity,
                payload_metrics=payload.get("metrics"),
                scores=scores,
                news_items=payload.get("news"),
            )
            if not errs:
                flags.append("m7_debate_llm_used")
                if cost_usd > 0:
                    flags.append(f"debate_cost_usd:{cost_usd:.6f}")
                uniq = []
                for f in flags:
                    if f not in uniq:
                        uniq.append(f)
                _merge_flags(cfg, uniq)
                cfg["_debate_cost_usd"] = cost_usd
                return list(bull), list(bear)
            feedback = "; ".join(errs[:6])
        except Exception as e:
            feedback = str(e)[:200]
            extra = getattr(e, "flags", None)
            if isinstance(extra, list):
                flags.extend(extra)
            # Hết mọi provider/model → không đốt thêm attempts validation
            # KHÔNG break sớm chỉ vì http_5xx (generate_json đã retry nội bộ)
            if "all_providers_failed" in feedback or "missing" in feedback.lower():
                break

    # Template fallback — ghi rõ lý do cuối
    if feedback:
        flags.append(f"debate_fallback_reason:{feedback[:120]}")
    bull_t, bear_t, tflags = build_template_debate(payload, cfg=cfg_for_payload)
    flags.extend(tflags)
    uniq = []
    for f in flags:
        if f not in uniq:
            uniq.append(f)
    _merge_flags(cfg, uniq)
    cfg["_debate_cost_usd"] = cost_usd
    return bull_t, bear_t
