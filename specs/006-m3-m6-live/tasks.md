# Tasks: M3 + M6 Live on HOSE+HNX Snapshots

**Input**: Design documents from `/specs/006-m3-m6-live/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/m3-m6-live.md, quickstart.md

**Tests**: TDD fail-first **bắt buộc** (spec FR-012 / US3). Mỗi user story: viết test trước → confirm fail trên stub → mới implement.

**Organization**: Tasks theo user story để implement/test độc lập. Phạm vi file: `src/stockai/m3_technical/`, `src/stockai/m6_risk/`, `tests/test_m3_*.py`, `tests/test_m6_*.py`, `config/technical.yaml` (ưu tiên; **không** sửa `config/scoring.yaml` trừ khi chứng minh cần). MUST NOT sửa `m1_data`, `pipeline.py`, `contracts/*`, `docs/CONTRACTS.md`, M7. Q1:B locked: R cao = rủi ro cao; chỉ đảo mapping chấm điểm. Không commit/push.

**Tham chiếu chỉ-đọc**: `D:\Projects\StockAI\src\stockai\m3_technical\run.py`, `D:\Projects\StockAI\src\stockai\m6_risk\run.py`

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- Single project: `src/`, `tests/`, `config/` at repository root

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Khởi tạo cấu hình và khung test offline cho M3/M6; không port logic chưa.

- [x] T001 Confirm feature artifacts sẵn sàng (`specs/006-m3-m6-live/spec.md`, `plan.md`, `research.md`, `data-model.md`, `contracts/m3-m6-live.md`, `quickstart.md`) và ghi phạm vi cấm (không đụng `src/stockai/m1_data/`, `pipeline.py`, `src/stockai/contracts/`, `docs/CONTRACTS.md`, M7) vào ghi chú làm việc local
- [x] T002 [P] Create `config/technical.yaml` với khóa `m3.*` / `m6.*` theo research R6 (min_sessions_ma200=200, stale_calendar_days=7, RSI/MACD/ATR windows, rubric trend/momentum/volume/volatility; `m6.scoring_polarity: high_R_means_high_risk`, `inverted_vs_stockai: true`, `inverted_components`, lookback=252, min_observations=120, safety_coeffs, weights)
- [x] T003 [P] Create shared offline snapshot builders in `tests/helpers_m3_m6_snapshots.py` (đủ ≥200 phiên; thiếu history; future dates; bad OHLC; stale; empty ATP-like; M6 identical stock=index; high-vol/deep-DD vs stable; unadjusted; synthetic)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Pattern đọc cfg + helper test dùng chung — MUST xong trước mọi story

**⚠️ CRITICAL**: Không bắt đầu port M3/M6 cho đến khi phase này xong

- [x] T004 Define cfg merge/default pattern (đọc `config/technical.yaml` khi thiếu khóa trong `cfg`; safe defaults khớp StockAI numeric; gắn `m3_config_defaulted` / `m6_invalid_config_defaulted`) documented in comments of intended loaders inside `src/stockai/m3_technical/run.py` and `src/stockai/m6_risk/run.py` (chưa port chỉ báo — chỉ skeleton load cfg + giữ chữ ký `run(snapshot, upstream, cfg)`)
- [x] T005 Wire pytest imports for helpers: ensure `tests/helpers_m3_m6_snapshots.py` importable from planned `tests/test_m3_technical.py` and `tests/test_m6_risk.py` (PYTHONPATH=src; no network)
- [x] T006 Document Q1:B polarity notes in `config/technical.yaml` (`scoring_polarity`, `inverted_vs_stockai`, list inverted subscores) matching contracts/m3-m6-live.md — MUST NOT edit `config/scoring.yaml` or M7

**Checkpoint**: Foundation ready — có thể viết fail-first tests US1/US2 song song

---

## Phase 3: User Story 1 - M3 chấm điểm kỹ thuật T (Priority: P1) 🎯 MVP

**Goal**: M3 live: lọc `date <= as_of`, loại OHLC lỗi + đếm/cờ, chỉ báo MA/RSI/MACD/volume/ATR, điểm T 0–100 từ cfg; thiếu history → score null; stale >7d → `m3_stale_price_data`; empty không crash.

**Independent Test**: Snapshot dựng tay (đủ/thiếu/OHLC lỗi/lookahead/stale/rỗng) + chạy `run` M3 độc lập; không cần M6.

### Tests for User Story 1 (TDD — viết trước, MUST FAIL trên stub)

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [x] T007 [P] [US1] Add fail-first test enough history (≥200) → numeric score ∈ [0,100], status ok/partial đúng, metrics MA20/50/200 RSI14 MACD(+signal+hist) volume_ratio_20 ATR14 in `tests/test_m3_technical.py`
- [x] T008 [P] [US1] Add fail-first test short history (<200) → `score is None`, flag `m3_insufficient_history_ma200`, `status=partial` in `tests/test_m3_technical.py`
- [x] T009 [P] [US1] Add fail-first test future rows (`date > as_of`) unused in indicators/score in `tests/test_m3_technical.py`
- [x] T010 [P] [US1] Add fail-first test bad OHLC excluded + flag `m3_invalid_price_rows_excluded` + count metric `invalid_price_rows` in `tests/test_m3_technical.py`
- [x] T011 [P] [US1] Add fail-first test stale last session >7 calendar days → flag `m3_stale_price_data` in `tests/test_m3_technical.py`
- [x] T012 [P] [US1] Add fail-first test empty prices (ATP/BCH/MDD-like) → no exception, `score is None`, deficiency flags, `status=partial` in `tests/test_m3_technical.py`
- [x] T013 [US1] Run `python -m pytest -q tests/test_m3_technical.py` and confirm **FAIL** on current stub in `src/stockai/m3_technical/run.py` before any port

### Implementation for User Story 1

- [x] T014 [US1] Port price row filter (`date <= as_of`, OHLC validation per research R4, dedupe date keep last) in `src/stockai/m3_technical/run.py`
- [x] T015 [US1] Port indicators MA20/50/200, RSI14 Wilder (EWM alpha=1/14), MACD(12,26,9)+signal+histogram, volume_ratio_20, ATR14 from StockAI formulas (pandas) in `src/stockai/m3_technical/run.py` — thresholds/windows from cfg/`config/technical.yaml` only
- [x] T016 [US1] Port T rubric scoring (trend≤35 / momentum≤30 / volume≤20 / volatility≤15) reading points from `config/technical.yaml` in `src/stockai/m3_technical/run.py` — MUST NOT hard-code thresholds
- [x] T017 [US1] Implement status/flags/evidence/metrics (`m3_insufficient_history_ma200`, `m3_stale_price_data`, synthetic/unadjusted flags) and `validate(out, "module_out")` before return in `src/stockai/m3_technical/run.py`
- [x] T018 [US1] Re-run `python -m pytest -q tests/test_m3_technical.py` until green for US1 acceptance scenarios

**Checkpoint**: M3 độc lập pass offline; MVP kỹ thuật sẵn sàng demo

---

## Phase 4: User Story 2 - M6 chấm điểm rủi ro R (Priority: P1)

**Goal**: M6 live: căn ngày không forward-fill; đo beta/vol/MDD/VaR95/CVaR95 đúng StockAI; **chỉ đảo mapping** → R cao = rủi ro cao; eligible → `status=ok` + score; polarity-lock.

**Independent Test**: Snapshot dựng tay (chuỗi trùng; thiếu obs; lệch ngày; unadjusted; stale aligned; high-vol vs stable) + polarity-lock; chạy M6 độc lập.

### Tests for User Story 2 (TDD — viết trước, MUST FAIL trên stub)

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [x] T019 [P] [US2] Add fail-first test eligible path → numeric R ∈ [0,100], `status=ok`, metrics beta/vol/MDD/VaR95/CVaR95 in `tests/test_m6_risk.py`
- [x] T020 [P] [US2] Add fail-first test insufficient aligned returns → `score is None`, not_ready/insufficient flags, no fabricated score in `tests/test_m6_risk.py`
- [x] T021 [P] [US2] Add fail-first test date alignment uses intersection only (no forward-fill) in `tests/test_m6_risk.py`
- [x] T022 [P] [US2] Add fail-first test identical stock/index series → beta ≈ 1 (float tolerance) in `tests/test_m6_risk.py`
- [x] T023 [P] [US2] Add fail-first test unadjusted/synthetic → `score is None`, not eligible, status not hard-coded always-partial across cases in `tests/test_m6_risk.py`
- [x] T024 [P] [US2] Add fail-first polarity order test: high-vol/deep-DD fixture R **>** stable fixture same frame in `tests/test_m6_risk.py`
- [x] T025 [P] [US2] Add fail-first polarity-lock test that **fails** if scoring polarity flipped back to “high R = low risk” in `tests/test_m6_risk.py`
- [x] T026 [US2] Run `python -m pytest -q tests/test_m6_risk.py` and confirm **FAIL** on current stub in `src/stockai/m6_risk/run.py` before any port

### Implementation for User Story 2

- [x] T027 [US2] Port price/index clean + aligned return series (intersection, gap = missed index sessions > N drop, no forward-fill; holiday chung không flag) in `src/stockai/m6_risk/run.py`
- [x] T028 [US2] Port risk measures beta, annualized volatility, max drawdown, historical VaR95, CVaR95 **unchanged StockAI formulas** in `src/stockai/m6_risk/run.py`
- [x] T029 [US2] Implement safety subscores with StockAI coeffs then invert each (`risk_sub = 100 - safety_sub`) and weighted R per research R0; document invert in module docstring of `src/stockai/m6_risk/run.py` and keys already in `config/technical.yaml`
- [x] T030 [US2] Implement eligibility (`not synthetic`, `adjusted is True`, beta available, last aligned ≤10 days, `n >= min_observations`) → `status=ok` + numeric score; else `score=null` + flags — MUST NOT hard-code `status=partial` always — in `src/stockai/m6_risk/run.py`
- [x] T031 [US2] Emit metrics/evidence/flags catalog (incl. `m6_not_ready_for_risk_score`, `m6_historical_risk_estimate`, gap/future/duplicate flags) and `validate(out, "module_out")` in `src/stockai/m6_risk/run.py`
- [x] T032 [US2] Re-run `python -m pytest -q tests/test_m6_risk.py` until green including polarity-lock

**Checkpoint**: M6 độc lập pass; cực tính CONTRACTS khóa bằng test

---

## Phase 5: User Story 3 - TDD offline + smoke batch full+limited (Priority: P1)

**Goal**: Chứng minh fail-first đã áp dụng; full pytest xanh; smoke ~235 mã full+limited; báo cáo polarity + phân bố; diff phạm vi đúng.

**Independent Test**: Sau US1+US2 — full suite + smoke bảng phân bố; kiểm tra không đụng file cấm.

### Tests / verification for User Story 3

> **NOTE: Optional real-snapshot tests may skip if `data/snapshots_ext` missing**

- [x] T033 [P] [US3] Add optional 1–2 real-snapshot tests (skip if missing) loading from `data/snapshots_ext` in `tests/test_m3_technical.py` and/or `tests/test_m6_risk.py`
- [x] T034 [US3] Run full project suite `python -m pytest -q` offline; record total passed count for completion report
- [x] T035 [US3] Create batch smoke runner `scripts/smoke_m3_m6_batch.py` (~235 `quality_tier_full`+`quality_tier_limited` on HOSE+HNX snapshots) printing T/R score histograms, counts ok/partial, counts score null — no mass crash
- [x] T036 [US3] Execute smoke runner against available snapshots under `data/snapshots_ext` (or documented equivalent path) and paste distribution table into local completion note under `specs/006-m3-m6-live/`
- [x] T037 [US3] Verify scope with `git diff --stat --ignore-space-at-eol`: only `m3_technical/`, `m6_risk/`, `tests/test_m3_*`/`tests/test_m6_*`/`tests/helpers_m3_m6_snapshots.py`, `config/technical.yaml`, optional `scripts/smoke_m3_m6_batch.py` — no `m1_data`, `pipeline.py`, `contracts`, `docs/CONTRACTS.md`, M7, no `config/scoring.yaml` unless justified
- [x] T038 [US3] Write completion note listing inverted StockAI scoring parts (subscores + weights) and stating M6 matches CONTRACTS (R high = risk high) in `specs/006-m3-m6-live/` (local only; no commit/push)

**Checkpoint**: SC-006 / SC-007 / SC-008 satisfied; sẵn sàng đóng feature khi user yêu cầu

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Đồng bộ docstring/quickstart và vệ sinh cuối

- [x] T039 [P] Align module docstrings in `src/stockai/m3_technical/run.py` and `src/stockai/m6_risk/run.py` with Q1:B / inverted list / status rules (Vietnamese comments)
- [x] T040 [P] Cross-check `specs/006-m3-m6-live/quickstart.md` expected checklist against actual commands/paths after implement
- [x] T041 Confirm no network calls in tests; all fixtures use `tests/helpers_m3_m6_snapshots.py` or skip-if-missing pattern
- [x] T042 Final `python -m pytest -q` green and note count; do **not** commit/push unless user explicitly asks

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Setup — **BLOCKS** all user stories
- **User Story 1 (Phase 3)**: After Foundational — tests T007–T013 before implement T014–T018
- **User Story 2 (Phase 4)**: After Foundational — independent of US1 code; tests T019–T026 before implement T027–T032
- **User Story 3 (Phase 5)**: After US1 + US2 implementation green; smoke/full pytest need both modules live
- **Polish (Phase 6)**: After desired stories complete

### User Story Dependencies

- **US1 (P1)**: Independent after Foundational — MVP
- **US2 (P1)**: Independent after Foundational — can parallel US1 if staffed
- **US3 (P1)**: Depends on US1 + US2 for green suite + smoke; optional real-snapshot tests can be drafted earlier but assert live behavior after port

### Within Each User Story

- Tests MUST be written and FAIL on stub before implementation
- Filter/align before indicators/measures
- Measures before scoring/invert
- Scoring before status/flags/validate
- Story tests green before moving on

### Parallel Opportunities

- T002 ∥ T003 (Setup)
- T007–T012 all [P] (US1 tests)
- T019–T025 all [P] (US2 tests)
- After Foundational: Developer A = US1, Developer B = US2
- T033 ∥ draft of T035 script structure (before smoke run)
- T039 ∥ T040 (Polish)

---

## Parallel Example: User Story 1

```bash
# Launch all US1 fail-first tests together:
Task: "Add fail-first test enough history in tests/test_m3_technical.py"
Task: "Add fail-first test short history in tests/test_m3_technical.py"
Task: "Add fail-first test future rows unused in tests/test_m3_technical.py"
Task: "Add fail-first test bad OHLC excluded in tests/test_m3_technical.py"
Task: "Add fail-first test stale flag in tests/test_m3_technical.py"
Task: "Add fail-first test empty prices in tests/test_m3_technical.py"
```

## Parallel Example: User Story 2

```bash
# Launch all US2 fail-first tests together:
Task: "Add fail-first eligible path in tests/test_m6_risk.py"
Task: "Add fail-first insufficient aligned in tests/test_m6_risk.py"
Task: "Add fail-first no forward-fill in tests/test_m6_risk.py"
Task: "Add fail-first beta≈1 in tests/test_m6_risk.py"
Task: "Add fail-first unadjusted/synthetic in tests/test_m6_risk.py"
Task: "Add fail-first polarity order in tests/test_m6_risk.py"
Task: "Add fail-first polarity-lock in tests/test_m6_risk.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational
3. Complete Phase 3: US1 (tests red → M3 port → green)
4. **STOP and VALIDATE**: M3 independent offline
5. Demo điểm T trên snapshot tay / 1 mã thật nếu có

### Incremental Delivery

1. Setup + Foundational → foundation ready
2. US1 → M3 live (MVP)
3. US2 → M6 live + polarity-lock
4. US3 → full pytest + smoke 235 + completion note (local)
5. Polish → docstring/quickstart sync

### Parallel Team Strategy

1. Team completes Setup + Foundational together
2. After Foundational:
   - Dev A: US1 (M3)
   - Dev B: US2 (M6)
3. Together: US3 smoke + scope audit + completion note

---

## Notes

- [P] = different files / no incomplete-task dependency
- [USx] maps to spec user stories
- Prefer `config/technical.yaml` over `config/scoring.yaml` (research R6 / OWNERSHIP N4)
- Q1:B: invert scoring mapping only; polarity-lock MUST stay
- Không commit / push / Co-authored-by trong giai đoạn này
- Constitution file (`.specify/memory/constitution.md`) không có trong repo — áp dụng gates đã ghi trong plan.md
