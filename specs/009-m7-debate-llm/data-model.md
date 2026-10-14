# Data Model: M7 Debate LLM (009)

No new JSON Schema types in `src/stockai/contracts/schemas.py`. Debate items
remain under existing `result.bull` / `result.bear` (required `text` only;
`refs` accepted as extra property). M8 `validation` issues stay
`{severity, message, where?}`.

## Entities

### 1. DebateItem

Persisted on `analysis_result` (`result` schema) as elements of `bull[]` / `bear[]`.

| Field | Type | Rules |
|-------|------|-------|
| `text` | string | Non-empty; tiếng Việt; không chứa giá mục tiêu / số bịa |
| `refs` | `string[]` | **Bắt buộc** trên nhánh scored (convention); phẳng |

**Convention `refs` (Q2:B)**:

| Pattern | Meaning | Resolve against |
|---------|---------|-----------------|
| `^m[0-9]+\.[A-Za-z0-9_]+$` | Metric module field | Compact allow-list / `upstream[mN].metrics[name]` |
| `^n[0-9]+$` | News slot in payload | `news_ref_map[nK]` → `snapshot.news[].id` |

Cardinality scored path: **2–4** items mỗi phía bull và bear.

**Relationships**: Consumed by M8 (grounding), M9 (display). Produced by
`run_debate` (LLM hoặc template).

### 2. DebatePayload (compact, ephemeral)

Built per call; hashed for cache; sent to LLM; **not** written into `result`.

| Field | Type | Rules |
|-------|------|-------|
| `ticker` / `as_of` / `profile` | string | From snapshot / M7 |
| `score` / `rating` / `scores` | number\|null / string / object | After `compute_score` |
| `metrics` | object | Map `mN.name` → `{value, unit?}` subset |
| `metrics_allowed` | `string[]` | Explicit allow-list for refs |
| `news` | array | `{ref: "nK", id, title, summary?}` |
| `news_ref_map` | object | `nK` → real `news.id` (validator/M8) |
| `evidence_summaries` | array | Short texts only |
| `prompt_version` | string | Bump when prompt text changes |

**MUST NOT** include full `prices.rows`.

### 3. ProviderResult (ephemeral)

Raw JSON dict from `generate_json` before validation.

| Field | Type | Rules |
|-------|------|-------|
| `bull` / `bear` | array | Expected shape DebateItem[]; may be invalid until validated |

### 4. DebateCacheEntry (disk)

Path: `data/llm_cache/<hash>.json` (local; gitignore).

| Field | Type | Rules |
|-------|------|-------|
| `key` | string | Hash(ticker, as_of, model, prompt_version, payload_hash) |
| `bull` / `bear` | DebateItem[] | Post-validate or raw+validated snapshot |
| `provider` | string | `gemini` \| `glm` \| `cache` |
| `model` | string | e.g. `gemini-3.8-flash` |
| `created_at` | string | ISO timestamp |
| `flags` | `string[]` | optional |

### 5. LLM Config

File: `config/llm.yaml` (N5). Extend existing stub (`provider`/`model` anthropic).

| Section | Purpose |
|---------|---------|
| `debate.providers` | Ordered list e.g. `[gemini, glm]` |
| `debate.gemini.model` | default `gemini-3.8-flash` |
| `debate.glm.model` | default `glm-5.3-flash` |
| `debate.glm.base_url` | `https://api.z.ai/api/paas/v4/` |
| `debate.temperature` | prefer `0` |
| `debate.max_llm_attempts` | default `3` |
| `debate.timeout_sec` | HTTP timeout |
| `debate.cache_dir` | default `data/llm_cache` |
| `debate.prompt_version` | string for cache key |
| env key names | document `GEMINI_API_KEY`, `ZAI_API_KEY` (values never in file) |

### 6. ValidationIssue `debate_ungrounded`

Emitted by M8 into `validation.issues[]`.

| Field | Value |
|-------|--------|
| `severity` | `"warn"` |
| `message` | Contains substring `debate_ungrounded` (+ chi tiết ref/item) |
| `where` | e.g. `m7.bull[0]`, `m7.bear[2]` |

**State**: Does not by itself force formula fatal; contributes to overall
`status` via existing warn aggregation.

### 7. Flags (M7 `result.flags` additions)

| Flag | When |
|------|------|
| `debate_fallback_template` | Template path used |
| `debate_llm_unavailable` | No usable provider/key |
| `debate_cache_hit` | Optional; or only in batch report |
| `debate_cache_ignored` | Corrupt cache skipped |
| `llm_missing_key_gemini` / `llm_missing_key_glm` | Missing env for provider |

(Exact flag names MAY be refined at implement if tests lock them — keep stable
in contract.)

## Validation rules (from requirements)

1. Scored debate: 2–4 bull, 2–4 bear; each `text` + non-empty grounded `refs`.
2. Regex classify metric vs news vs invalid (tests).
3. Resolve fail → ungrounded.
4. `validate(result, "result")` still passes with `refs` present; schemas unchanged.
5. Quality-gate insufficient branch: existing texts without refs OK; M8 skip
   strict grounding for that branch.
6. Scoring numbers unchanged by debate path.

## State transitions (debate orchestration)

```text
[quality_gate unscored] → return early in run.py (no LLM)
         │
         ▼
[build payload] → [cache hit?] --yes→ [return cached bull/bear]
         │ no
         ▼
[generate_json provider order] → [validate]
         │ fail
         ▼
[retry ≤ max] → still fail → [template fallback + flags]
         │ ok
         ▼
[write cache] → [return bull/bear]
```

## Relationships diagram (logical)

```text
snapshot + upstream(m2..m6) + cfg
        │
        ▼
   DebatePayload ──► generate_json ──► ProviderResult
        │                                   │
        │                                   ▼
        │                          DebateItem[] (validated)
        │                                   │
        ├──────── news_ref_map / metrics ───┤
        │                                   ▼
        │                          result.bull / result.bear
        │                                   │
        └──────────────────────────► M8 debate_ungrounded
```
