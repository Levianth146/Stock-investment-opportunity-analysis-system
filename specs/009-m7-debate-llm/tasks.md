---
description: "Task list for Feature 009 — M7 Debate (Bull/Bear) qua LLM"
---

# Tasks: M7 Debate (Bull/Bear) qua LLM

**Input**: Design documents from `/specs/009-m7-debate-llm/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/m7-debate-llm.md, quickstart.md

**Tests**: BẮT BUỘC — spec FR-012 / US4 yêu cầu pytest offline mock `requests` (validator, regex refs, retry, fallback, cache, flags, M8 `debate_ungrounded`). Smoke provider + batch ≥10 ticker = **optional/manual** khi có khóa (không bắt buộc CI).

**Organization**: Tasks theo user story để implement/test độc lập. Clarifications khóa: **Q1:B** (không `schemas.py`; 1 dòng `CONTRACTS.md`), **Q2:B** (refs phẳng + regex), **Q3:A** (`requests` REST only).

**MUST NOT touch**: `src/stockai/m7_scoring/scoring.py`, `config/scoring.yaml`, M1–M6 bodies, `pipeline.py`, `main.py`, `src/stockai/contracts/schemas.py`, thêm SDK vào `requirements.txt`.

**Touch allowed**: `debate.py` (+ helpers), `src/stockai/llm/`, `config/llm.yaml`, `scripts/run_debate_batch.py`, tests M7/llm/M8, M8 warn, 1 dòng `docs/CONTRACTS.md`, `.gitignore` cho `data/llm_cache/`.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g. US1, US2, US3, US4)
- Include exact file paths in descriptions

## Path Conventions

- Single project: `src/`, `tests/`, `config/`, `scripts/` at repository root

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Khởi tạo cấu trúc package/config/gitignore theo plan — chưa gọi LLM

- [X] T001 Create package skeleton `src/stockai/llm/__init__.py` and `src/stockai/llm/providers/__init__.py` (empty exports ready for generate/cache/providers)
- [X] T002 [P] Add `data/llm_cache/` (or `data/llm_cache/**`) to `.gitignore` so disk cache is never committed
- [X] T003 [P] Extend `config/llm.yaml` with debate section: `debate.providers` order `[gemini, glm]`, `debate.gemini.model: gemini-3.8-flash`, `debate.glm.model: glm-5.3-flash`, `debate.glm.base_url: https://api.z.ai/api/paas/v4/`, `debate.temperature: 0`, `debate.max_llm_attempts: 3`, `debate.timeout_sec`, `debate.cache_dir: data/llm_cache`, `debate.prompt_version`, and document env key *names only* (`GEMINI_API_KEY`, `ZAI_API_KEY`) — never store secret values

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Shared refs convention + payload foundations mọi story phụ thuộc

**⚠️ CRITICAL**: No user story implementation until this phase is complete

- [X] T004 Implement refs classify helpers in `src/stockai/m7_scoring/debate_validate.py`: metric regex `^m[0-9]+\.[A-Za-z0-9_]+$`, news regex `^n[0-9]+$`; functions return kind `metric` | `news` | `invalid` (Q2:B)
- [X] T005 [P] Implement resolve helpers in `src/stockai/m7_scoring/debate_validate.py`: resolve metric against `metrics_allowed` / `upstream[mN].metrics`; resolve news via `news_ref_map[nK]` → real `snapshot.news[].id`; unmatched regex or unresolved → ungrounded
- [X] T006 [P] Implement compact `DebatePayload` builder in `src/stockai/llm/payload.py`: ticker/as_of/profile/score/rating/scores; `metrics` map `mN.name` → `{value, unit?}`; `metrics_allowed: string[]`; `news` as `{ref: "nK", id, title, summary?}` with stable 1-based `nK` + `news_ref_map`; `evidence_summaries` short only; `prompt_version`; **MUST NOT** include full `prices.rows`
- [X] T007 Add length/text/`refs` non-empty validators (scored path: each side **2–4** items; each item `text` non-empty + `refs: string[]` non-empty + all grounded) in `src/stockai/m7_scoring/debate_validate.py`

**Checkpoint**: Foundation ready — US2/US1/US4/US3 can proceed

---

## Phase 3: User Story 2 — Provider LLM thống nhất qua `requests` + env secrets (Priority: P1)

**Goal**: `generate_json(...) -> dict`; Gemini + GLM REST via `requests` only; disk cache; missing key → skip + flags; no secrets printed; no new SDK in `requirements.txt`

**Independent Test**: Mock `requests`; missing env → fallback path + flags; cache hit → 0 HTTP; request body has no full OHLCV

### Tests for User Story 2 (REQUIRED — write FAIL first)

- [X] T008 [P] [US2] Offline unit tests for missing `GEMINI_API_KEY` / `ZAI_API_KEY` → skip provider + flags `llm_missing_key_gemini` / `llm_missing_key_glm` (no secret in logs) in `tests/test_llm_generate.py`
- [X] T009 [P] [US2] Offline unit tests for disk cache hit → second `generate_json` / debate call makes **0** HTTP (`requests` patched) in `tests/test_llm_cache.py`
- [X] T010 [P] [US2] Offline unit tests asserting compact payload / request body does **not** contain full `prices.rows` in `tests/test_llm_payload.py`

### Implementation for User Story 2

- [X] T011 [P] [US2] Implement Gemini REST client in `src/stockai/llm/providers/gemini_rest.py`: `POST https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent` via `requests`; auth header `x-goog-api-key` from `GEMINI_API_KEY`; JSON/structured output; default model `gemini-3.8-flash` (Q3:A)
- [X] T012 [P] [US2] Implement GLM REST client in `src/stockai/llm/providers/glm_rest.py`: `POST {base_url}/chat/completions` via `requests`; auth from `ZAI_API_KEY`; `response_format: {"type":"json_object"}`; default model `glm-5.3-flash`; base `https://api.z.ai/api/paas/v4/` (Q3:A — no OpenAI SDK)
- [X] T013 [US2] Implement disk cache read/write/corrupt-skip in `src/stockai/llm/cache.py`: path under `data/llm_cache/<hash>.json`; key hash(ticker, as_of, model, prompt_version, payload_hash); corrupt → ignore + flag `debate_cache_ignored`
- [X] T014 [US2] Implement unified `generate_json(...)` in `src/stockai/llm/generate.py`: load `config/llm.yaml` provider order; try providers with timeout; parse JSON; limited retry on 429/timeout; never print API keys; return parsed `dict` (depends on T011–T013)
- [X] T015 [US2] Export public façade from `src/stockai/llm/__init__.py` (`generate_json`, payload helpers as needed) without adding packages to `requirements.txt`

**Checkpoint**: Provider layer usable offline with mocks; live keys not required for CI

---

## Phase 4: User Story 1 — Thay stub debate bằng Bull/Bear grounded (Priority: P1) 🎯 MVP

**Goal**: Replace stub `run_debate` with LLM→validate→retry≤3→deterministic template fallback; keep signature `run_debate(snapshot, upstream, cfg) -> (bull, bear)`; quality_gate unscored skips LLM; scoring untouched

**Independent Test**: Mock provider JSON valid / bad / bad refs; assert 2–4 items, `text`+`refs`; retry then template + `debate_fallback_template`; `quality_gate.scored == false` → no LLM; score/rating unchanged

### Tests for User Story 1 (REQUIRED — write FAIL first)

- [X] T016 [P] [US1] Offline tests happy-path mock LLM → 2–4 bull/bear, each `text` + flat grounded `refs` (`mN.name` / `nK`), and `validate(result, "result")` passes in `tests/test_m7_debate.py`
- [X] T017 [P] [US1] Offline tests bad JSON / invented numbers / invalid refs → reject → retry → template fallback + flag `debate_fallback_template` (non-empty debate, no crash) in `tests/test_m7_debate_fallback.py`
- [X] T018 [P] [US1] Offline tests `quality_gate.scored == false` path: existing quality_gate bull/bear; **no** LLM/`generate_json` call in `tests/test_m7_debate_quality_gate.py`
- [X] T019 [P] [US1] Offline regression: same upstream fixture → M7 `score`/`rating` unchanged vs baseline (debate-only change; do not edit `scoring.py`) in `tests/test_m7_debate_scoring_unchanged.py`

### Implementation for User Story 1

- [X] T020 [P] [US1] Implement deterministic template fallback in `src/stockai/m7_scoring/debate_template.py`: same snapshot+upstream+cfg → same `text`; prefer valid grounded `refs` from metrics/news; attach flags `debate_fallback_template` and/or `debate_llm_unavailable` as applicable
- [X] T021 [US1] Implement prompt builder (Vietnamese; bans: invented numbers, LLM target price, fake refs outside allow-list) inside `src/stockai/m7_scoring/debate.py` or helper module under `src/stockai/m7_scoring/`
- [X] T022 [US1] Replace stub orchestration in `src/stockai/m7_scoring/debate.py`: build payload → cache lookup → `generate_json` (provider order) → `debate_validate` → retry ≤ `max_llm_attempts` (default 3) → template fallback → write cache; keep signature compatible with `src/stockai/m7_scoring/run.py` (do **not** change `run.py` scoring flow beyond existing `run_debate` call)
- [X] T023 [US1] Ensure scored-path outputs always attach `refs: string[]` on each bull/bear item and surface M7 flags (`debate_fallback_template`, `debate_llm_unavailable`, `debate_cache_hit` optional, `debate_cache_ignored`, `llm_missing_key_*`) via result flags wiring already used by M7 run — without modifying `scoring.py` / `scoring.yaml`

**Checkpoint**: US1 MVP — grounded debate or deterministic fallback offline; scoring identical

---

## Phase 5: User Story 4 — Kiểm thử offline với mock (Priority: P1)

**Goal**: Full offline suite for feature 009: mock `requests` only; no network; no dependency on real API keys; fail-first then green; regex classify + resolve covered

**Independent Test**: `python -m pytest -q` green offline; suite never needs live keys

### Tests for User Story 4 (REQUIRED)

- [X] T024 [P] [US4] Unit tests regex classify cases `m4.pe`, `n12` valid; `bad`, `m4`, `nX` invalid in `tests/test_m7_debate_refs.py` (FR-012 / SC-005)
- [X] T025 [P] [US4] Unit tests resolve fail when metric/news id not in allow-list / map → ungrounded in `tests/test_m7_debate_refs.py`
- [X] T026 [P] [US4] Integration-style offline tests patching `requests` for Gemini+GLM response shapes (success + parse error + 429) in `tests/test_llm_providers_mock.py`
- [X] T027 [US4] Confirm fail-first then green: run targeted pytest from `specs/009-m7-debate-llm/quickstart.md` section 1–2 (`tests/test_m7_debate*.py`, `tests/test_llm_*.py`) until all pass offline without env keys

**Checkpoint**: Offline CI path for debate/llm is complete and reproducible

---

## Phase 6: User Story 3 — M8 `debate_ungrounded` + batch script (Priority: P2)

**Goal**: M8 `warn` with message containing `debate_ungrounded` (regex + resolve); batch script reports ok/fallback/cache; smoke live = optional/manual only

**Independent Test**: Ungrounded fixture → M8 warn; grounded → no that warn; severity not formula-fatal; batch script dry-runnable offline

### Tests for User Story 3 (REQUIRED — write FAIL first)

- [X] T028 [P] [US3] Extend `tests/test_m8_run.py` (or `tests/test_m8_debate_ungrounded.py`): ungrounded bull/bear (missing refs / bad regex / unresolved) → issue `severity: "warn"` and message contains `debate_ungrounded`; `where` like `m7.bull[0]`
- [X] T029 [P] [US3] Extend M8 tests: fully grounded fixture → **no** `debate_ungrounded`; quality_gate unscored branch does **not** require refs warn as fatal
- [X] T030 [P] [US3] Offline smoke of `scripts/run_debate_batch.py` with mocked debate/provider (or fixture snapshots) — assert no batch-wide crash and prints counts llm_ok/fallback/cache_hit/error (no live network in pytest)

### Implementation for User Story 3

- [X] T031 [US3] Add `_check_debate_grounding` (or equivalent) in `src/stockai/m8_validate/run.py`: walk `upstream["m7"].bull`/`bear`; reuse same regex+resolve rules as `debate_validate`; emit warn `debate_ungrounded`; **MUST NOT** change M7 score/rating/target formula fatals; skip/relax refs when `quality_gate.scored == false`
- [X] T032 [US3] Implement `scripts/run_debate_batch.py` CLI: `--as-of YYYY-MM-DD`, `--snapshots-dir`, `--tickers` / `--limit 10`, `--config config/llm.yaml`; per-ticker try/except (no whole-batch crash); print llm_ok / fallback / cache_hit / error
- [X] T033 [P] [US3] **OPTIONAL / MANUAL (ops, not CI)**: When `GEMINI_API_KEY` / `ZAI_API_KEY` present, smoke 1× `generate_json` per provider and run batch ≥10 tickers per `specs/009-m7-debate-llm/quickstart.md` sections 4–5 (SC-006/SC-007) — record outcome; do **not** require live network for CI tasks

**Checkpoint**: M8 grounding warn + batch script ready; live smoke left as optional ops

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Docs contract line + final offline verification

- [X] T034 Add **exactly one line** (or one bullet) to `docs/CONTRACTS.md` (M7 section) describing debate item `text` + `refs` string array convention `mN.name` / `nK` (Q1:B / FR-016 / SC-009) — **do not** edit `src/stockai/contracts/schemas.py`
- [X] T035 [P] Verify `git diff -- src/stockai/contracts/schemas.py` is empty for this feature; confirm `requirements.txt` has no new Gemini/GLM SDK
- [X] T036 Run full offline suite `python -m pytest -q` (with `PYTHONPATH=src`) and confirm green without live API keys
- [X] T037 [P] **OPTIONAL / MANUAL**: Walk `specs/009-m7-debate-llm/quickstart.md` sections 3–6 when keys/snapshots available — not a CI gate

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Setup — **BLOCKS** all user stories
- **US2 (Phase 3)**: After Foundational — provider/cache needed by US1 orchestration
- **US1 (Phase 4)**: After Foundational; ideally after US2 `generate_json` (or mock `generate_json` for parallel US1 tests)
- **US4 (Phase 5)**: After Foundational; expands/locks offline tests (can parallelize test writing with US1/US2 impl)
- **US3 (Phase 6)**: After US1 debate item shape + shared refs helpers; M8 + batch
- **Polish (Phase 7)**: After desired stories complete

### User Story Dependencies

- **User Story 2 (P1)**: After Phase 2 — no dependency on US1/US3
- **User Story 1 (P1) MVP**: After Phase 2; uses US2 `generate_json` (or test doubles)
- **User Story 4 (P1)**: Cross-cutting offline tests — starts after Phase 2; completes after US1/US2 code exists
- **User Story 3 (P2)**: After US1 item contract + Phase 2 refs helpers; batch may call US1/US2

### Within Each User Story

- Tests (REQUIRED) written and FAIL before implementation
- Shared validate/payload before providers/debate orchestration
- Providers/cache before `generate_json`
- Template + validate before replacing stub `debate.py`
- M8 warn after debate shape stable
- Story complete before raising priority next (or parallel if staffed)

### Parallel Opportunities

- T002 ∥ T003 (Setup)
- T005 ∥ T006 (Foundational, different files)
- T008 ∥ T009 ∥ T010 (US2 tests)
- T011 ∥ T012 (Gemini vs GLM clients)
- T016 ∥ T017 ∥ T018 ∥ T019 (US1 tests)
- T024 ∥ T025 ∥ T026 (US4 tests)
- T028 ∥ T029 ∥ T030 (US3 tests)
- After Phase 2: Developer A = US2, Developer B = US1 tests/template, Developer C = US4 regex tests
- T033 / T037 optional manual — never block CI

---

## Parallel Example: User Story 2

```bash
# Tests in parallel:
Task: "Offline unit tests missing keys in tests/test_llm_generate.py"
Task: "Offline unit tests cache hit in tests/test_llm_cache.py"
Task: "Offline unit tests no prices.rows in tests/test_llm_payload.py"

# Providers in parallel:
Task: "Implement Gemini REST in src/stockai/llm/providers/gemini_rest.py"
Task: "Implement GLM REST in src/stockai/llm/providers/glm_rest.py"
```

## Parallel Example: User Story 1

```bash
Task: "Happy-path debate tests in tests/test_m7_debate.py"
Task: "Fallback/retry tests in tests/test_m7_debate_fallback.py"
Task: "Quality-gate no-LLM tests in tests/test_m7_debate_quality_gate.py"
Task: "Scoring unchanged regression in tests/test_m7_debate_scoring_unchanged.py"
```

## Parallel Example: User Story 3

```bash
Task: "M8 ungrounded fixture tests"
Task: "M8 grounded fixture tests"
Task: "Batch script offline mock test"
```

---

## Implementation Strategy

### MVP First (User Story 1 + supporting US2)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL)
3. Complete Phase 3: US2 providers/cache/`generate_json` (or minimal mockable façade)
4. Complete Phase 4: US1 `run_debate` + validate + fallback
5. **STOP and VALIDATE**: Offline pytest for debate — 2–4 grounded items or template; scoring unchanged
6. Then US4 lock full offline suite → US3 M8/batch → Polish CONTRACTS line

### Incremental Delivery

1. Setup + Foundational → shared refs/payload ready
2. US2 → providers offline-testable
3. US1 → MVP debate value
4. US4 → CI offline green for feature
5. US3 → grounding warn + batch ops
6. Polish → one CONTRACTS line; optional live smoke

### Parallel Team Strategy

1. Team finishes Setup + Foundational together
2. Then: A → US2 providers; B → US1 debate/template; C → US4 regex/M8 test fixtures
3. Integrate; then US3 M8 + batch

---

## Notes

- [P] = different files, no incomplete-task dependencies
- [USn] maps to spec user stories for traceability
- Live network is **never** required for CI tasks; T033/T037 are optional/manual when keys exist
- Do not commit `data/llm_cache/`, `.env`, or API key values
- Commit only when user requests; do not push from tasks generation
- Avoid editing forbidden files listed at top of this document

## Round-1 fix notes (2026-10-13)

- Batch: bỏ `_upstream_stub`; upstream M2–M6 thật qua `pipeline._safe`; mặc định `data/snapshots_ext`
- Template: `module_polarity` d_k; không in raw `mN.name` / số dài; KOS Bull không cite `net_income_growth`
- Payload: news từ `m5.evidence` (max 6, pos/neg); `evidence_summaries` ≤2/module; `module_polarity`
- Validate: polarity sign + số khớp payload; generate: retry 429/5xx backoff + model/provider failover
- Pricing cập nhật trong `config/llm.yaml` (Gemini Flash tăng giá 01/01/2027)
