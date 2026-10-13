# Tasks: M4 Relative Valuation (điểm V)

**Input**: Design documents from `/specs/008-m4-relative-valuation/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/m4-relative-valuation.md, quickstart.md

**Tests**: TDD fail-first **bắt buộc** (spec FR-012 / US3 + user request). Mỗi user story: viết test trước → confirm FAIL trên stub → mới implement.

**Organization**: Tasks theo user story để implement/test độc lập. Phạm vi file: `src/stockai/m4_valuation/`, `tests/test_m4_*.py`, `config/valuation.yaml`, `scripts/build_m4_sector_stats.py`, `data/valuation_sector_stats.json` (generated), optional `scripts/smoke_m4_batch.py`. MUST NOT sửa `m1_data/*`, `contracts/*`, `pipeline.py`, `main.py`, M3/M5/M6, M7, `docs/CONTRACTS.md`. Khóa research: PE/PB, TTM đúng 4Q else annual+`m4_eps_ttm_fallback_annual`, winsorize rồi median, bank P/B primary, sector stats JSON cache (không median từ peers), `score=null` MUST NOT ép 50, evidence tiếng Việt. Không commit/push.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- Single project: `src/`, `tests/`, `config/`, `scripts/`, `data/` at repository root

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Khởi tạo khung package M4 + helper test offline; chưa chấm điểm live.

- [x] T001 Confirm feature artifacts sẵn sàng (`specs/008-m4-relative-valuation/spec.md`, `plan.md`, `research.md`, `data-model.md`, `contracts/m4-relative-valuation.md`, `quickstart.md`) và ghi phạm vi cấm (không đụng `src/stockai/m1_data/`, `src/stockai/contracts/`, `pipeline.py`, `main.py`, `src/stockai/m3_technical/`, `src/stockai/m5_sentiment/`, `src/stockai/m6_risk/`, M7; không commit/push) vào ghi chú làm việc local
- [x] T002 [P] Create package layout under `src/stockai/m4_valuation/` (`__init__.py` nếu thiếu; giữ `run.py` stub; thêm module helpers trống `multiples.py`, `config_loader.py`, `sector_stats.py` — chỉ skeleton importable, chưa logic chấm)
- [x] T003 [P] Create shared offline snapshot builders in `tests/helpers_m4_snapshots.py` (non-bank đủ PE/PB cùng sector rẻ vs đắt; bank `is_bank=true` thiếu PE nhưng đủ PB; thiếu giá/shares/equity; EPS quý tổng 0 + annual >0 như SSI-like; lookahead `date`/`published_at` > as_of; stale >7 ngày; `meta.synthetic=true`; thiếu `company.sector` / sector không có trong stats)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Config valuation + shared PE/PB helpers + script build sector stats — MUST xong trước mọi story chấm điểm

**⚠️ CRITICAL**: Không bắt đầu implement live `run.py` scoring cho đến khi phase này xong (được phép skeleton load cfg)

- [x] T004 Create `config/valuation.yaml` với khóa `m4.*` theo research R9 (`sector_stats_path`, `stale_calendar_days: 7`, `winsor.low_pct/high_pct: 0.05/0.95`, `min_sector_n: 5`, `weights.bank` pe=0.0 pb=1.0, `weights.non_bank` pe=0.5 pb=0.5, `cheapness_map.r_low/r_high`, `target_bands.bull_mult/bear_mult`, `enable_dcf: false`) — comment sở hữu N3; không hard-code ngưỡng nghiệp vụ chỉ trong Python
- [x] T005 Implement cfg merge/default loader in `src/stockai/m4_valuation/config_loader.py` (đọc `config/valuation.yaml`; overlay `cfg.m4`; thiếu file/khóa → safe defaults + flag token `m4_config_defaulted`; pattern giống M3 nhưng **không** sửa `src/stockai/m3_technical/`)
- [x] T006 Implement shared relative-multiple inputs in `src/stockai/m4_valuation/multiples.py` theo research R0/R1: price close cuối `date<=as_of` close>0; EPS TTM = sum đúng 4 quý `published_at<=as_of` chỉ khi `len==4` và sum≠0 else EPS năm mới nhất ≤as_of + nguồn `ttm_4q`|`annual`; equity quý ưu tiên rồi năm; book_ps = equity/shares; PE/PB khi mẫu số >0; bỏ lookahead; đơn vị VND thô không scale thêm
- [x] T007 Implement sector-stats IO + winsorize-then-median helpers in `src/stockai/m4_valuation/sector_stats.py` (load JSON R4 schema; lookup theo `company.sector`; `min_sector_n`; winsor low/high pct trên mẫu PE/PB trong sector rồi median — dùng chung cho build script và runtime)
- [x] T008 Implement `scripts/build_m4_sector_stats.py` CLI (`--as-of`, `--snapshots-dir`, `--out`, `--config`) lọc universe `quality_tier_full`|`quality_tier_limited`, gọi helpers T006/T007, ghi `data/valuation_sector_stats.json` (version, as_of, built_at, universe, winsor, min_sector_n, sectors.{n_pe,n_pb,median_pe,median_pb,flags}); offline; idempotent cùng input
- [x] T009 [P] Add tiny offline sector-stats fixture JSON under `tests/fixtures/m4_sector_stats_mini.json` (ít nhất Banks + Technology + một sector generic) để unit test không phụ thuộc `data/snapshots_ext`
- [x] T010 Wire stub `src/stockai/m4_valuation/run.py` chỉ load cfg qua `config_loader` (vẫn `status=stub` / `stub_out`) để test import path ổn; **chưa** chấm V

**Checkpoint**: Foundation ready — có config, helpers PE/PB, build script, fixture stats; có thể viết fail-first tests US1/US2

---

## Phase 3: User Story 1 - Chấm điểm V bằng định giá tương đối PE/PB so ngành (Priority: P1) 🎯 MVP

**Goal**: `run(snapshot, upstream, cfg)` tính PE/PB (TTM/annual, as_of-safe), so median ngành từ JSON, chấm V cao = rẻ; bank P/B primary; thiếu blocker → `score=null` (không 50); stale/lookahead flags.

**Independent Test**: Snapshot dựng tay (rẻ vs đắt cùng ngành; bank; thiếu EPS; thiếu equity; giá sau as_of bị loại) + chạy M4 độc lập với `tests/fixtures/m4_sector_stats_mini.json`; không cần M3/M5/M6.

### Tests for User Story 1 (TDD — viết trước, MUST FAIL trên stub)

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [x] T011 [P] [US1] Add fail-first polarity test: cùng sector, fixture rẻ (multiple thấp) → `score` **>** fixture đắt trong `tests/test_m4_valuation.py`
- [x] T012 [P] [US1] Add fail-first bank test: `is_bank=true` đủ PB dù PE unavailable → numeric V ∈ [0,100] + flag `m4_bank_primary_pb` trong `tests/test_m4_valuation.py`
- [x] T013 [P] [US1] Add fail-first null test: thiếu giá hoặc thiếu mọi chân định giá → `score is None`, flags thiếu dữ liệu (`m4_insufficient_for_score` hoặc tương đương), **MUST NOT** `score == 50` trong `tests/test_m4_valuation.py`
- [x] T014 [P] [US1] Add fail-first as_of/lookahead test: rows `date`/`published_at` > as_of không vào PE/PB/điểm; MAY flag `m4_lookahead_rows_excluded` trong `tests/test_m4_valuation.py`
- [x] T015 [P] [US1] Add fail-first stale test: phiên giá cuối > `stale_calendar_days` (default 7) → flag `m4_stale_price_data` và vẫn chấm nếu đủ multiple (default) trong `tests/test_m4_valuation.py`
- [x] T016 [P] [US1] Add fail-first EPS fallback test: 4 quý sum=0 (hoặc thiếu 4Q) + annual >0 → dùng annual + `m4_eps_ttm_fallback_annual`; không crash; không PE vô hạn trong `tests/test_m4_valuation.py`
- [x] T017 [US1] Run `python -m pytest -q tests/test_m4_valuation.py` and confirm **FAIL** on current stub in `src/stockai/m4_valuation/run.py` before live scoring

### Implementation for User Story 1

- [x] T018 [US1] Implement live path in `src/stockai/m4_valuation/run.py`: parse `meta.as_of`; load cfg + sector stats path (override bằng fixture path trong test via `cfg.m4`); derive multiples qua `multiples.py`; resolve sector medians; gắn flags thiếu giá/shares/equity/PE/PB
- [x] T019 [US1] Implement cheapness scoring in `src/stockai/m4_valuation/run.py` (hoặc helper cùng package): `r = multiple/median`; map qua `cheapness_map` từ yaml → điểm chân 0–100 (cao = rẻ); blend weights bank/non-bank với renormalize khi thiếu một chân; `V = round(weighted, 2)`
- [x] T020 [US1] Emit `metrics` tối thiểu (`pe`, `pb`, `eps_used`, `book_per_share`, `price_close`, `sector_median_pe`/`pb`, `v_pe_leg`/`v_pb_leg`) dạng `{value, unit[, note]}`; set `status` ok|partial; `validate(out, "module_out")`; synthetic → `m4_synthetic_data` trong `src/stockai/m4_valuation/run.py`
- [x] T021 [US1] Re-run `python -m pytest -q tests/test_m4_valuation.py` until US1 scenarios green (polarity, bank, null≠50, as_of, stale, EPS fallback)

**Checkpoint**: MVP điểm V relative chạy offline trên fixture; sẵn sàng demo US1

---

## Phase 4: User Story 2 - Sector stats, target relative, DCF tắt, evidence VI (Priority: P1)

**Goal**: Metrics lộ median/version thống kê ngành; thiếu sector/min_n → không bịa median; `target` từ relative multiples; `enable_dcf: false` không nhánh DCF; evidence tiếng Việt không bắt buộc `news_id`.

**Independent Test**: Mini sector stats + fixture thiếu sector; assert `target.method` relative; DCF off; evidence `text` tiếng Việt.

### Tests for User Story 2 (TDD — viết trước, MUST FAIL trước khi hoàn thiện target/evidence)

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation of this story’s behavior**

- [x] T022 [P] [US2] Add fail-first test metrics expose sector median + stats version/n (`sector_stats_version` / `sector_n_pe` / `sector_n_pb` hoặc note tương đương) khi JSON hợp lệ trong `tests/test_m4_valuation.py`
- [x] T023 [P] [US2] Add fail-first test missing sector / `n < min_sector_n` / thiếu file stats → không bịa median; `score is None` hoặc chỉ chân còn median hợp lệ + flags `m4_sector_stats_missing` / `m4_sector_median_unavailable` trong `tests/test_m4_valuation.py`
- [x] T024 [P] [US2] Add fail-first test `target` ≠ null khi suy được implied price: keys `base`/`bull`/`bear`/`method`/`assumptions`; `method` phản ánh relative (không DCF) trong `tests/test_m4_valuation.py`
- [x] T025 [P] [US2] Add fail-first test `enable_dcf: false` (default) → không metrics/method DCF trong `tests/test_m4_valuation.py`
- [x] T026 [P] [US2] Add fail-first test mọi `evidence[*].text` là tiếng Việt; `news_id` không bắt buộc trong `tests/test_m4_valuation.py`
- [x] T027 [P] [US2] Add fail-first unit/ops test cho build script: chạy `scripts/build_m4_sector_stats.py` trên temp snapshots nhỏ → JSON có winsor+median theo sector trong `tests/test_m4_sector_stats_build.py`
- [x] T028 [US2] Run `python -m pytest -q tests/test_m4_valuation.py tests/test_m4_sector_stats_build.py` and confirm new US2 assertions **FAIL** (or red on missing target/evidence) before implementing US2 pieces

### Implementation for User Story 2

- [x] T029 [US2] Complete sector-stats runtime wiring in `src/stockai/m4_valuation/run.py` / `sector_stats.py`: expose medians + version/n in metrics; enforce `min_sector_n`; peers chỉ optional note — MUST NOT thay median ngành
- [x] T030 [US2] Implement relative `target` in `src/stockai/m4_valuation/run.py`: `implied_pe = median_pe * eps_used`, `implied_pb = median_pb * book_ps`; blend `base` theo weights đang dùng; `bull`/`bear` từ `target_bands`; `method` = relative string; `assumptions` mô tả median/winsor/EPS nguồn/weights; thiếu implied → `target=null`
- [x] T031 [US2] Implement Vietnamese evidence strings (PE/PB vs ngành, bank PB primary, fallback EPS, stale) without required `news_id`; honor `enable_dcf: false` (no DCF branch) in `src/stockai/m4_valuation/run.py`
- [x] T032 [US2] Re-run `python -m pytest -q tests/test_m4_valuation.py tests/test_m4_sector_stats_build.py` until US2 green

**Checkpoint**: Target + evidence + sector-stats contract đủ; DCF off khóa bằng test

---

## Phase 5: User Story 3 - TDD offline, 5 mã thật, smoke ~235, pytest xanh (Priority: P1)

**Goal**: Chứng minh fail-first; 5 mã VCB/FPT/HPG/VIC/SSI; full pytest xanh; smoke full+limited ~235 với bảng phân bố; diff phạm vi đúng; không commit/push.

**Independent Test**: Sau US1+US2 — real-5 (skip nếu thiếu file) + full suite + smoke phân bố; review diff không đụng file cấm.

### Tests / verification for User Story 3 (TDD / ops — viết hoặc chạy trước khi đóng feature)

> **NOTE: Real snapshot tests MAY skip if `data/snapshots_ext` missing**

- [x] T033 [P] [US3] Add conditional real-5 test VCB/FPT/HPG/VIC/SSI (as_of 2026-10-08 nếu có) → no exception; VCB bank PB path; metrics có PE và/hoặc PB khi dữ liệu cho phép; skip nếu thiếu file trong `tests/test_m4_real_snapshots.py`
- [x] T034 [US3] Create optional `scripts/smoke_m4_batch.py`: lọc `quality_tier_full`|`limited` cùng as_of; gọi M4; in histogram score V, đếm ok/partial/null, đếm bank dùng PB; không mạng
- [x] T035 [US3] Build local sector stats for smoke: `python scripts/build_m4_sector_stats.py --as-of 2026-10-08 --snapshots-dir data/snapshots_ext --out data/valuation_sector_stats.json` (ops; skip nếu thiếu snapshots_ext) và xác nhận sectors đủ cho 5 mã mẫu
- [x] T036 [US3] Run `python -m pytest -q` (full project, PYTHONPATH=src) và xác nhận **green**; ghi số test vào báo cáo hoàn thành
- [x] T037 [US3] Run smoke ~235 via `python scripts/smoke_m4_batch.py` (khi có snapshots + sector stats); dán bảng phân bố V / ok / partial / null vào báo cáo hoàn thành (SC-007)
- [x] T038 [US3] Diff scope check: `git diff --stat --ignore-space-at-eol` chỉ trong phạm vi M4/tests/config valuation/scripts build+smoke/data artifact; **không** sửa M1/contracts/M3/M5/M6/pipeline/main; **không** commit/push

**Checkpoint**: Feature sẵn sàng audit; TDD + offline + smoke chứng minh

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Hoàn thiện nhanhstart/docs nội bộ feature và dọn code trong phạm vi M4

- [x] T039 [P] Align `specs/008-m4-relative-valuation/quickstart.md` commands with actual test filenames (`tests/test_m4_*.py`) and smoke script path if renamed
- [x] T040 [P] Add brief module docstrings tiếng Việt in `src/stockai/m4_valuation/run.py`, `multiples.py`, `sector_stats.py`, `config_loader.py` (khóa as_of, null≠50, bank PB, không peers-as-median)
- [x] T041 Code cleanup within `src/stockai/m4_valuation/` only (dead imports, consistent flag tokens vs research R7 catalog)
- [x] T042 Final gate: re-run `python -m pytest -q` and confirm still green after polish

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Setup — **BLOCKS** all user stories
- **User Story 1 (Phase 3)**: Depends on Foundational — MVP scoring
- **User Story 2 (Phase 4)**: Depends on Foundational; integrates with US1 runtime (target/evidence/sector metrics) nhưng testable độc lập bằng fixture
- **User Story 3 (Phase 5)**: Depends on US1+US2 implement xong cho green/smoke meaningful
- **Polish (Phase 6)**: After desired stories complete

### User Story Dependencies

- **User Story 1 (P1)**: After Foundational — no dependency on US2 target/evidence completeness for polarity/bank/null
- **User Story 2 (P1)**: After Foundational — needs US1 live path for end-to-end target tests; build-script test (T027) có thể song song sớm hơn sau T008
- **User Story 3 (P1)**: After US1+US2 green — real-5 + full pytest + smoke 235

### Within Each User Story

- Tests MUST be written and FAIL before implementation
- Helpers/config before scoring
- Scoring before target/evidence polish
- Story green before next priority when sequential

### Parallel Opportunities

- T002 ∥ T003 (Setup)
- T009 ∥ (sau T007) fixture JSON
- T011–T016 [P] fail-first US1 cùng file khác nhau về case — có thể soạn song song rồi T017 confirm red
- T022–T027 [P] fail-first US2
- T033 ∥ T034 (US3 test file vs smoke script)
- T039 ∥ T040 (Polish docs)

---

## Parallel Example: User Story 1

```bash
# Launch fail-first tests for US1 together:
Task: "Polarity cheap>expensive in tests/test_m4_valuation.py"
Task: "Bank PB primary in tests/test_m4_valuation.py"
Task: "score null ≠ 50 in tests/test_m4_valuation.py"
Task: "Lookahead excluded in tests/test_m4_valuation.py"
Task: "Stale flag in tests/test_m4_valuation.py"
Task: "EPS TTM fallback annual in tests/test_m4_valuation.py"

# Then confirm red, then implement run.py scoring sequentially T018→T021
```

## Parallel Example: User Story 2

```bash
# Launch fail-first US2 tests together:
Task: "Sector median/version metrics in tests/test_m4_valuation.py"
Task: "Missing sector stats flags in tests/test_m4_valuation.py"
Task: "Relative target shape in tests/test_m4_valuation.py"
Task: "DCF off in tests/test_m4_valuation.py"
Task: "Vietnamese evidence in tests/test_m4_valuation.py"
Task: "Build script mini test in tests/test_m4_sector_stats_build.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (config + helpers + build script) — CRITICAL
3. Complete Phase 3: User Story 1 (fail-first → live V score)
4. **STOP and VALIDATE**: polarity + bank + null≠50 offline
5. Demo MVP điểm V

### Incremental Delivery

1. Setup + Foundational → foundation ready
2. US1 → MVP relative V
3. US2 → target + evidence + sector-stats contract hoàn chỉnh
4. US3 → real-5 + pytest full + smoke 235 + scope check
5. Polish → quickstart/docs + final pytest

### Parallel Team Strategy

1. Team completes Setup + Foundational together
2. After Foundational:
   - Dev A: US1 fail-first + scoring
   - Dev B: US2 build-script tests + target/evidence (sau khi US1 path tồn tại cho integration)
3. Together: US3 smoke + full pytest

---

## Notes

- [P] = different files / independent cases, no incomplete-task dependency
- [USn] maps to spec user stories for traceability
- Verify tests fail before implementing each story
- Score null stays null inside M4 — M7 owns `V_missing_used_neutral`
- Peers never silently replace sector median
- Do not commit/push unless user explicitly asks later
- Avoid: vague tasks, editing forbidden modules, hard-coded business thresholds outside yaml defaults
