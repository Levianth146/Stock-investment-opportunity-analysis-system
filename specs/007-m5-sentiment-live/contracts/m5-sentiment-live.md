# Contract: M5 Sentiment Live

## Interface

```text
run(snapshot: dict, upstream: dict, cfg: dict) -> dict  # module_out
```

- `upstream` có thể `{}` (M5 không phụ thuộc F/T/V/R).
- Đầu ra MUST `validate(out, "module_out") == []`.
- MUST NOT sửa `src/stockai/contracts/*` hay `docs/CONTRACTS.md`.

## Behavioural contract

| Case | score | status | flags (tối thiểu) |
|------|-------|--------|-------------------|
| Đủ relevant + directional, không synthetic | số [0,100] | `ok` | `m5_heuristic_headline_only` |
| Thiếu tin / dưới ngưỡng | `null` | `partial` | `m5_insufficient_news` |
| synthetic=true | `null` | `partial` | `m5_synthetic_data`, `m5_insufficient_news` |
| news missing/invalid | `null` | `partial` | `m5_news_missing` / … |
| Tin published_at > as_of | không vào score | — | `m5_future_news_excluded` nếu có |

## Scoring (config-driven)

- Title-only lexicon polarity ∈ [-1, 1]
- Time decay: `exp(-ln(2)*age/half_life_days)` default half_life=14
- `S = clamp(50 + 35 * weighted_polarity * confidence, 0, 100)`
- Ready: `n_relevant >= min_relevant_news` (8) AND `n_directional >= min_directional_news` (4)

## Filters

- as_of / lookback (default lookback_days=30)
- ticker OR company/alias match
- ambiguous tickers (CEO,HCM,VND,AAA): require finance keyword OR company match
- warrant / multi-ticker / empty title / dedupe

## Evidence

1. Summary text (counts, lookback, heuristic note)
2. Up to **6** strongest directional headlines with `news_id` when present

## Config files (M5-owned)

- `config/sentiment.yaml`
- `config/sentiment_lexicon.yaml`
- `config/news_aliases.yaml`

`ambiguous_tickers` MUST equal approved seed only unless user later approves scan proposals.

## Out of scope

m1_data, pipeline, contracts, CONTRACTS.md, M7, LLM, changing default lookback without user ask.
