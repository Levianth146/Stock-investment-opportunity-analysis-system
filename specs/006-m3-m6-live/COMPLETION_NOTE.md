# Completion note — 006 M3 + M6 Live

**Date**: 2026-10-13  
**No commit / no push** trong pass implement này.

## Phạm vi cấm (đã giữ)

Không sửa: `src/stockai/m1_data/`, `pipeline.py`, `src/stockai/contracts/`,
`docs/CONTRACTS.md`, M7, `config/scoring.yaml`.

## Pytest

- Fail-first trên stub: đã đỏ (status=stub) trước khi port.
- Full suite: **178 passed** (`python -m pytest -q`) — gồm 2 test gap mới
  (holiday chung / stock suspended).

## Smoke batch (~235 full+limited)

Nguồn: `data/snapshots_ext` (235 file `quality_tier_full` + `quality_tier_limited`).

| Metric | Value |
|--------|-------|
| crashes | **0** |
| T status ok / partial | 230 / 5 |
| R status ok / partial | 234 / 1 |
| T score null | 0 |
| R score null | 1 |
| `m6_long_market_gaps_excluded` | **8** (AFX, BVB, CAR, GKM, KLB, NTC, VBB, VVS) — trước fix ~235 vì Tết |

### T histogram

| Bucket | Count |
|--------|------:|
| null | 0 |
| 0-19 | 60 |
| 20-39 | 80 |
| 40-59 | 23 |
| 60-79 | 48 |
| 80-100 | 24 |

### R histogram (sau fix gap phiên chỉ số)

| Bucket | Count |
|--------|------:|
| null | 1 |
| 0-19 | 13 |
| 20-39 | 89 |
| 40-59 | 93 |
| 60-79 | 36 |
| 80-100 | 3 |

## Fix gap M6 (pass sau)

- Config: `max_missed_index_sessions: 5` (thay `max_return_gap_days` ngày lịch;
  alias cũ vẫn đọc nếu không có khóa mới).
- Đo gap = số phiên **chỉ số** nằm giữa hai ngày giao liên tiếp; nghỉ chung với
  chỉ số → 0 → giữ return đa ngày; treo stock-specific > N → loại + flag.

## StockAI M6 scoring pieces inverted (Q1:B)

Công thức **đo** giữ nguyên StockAI: beta, annualized volatility, max drawdown,
historical VaR95, historical CVaR95.

Hệ số **safety** giữ nguyên (`safety_coeffs` trong `config/technical.yaml`):
`vol_floor/mult`, `mdd_mult`, `var_mult`, `cvar_mult`, `beta_floor/mult`.

**Đảo mapping** (mỗi subscore): `risk_sub = 100 - safety_sub`, rồi:

```text
R = 0.25*vol_risk + 0.25*dd_risk + 0.20*var_risk + 0.15*tail_risk + 0.15*beta_risk
```

`inverted_components`: volatility, drawdown, var, cvar, beta.  
**CONTRACTS / M7**: R cao = rủi ro cao (khớp `−lambda*R`, `risk_gate`).

## Flags mới / dùng

M3: `m3_invalid_snapshot`, `m3_missing_as_of`, `m3_synthetic_data`,
`m3_unadjusted_prices`, `m3_invalid_price_rows_excluded`, `m3_no_valid_price_rows`,
`m3_insufficient_history_ma200`, `m3_stale_price_data`, `m3_rsi_unavailable`,
`m3_volume_ratio_unavailable`, `m3_config_defaulted`.

M6: `m6_historical_risk_estimate`, `m6_invalid_as_of`, `m6_invalid_config_defaulted`,
`m6_future_prices_excluded`, `m6_invalid_prices_excluded`, `m6_duplicate_dates_excluded`,
`m6_long_market_gaps_excluded` (nghĩa: stock miss > N phiên chỉ số),
`m6_synthetic_data`, `m6_unadjusted_stock_prices`,
`m6_insufficient_stock_prices`, `m6_insufficient_index_prices`,
`m6_insufficient_aligned_returns`, `m6_beta_unavailable`, `m6_not_ready_for_risk_score`,
`m6_data_quality_review_required`.

## Giả định

- Index VNINDEX lấy từ `snapshot.index.rows` (đã có trong snapshot M1).
- Module tự load `config/technical.yaml` khi pipeline chưa merge (pipeline không sửa).
- Giá snapshot đã là VND (M1 scale).
