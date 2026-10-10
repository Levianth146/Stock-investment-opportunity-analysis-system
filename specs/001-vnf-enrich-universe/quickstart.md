# Quickstart: Validate FR-008 / FR-009

Proof the quality gate is consumed by scoring and report — **without** changing M1.

See also: [data-model.md](./data-model.md), [contracts/quality-gate.md](./contracts/quality-gate.md).

## Prerequisites

- Python venv with `pip install -r requirements.txt`
- Repo at project root
- Existing DEMO fixture: `fixtures/snapshot_DEMO.json`
- Implementation of plan items complete (helpers, M7 gate, schema, M9 surface, tests)

## 1. Regression — legacy DEMO still scores

```powershell
python main.py DEMO --profile long_term --snapshot fixtures/snapshot_DEMO.json
python -m pytest -q tests/test_pipeline_e2e.py
```

**Expect**: Pipeline completes; M7 returns a numeric `score` and one of the five trade ratings; no crash if snapshot lacks `quality_tier_*` (legacy/`absent`).

## 2. FR-008 — insufficient not ranked

Prepare a minimal offline snapshot copy (test helper or fixture) that is otherwise schema-valid and includes:

```text
meta.flags: ["quality_tier_insufficient", "quality_illiquid", ...]
```

Run unit tests:

```powershell
python -m pytest -q tests/test_m7_quality_gate.py
```

**Expect**:
- `result["score"] is None`
- `result["rating"] == "Không xếp hạng"`
- `result["quality_gate"]["scored"] is False`
- Reasons visible on `quality_gate.reasons` and/or `flags`

## 3. FR-009 — limited still scored, limitations visible

Same as above with:

```text
meta.flags: ["quality_tier_limited", "quality_news_few", ...]
```

**Expect**:
- Numeric `score`, trade rating in the five levels
- `quality_gate.scored is True`, `tier == "limited"`
- Limitation reasons appear on result flags / `quality_gate.reasons`
- PDF (M9) text includes tier/limitations (assert via test or open generated stub PDF lines)

## 4. Full offline suite

```powershell
python -m pytest -q
```

**Expect**: All green, including existing `tests/test_m1_vnf.py` and `tests/test_m1_wide.py` (M1 untouched).

## Non-goals for this quickstart

- Re-running VNF enrich or universe fetch against the network
- Editing `src/stockai/m1_data/**`
