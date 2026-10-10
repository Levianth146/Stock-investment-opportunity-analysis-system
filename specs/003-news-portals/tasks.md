---
description: "Task list for M1 Vietnamese financial news portals (003)"
---

# Tasks: Vietnamese Financial News Portals (M1)

**Input**: Design documents from `/specs/003-news-portals/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Scope**: M1 only (`src/stockai/m1_data/`, `config/`, `scripts/fetch_universe.py`,
`tests/test_m1_*.py`, `tests/fixtures/news_portals/`). **MUST NOT** edit
`src/stockai/contracts/schemas.py` or M2–M9.

**Tests**: Included — required by SC-001…006, acceptance scenarios, constitution V
(offline fixtures from **real** HTML captures, no network in CI tests).

**Updates (post-tasks)**: spike thật + robots/JS; dedupe bỏ URL `n/a`; `--tickers` →
`universe_name=custom`; FR-007 ok/empty **trước** cắt `max_news`.
**Phạm vi active (sau chẩn đoán)**: `news_portals_active: [cafef]` mặc định;
VnEconomy/TNCK parser giữ nhưng không chạy — thêm lại khi có search/RSS theo mã.

**User stories**:

| Story | Priority | Goal |
|-------|----------|------|
| US1 | P1 MVP | Portal fetch + date filter + merge/dedupe/cap + contract news |
| US2 | P2 | `news_portals_enabled` default false; only VN30/VN100 (not custom) |
| US3 | P3 | Per-portal fault isolation, retries/delay, URL cache + resume |

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Parallelizable (different files, no incomplete deps)
- **[Story]**: US1 / US2 / US3
- Exact file paths in every task

## Path Conventions

- Single project: `src/`, `tests/`, `config/`, `scripts/` at repository root

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Docs, config keys, fixture dirs

- [x] T001 Confirm feature docs under `specs/003-news-portals/` (plan.md, spec.md, research.md, data-model.md, contracts/news-portals.md, quickstart.md) and scope: no `schemas.py` / M2–M9 edits
- [x] T002 [P] Add `news_portals_enabled: false`, `news_portals_active: [cafef]`, plus `news_portal_interval_sec`, `news_portal_retries`, `news_portal_cache_dir` keys to `config/data_sources.yaml` (defaults per data-model.md)
- [x] T003 [P] Create `tests/fixtures/news_portals/` with README stating fixtures MUST be real HTML captured in spike (T004), never hand-authored markup

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Spike + shared helpers — MUST complete before story scrapers

**CRITICAL**: Blocks US1–US3

- [x] T004 Spike (manual/scripted, network once): for each of CafeF, VnEconomy, TinNhanhChungKhoan, fetch **1 ticker** (search + article), save real HTML under `tests/fixtures/news_portals/<slug>/`; check `robots.txt` and site terms; if a portal requires JS rendering, document in `specs/003-news-portals/research.md` (or spike notes) and **remove that portal from FR-001 scope** for this version; do not invent HTML for later T009
- [x] T005 Create `src/stockai/m1_data/news_portals.py` skeleton with portal slugs remaining in scope after T004 and display `source` names per `specs/003-news-portals/contracts/news-portals.md`
- [x] T006 [P] Implement in `src/stockai/m1_data/news_portals.py`: `normalize_url`, `normalize_title`, and `merge_news(existing, portal_articles, max_news)` — empty/`"n/a"` URLs MUST NOT be used as dedupe keys (title-only compare); valid URLs may dedupe by URL **or** title; on duplicate prefer portal; sort by `published_at` desc; truncate to `max_news`
- [x] T007 [P] Implement in `src/stockai/m1_data/news_portals.py`: date helpers — accept ISO datetime or `YYYY-MM-DD` only; reject year-only / undated; look-ahead/window via `published_at[:10]` vs `nstart`/`as_of`; never invent time; `summary` truncate to **500** chars (same as `normalize_news` path) with teaser preferred else body prefix
- [x] T008 Implement article cache read/write by normalized URL under `cfg["news_portal_cache_dir"]` in `src/stockai/m1_data/news_portals.py` (gitignored path; injectable for tests); skip cache key when URL empty/`n/a`

**Checkpoint**: Foundation ready — real fixtures + merge/date/cache APIs

---

## Phase 3: User Story 1 - Portal news fill & merge (Priority: P1) — MVP

**Goal**: Parse spiked fixtures; day-resolution dates; merge with Google/vnstock news; contract-valid items + flags ok/empty/no_date_dropped (ok/empty **before** `max_news` cut)

**Independent Test**: `python -m pytest -q tests/test_m1_news_portals.py`

### Tests for User Story 1 (write first — must fail before impl)

- [x] T009 [P] [US1] Organize spiked HTML from T004 under `tests/fixtures/news_portals/` (search + article; include undated / as_of date-only / as_of with time cases — capture or annotate real pages; **do not** fabricate HTML)
- [x] T010 [P] [US1] Failing tests in `tests/test_m1_news_portals.py`: dated articles within window → contract news (`id,title,url,source,published_at`; `summary` non-null if body); origin URL not Google redirect; `validate` snapshot news items
- [x] T011 [P] [US1] Failing tests: undated / year-only dropped + `news_portal_no_date_dropped:<n>`; `published_at[:10] > as_of` dropped; as_of day with and without time both kept
- [x] T012 [P] [US1] Failing tests: (a) Google dup by valid URL or normalized title → portal wins; (b) vnstock-style item with `url="n/a"` duplicates portal by title only → portal wins; (c) final list newest-first then length ≤ `max_news`; (d) `news_portal_ok` if ≥1 post-filter pre-cap article even if later truncated out of final list; (e) SC-005: fixture with few Google news + enough portal articles → after merge/`quality.apply`, no `quality_news_few` solely from thin Google News

### Implementation for User Story 1

- [x] T013 [P] [US1] Implement CafeF search+article parse in `src/stockai/m1_data/news_portals.py` against real fixtures (stdlib HTML; inject `fetch`; use cache from T008) — skip if removed in T004
- [x] T014 [P] [US1] Implement VnEconomy search+article parse in `src/stockai/m1_data/news_portals.py` — skip if removed in T004
- [x] T015 [P] [US1] Implement TinNhanhChungKhoan search+article parse in `src/stockai/m1_data/news_portals.py` — skip if removed in T004
- [x] T016 [US1] Implement `fetch_portals(...)` in `src/stockai/m1_data/news_portals.py`: after date/dedupe filters set `news_portal_ok|empty` **before** `max_news` truncate; `failed` on network/parse; `news_portal_no_date_dropped:<n>`; map to news shape with `source_id` `src_news_<slug>`
- [x] T017 [US1] Wire portals into `fetch_news` in `src/stockai/m1_data/fetch.py` after Google/RSS when enabled; merge via `merge_news`; append `sources`; `quality.apply` sees final `news` length
- [x] T018 [US1] Make T010–T012 pass via `python -m pytest -q tests/test_m1_news_portals.py`

**Checkpoint**: US1 independently verifiable offline

---

## Phase 4: User Story 2 - Enablement & universe gate (Priority: P2)

**Goal**: Default off; portals only for `universe_name` ∈ {VN30, VN100}; custom tickers never enable portals

**Independent Test**: Flag false / HOSE / custom → no portal fetch

### Tests for User Story 2

- [x] T019 [P] [US2] Failing tests in `tests/test_m1_news_portals.py`: `news_portals_enabled=false` → portal `fetch` spy not called; no portal flags
- [x] T020 [P] [US2] Failing tests: enabled + `universe_name` in `{HOSE, custom, ...}` not VN30/VN100 → no portal articles/flags; enabled + `VN30`/`VN100` → portals run

### Implementation for User Story 2

- [x] T021 [US2] Gate in `src/stockai/m1_data/fetch.py` / `news_portals.py`: run portals only if `cfg.get("news_portals_enabled")` and `cfg.get("universe_name") in {"VN30","VN100"}`
- [x] T022 [US2] In `scripts/fetch_universe.py`: set `cfg["universe_name"]` to selected `--universe`; when `--tickers` or `--tickers-file` is used set `cfg["universe_name"]="custom"` (do not enable portals); thread name through `fetch_all` in `src/stockai/m1_data/universe.py` if needed
- [x] T023 [US2] Make T019–T020 pass via `python -m pytest -q tests/test_m1_news_portals.py`

**Checkpoint**: US2 independently verifiable

---

## Phase 5: User Story 3 - Fault isolation & cache (Priority: P3)

**Goal**: One portal failure does not break snapshot; delay/retry; cache hit skips network on resume

**Independent Test**: Mock one portal raising → `news_portal_failed`; second call uses cache

### Tests for User Story 3

- [x] T024 [P] [US3] Failing tests in `tests/test_m1_news_portals.py`: one portal `fetch` raises → `news_portal_failed:<slug>`; other portals still contribute; snapshot build continues
- [x] T025 [P] [US3] Failing tests: success with 0 kept after date/dedupe → `news_portal_empty:<slug>` not `failed`; empty does not alone force worse `quality_tier` on fixture with enough other news
- [x] T026 [P] [US3] Failing tests: after caching an article URL, second `fetch_portals` with same cache dir does not call `fetch` for that URL (spy count)

### Implementation for User Story 3

- [x] T027 [US3] Wrap each portal in try/except in `src/stockai/m1_data/news_portals.py`; apply `news_portal_interval_sec` sleep only when real `http_get`; limited retries from `news_portal_retries`
- [x] T028 [US3] Ensure cache path used on resume in `src/stockai/m1_data/news_portals.py`; document `--resume` reuses `news_portal_cache_dir`
- [x] T029 [US3] Make T024–T026 pass; run `python -m pytest -q tests/test_m1_news_portals.py`

**Checkpoint**: US3 independently verifiable

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Notices, full suite, quickstart

- [x] T030 [P] If any logic adapted from vn-annual-report-miner, append MIT notice to `config/THIRD_PARTY_NOTICES.txt` (FR-009); otherwise note N/A in PR description
- [x] T031 [P] Confirm no secrets in `src/stockai/m1_data/news_portals.py` / config; any key only via env (FR-008)
- [x] T032 Run full `python -m pytest -q` and fix regressions only under M1 tests / fixtures
- [x] T033 [P] Align `specs/003-news-portals/quickstart.md` with actual test module names, spike/fixture policy, and commands

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: Immediate
- **Foundational (Phase 2)**: After Setup — **T004 spike BLOCKS** T009 and portal parsers
- **US1 (Phase 3)**: After Foundational
- **US2 (Phase 4)**: After US1 wiring (T017)
- **US3 (Phase 5)**: After US1 portal runners (T013–T016)
- **Polish (Phase 6)**: After desired stories complete

### User Story Dependencies

- **US1**: After Phase 2 (incl. T004)
- **US2**: After T017
- **US3**: After T013–T016

### Parallel Opportunities

- T001 ‖ T002 ‖ T003
- After T004: T006 ‖ T007 ‖ T008 (with T005)
- T010–T012 parallel tests; T013 ‖ T014 ‖ T015 scrapers (in-scope only)
- T019 ‖ T020; T024 ‖ T025 ‖ T026
- T030 ‖ T031 ‖ T033

---

## Parallel Example: User Story 1

```text
T010 contract-shaped news from real fixtures
T011 date / as_of edge cases
T012 dedupe n/a URL + portal prefer + ok before cap
T013–T015 portal parsers (only slugs still in scope)
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Phase 1 Setup  
2. Phase 2 Spike (T004) + helpers  
3. Phase 3 US1  
4. **STOP** — validate `tests/test_m1_news_portals.py`  

### Incremental Delivery

1. Setup + Spike + Foundational  
2. US1 → portal news MVP  
3. US2 → gate + `custom`  
4. US3 → resilience  
5. Polish → full `pytest -q`  

### Suggested MVP scope

**US1** after successful T004; **US2** before enabling in shared config; **US3** before VN100 batch.

---

## Notes

- Prefer stdlib HTML; add `trafilatura` only if spike shows need **and** portal remains non-JS
- Commit style: `m1: <việc ngắn>` when user asks to commit
- Next: `/speckit-implement`
