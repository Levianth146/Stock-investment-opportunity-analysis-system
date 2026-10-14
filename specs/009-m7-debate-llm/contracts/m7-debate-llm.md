# Contract: M7 Debate LLM (Bull/Bear)

**Owners**: N5 (`m7_scoring/`, `config/llm.yaml`, `src/stockai/llm/`); N6
(`m8_validate/` warn only — ghi PR). **Does not** change
`src/stockai/contracts/schemas.py`. At implement: **one line** in
`docs/CONTRACTS.md` describing `refs` convention.

## Signatures

```text
# unchanged caller in m7_scoring/run.py
run_debate(snapshot: dict, upstream: dict, cfg: dict) -> tuple[list[dict], list[dict]]

# new provider façade
generate_json(...) -> dict   # see research R3; returns parsed JSON object
```

M7 `run(snapshot, upstream, cfg) -> dict` (result) **signature unchanged**.
M8 `run(snapshot, upstream, cfg) -> dict` (validation) **signature unchanged**.

Each debate item (scored path):

```json
{"text": "<non-empty Vietnamese>", "refs": ["m4.pe", "n12"]}
```

## Scope boundary

| Allowed | Forbidden |
|---------|-----------|
| `src/stockai/m7_scoring/debate*.py` (replace stub) | `src/stockai/m7_scoring/scoring.py` |
| `src/stockai/llm/**` (new) | `config/scoring.yaml` |
| `config/llm.yaml` | `src/stockai/contracts/schemas.py` |
| `src/stockai/m8_validate/run.py` (grounding warn only) | M1–M6 module bodies |
| `scripts/run_debate_batch.py` | `pipeline.py`, `main.py` |
| `tests/test_m7_debate*`, `tests/test_llm_*`, `tests/test_m8_*` | New SDK in `requirements.txt` |
| `data/llm_cache/` + `.gitignore` entry | Commit secrets / cache contents |
| One-line `docs/CONTRACTS.md` (implement) | Live API calls in CI pytest |

## Locked clarifications

| ID | Decision |
|----|----------|
| **Q1:B** | No `schemas.py` change; one CONTRACTS.md line at implement |
| **Q2:B** | `refs: string[]` flat; metric `m<number>.<name>`; news `n<number>`; M8 regex |
| **Q3:A** | Gemini + GLM via `requests` REST only |

## Refs convention (normative)

| Kind | Regex | Example |
|------|-------|---------|
| Metric | `^m[0-9]+\.[A-Za-z0-9_]+$` | `m4.pe`, `m2.roe` |
| News | `^n[0-9]+$` | `n12` |

- Invalid regex → ungrounded.
- Valid regex but unresolved in payload map / upstream metrics / news ids → ungrounded.
- M8: `warn` + message containing `debate_ungrounded`; **not** formula `fatal`.

## Provider contract (REST)

### Gemini

- Model: `gemini-3.8-flash`
- `POST https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent`
- Auth: env `GEMINI_API_KEY` → header `x-goog-api-key`
- Prefer JSON / structured output per Google docs
- Client: **`requests` only**

### GLM (Z.AI)

- Model: `glm-5.3-flash`
- Base: `https://api.z.ai/api/paas/v4/` → `POST .../chat/completions`
- Auth: env `ZAI_API_KEY`
- `response_format: {"type":"json_object"}`
- Client: **`requests` only** (OpenAI-compatible URL shape, not OpenAI SDK)

### Shared

- Missing key → skip provider + flag; no print of secrets
- Timeouts / 429 → limited retry then failover/fallback
- Compact payload only (no full OHLCV)

## Behavior contract

| Concern | Requirement |
|---------|-------------|
| Count | 2–4 bull and 2–4 bear on scored path |
| Language | `text` Vietnamese |
| Prompt bans | No invented numbers; no LLM target price; no fake refs |
| Validate | Code checks length, text, refs regex+resolve |
| Retry | ≤3 LLM attempts (config) then template |
| Fallback | Deterministic template from upstream; flag `debate_fallback_template` |
| Cache | Disk under `data/llm_cache/`; key includes ticker, as_of, model, prompt_version, payload hash |
| Quality gate | `scored == false` → existing quality_gate bull/bear; no LLM |
| Scoring | Identical scores/rating for same inputs vs pre-feature (debate-only change) |
| Schema | `validate(result, "result")` passes; schemas.py untouched |
| M8 | Grounding warn only; no change to score/rating/target fatals |

## Batch script contract

```text
scripts/run_debate_batch.py
  --as-of YYYY-MM-DD
  [--snapshots-dir ...]
  [--tickers A,B,... | --limit 10]
  [--config config/llm.yaml]
```

- Must not crash the whole batch on one ticker failure
- Print counts: llm_ok / fallback / cache_hit / error
- Live provider calls only when keys present and flag/env allows — not in pytest

## Test contract (offline)

| Suite | Must prove |
|-------|------------|
| Mock HTTP | `requests` patched; 0 real network |
| Happy path | 2–4 items, refs grounded, result validates |
| Bad JSON / bad refs | retry then template non-empty |
| Regex | `m4.pe`/`n12` ok; `bad`/`m4`/`nX` invalid |
| Resolve | Unknown metric/news → ungrounded |
| Cache | Second call 0 HTTP |
| Missing key | fallback + flags; no secret leak |
| Quality gate | insufficient → no LLM |
| M8 | ungrounded fixture → `debate_ungrounded` warn; grounded → absent |
| Scoring | score/rating unchanged vs baseline fixture |
| Full pytest | green offline after implement |

## Downstream

- **M9**: displays `bull`/`bear` text (and MAY show refs later) — layout rewrite out of scope
- **M8**: new warn only
- **Pipeline**: unchanged call order M7 → M8
