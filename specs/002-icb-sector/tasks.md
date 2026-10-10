---
description: "Task list for ICB sector enrichment (002) — close gaps vs clarified spec"
---

# Tasks: ICB Sector Enrichment

**Input**: Design documents from `/specs/002-icb-sector/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Scope**: M1 only (`src/stockai/m1_data/`, `config/`, `scripts/fetch_universe.py`, `tests/test_m1_*.py`).
**MUST NOT** edit `src/stockai/contracts/` (including `schemas.py`) or M2–M9.

**Skeleton**: `icb_sector.py` / wiring already present — tasks close **gaps** in
[plan.md](./plan.md) (parent YAML, cascade rules, finance filter, VN30 peer gate).

**Tests**: Included — required by spec req 10, quickstart.md, constitution V.

**Task updates (2026-10-10)**: (1) explicit `use_icb_peer_cascade` (default `False`);
(2) `sector==""` + `is_bank` → financial for peer filter; (3) deterministic peer order
by market-cap distance then ticker; (4) remove/mark `industry_to_en`; comments use `""` not null.

**Derived user stories** (spec has numbered requirements; mapped for incremental delivery):

| Story | Priority | Spec reqs | Goal |
|-------|----------|-----------|------|
| US1 | P1 MVP | 1–3, 7–8 | L2→EN sector fill/compare, exchange aliases, `sector==""` + flags |
| US2 | P2 | 4–6, 9 | Parent from YAML, cascade peers, finance split, empty-sector peers |
| US3 | P3 | 10 + VN30 gate | VN30 peers unchanged; Banks↛BĐS tests; validate missing CSV |

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no incomplete deps)
- **[Story]**: US1 / US2 / US3
- Exact file paths in every task

## Path Conventions

- Single project: `src/`, `tests/`, `config/`, `scripts/` at repository root

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Confirm docs/config/wiring before gap work

- [x] T001 Confirm feature docs under `specs/002-icb-sector/` (plan.md, spec.md, research.md, data-model.md, contracts/icb-sector-flags.md, quickstart.md) and note scope: only `src/stockai/m1_data/`, `config/`, `scripts/fetch_universe.py`, `tests/test_m1_*.py` — **no** `contracts/` or M2–M9 edits
- [x] T002 [P] Confirm `config/listing_icb.csv`, `config/THIRD_PARTY_NOTICES.txt`, and `icb_sector_enabled` / `icb_sector_map` keys in `config/data_sources.yaml`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: YAML parent map keyed by Supersector — blocks correct peers for all stories

**CRITICAL**: No US2 peer logic until parent map is correct (BĐS ≠ Financials)

- [x] T003 Add `supersector_parent_en` (VI Supersector → EN parent) to `config/icb_sector_map.yaml` with constraint: Banks/Insurance/Financial Services parents → `Financials`; `"Bất động sản"` / Real Estate → parent exactly `Real Estate` (not `Financials`); document that CSV ICB L1 MUST NOT drive peer parent
- [x] T004 [P] Add `financial_sectors: [Banks, Insurance, Financial Services]` to `config/icb_sector_map.yaml` (exact three names per clarify)
- [x] T005 Update `load_listing` in `src/stockai/m1_data/icb_sector.py` to set `parent_en` from `supersector_parent_en` (by L2 VI or sector EN), **not** from CSV L1; **delete `industry_to_en` from `config/icb_sector_map.yaml`** or keep only with a clear comment `unused for peers — do not read in code`; remove any `industry_to_en` reads from `icb_sector.py`
- [x] T006 [P] Fix comments in `config/icb_sector_map.yaml` / `src/stockai/m1_data/icb_sector.py` docstring: missing sector → `""` + flags (**never** “sector null” / JSON null); no `schemas.py` / `contracts/` change

**Checkpoint**: Foundation ready — listing rows expose correct `parent_en` for Real Estate vs Financials

---

## Phase 3: User Story 1 - Sector fill & exchange (Priority: P1) — MVP

**Goal**: ICB L2→EN fill/compare; exchange aliases; missing → `sector==""` + flags; keep vnstock when present

**Independent Test**: `python -m pytest -q tests/test_m1_icb_sector.py -k "sector or exchange or validate or unmapped or not_found"` (or dedicated US1 cases)

### Tests for User Story 1 (write first — must fail if behavior wrong)

- [x] T007 [P] [US1] Assert in `tests/test_m1_icb_sector.py`: ticker absent from CSV + empty company → `company.sector == ""`, flag `icb_ticker_not_found`, `validate(snap, "snapshot")` passes
- [x] T008 [P] [US1] Assert in `tests/test_m1_icb_sector.py`: unmapped Supersector + empty company → `sector == ""` + `icb_sector_unmapped`
- [x] T009 [P] [US1] Assert in `tests/test_m1_icb_sector.py`: non-empty vnstock sector kept on mismatch / missing CSV; flags `icb_sector_mismatch` or `icb_ticker_not_found` / `icb_sector_unmapped` as applicable; never overwrite with ICB when existing non-empty
- [x] T010 [P] [US1] Assert VN30 map: all 30 tickers Supersector→EN match `data/snapshots/*_2026-10-08.json` `company.sector` (or fixture copies) in `tests/test_m1_icb_sector.py`

### Implementation for User Story 1

- [x] T011 [US1] Align `apply_to_company` in `src/stockai/m1_data/icb_sector.py` with contracts/icb-sector-flags.md: fill/compare sector + exchange (`HOSE`→`HSX`, `UPCOM`→`UpCoM`); flags `icb_sector_filled|mismatch|unmapped`, `icb_ticker_not_found`, `icb_exchange_filled|mismatch`
- [x] T012 [US1] Confirm `fetch_company` path in `src/stockai/m1_data/fetch.py` calls `apply_to_company` only when `cfg.get("icb_sector_enabled", True)`; no network in tests
- [x] T013 [US1] Make T007–T010 pass via `python -m pytest -q tests/test_m1_icb_sector.py`

**Checkpoint**: US1 independently verifiable offline

---

## Phase 4: User Story 2 - Peer cascade & finance split (Priority: P2)

**Goal**: Wide-universe peers: L2 → parent (if parent≠L2 and \|parent\|≥10) → market; always `sector_small_group` when leaving L2; finance filter; empty sector excluded as peer; deterministic order

**Independent Test**: Fixture universe in `tests/test_m1_icb_sector.py` / `tests/test_m1_universe.py` covering cascade + `peers_finance_nonfinance_blocked` + order stability

### Tests for User Story 2 (write first)

- [x] T014 [P] [US2] Fail/assert in `tests/test_m1_icb_sector.py`: Real Estate parent from listing == `Real Estate` (not `Financials`) for BCM/VHM/VIC/VRE
- [x] T015 [P] [US2] Fail/assert cascade: L2 size &lt; `min_peer_group_size` and parent==sector → market peers + `sector_small_group` (Real Estate case)
- [x] T016 [P] [US2] Fail/assert cascade: parent≠sector and parent group ≥10 → parent peers + `sector_small_group` (e.g. Banks under Financials when enough names in fixture)
- [x] T017 [P] [US2] Fail/assert: Banks ticker peers MUST NOT include BCM, VHM, VIC, VRE and reverse under wide ICB cascade (`use_icb_peer_cascade=True`); empty after filter → `peers==[]` + `peers_finance_nonfinance_blocked`
- [x] T018 [P] [US2] Fail/assert: `sector==""` ticker never appears in others' `peers`; itself gets market path + `sector_small_group`; **and** ticker with `sector==""` and `company.is_bank is True` is treated as **financial** in the peer filter (only financial peers allowed / blocked vs non-finance accordingly) — cover with an explicit test case in `tests/test_m1_icb_sector.py`
- [x] T030 [P] [US2] Fail/assert in `tests/test_m1_icb_sector.py` (or `tests/test_m1_universe.py`): peer list order is by **closest market-cap distance**, ties broken by **ticker ascending**; calling assign/fill **twice** on the same fixture yields **identical** peer ticker lists (element-wise and order)

### Implementation for User Story 2

- [x] T019 [US2] Rewrite `resolve_peer_group` in `src/stockai/m1_data/icb_sector.py` per data-model.md cascade; exclude `sector==""` from being selected as peers; empty-sector target → market + small-group; for finance membership: `sector in financial_sectors` **OR** (`sector==""` and `is_bank` True) counts as financial (read `is_bank` from `views` / company)
- [x] T020 [US2] Add finance/non-finance filter using `financial_sectors` from YAML + `is_bank` rule above; on empty result set flag `peers_finance_nonfinance_blocked` (wire through `universe._assign_peers` in `src/stockai/m1_data/universe.py`)
- [x] T021 [US2] Add explicit param `use_icb_peer_cascade: bool = False` to `fill_peers` and `fill_peers_dir` in `src/stockai/m1_data/universe.py` (and thread through `_assign_peers`); when `False`, keep legacy same-sector peer path; when `True`, apply ICB `resolve_peer_group` cascade + finance filter; pass `min_peer_group_size` from cfg/map; **do not** infer cascade solely from `icb_sector_enabled`
- [x] T031 [US2] Ensure `_closest` / peer ranking in `src/stockai/m1_data/universe.py` sorts by absolute market-cap difference ascending, tie-break by ticker string ascending; document in docstring
- [x] T022 [US2] Make T014–T018 and T030 pass via `python -m pytest -q tests/test_m1_icb_sector.py tests/test_m1_universe.py`

**Checkpoint**: US2 independently verifiable offline

---

## Phase 5: User Story 3 - VN30 peer freeze & acceptance (Priority: P3)

**Goal**: Preserve submitted VN30 peer lists (exact order); only `fetch_universe.py` turns on cascade for non-VN30; full offline acceptance per quickstart

**Independent Test**: Peer list regression vs 30 snapshots + `python -m pytest -q` green

### Tests for User Story 3

- [x] T023 [P] [US3] Add regression in `tests/test_m1_universe.py` (or `tests/test_m1_icb_sector.py`): with `use_icb_peer_cascade=False` (default), re-`fill_peers` on the VN30 snapshot set and assert each of the **30** files `data/snapshots/<TICKER>_2026-10-08.json` has peer ticker lists matching the baseline **element-by-element and in the same order** (not merely set equality)
- [x] T024 [P] [US3] Assert in tests that ICB peer cascade runs only when `use_icb_peer_cascade=True`; default `False` leaves legacy path; document that `scripts/fetch_universe.py` is the caller that sets `True` when universe ≠ `VN30`

### Implementation for User Story 3

- [x] T025 [US3] Wire `scripts/fetch_universe.py` to set `use_icb_peer_cascade=True` **only** when the selected universe is **not** `VN30` (and typically when `icb_sector_enabled`); VN30 runs leave default `False` so peers stay legacy; `fill_peers` / `fill_peers_dir` / `run_universe` in `src/stockai/m1_data/universe.py` honor the param without auto-enabling cascade
- [x] T026 [US3] Make T023–T024 pass; run `python -m pytest -q tests/test_m1_icb_sector.py tests/test_m1_universe.py tests/test_m1_build.py`

**Checkpoint**: US3 acceptance criteria green without changing VN30 peer snapshots semantics

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Full suite + quickstart alignment

- [x] T027 [P] Sync any remaining flag names with `specs/002-icb-sector/contracts/icb-sector-flags.md` in `src/stockai/m1_data/icb_sector.py` and `src/stockai/m1_data/universe.py` (**read** contract only — do not edit `contracts/` package or M2–M9)
- [x] T028 Run full `python -m pytest -q` and fix regressions in `tests/test_m1_*.py` only (no M2–M9 edits)
- [x] T029 [P] Verify `specs/002-icb-sector/quickstart.md` commands match actual test module names and expected outcomes (mention `use_icb_peer_cascade` default False)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: Immediate
- **Foundational (Phase 2)**: After Setup — **BLOCKS** US1 map correctness for parents used later and US2
- **US1 (Phase 3)**: After Foundational (T005 listing parent may already help US1 tests; sector fill can proceed after T006)
- **US2 (Phase 4)**: After Foundational + preferably US1 flags stable; **requires** T003–T005; T021 before T025
- **US3 (Phase 5)**: After US2 cascade + `use_icb_peer_cascade` param exists
- **Polish (Phase 6)**: After desired stories complete

### User Story Dependencies

- **US1 (P1)**: After Phase 2 — no dependency on US2/US3
- **US2 (P2)**: After Phase 2 (parent YAML); integrates with `universe.py` shared with US3
- **US3 (P3)**: After US2 (`resolve_peer_group` + `use_icb_peer_cascade` API)

### Parallel Opportunities

- T001 ‖ T002 (Setup)
- T003 then T005 (YAML before load_listing); T004 ‖ T006 with T003
- T007–T010 parallel test writes (US1)
- T014–T018 ‖ T030 parallel test writes (US2)
- T023 ‖ T024 (US3 tests)
- T027 ‖ T029 (Polish)

---

## Parallel Example: User Story 1

```text
T007 tests/test_m1_icb_sector.py — missing CSV → "" + flag + validate
T008 tests/test_m1_icb_sector.py — unmapped → "" + icb_sector_unmapped
T009 tests/test_m1_icb_sector.py — keep vnstock
T010 tests/test_m1_icb_sector.py — VN30 sector map match
```

## Parallel Example: User Story 2

```text
T014 parent Real Estate for BCM/VHM/VIC/VRE
T015 cascade parent==sector → market
T016 cascade parent group ≥10
T017 Banks ↛ BĐS + peers_finance_nonfinance_blocked
T018 sector=="" excluded; is_bank+"" → financial filter
T030 peer order by |Δcap| then ticker; two runs identical
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Phase 1 Setup
2. Phase 2 Foundational (parent YAML — even if peers deferred, listing truth matters)
3. Phase 3 US1 sector/exchange/flags
4. **STOP** — validate `tests/test_m1_icb_sector.py` US1 cases

### Incremental Delivery

1. Setup + Foundational → correct parents; drop/`unused` `industry_to_en`
2. US1 → sector fill MVP (`""` not null)
3. US2 → cascade + finance/`is_bank` + deterministic order + `use_icb_peer_cascade=False` default
4. US3 → `fetch_universe.py` enables cascade only if universe ≠ VN30; T023 exact peer order on 30 snapshots
5. Polish → quickstart + green suite

### Suggested MVP scope

**US1 only** (sector fill/compare + empty `""` + VN30 map tests) if shipping a thin PR first; **US2+US3 required** before claiming feature 002 complete per clarified peer rules.

---

## Notes

- Do not change `src/stockai/contracts/` or M2–M9; `sector` remains required string (`""` when missing)
- `use_icb_peer_cascade` defaults **False**; only `scripts/fetch_universe.py` sets **True** when universe ≠ `VN30`
- Do not rewrite VN30 peer lists under legacy path (`use_icb_peer_cascade=False`)
- Commit message style: `m1: <việc ngắn>` when user asks to commit
- Next command after tasks: `/speckit-implement`
