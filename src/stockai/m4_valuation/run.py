"""m4 - điểm V định giá tương đối PE/PB so median ngành.

Điểm V chỉ phản ánh định giá tương đối (rẻ/đắt so median ngành qua PE/PB).
Không đo chất lượng kinh doanh, tăng trưởng, hay rủi ro vận hành.

Khóa thiết kế:
- Tôn trọng as_of (không lookahead).
- V cao = rẻ/hấp dẫn; score=null khi không chấm được — MUST NOT ép 50.
- Bank (is_bank): P/B chân chính; không dùng peers thay median ngành.
- Sector nhỏ → median thị trường + m4_sector_fallback; chỉ PE (m4_pb_leg_dropped).
- Scoring: percentile inverted trong pe_sorted/pb_sorted (không quét lại snapshots).
- DCF tắt mặc định (enable_dcf: false).
- status=partial chỉ khi có cờ thiếu/suy giảm dữ liệu thật; cờ thông tin
  (m4_pb_uses_total_equity, m4_bank_primary_pb, m4_sector_weight_default) không ép partial.
"""
from __future__ import annotations

import math
from typing import Any

from stockai.contracts.schemas import validate
from stockai.m4_valuation.config_loader import load_m4_cfg, resolve_path
from stockai.m4_valuation.multiples import MultipleInputs, derive_multiples
from stockai.m4_valuation.sector_stats import (
    cheapness_percentile_score,
    lookup_sector_medians,
    load_sector_stats,
)


def _metric(value: Any, unit: str, note: str | None = None) -> dict[str, Any]:
    m: dict[str, Any] = {"value": value if value is None or isinstance(value, (int, float)) else None, "unit": unit}
    if note:
        m["note"] = note
    if isinstance(m["value"], float) and not math.isfinite(m["value"]):
        m["value"] = None
    return m


def _parse_weight_pair(w: Any, default_pe: float = 0.5, default_pb: float = 0.5) -> tuple[float, float]:
    if not isinstance(w, dict):
        return default_pe, default_pb
    try:
        w_pe = float(w.get("pe", default_pe))
    except (TypeError, ValueError):
        w_pe = default_pe
    try:
        w_pb = float(w.get("pb", default_pb))
    except (TypeError, ValueError):
        w_pb = default_pb
    return w_pe, w_pb


def _weights_for(mi: MultipleInputs, m4: dict, *, drop_pb: bool) -> tuple[float, float, list[str]]:
    """Trọng số theo is_bank / by_sector / default; drop_pb khi fallback thị trường."""
    flags: list[str] = []
    wcfg = m4.get("weights") or {}
    if mi.is_bank:
        w_pe, w_pb = _parse_weight_pair(wcfg.get("bank"), 0.0, 1.0)
        flags.append("m4_bank_primary_pb")
    else:
        by_sector = wcfg.get("by_sector") if isinstance(wcfg.get("by_sector"), dict) else {}
        sector_w = by_sector.get(mi.sector) if mi.sector else None
        if isinstance(sector_w, dict):
            w_pe, w_pb = _parse_weight_pair(sector_w, 0.5, 0.5)
        else:
            w_pe, w_pb = _parse_weight_pair(wcfg.get("default") or wcfg.get("non_bank"), 0.5, 0.5)
            if mi.sector:
                flags.append("m4_sector_weight_default")

    if drop_pb:
        w_pb = 0.0
        if "m4_pb_leg_dropped" not in flags:
            flags.append("m4_pb_leg_dropped")
    return w_pe, w_pb, flags


def _quality_flags(flags: list[str], *, w_pe: float) -> list[str]:
    """Flags làm status=partial khi vẫn có score số.

    Chỉ cờ thiếu/suy giảm dữ liệu thật. Thông tin thuần
    (m4_pb_uses_total_equity, m4_bank_primary_pb, m4_sector_weight_default) → không ép partial.
    m4_pe_unavailable / m4_pe_not_meaningful chỉ material khi trọng số PE > 0.
    """
    material = {
        "m4_stale_price_data",
        "m4_stale_financials",
        "m4_eps_ttm_fallback_annual",
        "m4_eps_quarter_gap",
        "m4_sector_fallback",
        "m4_pb_leg_dropped",
        "m4_missing_shares",
        "m4_missing_equity",
        "m4_pb_unavailable",
        "m4_pb_not_meaningful",
        "m4_peer_group_small",
        "m4_config_defaulted",
        "m4_synthetic_data",
        "m4_no_valid_price",
    }
    out = [f for f in flags if f in material]
    if w_pe > 0:
        for f in ("m4_pe_unavailable", "m4_pe_not_meaningful"):
            if f in flags and f not in out:
                out.append(f)
    return out


def _build_evidence(mi: MultipleInputs, med_pe: float | None, med_pb: float | None, flags: list[str]) -> list[dict]:
    parts: list[dict] = []
    src = mi.price_source_id

    def ev(text: str) -> dict:
        d: dict[str, Any] = {"text": text}
        if src:
            d["source_id"] = src
        return d

    if mi.pe is not None and med_pe is not None and med_pe > 0:
        pct = (mi.pe / med_pe - 1.0) * 100.0
        direction = "thấp hơn" if pct < 0 else "cao hơn"
        parts.append(
            ev(
                f"P/E = {mi.pe:.2f} so median ngành {med_pe:.2f} "
                f"({abs(pct):.1f}% {direction}; nguồn EPS={mi.eps_source or 'n/a'})."
            )
        )
    if mi.pb is not None and med_pb is not None and med_pb > 0 and "m4_pb_leg_dropped" not in flags:
        pct = (mi.pb / med_pb - 1.0) * 100.0
        direction = "thấp hơn" if pct < 0 else "cao hơn"
        bank_note = " Ngân hàng ưu tiên P/B." if mi.is_bank else ""
        parts.append(
            ev(
                f"P/B = {mi.pb:.2f} so median ngành {med_pb:.2f} "
                f"({abs(pct):.1f}% {direction}).{bank_note}"
            )
        )
    if "m4_eps_ttm_fallback_annual" in flags:
        parts.append(ev("EPS TTM quý (NI/shares) không dùng được; đã fallback EPS năm."))
    if "m4_eps_quarter_gap" in flags:
        parts.append(ev("Chuỗi quý không liên tiếp đủ 4 kỳ — không cộng EPS quý."))
    if "m4_stale_price_data" in flags:
        parts.append(ev("Giá đóng cửa lệch ngày as_of quá ngưỡng stale lịch."))
    if "m4_sector_fallback" in flags:
        parts.append(ev("Ngành mẫu nhỏ hoặc thiếu; đã dùng median thị trường (chỉ chân P/E)."))
    if "m4_pb_uses_total_equity" in flags:
        parts.append(ev("P/B dùng total_equity (gồm minority); lệch NI parent đáng kể."))
    if not parts:
        parts.append(ev("Không đủ dữ liệu để so sánh định giá tương đối PE/PB với ngành."))
    return parts


def _build_target(
    mi: MultipleInputs,
    med_pe: float | None,
    med_pb: float | None,
    w_pe: float,
    w_pb: float,
    used_pe: bool,
    used_pb: bool,
    m4: dict,
) -> dict | None:
    bands = m4.get("target_bands") or {}
    try:
        bull_m = float(bands.get("bull_mult", 1.15))
    except (TypeError, ValueError):
        bull_m = 1.15
    try:
        bear_m = float(bands.get("bear_mult", 0.85))
    except (TypeError, ValueError):
        bear_m = 0.85

    implied: list[tuple[float, float]] = []  # (price, weight)
    if used_pe and med_pe is not None and mi.eps_used is not None and mi.eps_used > 0 and w_pe > 0:
        implied.append((med_pe * mi.eps_used, w_pe))
    if used_pb and med_pb is not None and mi.book_ps is not None and mi.book_ps > 0 and w_pb > 0:
        implied.append((med_pb * mi.book_ps, w_pb))
    if not implied:
        return None
    wsum = sum(w for _, w in implied)
    if wsum <= 0:
        return None
    base = sum(p * w for p, w in implied) / wsum
    assumptions = [
        f"implied từ median ngành (PE={med_pe}, PB={med_pb})",
        f"EPS nguồn={mi.eps_source}",
        f"trọng số pe={w_pe}, pb={w_pb}",
        "book dùng total_equity (gồm minority) đến khi có parent_equity",
        "score percentile inverted từ pe_sorted/pb_sorted sector stats",
    ]
    return {
        "base": round(base, 2),
        "bull": round(base * bull_m, 2),
        "bear": round(base * bear_m, 2),
        "method": "relative_multiples_pe_pb",
        "assumptions": assumptions,
    }


def run(snapshot: dict, upstream: dict, cfg: dict) -> dict:
    """Chấm điểm V relative (chỉ định giá so ngành; không phản ánh chất lượng DN).

    validate module_out trước khi trả.
    """
    flags: list[str] = []
    metrics: dict[str, Any] = {}
    m4, defaulted = load_m4_cfg(cfg if isinstance(cfg, dict) else {})
    if defaulted:
        flags.append("m4_config_defaulted")

    if not isinstance(snapshot, dict):
        out = {
            "module": "m4",
            "status": "error",
            "score": None,
            "metrics": {},
            "evidence": [{"text": "Snapshot không hợp lệ."}],
            "flags": ["m4_invalid_snapshot", "m4_insufficient_for_score"],
            "target": None,
            "error": "invalid_snapshot",
        }
        validate(out, "module_out")
        return out

    mi = derive_multiples(
        snapshot,
        stale_calendar_days=int(m4.get("stale_calendar_days", 7)),
        stale_financials_days=int(m4.get("stale_financials_days", 200)),
    )
    for f in mi.flags:
        if f not in flags:
            flags.append(f)

    stats_path = resolve_path(str(m4.get("sector_stats_path") or "data/valuation_sector_stats.json"))
    # Cho phép absolute path từ cfg (fixture test)
    raw_path = (cfg or {}).get("m4", {}).get("sector_stats_path") if isinstance(cfg, dict) else None
    if isinstance(raw_path, str) and raw_path:
        from pathlib import Path

        p = Path(raw_path)
        stats_path = p if p.is_absolute() or p.exists() else resolve_path(raw_path)

    stats = load_sector_stats(stats_path)
    med = lookup_sector_medians(
        stats,
        mi.sector,
        min_sector_n=int(m4.get("min_sector_n", 5)),
    )
    for f in med.flags:
        if f not in flags:
            flags.append(f)

    drop_pb = "m4_sector_fallback" in flags or "m4_pb_leg_dropped" in flags
    w_pe, w_pb, wflags = _weights_for(mi, m4, drop_pb=drop_pb)
    for f in wflags:
        if f not in flags:
            flags.append(f)

    # Metrics cơ bản
    metrics["price_close"] = _metric(mi.price_close, "VND/share")
    metrics["eps_used"] = _metric(mi.eps_used, "VND/share", note=mi.eps_source)
    metrics["book_per_share"] = _metric(mi.book_ps, "VND/share")
    metrics["pe"] = _metric(mi.pe, "x")
    metrics["pb"] = _metric(mi.pb, "x")
    metrics["sector_median_pe"] = _metric(med.median_pe, "x")
    metrics["sector_median_pb"] = _metric(med.median_pb, "x")
    metrics["sector_stats_version"] = _metric(med.version, "int")
    metrics["sector_n_pe"] = _metric(med.n_pe, "count")
    metrics["sector_n_pb"] = _metric(med.n_pb, "count")

    v_pe = None
    v_pb = None
    used_pe = False
    used_pb = False

    if w_pe > 0 and mi.pe is not None and med.pe_sorted:
        v_pe = cheapness_percentile_score(mi.pe, med.pe_sorted)
        if v_pe is not None:
            used_pe = True
    elif w_pe > 0 and mi.pe is not None and med.median_pe is not None and med.median_pe > 0:
        # Fixture cũ không có pe_sorted: map quanh median (tương thích test mini)
        r = mi.pe / med.median_pe
        # proxy: r=0.5 → ~100, r=1.5 → ~0 (giống cheapness cũ)
        v_pe = round(100.0 * max(0.0, min(1.0, (1.5 - r) / 1.0)), 4)
        used_pe = True

    if w_pb > 0 and mi.pb is not None and med.pb_sorted:
        v_pb = cheapness_percentile_score(mi.pb, med.pb_sorted)
        if v_pb is not None:
            used_pb = True
    elif w_pb > 0 and mi.pb is not None and med.median_pb is not None and med.median_pb > 0:
        r = mi.pb / med.median_pb
        v_pb = round(100.0 * max(0.0, min(1.0, (1.5 - r) / 1.0)), 4)
        used_pb = True

    metrics["v_pe_leg"] = _metric(v_pe, "score_0_100")
    metrics["v_pb_leg"] = _metric(v_pb, "score_0_100")

    score: float | None = None
    legs: list[tuple[float, float]] = []
    if used_pe and v_pe is not None:
        legs.append((v_pe, w_pe))
    if used_pb and v_pb is not None:
        legs.append((v_pb, w_pb))

    if legs:
        wsum = sum(w for _, w in legs)
        if wsum > 0:
            raw = sum(s * w for s, w in legs) / wsum
            score = round(max(0.0, min(100.0, raw)), 2)
            metrics["score_V"] = _metric(score, "score_0_100")
    else:
        if "m4_insufficient_for_score" not in flags:
            flags.append("m4_insufficient_for_score")

    target = _build_target(
        mi,
        med.median_pe,
        med.median_pb,
        w_pe,
        w_pb,
        used_pe,
        used_pb,
        m4,
    )

    if score is None:
        target = None
        status = "partial"
    else:
        qf = _quality_flags(flags, w_pe=w_pe)
        status = "partial" if qf else "ok"

    evidence = _build_evidence(mi, med.median_pe, med.median_pb, flags)

    out: dict[str, Any] = {
        "module": "m4",
        "status": status,
        "score": score,
        "metrics": metrics,
        "evidence": evidence,
        "flags": flags,
        "target": target,
    }
    errs = validate(out, "module_out")
    if errs:
        out["status"] = "error"
        out["error"] = "; ".join(errs[:5])
        out["flags"] = list(dict.fromkeys([*flags, "m4_validate_failed"]))
    return out
