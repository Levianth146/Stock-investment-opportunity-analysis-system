# Research: M7 Debate LLM (009)

**Scope**: Khóa thiết kế implement debate Bull/Bear qua LLM. Survey schema /
provider / `.env` / deps đã nhúng trong [spec.md](./spec.md). Clarifications
**Q1:B / Q2:B / Q3:A** khóa 2026-10-13. Không còn NEEDS CLARIFICATION.

Pass plan **không** gọi API live, không implement, không sửa `CONTRACTS.md`.

## R0 — Schema & CONTRACTS (Q1:B)

**Decision**:

- **MUST NOT** sửa `src/stockai/contracts/schemas.py`.
- `RESULT_SCHEMA` item `bull`/`bear`: `required: ["text"]` only; không khai
  `properties`; không `additionalProperties: false` → field `refs` được chấp nhận.
- Thử nghiệm specify (2026-10-13): `{"text":"ok","refs":["m4.pe","n12"]}` pass
  `Draft202012Validator` trên item schema.
- Lúc **implement**: thêm **một dòng** (hoặc một bullet) vào `docs/CONTRACTS.md`
  mục M7 mô tả convention `refs` (`mN.name` / `nK`). Không mở rộng JSON Schema.

**Rationale**: Giữ hợp đồng ổn định (constitution I); tránh chờ N1 patch schema.

**Alternatives considered**:
- Patch `schemas.py` thêm `refs` required → rejected (Q1:B).
- Object refs `{type,id}` → rejected (Q2:B flat strings).

**Sources**: `src/stockai/contracts/schemas.py` (`RESULT_SCHEMA`); spec survey (a).

## R1 — Convention `refs` flat + regex (Q2:B)

**Decision**:

Mỗi luận điểm scored:

```json
{"text": "…", "refs": ["m4.pe", "n12", "m2.roe"]}
```

| Loại | Regex | Ví dụ | Resolve |
|------|-------|-------|---------|
| Metric | `^m[0-9]+\.[A-Za-z0-9_]+$` | `m4.pe`, `m2.roe`, `m6.beta` | Khóa có trong compact payload allow-list **hoặc** `upstream["mN"].metrics` (value dict có `value`) |
| News | `^n[0-9]+$` | `n12` | Map ổn định `nK` → `snapshot.news[].id` đã expose trong payload |

Quy tắc grounding:

1. Chuỗi không khớp regex → **ungrounded**.
2. Khớp regex nhưng không resolve → **ungrounded**.
3. `refs` thiếu / rỗng trên item scored → fail validator (retry) hoặc M8 warn nếu lọt.
4. M8 phân loại **cùng regex**; message chứa `debate_ungrounded`; severity `warn`
   (không `fatal` chỉ vì thiếu refs).
5. **MUST** có unit test: classify (`m4.pe`, `n12`, `bad`, `m4`, `nX`) + resolve
   fail khi metric/news không tồn tại + M8 fixture grounded/ungrounded.

**Ánh xạ `nK` (ổn định)**: Khi build compact payload, gán tin theo thứ tự ổn định
(ví dụ index 1-based trong danh sách tin đã lọc gửi LLM): tin thứ `k` → id nội bộ
`n{k}` và bảng `news_ref_map: {"n12": "<real news.id>"}`. Validator/M8 resolve
qua map (hoặc tái dựng cùng quy tắc từ snapshot). LLM **chỉ** được trích `nK`
đã liệt kê trong payload.

**Ánh xạ `mN.name`**: Payload liệt kê `metrics_allowed: ["m2.roe", "m4.pe", …]`
lấy từ keys `upstream[mN].metrics` (và/hoặc alias điểm `m7` scores nếu expose —
ưu tiên metrics module). Resolve: `mN` ∈ {2..6} và `name` ∈ metrics keys của
module đó (hoặc trong allow-list payload).

**Rationale**: Flat string dễ prompt + regex M8; truy nguồn metric/news rõ.

**Alternatives considered**:
- `refs: [{kind, id}]` → phức tạp schema/prompt; rejected Q2:B.
- Dùng `news_id` UUID thẳng trong refs → dài, lệch convention metric; rejected.

## R2 — Transport REST only (Q3:A)

**Decision**: Cả Gemini và GLM gọi bằng **`requests`** HTTP. **Không** thêm SDK
mới vào `requirements.txt`. Không dùng `openai`/`anthropic` Python SDK cho path
debate 009 (dù package đã có).

| Provider | Model | Endpoint | Auth env | JSON mode |
|----------|-------|----------|----------|-----------|
| Google Gemini | `gemini-3.8-flash` | `POST https://generativelanguage.googleapis.com/v1beta/models/gemini-3.8-flash:generateContent` | `GEMINI_API_KEY` (header `x-goog-api-key`) | Structured output / JSON schema trong `generationConfig` (docs Google) |
| Z.AI GLM | `glm-5.3-flash` | `POST https://api.z.ai/api/paas/v4/chat/completions` | `ZAI_API_KEY` | `response_format: {"type":"json_object"}` |

**Rationale**: Spec Q3:A; giảm surface deps N1; thống nhất mock `requests` trong test.

**Alternatives considered**:
- `google-genai` / `zai-sdk` → rejected (FR-018).
- Dùng `openai` SDK với `base_url` Z.AI → tiện nhưng lệch Q3:A “requests only”;
  rejected cho feature này.

**Official docs** (cite):

- Gemini model: https://ai.google.dev/gemini-api/docs/models/gemini-3.8-flash
- Gemini generateContent REST / get-started: https://ai.google.dev/gemini-api/docs/generate-content/get-started
- Gemini structured output: https://ai.google.dev/gemini-api/docs/generate-content/structured-output
- Gemini rate limits: https://ai.google.dev/gemini-api/docs/rate-limits
- GLM Flash: https://docs.z.ai/guides/vlm/glm-5.3-flash
- Z.AI OpenAI-compatible base: https://docs.z.ai/guides/develop/openai/python
  (`base_url=https://api.z.ai/api/paas/v4/`, env `ZAI_API_KEY`)
- Z.AI structured / JSON mode: https://docs.z.ai/guides/capabilities/struct-output

**Repo facts**: `.env` đã gitignore; `requirements.txt` có `requests`, `openai`,
`anthropic` — feature 009 chỉ **dùng** `requests`.

## R3 — Unified `generate_json` + provider order

**Decision**:

```text
generate_json(prompt: str, schema_hint: dict | None, *, cfg, cache_key_parts) -> dict
```

- Đọc `config/llm.yaml`: `providers` order (ví dụ `[gemini, glm]`), model ids,
  timeout, max_retries per call, temperature≈0.
- Thiếu khóa env cho provider đang chọn → skip provider + flag
  (`llm_missing_key_<provider>`); thử provider tiếp theo nếu cấu hình failover;
  hết → caller fallback template.
- Parse body JSON từ text response; lỗi parse → raise/return error để orchestrator retry.
- Không log giá trị API key.

**Rationale**: FR-002 / FR-003 / FR-004; một chỗ mock trong test.

**Alternatives considered**: Gọi thẳng từng SDK trong `debate.py` → khó test /
khó failover → rejected.

## R4 — Compact payload

**Decision**: Payload gửi LLM chỉ gồm:

- `ticker`, `as_of`, `profile`, `rating`, `score` (từ M7 scoring đã tính — debate
  chạy **sau** scoring trong `run.py`)
- `scores` F/T/V/S/R (số hoặc null)
- `metrics` tóm tắt: map `mN.name` → value (+ unit ngắn) từ upstream m2–m6
- `evidence` rút gọn (vài dòng text + optional news_id đã map)
- `news`: list `{ref: "nK", id, title, summary?}` — **không** full body dài
- `metrics_allowed` / `news_refs` explicit cho prompt
- **MUST NOT** include full `prices.rows` / OHLCV dump

**Rationale**: FR-005; tiết kiệm token; giảm hallucination từ nhiễu.

**Alternatives considered**: Dump cả snapshot → đắt + dễ lệch as_of noise → rejected.

## R5 — Prompt bans + output shape

**Decision**: System/user prompt tiếng Việt (luận điểm tiếng Việt) MUST cấm:

- Bịa số không có trong payload
- Tự đặt giá mục tiêu / target
- Khẳng định không có evidence khi có metrics/news
- Trích `refs` ngoài allow-list / sai regex

Output JSON kỳ vọng:

```json
{
  "bull": [{"text": "...", "refs": ["m4.pe", "n12"]}],
  "bear": [{"text": "...", "refs": ["m6.beta"]}]
}
```

Mỗi phía **2–4** items. Prompt nêu rõ regex refs.

**Rationale**: FR-006 / FR-007; constitution IV.

## R6 — Validator, retry, template fallback

**Decision**:

1. Validate: mỗi phía len ∈ [2,4]; mỗi item `text` non-empty str; `refs` non-empty
   list[str]; mọi ref grounded (R1); heuristic chống số/target bịa (ví dụ cấm
   pattern giá mục tiêu / số không xuất hiện trong payload — chi tiết implement
   conservative).
2. Fail → retry LLM (tổng lần gọi LLM debate ≤ **3** mặc định, config) với
   feedback lỗi ngắn.
3. Hết retry / không có provider → **template fallback** deterministic:
   cùng snapshot+upstream+cfg → cùng text; gắn flag `debate_fallback_template`
   (và/hoặc `debate_llm_unavailable`); vẫn cố gắng `refs` hợp lệ từ metrics/news
   sẵn có; nếu không đủ tin/metrics → vẫn ≥2 items với refs tối thiểu resolve được
   hoặc đánh dấu để M8 warn (ưu tiên không crash M7).
4. Nhánh `quality_gate.scored == false`: **không** gọi LLM (đã xử lý trong
   `run.py`).

**Rationale**: FR-008 / FR-009 / SC-002; tái lập được.

**Alternatives considered**: Crash khi LLM lỗi → phá pipeline → rejected.
Stub cố định `[stub]` → rejected (giá trị feature).

## R7 — Disk cache

**Decision**:

- Dir: `data/llm_cache/` (thêm vào `.gitignore` lúc implement).
- Key: hash ổn định của `(ticker, as_of, model, prompt_version, payload_hash)`.
- Value: JSON `{bull, bear, meta}` (provider, cached_at).
- Hit → không HTTP; miss → gọi provider rồi ghi.
- Cache corrupt → bỏ qua + flag `debate_cache_ignored`; vẫn chạy.

**Rationale**: FR-010 / US2; tiết kiệm quota.

**Alternatives considered**: Chỉ memory cache → mất giữa process → rejected cho batch.

## R8 — M8 `debate_ungrounded`

**Decision**: Trong `m8_validate/run.py`, sau `_check_m7` (hoặc trong đó):

- Duyệt `upstream["m7"].bull` / `bear`.
- Bỏ qua hoặc nới khi `quality_gate.scored == false` (quality_gate text không
  bắt buộc refs) — **warn không bắt** nhánh insufficient vì thiếu refs.
- Item scored thiếu refs / ref invalid / không resolve → issue
  `severity: "warn"`, message chứa `debate_ungrounded`, `where` như `m7.bull[i]`.
- **MUST NOT** đổi ngưỡng fatal công thức điểm / rating / target.

**Rationale**: FR-013; OWNERSHIP N6 — ghi rõ trong PR.

## R9 — Batch script & smoke (post-implement)

**Decision**:

- `scripts/run_debate_batch.py`: đọc list ticker + as_of + snapshots dir; gọi
  scoring path hoặc chỉ `run_debate` với upstream fixture/module outs; in thống kê
  llm_ok / fallback / cache_hit / errors.
- Smoke từng provider: 1 lần `generate_json` khi có khóa; thiếu khóa → ghi nhận
  rõ (không fail CI).
- Specify/plan **không** chạy live.

**Rationale**: FR-011 / SC-006 / SC-007.

## R10 — Out of scope (khóa)

- `scoring.py` / `scoring.yaml` / trọng số / risk_gate
- M1–M6, `pipeline.py`, `main.py`
- `schemas.py`
- SDK mới / fine-tune / RAG ngoài snapshot+upstream
- Viết lại M9 PDF layout

## R11 — Research resolution summary

| Topic | Status |
|-------|--------|
| Schema refs | Resolved Q1:B — no schemas.py; CONTRACTS 1 line at implement |
| refs format | Resolved Q2:B — flat strings + regex |
| HTTP transport | Resolved Q3:A — requests REST both providers |
| Model IDs / URLs | Resolved from official docs (R2) |
| nK / mN mapping | Resolved design R1 |
| Retry / fallback / cache | Resolved R6–R7 |
| M8 warn | Resolved R8 |
| Live API in plan | N/A — deferred to post-implement acceptance |

**No NEEDS CLARIFICATION remaining.**
