# Contract: M3 technical + M6 risk live modules

**Owner**: N4 (`m3_technical/`, `m6_risk/`). **Does not** change
`src/stockai/contracts/schemas.py` or `docs/CONTRACTS.md`.

Outputs MUST validate as `module_out`. Signature MUST remain:

```text
run(snapshot: dict, upstream: dict, cfg: dict) -> dict
```

## Scope boundary

| Allowed | Forbidden |
|---------|-----------|
| `src/stockai/m3_technical/**` | `src/stockai/m1_data/**` |
| `src/stockai/m6_risk/**` | `pipeline.py`, `main.py` |
| `tests/test_m3_*.py`, `tests/test_m6_*.py` | `src/stockai/contracts/**` |
| `config/technical.yaml` (create/extend) | `docs/CONTRACTS.md`, M7 code |
| `config/scoring.yaml` only if proven necessary | Commit/push without user ask |

## M3 behavior contract

| Concern | Requirement |
|---------|-------------|
| Input | `snapshot.prices.rows` OHLC+volume; `meta.as_of` |
| Lookahead | Ignore `date > as_of` |
| Bad OHLC | Exclude; flag `m3_invalid_price_rows_excluded`; expose count in metrics |
| History | `< 200` valid sessions → `score=null`, `m3_insufficient_history_ma200` |
| Indicators | MA20/50/200, RSI14 Wilder, MACD(12,26,9)+signal+hist, volume_ratio_20, ATR14 (VND) |
| Score T | Rubric trend/momentum/volume/volatility; thresholds from cfg/technical.yaml |
| Stale | Last session > 7 calendar days before as_of → `m3_stale_price_data` |
| Empty | No crash; null score + flags; `status=partial` |
| Status | `ok` iff computed score and no blocking deficiency flags; else `partial` |

## M6 behavior contract

| Concern | Requirement |
|---------|-------------|
| Input | `prices` + `index` (VNINDEX); adjusted stock prices for scoring |
| Align | Same calendar dates only; **no forward-fill** |
| Gap | Skip return if calendar gap between consecutive aligned days > 7 |
| Measures | beta, annualized vol, MDD, hist VaR95, hist CVaR95 — **StockAI formulas** |
| Polarity | **R high = risk high** (Q1:B). Invert StockAI safety→risk mapping only |
| Config | Document `inverted_vs_stockai` + coeffs/weights in technical.yaml + docstring |
| Eligible | not synthetic; `adjusted is True`; beta available; last aligned ≤ 10 days from as_of; `n >= min_observations` |
| Status | `ok` when eligible and numeric score; **not** hard-coded `partial` |
| Beta check | Identical stock/index series → beta ≈ 1 (float tolerance) |
| Polarity-lock | High-vol/deep-DD fixture R **>** stable fixture; test fails if polarity flipped |

## Config contract (`config/technical.yaml`)

- MUST be readable without network.
- Missing keys → safe defaults matching StockAI numeric coeffs (then invert for R)
  + optional `*_config_defaulted` flag.
- MUST state scoring polarity for M6 explicitly.
- M7 `config/scoring.yaml` remains source of `lambda_R` / `risk_gate` — this
  feature does not redefine those.

## Test contract (offline)

| Suite | Must prove |
|-------|------------|
| Fail-first | New tests fail on current stubs |
| M3 | enough → score+ok; short history → null; future dates unused; bad OHLC flagged; stale; empty no crash |
| M6 | enough → score+ok; insufficient → null; no forward-fill; beta≈1; unadjusted/synthetic null; polarity order + lock |
| Full pytest | Green after implement; count reported |
| Smoke (ops) | ~235 full+limited no mass crash; print T/R distributions |

## Reference (read-only)

- `D:\Projects\StockAI\src\stockai\m3_technical\run.py`
- `D:\Projects\StockAI\src\stockai\m6_risk\run.py`

Do not modify reference files. Intentional deltas vs reference: M6 status `ok`;
M6 R polarity inverted; thresholds externalized to config.
