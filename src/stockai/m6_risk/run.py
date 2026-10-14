"""m6 - điểm R rủi ro thị trường định lượng.

Cực tính Q1:B / docs/CONTRACTS.md / M7 (−lambda*R, risk_gate):
  R ∈ [0, 100], R cao = rủi ro cao.

StockAI tham chiếu chấm safety-subscore (cao = rủi ro thấp) rồi weighted average.
Feature này GIỮ nguyên công thức đo (beta, ann vol, MDD, VaR95, CVaR95) và hệ số
safety_coeffs; CHỈ đảo mapping:
  risk_sub = 100 - safety_sub
  R = 0.25*vol_risk + 0.25*dd_risk + 0.20*var_risk + 0.15*tail_risk + 0.15*beta_risk
  (tương đương R = 100 - StockAI_score khi cùng trọng số)

Các thành phần đã đảo (config m6.inverted_components): volatility, drawdown, var,
cvar, beta. Metrics *_risk_subscore mang hướng rủi ro (cao = rủi ro cao).

Chữ ký: run(snapshot, upstream, cfg) -> dict validate module_out.
status=ok khi eligible + có score số; không hard-code partial.
"""
from __future__ import annotations

import bisect
import math
import statistics
from copy import deepcopy
from datetime import date
from pathlib import Path
from typing import Any

import yaml

from stockai.contracts.schemas import validate

_ROOT = Path(__file__).resolve().parents[3]
_TECHNICAL_YAML = _ROOT / "config" / "technical.yaml"

_DEFAULT_M6: dict[str, Any] = {
    "scoring_polarity": "high_R_means_high_risk",
    "inverted_vs_stockai": True,
    "inverted_components": ["volatility", "drawdown", "var", "cvar", "beta"],
    "lookback_sessions": 252,
    "min_observations": 120,
    "annual_sessions": 252,
    # Số phiên chỉ số bị bỏ qua giữa hai ngày giao liên tiếp; nghỉ chung (Tết) = 0.
    # Thay max_return_gap_days (ngày lịch) — giữ alias đọc ở _resolve_max_missed.
    "max_missed_index_sessions": 5,
    "max_stale_aligned_days": 10,
    "safety_coeffs": {
        "vol_floor": 0.15,
        "vol_mult": 200,
        "mdd_mult": 180,
        "var_mult": 1400,
        "cvar_mult": 900,
        "beta_floor": 0.7,
        "beta_mult": 45,
    },
    "weights": {
        "vol": 0.25,
        "drawdown": 0.25,
        "var": 0.20,
        "tail": 0.15,
        "beta": 0.15,
    },
}


def _deep_merge(base: dict, overlay: dict) -> dict:
    out = deepcopy(base)
    for k, v in (overlay or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def _load_m6_cfg(cfg: dict | None) -> tuple[dict[str, Any], bool]:
    """Gộp cfg.m6 với technical.yaml; lỗi/thiếu → default + m6_invalid_config_defaulted."""
    defaulted = False
    file_m6: dict[str, Any] = {}
    try:
        if _TECHNICAL_YAML.is_file():
            raw = yaml.safe_load(_TECHNICAL_YAML.read_text(encoding="utf-8")) or {}
            file_m6 = dict(raw.get("m6") or {})
        else:
            defaulted = True
    except (OSError, yaml.YAMLError, TypeError):
        defaulted = True
        file_m6 = {}

    merged = _deep_merge(_DEFAULT_M6, file_m6)
    cfg = cfg if isinstance(cfg, dict) else {}
    overlay = cfg.get("m6") if isinstance(cfg.get("m6"), dict) else {}
    flat_keys = (
        "lookback_sessions",
        "min_observations",
        "annual_sessions",
        "max_missed_index_sessions",
        "max_return_gap_days",  # deprecated alias
        "max_stale_aligned_days",
    )
    flat = {k: cfg[k] for k in flat_keys if k in cfg}
    if flat:
        overlay = _deep_merge(overlay, flat)
    if overlay:
        merged = _deep_merge(merged, overlay)
    # Migrate alias: chỉ khi caller/file đặt max_return_gap_days mà không đặt khóa mới.
    explicit_new = (
        "max_missed_index_sessions" in file_m6
        or "max_missed_index_sessions" in overlay
    )
    explicit_old = (
        "max_return_gap_days" in file_m6 or "max_return_gap_days" in overlay
    )
    if not explicit_new and explicit_old:
        merged["max_missed_index_sessions"] = merged["max_return_gap_days"]
    if not file_m6 and not overlay:
        defaulted = True
    return merged, defaulted


def metric(value, unit, note=None):
    result = {
        "value": float(value) if value is not None else None,
        "unit": unit,
    }
    if note:
        result["note"] = note
    return result


def finite(value):
    try:
        result = float(value)
        return result if math.isfinite(result) else None
    except (ValueError, TypeError):
        return None


def parse_date(value):
    try:
        return date.fromisoformat(str(value)[:10])
    except (ValueError, TypeError):
        return None


def clean_prices(rows, as_of):
    result = {}
    excluded_future = 0
    excluded_bad = 0
    duplicates = 0

    if not isinstance(rows, list):
        return result, excluded_future, excluded_bad, duplicates

    for row in rows:
        if not isinstance(row, dict):
            excluded_bad += 1
            continue

        day = parse_date(row.get("date"))
        close = finite(row.get("close"))

        if day is None or close is None or close <= 0:
            excluded_bad += 1
            continue

        if day > as_of:
            excluded_future += 1
            continue

        if day in result:
            duplicates += 1
            continue

        result[day] = close

    return result, excluded_future, excluded_bad, duplicates


def percentile(values, quantile):
    ordered = sorted(values)
    index = (len(ordered) - 1) * quantile
    left = int(math.floor(index))
    right = int(math.ceil(index))
    weight = index - left
    return ordered[left] * (1 - weight) + ordered[right] * weight


def max_drawdown(prices):
    peak = prices[0]
    worst = 0.0
    for price in prices:
        peak = max(peak, price)
        drawdown = price / peak - 1.0
        worst = min(worst, drawdown)
    return abs(worst)


def clamp(value, low=0.0, high=100.0):
    return max(low, min(high, value))


def _resolve_max_missed(m6_cfg: dict[str, Any]) -> int:
    """Ngưỡng phiên chỉ số bị bỏ qua; ưu tiên max_missed_index_sessions.

    Alias cũ max_return_gap_days (ngày lịch) vẫn được đọc nếu khóa mới vắng —
    giá trị số giữ nguyên nhưng nghĩa đã đổi sang số phiên chỉ số.
    """
    if "max_missed_index_sessions" in m6_cfg:
        return int(m6_cfg["max_missed_index_sessions"])
    if "max_return_gap_days" in m6_cfg:
        return int(m6_cfg["max_return_gap_days"])
    return int(_DEFAULT_M6["max_missed_index_sessions"])


def run(snapshot: dict, upstream: dict, cfg: dict) -> dict:
    snapshot = snapshot if isinstance(snapshot, dict) else {}
    m6_cfg, cfg_defaulted = _load_m6_cfg(cfg)

    meta = snapshot.get("meta") or {}
    price_data = snapshot.get("prices") or {}
    index_data = snapshot.get("index") or {}

    flags = ["m6_historical_risk_estimate"]
    if cfg_defaulted:
        flags.append("m6_invalid_config_defaulted")

    metrics: dict[str, Any] = {}
    evidence: list[dict] = []
    score = None
    status = "partial"

    as_of = parse_date(meta.get("as_of"))
    if as_of is None:
        flags.append("m6_invalid_as_of")
        as_of = date.min

    try:
        lookback = int(m6_cfg.get("lookback_sessions", 252))
        minimum = int(m6_cfg.get("min_observations", 120))
        annual_sessions = int(m6_cfg.get("annual_sessions", 252))
        max_missed = _resolve_max_missed(m6_cfg)
        max_stale = int(m6_cfg.get("max_stale_aligned_days", 10))
    except (TypeError, ValueError, OverflowError):
        lookback, minimum, annual_sessions = 252, 120, 252
        max_missed, max_stale = 5, 10
        flags.append("m6_invalid_config_defaulted")

    lookback = max(60, min(1260, lookback))
    minimum = max(60, min(lookback, minimum))
    annual_sessions = max(200, min(365, annual_sessions))
    max_missed = max(0, min(60, max_missed))

    coeffs = m6_cfg.get("safety_coeffs") or _DEFAULT_M6["safety_coeffs"]
    weights = m6_cfg.get("weights") or _DEFAULT_M6["weights"]

    stock, future_s, bad_s, dup_s = clean_prices(price_data.get("rows"), as_of)
    market, future_m, bad_m, dup_m = clean_prices(index_data.get("rows"), as_of)

    future_count = future_s + future_m
    bad_count = bad_s + bad_m
    duplicate_count = dup_s + dup_m

    if future_count:
        flags.append("m6_future_prices_excluded")
    if bad_count:
        flags.append("m6_invalid_prices_excluded")
    if duplicate_count:
        flags.append("m6_duplicate_dates_excluded")

    # Chỉ giao ngày chung — không forward-fill ngày thiếu.
    common_days = sorted(set(stock) & set(market))
    common_days = common_days[-(lookback + 1):]
    index_days_sorted = sorted(market)

    stock_ret = []
    index_ret = []
    gap_count = 0

    # Gap bất thường = cổ phiếu bỏ qua > N phiên chỉ số giữa hai ngày giao.
    # Nghỉ chung với chỉ số (Tết…) → 0 phiên chỉ số ở giữa → giữ return đa ngày.
    for previous, current in zip(common_days, common_days[1:]):
        left = bisect.bisect_right(index_days_sorted, previous)
        right = bisect.bisect_left(index_days_sorted, current)
        missed_index_sessions = right - left
        if missed_index_sessions > max_missed:
            gap_count += 1
            continue
        rs = stock[current] / stock[previous] - 1.0
        rm = market[current] / market[previous] - 1.0
        if not math.isfinite(rs) or not math.isfinite(rm):
            continue
        stock_ret.append(rs)
        index_ret.append(rm)

    n = len(stock_ret)

    metrics["aligned_observations"] = metric(n, "sessions")
    metrics["future_rows_excluded"] = metric(future_count, "rows")
    metrics["gap_returns_excluded"] = metric(gap_count, "returns")

    # Flag: đã loại return vì stock miss > N phiên chỉ số (không phải nghỉ chung).
    if gap_count:
        flags.append("m6_long_market_gaps_excluded")

    if meta.get("synthetic") is True:
        flags.append("m6_synthetic_data")

    if price_data.get("adjusted") is not True:
        flags.append("m6_unadjusted_stock_prices")

    if len(stock) < minimum + 1:
        flags.append("m6_insufficient_stock_prices")

    if len(market) < minimum + 1:
        flags.append("m6_insufficient_index_prices")

    sufficient = n >= minimum

    if sufficient:
        stock_std = statistics.stdev(stock_ret)
        index_std = statistics.stdev(index_ret)
        covariance = statistics.covariance(stock_ret, index_ret)
        index_variance = statistics.variance(index_ret)

        beta = covariance / index_variance if index_variance > 1e-18 else None

        volatility = stock_std * math.sqrt(annual_sessions)
        benchmark_vol = index_std * math.sqrt(annual_sessions)

        q05 = percentile(stock_ret, 0.05)
        var95 = max(0.0, -q05)
        tail = [r for r in stock_ret if r <= q05]
        cvar95 = max(0.0, -statistics.mean(tail))

        stock_path = [stock[d] for d in common_days]
        index_path = [market[d] for d in common_days]
        mdd = max_drawdown(stock_path)
        benchmark_mdd = max_drawdown(index_path)

        negative = sum(r < 0 for r in stock_ret)
        positive = sum(r > 0 for r in stock_ret)

        metrics.update({
            "annualized_volatility": metric(
                volatility * 100, "%", "Historical daily returns annualized"
            ),
            "benchmark_volatility": metric(benchmark_vol * 100, "%"),
            "beta": metric(beta, "times", "Cov(stock,index) / Var(index)"),
            "max_drawdown": metric(mdd * 100, "%"),
            "benchmark_max_drawdown": metric(benchmark_mdd * 100, "%"),
            "historical_var_95": metric(
                var95 * 100, "%", "One-session historical loss estimate"
            ),
            "historical_cvar_95": metric(
                cvar95 * 100, "%", "Mean loss in the worst 5% of sessions"
            ),
            "negative_sessions": metric(negative, "sessions"),
            "positive_sessions": metric(positive, "sessions"),
            "last_aligned_date": metric(
                (as_of - common_days[-1]).days,
                "days",
                "Calendar days since last aligned close",
            ),
        })

        # Safety subscores StockAI (cao = rủi ro thấp) — rồi đảo sang risk.
        vol_floor = float(coeffs.get("vol_floor", 0.15))
        vol_mult = float(coeffs.get("vol_mult", 200))
        mdd_mult = float(coeffs.get("mdd_mult", 180))
        var_mult = float(coeffs.get("var_mult", 1400))
        cvar_mult = float(coeffs.get("cvar_mult", 900))
        beta_floor = float(coeffs.get("beta_floor", 0.7))
        beta_mult = float(coeffs.get("beta_mult", 45))

        vol_safety = clamp(100 - max(0, volatility - vol_floor) * vol_mult)
        dd_safety = clamp(100 - mdd * mdd_mult)
        var_safety = clamp(100 - var95 * var_mult)
        tail_safety = clamp(100 - cvar95 * cvar_mult)

        if beta is not None:
            beta_safety = clamp(100 - max(0.0, beta - beta_floor) * beta_mult)
        else:
            beta_safety = None
            flags.append("m6_beta_unavailable")

        # Invert: risk_sub = 100 - safety_sub (Q1:B)
        vol_risk = 100.0 - vol_safety
        dd_risk = 100.0 - dd_safety
        var_risk = 100.0 - var_safety
        tail_risk = 100.0 - tail_safety
        beta_risk = (100.0 - beta_safety) if beta_safety is not None else None

        metrics.update({
            "volatility_risk_subscore": metric(
                vol_risk, "points", "Higher = higher risk (inverted vs StockAI safety)"
            ),
            "drawdown_risk_subscore": metric(
                dd_risk, "points", "Higher = higher risk (inverted vs StockAI safety)"
            ),
            "var_risk_subscore": metric(
                var_risk, "points", "Higher = higher risk (inverted vs StockAI safety)"
            ),
            "tail_risk_subscore": metric(
                tail_risk, "points", "Higher = higher risk (inverted vs StockAI safety)"
            ),
        })
        if beta_risk is not None:
            metrics["beta_risk_subscore"] = metric(
                beta_risk, "points", "Higher = higher risk (inverted vs StockAI safety)"
            )

        eligible = (
            meta.get("synthetic") is not True
            and price_data.get("adjusted") is True
            and beta_risk is not None
            and n >= minimum
            and (as_of - common_days[-1]).days <= max_stale
        )

        if eligible:
            w_vol = float(weights.get("vol", 0.25))
            w_dd = float(weights.get("drawdown", 0.25))
            w_var = float(weights.get("var", 0.20))
            w_tail = float(weights.get("tail", 0.15))
            w_beta = float(weights.get("beta", 0.15))
            score = round(
                w_vol * vol_risk
                + w_dd * dd_risk
                + w_var * var_risk
                + w_tail * tail_risk
                + w_beta * beta_risk,
                2,
            )
            status = "ok"
        else:
            flags.append("m6_not_ready_for_risk_score")
            score = None
            status = "partial"

        evidence.append({
            "text": (
                f"Quantitative risk estimated from {n} aligned "
                f"stock/benchmark return observations through "
                f"{common_days[-1].isoformat()}; "
                f"historical lookback={lookback} sessions. "
                "R high = higher measured risk (CONTRACTS / Q1:B; "
                "StockAI safety mapping inverted). "
                "Historical VaR/CVaR are not worst-case loss limits."
            )
        })
    else:
        flags.append("m6_insufficient_aligned_returns")
        evidence.append({
            "text": (
                f"Only {n} aligned return observations "
                f"(minimum {minimum}); no risk score assigned."
            )
        })
        status = "partial"
        score = None

    if "m6_unadjusted_stock_prices" in flags or "m6_synthetic_data" in flags:
        flags.append("m6_data_quality_review_required")

    out = {
        "module": "m6",
        "status": status,
        "score": score,
        "metrics": metrics,
        "evidence": evidence,
        "flags": list(dict.fromkeys(flags)),
    }

    errors = validate(out, "module_out")
    if errors:
        raise ValueError("M6 schema errors: " + "; ".join(errors))

    return out
