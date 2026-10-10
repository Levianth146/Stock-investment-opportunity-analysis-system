# Implementation Plan: VNF Enrich & Wide Universe (FR-008 / FR-009)

**Branch**: `001-vnf-enrich-universe` | **Date**: 2026-10-10 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/001-vnf-enrich-universe/spec.md`

**Note**: Spec marks FR-001..007, 010, 011 as already implemented in M1. This plan
covers **only FR-008 and FR-009**. **Do not modify** `src/stockai/m1_data/`.

## Summary

Consume snapshot quality tiers already written by M1 (`quality_tier_full|limited|insufficient`
plus `quality_*` reason flags) so that:

- **FR-008**: `insufficient` tickers are **not ranked** (no real recommendation score);
  exclusion reasons appear on the analysis result and PDF.
- **FR-009**: `limited` tickers **are scored**, and known data limitations appear on the
  result and PDF (not hidden).

Technical approach: read-only flag parsing (shared helper under `contracts/`), gate in
**M7**, surface in **M9**, minimal **RESULT_SCHEMA** amend (nullable score +
`"Không xếp hạng"` + optional `quality_gate`), optional pipeline short-circuit. Details in
[research.md](./research.md).

## Technical Context

**Language/Version**: Python 3.10+ (CI 3.11)

**Primary Dependencies**: Existing stack only (`pyyaml`, `reportlab`, pytest); no new
packages for this slice

**Storage**: Snapshot JSON on disk (`data/snapshots/`, `fixtures/`); result JSON + PDF under
`reports/` — no DB

**Testing**: `pytest` offline; new tests under `tests/test_m7_*.py` and/or
`tests/test_pipeline_e2e.py` / `tests/test_m9_*.py`

**Target Platform**: Local CLI / CI (Windows + Linux)

**Project Type**: Single-repo Python CLI pipeline (M1→M9)

**Performance Goals**: Negligible — O(flags) parse per ticker; no network in gate path

**Constraints**:
- MUST NOT edit `src/stockai/m1_data/**`
- MUST preserve `run(snapshot, upstream, cfg) -> dict` signatures
- MUST keep DEMO / existing e2e green when quality flags absent (legacy scorable)
- Offline tests only (constitution V)
- Schema changes only via N1 (`contracts/`, possibly `docs/CONTRACTS.md`)

**Scale/Scope**: Single-ticker `analyze()` path first; batch universe fetch already exists in
M1 and is out of scope except consuming per-snapshot flags

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Gate | Status |
|-----------|------|--------|
| I. Data contract is law | Keep module `run(...)` signatures; any RESULT_SCHEMA change documented and validated; DEMO e2e must still pass | PASS — plan requires minimal schema amend + tests |
| II. `as_of` integrity | Quality gate does not fetch new market data; uses flags already on snapshot | PASS |
| III. Data honesty | `insufficient` → no fabricated score; `limited` limitations surfaced via flags/report | PASS — core of FR-008/009 |
| IV. Numbers from code | Gate and scoring remain deterministic code; no LLM numbers | PASS |
| V. Offline / reproducible | Tests use stamped fixture snapshots; no network | PASS |
| VI. Ownership / small diffs | Touch N1 contracts (+ optional pipeline), N5 M7, N6 M9 only; leave M1 alone | PASS |
| Tech constraint | `insufficient` MUST NOT be scored | PASS — explicit M7 behavior |

**Post-design re-check**: Same gates hold. Schema nullable `score` is justified (honesty >
forcing a fake rating). No unjustified complexity (Complexity Tracking empty).

## Project Structure

### Documentation (this feature)

```text
specs/001-vnf-enrich-universe/
├── plan.md              # This file
├── research.md          # Phase 0
├── data-model.md        # Phase 1
├── quickstart.md        # Phase 1
├── contracts/           # Phase 1
│   └── quality-gate.md
└── tasks.md             # Phase 2 (/speckit-tasks — not created here)
```

### Source Code (repository root)

```text
src/stockai/
├── contracts/
│   ├── schemas.py          # N1: RESULT_SCHEMA amend (nullable score, rating enum, quality_gate)
│   └── helpers.py          # N1: quality_tier / quality_reason_flags helpers
├── pipeline.py             # N1 (optional): short-circuit M2–M6 when insufficient
├── m7_scoring/
│   └── run.py              # N5: gate — skip rank if insufficient; pass through limited flags
└── m9_report/
    └── run.py              # N6: print tier + limitations / skip reason on PDF

tests/
├── test_m7_quality_gate.py # new offline tests for FR-008/009
├── test_pipeline_e2e.py    # extend: DEMO + insufficient fixture behavior
└── test_m9_*.py            # optional: assert PDF/result payload mentions limitations

# OUT OF SCOPE (do not modify for this plan)
src/stockai/m1_data/        # quality.py, universe.py, vnf_source.py already ship FR-001..007
```

**Structure Decision**: Stay in the existing single-package layout. Only add a small
contracts helper and tests; no new apps/services.

## Complexity Tracking

> No constitution violations requiring justification.
