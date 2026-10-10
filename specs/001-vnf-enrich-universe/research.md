# Research: VNF Enrich & Wide Universe (FR-008 / FR-009 only)

**Scope**: Consume M1 quality tiers in scoring + report. **Do not modify** `src/stockai/m1_data/`.

## R1 — Where to enforce the quality gate

**Decision**: Enforce at **M7** (authoritative “scored or not”) and **surface** at **M9**; optional early short-circuit in `pipeline.py` (N1) to skip M2–M6 work for `insufficient`.

**Rationale**:
- FR-008 is about not **chấm điểm / xếp hạng** — that is M7’s contract (`result`).
- Quality tier is already on the snapshot as `meta.flags` (`quality_tier_*`, `quality_*`); M1’s job is done.
- M9 must expose exclusion reasons and `limited` limitations to humans (FR-008/009 “xuất hiện trong kết quả/báo cáo”).

**Alternatives considered**:
- Gate only in `pipeline.py` without M7 changes → M7 could still be called ad-hoc and produce a rating; weaker guarantee.
- Gate inside each of M2–M6 → scatters policy, more owners, violates YAGNI.
- Re-call `quality.assess` downstream → duplicates M1 thresholds; risk of drift; forbidden “change M1” spirit if logic is copied wrongly.

## R2 — How to read the tier without importing M1

**Decision**: Parse `snapshot["meta"]["flags"]` for `quality_tier_{full|limited|insufficient}` (same convention M1 already writes). Prefer a **tiny shared helper** in `stockai.contracts.helpers` (N1) e.g. `quality_tier(snapshot) -> str | None` and `quality_reason_flags(snapshot) -> list[str]`, so M7/M9/pipeline do not import `m1_data.quality`.

**Rationale**: Keeps ownership boundary (M1 untouched); flags are the published wire format; helper is read-only.

**Alternatives considered**:
- `from stockai.m1_data.quality import tier_of` in M7 → couples scoring to M1 package; works but blurs OWNERSHIP.
- Duplicate parse inline in M7 and M9 → drift risk.

## R3 — RESULT_SCHEMA vs “must not score”

**Decision**: **Minimal N1 schema amend** for skipped quality gate:
- Allow `score` to be `number | null`.
- Extend `rating` enum with `"Không xếp hạng"` (or equivalent ASCII-safe label agreed in CONTRACTS).
- Add optional `quality_gate`: `{ "tier": "insufficient"|"limited"|"full", "scored": bool, "reasons": [str] }` (reasons = flags stripped of `quality_` prefix or raw `quality_*` flags).

When `tier == insufficient`: M7 returns `score: null`, `rating: "Không xếp hạng"`, `quality_gate.scored: false`, and includes `quality_tier_insufficient` plus reason flags in `flags`. Do **not** invent a fake 0–100 score.

When `tier == limited` or `full` (or missing tier → treat as legacy VN30/`full` behavior): compute score as today; for `limited`, append reason flags and set `quality_gate.scored: true`.

**Rationale**: Current RESULT_SCHEMA requires numeric `score` and a 5-level rating — returning a real score for `insufficient` would violate constitution and FR-008. Schema change is the honest fix; N1 owns `contracts/`.

**Alternatives considered**:
- Keep fake score + flag only → fails data honesty (constitution III) and SC-003.
- Omit M7 output entirely → breaks pipeline/M9 assumptions that `upstream["m7"]` exists.

## R4 — Pipeline short-circuit

**Decision**: Recommended but not strictly required for FR correctness: if tier is `insufficient`, `analyze()` may skip M2–M6 (fill stub/error-neutral upstream or empty module outs with `status: "partial"` + flag `skipped_quality_insufficient`) and still run M7 (skip path), M8, M9 so a report explains exclusion.

**Rationale**: Saves work; guarantees no accidental use of component scores. If short-circuit is deferred, M7 skip alone still satisfies FR-008 as long as rating/score are not emitted as a real recommendation.

**Alternatives considered**: Always run M2–M6 then discard at M7 → simpler first PR; acceptable MVP if documented.

## R5 — Limited limitations on the report (FR-009)

**Decision**: M7 copies all `quality_*` / `quality_tier_*` flags onto `result.flags` and fills `quality_gate`. M9 prints tier + human-readable reasons (at least the flag strings) on the PDF stub/layout so limitations are not hidden.

**Rationale**: Flags already encode reasons (`quality_low_liquidity`, `quality_news_few`, …). No new M1 fields.

## R6 — Missing quality flags on older snapshots

**Decision**: If no `quality_tier_*` flag is present, treat as **scorable** (legacy behavior), and add flag `quality_tier_absent` on the result for transparency. Do not block DEMO/VN30 fixtures that predate the gate.

**Rationale**: Avoid breaking e2e on `fixtures/snapshot_DEMO.json` (constitution I).

## R7 — Tests (offline)

**Decision**:
- Unit: M7 with fixture snapshots stamped `quality_tier_insufficient` / `quality_tier_limited` (+ reason flags).
- Assert insufficient → `score is None`, rating not in the five trade ratings, `quality_gate.scored is False`.
- Assert limited → numeric score present, reasons visible on `flags` / `quality_gate`.
- Pipeline e2e: DEMO unchanged; optional insufficient fixture in `tests/` (not requiring M1 code changes).

**Rationale**: Constitution V — offline, no network.
