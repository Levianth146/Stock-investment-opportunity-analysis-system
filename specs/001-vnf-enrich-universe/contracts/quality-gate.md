# Contract: Quality gate (consumer side)

## Snapshot flags (producer = M1, already shipped)

Immutable for this feature slice (do not change M1).

| Flag pattern | Meaning |
|--------------|---------|
| `quality_tier_full` | Scorable, no soft limitations from gate |
| `quality_tier_limited` | Scorable with known limitations |
| `quality_tier_insufficient` | MUST NOT receive a trade rating |
| `quality_<reason>` | Reason token, e.g. `quality_illiquid`, `quality_news_few` |

## Shared helper (N1 — `stockai.contracts.helpers`)

```text
quality_tier(snapshot) -> "full" | "limited" | "insufficient" | None
quality_reasons(snapshot) -> list[str]   # tokens without "quality_" prefix, excluding tier
```

`None` tier means legacy / absent → treat as scorable (`tier` recorded as `absent` on result).

## M7 `result` amendments (`validate(..., "result")`)

### Schema deltas

1. `score`: `number | null` (was number only).
2. `rating` enum adds: `"Không xếp hạng"`.
3. Optional property `quality_gate`:

```json
{
  "type": "object",
  "required": ["tier", "scored", "reasons"],
  "properties": {
    "tier": { "enum": ["full", "limited", "insufficient", "absent"] },
    "scored": { "type": "boolean" },
    "reasons": { "type": "array", "items": { "type": "string" } }
  }
}
```

### Behavioral contract

| Input tier | `quality_gate.scored` | `score` | `rating` | Notes |
|------------|----------------------|---------|----------|-------|
| `insufficient` | `false` | `null` | `Không xếp hạng` | Flags MUST retain / echo quality flags |
| `limited` | `true` | number | one of 5 trade ratings | Reasons MUST be visible on `flags` or `quality_gate.reasons` |
| `full` | `true` | number | one of 5 | Normal path |
| absent (`None`) | `true` | number | one of 5 | Add `quality_tier_absent` on result flags for transparency |

## M8 validation contract

Given `upstream["m7"]` (M7 `result`):

- If `result.get("quality_gate", {}).get("scored") is False` (or equivalent: `score is None` / rating `"Không xếp hạng"` after gate):
  - M8 **MUST NOT** fail (or warn-as-fatal) on **score formula recomputation** checks.
  - M8 **MUST NOT** fail on **recommendation / rating threshold** checks that assume a numeric trade score and one of the five trade ratings.
  - M8 MAY still run unrelated checks (synthetic snapshot, stub modules, source traceability, etc.).
- If `quality_gate.scored` is true / absent gate on a legacy scored result: existing score-formula and rating-threshold checks apply as today.

## M9 report contract

Given `upstream["m7"]`:

- If `quality_gate.scored == false`: PDF MUST state ticker was not ranked and list reasons.
- If `tier == limited`: PDF MUST state scored-with-limitations and list reasons.
- MUST NOT invent numeric scores; copy from M7 only.
- **`result["score"]` MAY be `null`**: formatters MUST NOT use `{result['score']:.1f}` (or any float format) without a null guard — e.g. show `n/a` / `Không xếp hạng` when `score is None` (see current stub line in `src/stockai/m9_report/run.py` that formats Score).

## Downstream consumers of M7 `score` / `rating`

Any code that reads M7 result `score` or `rating` (CLI, pipeline JSON, Streamlit app, notebooks, tests) MUST tolerate:

- `score is None`
- `rating == "Không xếp hạng"`

Implementers MUST `grep` the repo for these call sites and list them in the PR description (see tasks.md).

## Pipeline short-circuit

**Out of scope for this slice** — do not add M2–M6 short-circuit in `pipeline.py` here.

## Out of scope

- Changing how M1 computes tiers or VNF enrich (`src/stockai/m1_data/**`).
- Point-in-time universe rebuild.
- Pipeline early-skip of M2–M6 when `insufficient`.
