# Data Model: Quality gate consumption (FR-008 / FR-009)

## Entities

### SnapshotQuality (already produced by M1 — read-only)

Represented **on the snapshot**, not a separate store.

| Field | Location | Values / notes |
|-------|----------|----------------|
| `tier` | `meta.flags` entry `quality_tier_{tier}` | `full` \| `limited` \| `insufficient` |
| `reasons` | `meta.flags` entries `quality_{reason}` | e.g. `illiquid`, `prices_lt_750`, `low_liquidity`, `news_few` |
| `data_status` | `meta.data_status` | Existing snapshot field; orthogonal to tier |

**Rules**:
- At most one `quality_tier_*` flag SHOULD be present (M1 overwrites its own flags on apply).
- Downstream MUST NOT recompute thresholds; only read flags.
- If no `quality_tier_*` → treat as **legacy scorable** (see research R6).

### QualityGateOutcome (new on M7 `result`)

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `tier` | `full` \| `limited` \| `insufficient` \| `absent` | yes | `absent` when no tier flag |
| `scored` | bool | yes | `false` only for `insufficient` |
| `reasons` | string[] | yes | Human/machine reason tokens (from `quality_*` flags) |

### AnalysisResult (M7 — amended)

Existing RESULT fields plus:

| Field | Change |
|-------|--------|
| `score` | MAY be `null` when `quality_gate.scored == false` |
| `rating` | MAY be `"Không xếp hạng"` when not scored |
| `flags` | MUST include `quality_tier_*` and relevant `quality_*` when present on snapshot |
| `quality_gate` | Optional object (QualityGateOutcome); required when implementing FR-008/009 |

Component `scores` / `weights` / `contributions`: when not scored, use neutral/empty consistent with schema validation (document in tasks: either omit numeric meaning or fill neutrals with flag `scoring_skipped_insufficient` — prefer **null score + empty or zeroed contributions with explicit flags**, as long as schema allows).

**Preferred skipped payload**:
- `score: null`
- `rating: "Không xếp hạng"`
- `scores`: may still list F/T/V/S/R as null or unused; if schema requires numbers inside `scores`, use documented neutrals **and** flag `scoring_skipped_insufficient` so consumers ignore them
- `quality_gate.scored: false`

### ReportSurface (M9)

Not a separate persisted entity; PDF (and any text lines) MUST include:
- Tier label
- For `insufficient`: explicit “not ranked” + reasons
- For `limited`: “scored with limitations” + reasons
- For `full` / `absent`: no extra warning required beyond normal report

## State transitions

```text
Snapshot with flags
        │
        ▼
   parse tier
        │
   ┌────┴────────────────────────┐
   │                             │
insufficient                  limited / full / absent
   │                             │
   ▼                             ▼
M7: scored=false              M7: compute_score + rating
score=null                    score in [0,100]
rating=Không xếp hạng         rating in 5 levels
flags += quality_*            flags += quality_* (if limited)
   │                             │
   └────────────┬────────────────┘
                ▼
         M8 validate (unchanged rules)
                ▼
         M9 surface quality_gate + flags
```

## Validation rules

1. `insufficient` ⇒ `quality_gate.scored == false` ∧ `score is null` ∧ rating not in the five trade ratings.
2. `limited` ∨ `full` ∨ `absent` ⇒ `quality_gate.scored == true` ∧ `score` is a number ∧ rating ∈ five trade ratings.
3. `limited` ⇒ at least one limitation reason appears in `quality_gate.reasons` or `flags`.
4. Downstream MUST NOT clear `quality_*` flags from the snapshot.
