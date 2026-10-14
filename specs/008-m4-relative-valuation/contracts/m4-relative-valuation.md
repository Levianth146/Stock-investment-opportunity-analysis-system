# Contract: M4 relative valuation (điểm V)

**Owner**: N3 (`m4_valuation/`, `config/valuation.yaml`). **Does not** change
`src/stockai/contracts/schemas.py` or `docs/CONTRACTS.md`.

Outputs MUST validate as `module_out`. Signature MUST remain:

```text
run(snapshot: dict, upstream: dict, cfg: dict) -> dict
```

`target` is M4-only: `{base, bull, bear, method, assumptions}` or `null`.

## Scope boundary

| Allowed | Forbidden |
|---------|-----------|
| `src/stockai/m4_valuation/**` | `src/stockai/m1_data/**` |
| `tests/test_m4_*.py` | `src/stockai/contracts/**`, `docs/CONTRACTS.md` |
| `config/valuation.yaml` | `pipeline.py`, `main.py` |
| `scripts/build_m4_sector_stats.py` | `m3_technical/**`, `m5_sentiment/**`, `m6_risk/**` |
| `data/valuation_sector_stats.json` (generated) | Sửa M7 / ép V=50 trong M4 |
| Optional `scripts/smoke_m4_batch.py` | Commit/push without user ask |

## Behavior contract

| Concern | Requirement |
|---------|-------------|
| Inputs | `meta.as_of`, `company` (sector, is_bank, shares_outstanding), `prices.rows`, `financials` (annual/quarterly items), optional `peers`, optional `upstream["m2"]` |
| Units | VND raw: price VND/share; EPS VND/share; equity VND; book = equity/shares |
| PE | `price / eps_used` khi `eps_used > 0` |
| EPS | TTM = `sum(NI_parent\|NI)` đúng 4 quý **liên tiếp** ≤ as_of / shares (`eps_source=ttm_ni`); **không** cộng `items.eps` quý; else annual ≠0 + `m4_eps_ttm_fallback_annual` (+ `m4_eps_quarter_gap` nếu không liên tiếp) |
| PB | `price / (total_equity/shares)`; `total_equity` gồm minority; flag `m4_pb_uses_total_equity` khi minority NI >5%; kế hoạch `parent_equity` khi M1 có |
| Lookahead | Ignore `date`/`published_at` > `as_of` |
| Sector compare | Median PE/PB sau winsorize từ `valuation_sector_stats.json` theo `company.sector`; **not** silent peer-median |
| Score polarity | **V cao = rẻ/hấp dẫn** — percentile inverted trên `pe_sorted`/`pb_sorted` trong sector stats (không quét lại snapshots) |
| Sector fallback | `n < min_sector_n` → `__market__` + `m4_sector_fallback`; chỉ chân PE (`m4_pb_leg_dropped`) |
| Bank | `is_bank` → P/B primary (`m4_bank_primary_pb`); thiếu PE không chặn nếu PB đủ |
| Null score | Không đủ chân/median → `score=null` + flags; **MUST NOT** assign 50 |
| M7 interaction | M7 existing: null V → `neutral_score_when_missing` + `V_missing_used_neutral` — M4 không làm việc đó |
| Stale | Last price > `stale_calendar_days` (default 7) before as_of → `m4_stale_price_data`; default vẫn chấm |
| Target | Relative multiples implied price; `enable_dcf: false` → no DCF branch |
| Evidence | Vietnamese `text`; `news_id` optional |
| Status | `ok` when numeric V and no material quality flags; else `partial` / null score |
| Config | Thresholds/weights from `config/valuation.yaml` / `cfg.m4`; missing keys → safe defaults + `m4_config_defaulted` |

## Sector stats build contract

```text
scripts/build_m4_sector_stats.py
  --as-of YYYY-MM-DD
  [--snapshots-dir data/snapshots_ext]
  [--out data/valuation_sector_stats.json]
  [--config config/valuation.yaml]
```

- Universe: tickers with `quality_tier_full` or `quality_tier_limited` for that as_of.
- Same PE/PB derivation rules as runtime (shared helper preferred).
- Winsorize then median per sector; write JSON shape in [research.md](../research.md) R4 / [data-model.md](../data-model.md).
- Offline local; no network. Idempotent for same inputs.

## Config contract (`config/valuation.yaml`)

- Readable without network.
- MUST expose: sector stats path, stale days, winsor bounds (build), min_sector_n,
  bank/non-bank weights, cheapness map, target bands, `enable_dcf: false`.
- MUST NOT hard-code business thresholds only inside Python without documented defaults.

## Test contract (offline)

| Suite | Must prove |
|-------|------------|
| Fail-first | New tests fail on current stub (`status=stub`) |
| Polarity | Same-sector cheap fixture V **>** expensive fixture |
| Bank | `is_bank` + PB đủ → numeric V dù PE unavailable |
| Null | Missing blockers → `score is None`, not 50 |
| as_of | Future price/fin rows unused |
| Stale | >7d → `m4_stale_price_data` |
| EPS fallback | Quarterly sum 0 + annual >0 → annual + fallback flag |
| Sector missing | No median → null or remaining leg only + flags |
| Real-5 | VCB/FPT/HPG/VIC/SSI no crash if files exist (skip if missing) |
| Full pytest | Green after implement; count reported |
| Smoke (ops) | ~235 FL no mass crash; print V distribution / ok / partial / null |

## Downstream consumers (read-only awareness)

- **M7**: reads `score` as V; copies `target`; null → neutral + `V_missing_used_neutral`.
- **M8/M9**: consume result; M4 MUST keep `module_out` shape valid.

This feature does **not** modify those modules.
