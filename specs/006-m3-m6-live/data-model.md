# Data Model: M3 + M6 Live (006)

No new schema types. Inputs/outputs remain under existing `snapshot` and
`module_out` contracts (`src/stockai/contracts/schemas.py`).

## Entities

### 1. Technical Module Output (M3)

| Field | Type | Rules |
|-------|------|-------|
| `module` | string | `"m3"` |
| `status` | enum | `ok` \| `partial` \| `error` (không còn `stub` sau implement) |
| `score` | number\|null | T ∈ [0, 100] khi đủ history + tính được; else `null` |
| `metrics` | object | Keys xem [research.md](./research.md) R7; mỗi value `{value, unit[, note]}` |
| `evidence` | array | ≥0; có `text` (+ `source_id` khi có từ `prices.source_id`) |
| `flags` | string[] | Opaque tokens dưới đây |

**Relationships**: Đọc `snapshot.meta`, `snapshot.prices` only. `upstream` unused.

### 2. Risk Module Output (M6)

| Field | Type | Rules |
|-------|------|-------|
| `module` | string | `"m6"` |
| `status` | enum | `ok` khi eligible + có score; `partial` khi thiếu/chưa sẵn sàng |
| `score` | number\|null | **R** ∈ [0, 100]; **cao = rủi ro cao** (Q1:B) |
| `metrics` | object | beta, vols, MDD, VaR/CVaR, aligned counts, risk subscores (post-invert) |
| `evidence` | array | Mô tả lookback / aligned n |
| `flags` | string[] | Tokens dưới đây |

**Relationships**: Đọc `snapshot.meta`, `snapshot.prices`, `snapshot.index`.
`upstream` unused.

### 3. Aligned Return Series (internal, not persisted)

| Field | Meaning |
|-------|---------|
| `common_days` | Ngày giao `prices` ∩ `index`, `<= as_of`, no forward-fill |
| `stock_ret` / `index_ret` | Lợi suất căn ngày; bỏ cặp gap lịch > 7 ngày |
| `n` | `len(stock_ret)` — so với `min_observations` |

Derived only inside M6 `run`; không ghi vào snapshot.

### 4. Scoring Thresholds Config

Persisted as `config/technical.yaml` (N4). Runtime: keys có thể nằm trong `cfg`
(override file). Không đổi schema snapshot.

| Section | Purpose |
|---------|---------|
| `m3.*` | cửa sổ chỉ báo, stale days, rubric điểm T |
| `m6.*` | lookback, min obs, coeffs safety→invert, weights, polarity notes |

## Flag catalog (canonical)

### M3

| Flag | When |
|------|------|
| `m3_invalid_snapshot` | snapshot không phải dict |
| `m3_missing_as_of` | thiếu `meta.as_of` |
| `m3_synthetic_data` | `meta.synthetic` |
| `m3_unadjusted_prices` | `prices.adjusted is not True` |
| `m3_invalid_price_rows_excluded` | có dòng OHLC lỗi bị loại |
| `m3_no_valid_price_rows` | không còn phiên hợp lệ |
| `m3_insufficient_history_ma200` | `< 200` phiên → score null |
| `m3_stale_price_data` | phiên cuối cách as_of > 7 ngày lịch |
| `m3_rsi_unavailable` / `m3_volume_ratio_unavailable` | nhánh thiếu như StockAI |
| `m3_config_defaulted` | (optional) thiếu khóa cfg → mặc định an toàn |

### M6

| Flag | When |
|------|------|
| `m6_historical_risk_estimate` | luôn (ước lượng lịch sử) |
| `m6_invalid_as_of` | as_of không parse |
| `m6_invalid_config_defaulted` | lookback/min/annual parse fail |
| `m6_future_prices_excluded` | có ngày > as_of bị bỏ |
| `m6_invalid_prices_excluded` | close/date lỗi |
| `m6_duplicate_dates_excluded` | trùng ngày (stock hoặc index) |
| `m6_long_market_gaps_excluded` | có return gap > 7 ngày |
| `m6_synthetic_data` | synthetic |
| `m6_unadjusted_stock_prices` | chưa adjusted |
| `m6_insufficient_stock_prices` / `m6_insufficient_index_prices` | độ dài thô < min+1 |
| `m6_insufficient_aligned_returns` | `n < min_observations` |
| `m6_beta_unavailable` | var(index) ~ 0 |
| `m6_not_ready_for_risk_score` | không eligible |
| `m6_data_quality_review_required` | unadjusted hoặc synthetic |

## Status transitions

### M3

```text
start → validate snapshot/as_of
  → filter rows (as_of + OHLC)
  → n < 200 ──────────────► score=null, partial (+ insufficient flag)
  → compute indicators + rubric
  → flags empty ──────────► status=ok, score=T
  → else ─────────────────► status=partial (score vẫn có nếu đã tính đủ)
```

### M6

```text
start → clean prices/index ≤ as_of
  → align returns (intersection, gap filter)
  → n < min ──────────────► score=null, partial
  → compute measures + safety subscores → invert → risk subscores
  → eligible? ────────────► yes: score=R, status=ok
                          └► no:  score=null, partial (+ not_ready / quality flags)
```

## Validation rules

- Mọi đầu ra: `validate(out, "module_out")` trước return; lỗi → raise.
- `score` null hoặc ∈ [0, 100]; không số ngoài khoảng.
- Không dùng `date > as_of` trong metrics/score.
- Không forward-fill chuỗi giá.
- Polarity: trên hai fixture cùng khung, high-risk R > stable R.

## Relationships (pipeline context, read-only)

```text
snapshot ──► M3 ──► module_out(T)
         └─► M6 ──► module_out(R) ──► M7 (unchanged; −lambda*R, risk_gate)
```

Feature 006 không sửa cạnh M7 / pipeline.
