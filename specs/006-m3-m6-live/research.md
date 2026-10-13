# Research: M3 + M6 Live (006)

**Scope**: Port M3/M6 từ StockAI tham chiếu; cực tính R theo Q1:B (CONTRACTS).
Clarification 2026-10-13 binding.

## R0 — Cực tính điểm R (Q1:B)

**Decision**: **R 0–100, R cao = rủi ro cao** (khớp `docs/CONTRACTS.md` dòng M6 và
M7: `Score = … − lambda*R`, `risk_gate.R_threshold`). Port nguyên công thức đo
chỉ số từ StockAI (beta, annualized volatility, MDD, VaR95, CVaR95 historical).
**Chỉ đảo mapping** từ chỉ số đo → điểm R / risk subscores.

StockAI tham chiếu (docstring): “higher means LOWER measured market risk” — safety
subscores rồi weighted average. Feature này:

1. Tính cùng các chỉ số đo (công thức không đổi).
2. Tính **safety subscores** bằng đúng hệ số StockAI (để đối chiếu / test nội bộ
   nếu cần), rồi **invert từng subscore**: `risk_sub = 100 - safety_sub`
   (clamp đã nằm trong safety_sub).
3. `R = round(0.25*vol_risk + 0.25*dd_risk + 0.20*var_risk + 0.15*tail_risk + 0.15*beta_risk, 2)`.
4. Tương đương `R = 100 - StockAI_score` khi cùng trọng số — MUST document trong
   docstring module và `config/technical.yaml` (mục `m6.scoring_polarity`,
   `inverted_vs_stockai: true`, liệt kê subscore đã đảo).

**Polarity-lock tests** (MUST):
- High-vol + deep-drawdown fixture có `score` **>** stable fixture cùng khung.
- Test khóa: nếu invert lại (giả lập safety-as-R) thì assertion fail — chứng minh
  cực tính CONTRACTS.

**MUST NOT** sửa `docs/CONTRACTS.md` hay M7 trong feature này.

**Rationale**: Spec Q1:B; tránh méo ranking M7.

**Alternatives considered**:
- Đổi M7 / CONTRACTS theo StockAI → bị từ chối (phạm vi + đã khóa Q1:B).
- Chỉ đảo điểm cuối mà không ghi config → thiếu audit trail → rejected.
- Đổi công thức VaR/beta → forbidden by FR-008/009.

## R1 — M6 `status` (lệch StockAI có chủ đích)

**Decision**: Khi đủ điều kiện chấm (`eligible` như StockAI: không synthetic,
`prices.adjusted is True`, `beta_score` có, `(as_of - last_aligned).days <= 10`,
và `n >= min_observations`) **và** đã gán `score` số → `status = "ok"`.
Khi chưa đủ → `score = null`, `status = "partial"` (hoặc giữ partial khi còn cờ
chất lượng chặn), **không** hard-code `"partial"` mọi lần chạy như StockAI.

**Rationale**: Spec US2 / FR-010.

**Alternatives considered**: Giữ hard-code partial → lệch FR-010.

## R2 — MA200 và ngưỡng lịch sử M3

**Decision**: Cần **≥ 200** phiên hợp lệ (`date <= as_of`, OHLC sạch) trước khi
tính chỉ báo và chấm T. Nếu `n < 200` → `score = null`, flag
`m3_insufficient_history_ma200`, `status = partial`, không bịa MA200/điểm.
Rolling MA dùng `min_periods` bằng cửa sổ (20/50/200) như StockAI.

**Rationale**: Spec FR-004 / SC-002; khớp tham chiếu.

## R3 — Date alignment M6 (không forward-fill)

**Decision**:
- Lọc giá cổ phiếu và chỉ số: `date <= as_of`, close hữu hạn > 0.
- Giao ngày chung: `common_days = sorted(set(stock) ∩ set(market))`.
- Cắt lookback: `common_days[-(lookback+1):]` (mặc định lookback=252).
- Lợi suất cặp `(prev, curr)` chỉ khi `(curr - prev).days <= 7`; khoảng > 7 ngày
  → bỏ quan sát đó, đếm `gap_returns_excluded`, flag
  `m6_long_market_gaps_excluded` nếu gap_count > 0.
- **Không** forward-fill giá ngày thiếu.

**Rationale**: Spec FR-008; StockAI comments/code.

## R4 — OHLC bad-row handling (M3)

**Decision**: Loại dòng khi: không phải dict; date không parse được; bất kỳ
OHLCV không finite; giá ≤ 0; `volume < 0`; `high < low`; close ngoài [low, high].
Dòng `date > as_of` **bỏ qua im lặng** (không đếm vào invalid — không phải “lỗi
OHLC”, là lookahead filter). Đếm `invalid_count` → nếu > 0 gắn
`m3_invalid_price_rows_excluded`; metrics nên lộ `invalid_price_rows` (sessions/rows)
để đáp ứng “kèm đếm” trong spec mà vẫn giữ tên flag StockAI.

Trùng ngày: `drop_duplicates(date, keep="last")` sau sort.

**Rationale**: Spec US1 scenarios 3–4; StockAI filter.

## R5 — Stale / readiness flags

**Decision**:

| Module | Rule | Flag / effect |
|--------|------|----------------|
| M3 | `(last_valid_date - as_of).days < -7` (phiên cuối cách as_of > 7 ngày lịch) | `m3_stale_price_data`; vẫn có thể có score nếu đủ history; `status=partial` nếu còn flags |
| M6 | `(as_of - last_common_day).days > 10` | không eligible → `score=null`, `m6_not_ready_for_risk_score` |
| M6 | `adjusted is not True` | `m6_unadjusted_stock_prices` + không eligible |
| M6 | `meta.synthetic is True` | `m6_synthetic_data` + không eligible |
| Empty prices / empty index | | M3: `m3_no_valid_price_rows`; M6: insufficient flags; không exception |

**Rationale**: Spec FR-007 / FR-010; StockAI eligible block.

## R6 — Config thresholds (không hard-code)

**Decision**: Tạo `config/technical.yaml` (OWNERSHIP N4). Module đọc qua `cfg`
(pipeline/caller merge file vào cfg, hoặc module load mặc định khi thiếu khóa —
implement chọn một pattern và gắn flag `m3_config_defaulted` /
`m6_invalid_config_defaulted` khi fallback).

Khóa đề xuất:

```yaml
# M3 rubric — điểm cộng tối đa trend 35 / momentum 30 / volume 20 / volatility 15
m3:
  min_sessions_ma200: 200
  stale_calendar_days: 7
  rsi_period: 14
  macd: {fast: 12, slow: 26, signal: 9}
  volume_ma: 20
  atr_period: 14
  # ngưỡng điểm (port từ StockAI heuristic; chỉnh sau không sửa code)
  trend: {above_ma_points: 10, alignment_bonus: 5}
  momentum: {macd_above_signal: 10, macd_above_zero: 10, rsi_bands: ...}
  volume: {up_high: 20, up_mid: 12, low_ratio: 8, else: 3, ratio_high: 1.2, ratio_mid: 0.8}
  volatility_atr_pct: [{max: 2, points: 15}, {max: 4, points: 10}, {max: 6, points: 5}, {else: 0}]

m6:
  scoring_polarity: "high_R_means_high_risk"   # Q1:B / CONTRACTS
  inverted_vs_stockai: true
  inverted_components: [volatility, drawdown, var, cvar, beta]
  lookback_sessions: 252
  min_observations: 120
  annual_sessions: 252
  max_return_gap_days: 7
  max_stale_aligned_days: 10
  # hệ số safety-subscore StockAI (trước invert)
  safety_coeffs:
    vol_floor: 0.15
    vol_mult: 200
    mdd_mult: 180
    var_mult: 1400
    cvar_mult: 900
    beta_floor: 0.7
    beta_mult: 45
  weights: {vol: 0.25, drawdown: 0.25, var: 0.20, tail: 0.15, beta: 0.15}
```

**Không** sửa `config/scoring.yaml` mặc định (N5 / M7 đã giả định R cao = rủi ro
cao). Spec cho phép scoring.yaml “nếu cần” — chỉ đụng khi có khóa chia sẻ bắt
buộc; research chọn tránh.

**Rationale**: FR-006 / FR-009; OWNERSHIP `technical.yaml`.

**Alternatives considered**: Hard-code như StockAI → vi phạm FR-006; nhét vào
scoring.yaml → đụng N5 không cần thiết.

## R7 — Metrics / evidence surface

**Decision**: Metrics keys bám StockAI để smoke/so sánh dễ:

- M3: `observations`, `close`, `ma20/50/200`, `rsi14`, `macd`, `macd_signal`,
  `macd_histogram`, `volume`, `volume_ma20`, `volume_ratio_20`, `atr14`,
  `atr_pct`, sub-scores trend/momentum/volume/volatility, `technical_score`,
  cộng `invalid_price_rows` nếu implement đếm.
- M6: `aligned_observations`, `future_rows_excluded`, `gap_returns_excluded`,
  `annualized_volatility`, `benchmark_volatility`, `beta`, `max_drawdown`,
  `benchmark_max_drawdown`, `historical_var_95`, `historical_cvar_95`,
  `negative_sessions`, `positive_sessions`, `last_aligned_date`, risk
  **subscores** (sau invert — docstring ghi rõ là risk-direction), optional
  evidence text cập nhật “higher R = higher measured risk”.

Mỗi metric: `{value, unit[, note]}` theo schema `module_out`.

## R8 — Testing & smoke strategy

**Decision**:
1. Fail-first trên stub hiện tại (`status=stub`) — test hành vi live MUST fail.
2. Offline fixtures: đủ 200+ phiên; thiếu history; future dates; bad OHLC; stale;
   empty (ATP-like); M6 identical series → beta≈1; high-vol vs stable polarity;
   unadjusted / synthetic → null score.
3. MAY 1–2 test load `data/snapshots_ext` với `pytest.importorskip` / skip if missing.
4. Sau implement: `python -m pytest -q` toàn repo; smoke script hoặc one-liner
   gọi `run_m3`/`run_m6` trên ~235 full+limited, in histogram T/R, đếm ok/partial/null.
5. Báo cáo hoàn thành MUST liệt kê phần scoring StockAI đã đảo.

**Rationale**: FR-012 / FR-013 / SC-006 / SC-007.

## R9 — Dependencies & pandas RSI nuance

**Decision**: Giữ cách StockAI tính RSI (EWM alpha=1/14, nhánh avg_loss==0 → 100/50)
và ATR EWM — không “cải tiến” công thức trong feature này. `pandas` đã có trong
repo (M1/tests). Không thêm dependency.

**Rationale**: FR-003 port hành vi; YAGNI.

## Resolved unknowns checklist

| Former unknown | Resolution |
|----------------|------------|
| R polarity | R0 — Q1:B high = risk high; invert mapping only |
| MA200 gate | R2 — ≥200 sessions |
| Date align | R3 — intersection, no forward-fill, gap>7 drop |
| OHLC bad rows | R4 — exclude + count + flag |
| Stale | R5 — M3 7d flag; M6 10d eligibility |
| Config | R6 — `config/technical.yaml` |
| Status M6 | R1 — ok when eligible |
| Contracts/M7 edits | Forbidden — none |

All Technical Context items resolved — no remaining NEEDS CLARIFICATION.
