---
description: "Task list for FR-008/FR-009 quality-gate consumption"
---

# Tasks: VNF Enrich & Wide Universe (FR-008 / FR-009)

**Input**: Design documents from `/specs/001-vnf-enrich-universe/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Scope trim**: FR-001..007, 010, 011 already shipped in M1. **Do not modify**
`src/stockai/m1_data/**`. Remaining backlog = **FR-008** + **FR-009** (US2 scenarios 2–3).

**Out of scope**: Pipeline M2–M6 short-circuit in `src/stockai/pipeline.py` (former **T014 removed**).

**Owners (this slice)**: N1 `contracts/`; N5 `m7_scoring/`; N6 `m8_validate/`, `m9_report/`.

**Tests**: Included — required by SC-003, plan.md, and constitution V (`pytest -q` clean).

**Organization**: US1/US3 = verify-only (already done). US2 = implement gate + M8/M9 surface.

**Status**: Implementation complete (`/speckit-implement` 2026-10-10). `pytest -q` → 62 passed.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: US1 / US2 / US3
- Exact file paths in every task

## Path Conventions

- Single project: `src/`, `tests/` at repository root

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Align working tree and constraints before code changes

- [x] T001 Confirm feature docs present under `specs/001-vnf-enrich-universe/` (plan.md, spec.md, research.md, data-model.md, contracts/quality-gate.md, quickstart.md) and note constraint: never edit `src/stockai/m1_data/**`
- [x] T002 [P] Skim `docs/OWNERSHIP.md` and confirm owners for this slice (N1: `contracts/`; N5: `m7_scoring/`; N6: `m8_validate/`, `m9_report/`) — no `pipeline.py` short-circuit in this PR

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Shared flag helpers + RESULT schema so M7/M8/M9 can implement the gate

**CRITICAL**: No US2 implementation until this phase completes

- [x] T003 Add `quality_tier(snapshot) -> str | None` and `quality_reasons(snapshot) -> list[str]` to `src/stockai/contracts/helpers.py` per `specs/001-vnf-enrich-universe/contracts/quality-gate.md` (parse `quality_tier_*` / `quality_*` from `meta.flags` only; do not import `m1_data`)
- [x] T004 [P] Amend `RESULT_SCHEMA` in `src/stockai/contracts/schemas.py`: `score` type `number|null`; extend `rating` enum with `"Không xếp hạng"`; add optional `quality_gate` object with required fields `tier` (`full|limited|insufficient|absent`), `scored` (bool), `reasons` (string[])
- [x] T005 [P] Document the RESULT schema deltas for quality gate in `docs/CONTRACTS.md` (M7 row / result notes)
- [x] T006 Add unit assertions for helpers in `tests/test_contracts.py` (or new `tests/test_quality_helpers.py`): tier extraction, reasons list, absent tier → `None`

**Checkpoint**: Foundation ready — US2 can start

---

## Phase 3: User Story 1 - VNF enrich fill/cross-check (Priority: P1) — VERIFY ONLY

**Goal**: Confirm US1 remains green without touching M1

**Independent Test**: `python -m pytest -q tests/test_m1_vnf.py`

- [x] T007 [US1] Run `python -m pytest -q tests/test_m1_vnf.py` and confirm pass; do not change any file under `src/stockai/m1_data/`

**Checkpoint**: US1 still delivered by existing M1 code

---

## Phase 4: User Story 2 - Quality gate in scoring & report (Priority: P2) — MVP REMAINING

**Goal**: FR-008 — `insufficient` not ranked; FR-009 — `limited` scored with limitations visible on result + PDF; M8 skips score/rating checks when not scored

**Independent Test**: Offline tests in `tests/test_m7_quality_gate.py`, `tests/test_m8_*.py`, M9 null-safe PDF; see `specs/001-vnf-enrich-universe/quickstart.md` sections 2–3

### Tests for User Story 2 (write first — must fail before impl)

- [x] T008 [P] [US2] Create failing tests for insufficient path in `tests/test_m7_quality_gate.py`: stamped snapshot flags `quality_tier_insufficient` + reason flags → `score is None`, `rating == "Không xếp hạng"`, `quality_gate.scored is False`, reasons visible
- [x] T009 [P] [US2] Add failing tests for limited path in `tests/test_m7_quality_gate.py`: `quality_tier_limited` + reasons → numeric `score`, trade rating in five levels, `quality_gate.scored is True`, reasons on `flags`/`quality_gate.reasons`
- [x] T010 [P] [US2] Add failing test for absent-tier legacy path in `tests/test_m7_quality_gate.py`: no `quality_tier_*` → still scores; result flags include `quality_tier_absent`
- [x] T023 [P] [US2] Add failing tests in `tests/test_m8_run.py` (and/or `tests/test_m8_quality_gate.py`): when `upstream["m7"]["quality_gate"]["scored"] is False`, M8 MUST NOT fail on **score-formula** or **recommendation-threshold** checks; unrelated checks may still run

### Implementation for User Story 2

- [x] T011 [US2] Implement quality-gate branch in `src/stockai/m7_scoring/run.py`: if `quality_tier(snapshot) == "insufficient"` return skip payload (`score: null`, `rating: "Không xếp hạng"`, `quality_gate` with `tier/scored/reasons`, echo quality flags); else call existing `compute_score`/`to_rating`/`run_debate`
- [x] T012 [US2] For `limited`/`full`/`absent` paths in `src/stockai/m7_scoring/run.py`, attach `quality_gate` and merge `quality_*` flags onto `result["flags"]` (limited MUST expose reasons per FR-009)
- [x] T013 [P] [US2] Update `src/stockai/m9_report/run.py`: surface tier + skip/limitations from `upstream["m7"]["quality_gate"]` / flags **and** handle `result["score"] is None` on the Score line (~line 19); when `score is None` show `n/a` / not-ranked text (no float format); tolerate rating `"Không xếp hạng"`
- [x] T015 [P] [US2] Update `src/stockai/m8_validate/run.py` to **skip** checks of score formula and recommendation/rating thresholds when `upstream["m7"].get("quality_gate", {}).get("scored") is False` (see `contracts/quality-gate.md` § M8); keep other checks; make `tests/test_m8_*.py` (T023) pass
- [x] T016 [US2] Re-run `python -m pytest -q tests/test_m7_quality_gate.py tests/test_m8_*.py` until T008–T010 and T023 pass; fix schema/validate issues in `src/stockai/contracts/schemas.py` or M7/M8/M9 payloads if needed
- [x] T017 [US2] Extend `tests/test_pipeline_e2e.py` (or add focused case) so DEMO/`fixtures/snapshot_DEMO.json` still scores end-to-end after schema change

> **T014 REMOVED FROM SCOPE** — former optional `pipeline.py` M2–M6 short-circuit. Do not implement in this slice.

**Checkpoint**: US2 FR-008/009 independently verifiable offline

---

## Phase 5: User Story 3 - Enrich batch summary (Priority: P3) — VERIFY ONLY

**Goal**: Confirm US3 remains green without touching M1

**Independent Test**: `python -m pytest -q tests/test_m1_wide.py` (and related M1 suite)

- [x] T018 [US3] Run `python -m pytest -q tests/test_m1_wide.py` and confirm pass; do not change `src/stockai/m1_data/universe.py` or other M1 files

**Checkpoint**: US3 still delivered by existing M1 code

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Consumer audit, full-suite validation, docs hygiene

- [x] T019 [P] Update `docs/CONTRACTS.md` examples if M7 skip payload needs a one-line sample for `quality_gate` / nullable `score`
- [x] T020 Grep the whole repo for consumers of M7 result `score` / `rating` — list in `specs/001-vnf-enrich-universe/CONSUMERS_SCORE_RATING.md` (and PR description). No Streamlit app in repo. Also null-safe `main.py`.
- [x] T021 Run full offline suite `python -m pytest -q` and fix any regressions outside `m1_data/`
- [x] T022 Execute validation steps in `specs/001-vnf-enrich-universe/quickstart.md` (DEMO + insufficient + limited) and note results in the PR description

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: None
- **Foundational (Phase 2)**: After Setup — **BLOCKS** US2 implementation
- **US1 verify (Phase 3)**: Can run anytime; does not block US2
- **US2 (Phase 4)**: After Foundational; this is the only net-new delivery
- **US3 verify (Phase 5)**: Can run anytime; does not block US2
- **Polish (Phase 6)**: After US2 complete (+ preferred after US1/US3 verify)

### User Story Dependencies

- **US1 (P1)**: Already implemented in M1 — verify only (T007)
- **US2 (P2)**: Depends on Phase 2 (T003–T006); implements FR-008/009 + M8/M9 null-safe paths
- **US3 (P3)**: Already implemented in M1 — verify only (T018)

### Within US2

1. Failing tests T008–T010 and T023 first
2. M7 gate T011–T012
3. M9 null-safe T013 ∥ M8 skip T015
4. Make tests pass T016; protect DEMO T017

### Parallel Opportunities

- T002 || docs skim during T001
- T004 || T005 after T003 started
- T006 can follow T003 closely
- T008 || T009 || T010 || T023 once foundation ready
- T013 || T015 after T011 (different files: `m9_report/run.py` vs `m8_validate/run.py`)
- T007 || T018 anytime vs US2 work
- T019 || T020 during polish

---

## Notes

- [P] = different files, no incomplete-task dependency
- Never edit `src/stockai/m1_data/**`
- **T014 removed from scope** (pipeline short-circuit) — do not implement
- Commit message style: `<module>: <short>` (no `Co-authored-by`)
- Suggested commit: `m7: quality gate skip insufficient; m8/m9 null-safe score`
