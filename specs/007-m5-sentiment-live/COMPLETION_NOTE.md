# Completion Note — Feature 007 M5 Sentiment Live

**Branch**: `007-m5-sentiment` (local, no push)  
**Date**: 2026-10-13  
**Commit**: none (per user request)

## Spec / plan / tasks

- `specs/007-m5-sentiment-live/spec.md`
- `specs/007-m5-sentiment-live/plan.md`
- `specs/007-m5-sentiment-live/research.md`
- `specs/007-m5-sentiment-live/data-model.md`
- `specs/007-m5-sentiment-live/contracts/m5-sentiment-live.md`
- `specs/007-m5-sentiment-live/quickstart.md`
- `specs/007-m5-sentiment-live/tasks.md`
- `specs/007-m5-sentiment-live/checklists/requirements.md`

## Ambiguous tickers

**Config seed (APPROVED, written)**: CEO, HCM, VND, AAA — **not** DRC.

**Re-scan proposal (corrected rule; NOT written to config)**:

Method: lookback=30d; EXCLUDE vnstock/VCI; only Google News; require ≥8 GN in window; threshold ≥30% headlines without finance keywords; full+limited only.

Evaluated=58, skipped_low_gn=177, DRC in proposed=False.

Proposed for user review (NEW = needs approval; SEED = already approved):

| Ticker | Mark | use% | GN in window |
|--------|------|------|--------------|
| BSR | NEW | 90.0 | 20 |
| VND | SEED | 83.3 | 30 |
| HCM | SEED | 82.5 | 40 |
| BCM | NEW | 77.8 | 9 |
| ACB | NEW | 69.2 | 13 |
| CEO | SEED | 63.4 | 41 |
| VIB | NEW | 61.5 | 13 |
| NLG | NEW | 60.0 | 10 |
| OCB | NEW | 54.5 | 11 |
| GAS | NEW | 50.0 | 10 |
| GVR | NEW | 50.0 | 12 |
| PLX | NEW | 50.0 | 8 |
| REE | NEW | 45.5 | 11 |
| KBC | NEW | 44.4 | 9 |
| MBS | NEW | 40.0 | 15 |
| GMD | NEW | 37.5 | 8 |
| PET | NEW | 36.4 | 11 |
| VNM | NEW | 36.4 | 11 |
| SHB | NEW | 35.3 | 17 |
| KOS | NEW | 34.8 | 23 |
| LPB | NEW | 33.3 | 9 |
| PC1 | NEW | 33.3 | 24 |
| MSB | NEW | 30.4 | 23 |

AAA: approved seed but did not meet threshold under corrected rule.  
Script: `scripts/_scan_ambiguous_m5.py`

## Pytest

- Fail-first on stub: 10 failed / 1 passed (gold CSV)
- After implement: `tests/test_m5_sentiment.py` → **11 passed**
- Full suite: **189 passed** in ~76s

## Smoke 235 full+limited (`scripts/smoke_m5_batch.py`)

half_life=14; config default lookback **stays 30**.

| Metric | lookback=30 | lookback=60 |
|--------|-------------|-------------|
| n | 235 | 235 |
| crashes | 0 | 0 |
| status ok | 10 | 33 |
| status partial | 225 | 202 |
| score null | 225 | 202 |
| **m5_insufficient_news** | **225** | **202** |
| offtopic_excluded sum | 374 | 748 |

S histogram @30 (10 scored): [20,40)=4; [40,50)=2; [50,60)=4

Top10 @30 (only 10 scored — same set as bottom ordered):  
MBS 56.85, SSB 56.70, SSI 54.53, VPB 52.46, SHB 49.37, FPT 41.07, PNJ 39.40, DIG 32.89, NVL 29.31, KOS 23.64  
(each with 2 evidence headlines in smoke stdout)

Note: At lookback 30 most tickers fail readiness (min_relevant=8 AND min_directional=4) because many headlines in-window are neutral vs lexicon; widening lookback to 60 raises ok 10→33. Default config unchanged.

## Files changed (no commit)

- `src/stockai/m5_sentiment/run.py`
- `config/sentiment.yaml`, `config/sentiment_lexicon.yaml`, `config/news_aliases.yaml`
- `fixtures/m5_gold_labels.csv`
- `tests/test_m5_sentiment.py`, `tests/helpers_m5_snapshots.py`
- `scripts/smoke_m5_batch.py`, `scripts/_scan_ambiguous_m5.py` (local)
- `specs/007-m5-sentiment-live/*`

Did **not** edit: m1_data, pipeline.py, contracts/*, docs/CONTRACTS.md, M7.
