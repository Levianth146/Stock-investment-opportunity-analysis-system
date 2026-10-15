# Tasks: M5 Sentiment Live (Ä‘iá»ƒm S)

**Input**: Design documents from `/specs/007-m5-sentiment-live/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/m5-sentiment-live.md, quickstart.md

**Tests**: TDD fail-first **báº¯t buá»™c**. Viáº¿t test trÆ°á»›c â†’ confirm FAIL trÃªn stub â†’ má»›i implement.

**Organization**: Theo user story. Pháº¡m vi: `src/stockai/m5_sentiment/`, `tests/test_m5_*.py`, `config/sentiment.yaml`, `config/sentiment_lexicon.yaml`, `config/news_aliases.yaml`, gold CSV, optional `scripts/smoke_m5_batch.py`. MUST NOT sá»­a m1_data, pipeline, contracts, CONTRACTS.md, M7. Ambiguous config = CEO,HCM,VND,AAA only. KhÃ´ng commit/push.

**Tham chiáº¿u chá»‰-Ä‘á»c**: `D:\Projects\StockAI\src\stockai\m5_sentiment\run.py` â€” Ã½ tÆ°á»Ÿng, khÃ´ng copy.

## Format: `[ID] [P?] [Story] Description`

---

## Phase 1: Setup (Shared Infrastructure)

- [x] T001 Confirm artifacts sáºµn sÃ ng dÆ°á»›i `specs/007-m5-sentiment-live/` vÃ  nhÃ¡nh local `007-m5-sentiment`; ghi pháº¡m vi cáº¥m (khÃ´ng Ä‘á»¥ng m1_data/pipeline/contracts/CONTRACTS/M7)
- [x] T002 [P] Create `config/sentiment.yaml` (lookback_days=30, half_life_days=14, min_relevant_news=8, min_directional_news=4, ambiguous_tickers=[CEO,HCM,VND,AAA], S coeffs, llm_enabled=false)
- [x] T003 [P] Create `config/sentiment_lexicon.yaml` vá»›i cá»¥m positive/negative cÃ³ trá»ng sá»‘ (giá»¯ Ä‘ trong nguá»“n; fold khi khá»›p); khÃ´ng Ä‘Æ¡n tá»« mÆ¡ há»“ tÄƒng/giáº£m/mua/bÃ¡n/lÃ£i/lá»—
- [x] T004 [P] Create `config/news_aliases.yaml` (finance_keywords, cw_patterns, multi_ticker_threshold, company aliases tá»‘i thiá»ƒu cho seed ambiguous)
- [x] T005 [P] Create `fixtures/m5_gold_labels.csv` vá»›i cá»™t nhÃ£n trá»‘ng

---

## Phase 2: Foundational (Blocking Prerequisites)

**âš ï¸ CRITICAL**: KhÃ´ng port heuristic cho Ä‘áº¿n khi phase nÃ y xong

- [x] T006 Skeleton cfg loader trong `src/stockai/m5_sentiment/run.py`: merge `cfg.m5` + 3 file yaml; safe defaults; cá» `m5_config_defaulted`; giá»¯ chá»¯ kÃ½ `run` + stub táº¡m náº¿u chÆ°a sáºµn sÃ ng US1
- [x] T007 [P] Helpers dá»±ng snapshot tin trong `tests/helpers_m5_snapshots.py` (Ä‘á»§ hÆ°á»›ng; thiáº¿u; future; duplicate; CW; multi-ticker; ambiguous CEO; tiÃªu Ä‘á» â€œÄ‘iá»u traâ€; synthetic)
- [x] T008 Wire pytest import helpers + PYTHONPATH=src offline

**Checkpoint**: Foundation ready â€” viáº¿t fail-first tests

---

## Phase 3: User Story 1 - Cháº¥m Ä‘iá»ƒm S tá»« tiÃªu Ä‘á» (Priority: P1) ðŸŽ¯ MVP

**Goal**: Lá»c as_of/lookback/liÃªn quan/dedupe/CW/ambiguous; lexicon title-only; S formula; status ok/partial; evidence â‰¤6 + news_id; validate.

**Independent Test**: Snapshot dá»±ng tay + `run` M5 Ä‘á»™c láº­p.

### Tests (TDD â€” MUST FAIL trÃªn stub)

- [x] T009 [P] [US1] Fail-first: Ä‘á»§ tin â†’ score sá»‘ [0,100], status=ok, metrics counts in `tests/test_m5_sentiment.py`
- [x] T010 [P] [US1] Fail-first: thiáº¿u tin â†’ score null, `m5_insufficient_news`, status=partial
- [x] T011 [P] [US1] Fail-first: tin published_at > as_of khÃ´ng vÃ o score + cá» future
- [x] T012 [P] [US1] Fail-first: tiÃªu Ä‘á» â€œÄ‘iá»u traâ€ khá»›p lexicon (giá»¯ Ä‘ / NFC)
- [x] T013 [P] [US1] Fail-first: duplicate title chá»‰ giá»¯ 1 + cá» duplicate
- [x] T014 [P] [US1] Fail-first: CW / multi-ticker / ambiguous seed thiáº¿u finance kw bá»‹ loáº¡i
- [x] T015 [US1] Run `python -m pytest -q tests/test_m5_sentiment.py` confirm **FAIL** trÃªn stub trÆ°á»›c implement

### Implementation

- [x] T016 [US1] Implement normalize NFC+giá»¯ Ä‘, parse_date, filters (as_of/lookback/identity/CW/multi/ambiguous/dedupe) trong `src/stockai/m5_sentiment/run.py`
- [x] T017 [US1] Implement lexicon match (title-only) + polarity clip trong `src/stockai/m5_sentiment/run.py`
- [x] T018 [US1] Implement S formula (half-life decay, confidence, clamp) + readiness gates tá»« config trong `src/stockai/m5_sentiment/run.py`
- [x] T019 [US1] Emit metrics/flags/evidence (â‰¤6, news_id) + `validate(out,"module_out")`; status ok khi ready â€” MUST NOT hard-code partial luÃ´n; MUST NOT hard-code FPT
- [x] T020 [US1] Re-run `python -m pytest -q tests/test_m5_sentiment.py` until green

**Checkpoint**: US1 offline pass

---

## Phase 4: User Story 2 - Config / lexicon / gold CSV (Priority: P1)

**Goal**: Má»i ngÆ°á»¡ng tá»« config; thiáº¿u khÃ³a â†’ default + cá»; gold CSV nhÃ£n trá»‘ng; khÃ´ng LLM.

### Tests

- [x] T021 [P] [US2] Fail-first/then-pass: ambiguous list Ä‘á»c tá»« config = seed only; llm_enabled false path in `tests/test_m5_sentiment.py`
- [x] T022 [P] [US2] Test gold CSV tá»“n táº¡i + cá»™t label trá»‘ng in `tests/test_m5_sentiment.py`
- [x] T023 [P] [US2] Test thiáº¿u khÃ³a config â†’ default + `m5_config_defaulted` / invalid defaulted

### Implementation

- [x] T024 [US2] HoÃ n thiá»‡n load 3 yaml + merge cfg; khÃ´ng hard-code ngÆ°á»¡ng nghiá»‡p vá»¥ trong mÃ£ nguá»“n
- [x] T025 [US2] XÃ¡c nháº­n `fixtures/m5_gold_labels.csv` schema; tests khÃ´ng phá»¥ thuá»™c nhÃ£n Ä‘Ã£ Ä‘iá»n
- [x] T026 [US2] Re-run M5 tests green cho US2

**Checkpoint**: Config-driven + gold sáºµn

---

## Phase 5: User Story 3 - Full pytest + smoke 235 (Priority: P1)

- [x] T027 [P] [US3] Optional 1â€“2 real-snapshot tests (skip if missing) in `tests/test_m5_sentiment.py`
- [x] T028 [US3] Run full `python -m pytest -q`; ghi sá»‘ pass
- [x] T029 [US3] Create `scripts/smoke_m5_batch.py` (~235 full+limited): histogram S, ok/partial, null, top10/bottom10 +2 headlines, off-topic filtered, `m5_insufficient_news` @ lookback 30 vÃ  60 (half_life=14); default config khÃ´ng Ä‘á»•i
- [x] T030 [US3] Execute smoke; dÃ¡n káº¿t quáº£ vÃ o `specs/007-m5-sentiment-live/COMPLETION_NOTE.md`
- [x] T031 [US3] Re-run / paste corrected ambiguous scan list (proposal only) vÃ o completion note â€” config váº«n seed-only
- [x] T032 [US3] Verify scope `git diff --stat --ignore-space-at-eol` â€” khÃ´ng Ä‘á»¥ng file cáº¥m; khÃ´ng commit/push

**Checkpoint**: SC-006/007/008

---

## Phase 6: Polish

- [x] T033 [P] Docstring tiáº¿ng Viá»‡t trong `src/stockai/m5_sentiment/run.py` (anti-pattern Ä‘ / FPT / status)
- [x] T034 [P] Cross-check quickstart.md vs lá»‡nh tháº­t
- [x] T035 Final `python -m pytest -q`; khÃ´ng commit

---

## Dependencies

- Setup â†’ Foundational â†’ US1 testsâ†’impl â†’ US2 â†’ US3 smoke â†’ Polish
- US1 blocks meaningful US2/US3 behaviour tests that need live scoring

## Parallel opportunities

- T002â€“T005 parallel; T009â€“T014 parallel; T021â€“T023 parallel

## Implementation Strategy

1. Setup configs + helpers
2. Fail-first tests confirm red
3. Implement run.py until green
4. Full pytest + smoke 30/60
5. Completion note; no commit
