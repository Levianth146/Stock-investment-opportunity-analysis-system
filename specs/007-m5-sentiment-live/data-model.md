# Data Model: M5 Sentiment Live

## Entities

### Sentiment Module Output (`module_out`)

| Field | Type | Notes |
|-------|------|-------|
| module | `"m5"` | Fixed |
| status | `ok` \| `partial` \| `error` | `ok` khi ready; `partial` khi thiếu; không hard-code luôn partial |
| score | number\|null | S ∈ [0,100] hoặc null |
| metrics | map of `{value, unit, note?}` | counts + polarity/confidence |
| evidence | list `{text, news_id?}` | 1 tổng hợp + ≤6 tiêu đề mạnh |
| flags | list[str] | tiền tố `m5_` |

**Metrics (bắt buộc khi chạy live)**:
- `news_input_count`, `news_relevant_count`, `news_directional_count`
- `news_positive_count`, `news_negative_count`, `news_neutral_count`
- `news_duplicate_count`, `news_future_excluded`, `news_old_excluded`
- `news_offtopic_excluded` (hoặc tách reason counts)
- Khi có score: `sentiment_polarity`, `sentiment_confidence`, `sentiment_score`

**Flags chính**:
- `m5_insufficient_news` (score null / chưa ready)
- `m5_future_news_excluded`, `m5_duplicate_news_excluded`
- `m5_invalid_as_of`, `m5_news_missing`, `m5_synthetic_data`
- `m5_config_defaulted` / `m5_invalid_config_defaulted`
- `m5_low_directional_coverage`
- `m5_heuristic_headline_only`

### News Item (input, từ snapshot)

`id`, `title`, `url`, `source`, `published_at`, `summary` — summary không dùng để chấm.

### Relevant Story (internal)

Sau lọc: `{id, title, date, age, polarity, weight, matches[]}`.

### Sentiment Config

- lookback_days (30), half_life_days (14)
- min_relevant_news (8), min_directional_news (4)
- ambiguous_tickers: [CEO, HCM, VND, AAA]
- S formula coeffs: base=50, scale=35, conf_dir_cap=12, conf_coverage_ref=0.35
- llm_enabled: false
- lexicon phrases + weights
- finance_keywords, cw_patterns, multi_ticker_threshold, company aliases

### Gold Label Row

CSV: `ticker,title,expected_polarity_or_label` với cột nhãn **trống**.

## Validation rules

- Output MUST pass `validate(out, "module_out")`
- score null XOR status ok (ok ⇒ score số; partial có thể score null)
- Evidence tin cụ thể MUST có `news_id` khi id có sẵn
- Không lookahead: age ≥ 0 và age ≤ lookback
