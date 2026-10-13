# Implementation Plan: M7 Debate (Bull/Bear) qua LLM

**Branch**: `009-m7-debate-llm` | **Date**: 2026-10-13 | **Spec**: [spec.md](./spec.md)

**Feature dir**: `specs/009-m7-debate-llm/`

**Input**: Feature specification from `/specs/009-m7-debate-llm/spec.md`
(clarifications khóa Q1:B / Q2:B / Q3:A; thay stub `debate.py`; provider
`src/stockai/llm/` qua `requests` REST; không đổi scoring / M1–M6 / pipeline /
`schemas.py`).

## Summary

Thay stub `src/stockai/m7_scoring/debate.py` bằng luồng debate thật: compact
payload → `generate_json` (Gemini `gemini-3.8-flash` và/hoặc GLM `glm-5.3-flash`
qua **`requests` REST only**) → validator code (`text` + `refs` phẳng
`mN.name` / `nK`) → retry ≤3 → template fallback xác định → cache đĩa
`data/llm_cache/`. Giữ chữ ký `run_debate(...) -> (bull, bear)` để `m7_scoring/run.py`
không đổi flow scoring. M8 thêm `warn` `debate_ungrounded` (regex + resolve).
Lúc implement: **một dòng** `docs/CONTRACTS.md` mô tả convention `refs`;
**MUST NOT** sửa `schemas.py`, `scoring.py`, `scoring.yaml`, M1–M6, `pipeline.py`,
`main.py`, `requirements.txt` (không SDK mới).

Chi tiết: [research.md](./research.md). Hợp đồng hành vi:
[contracts/m7-debate-llm.md](./contracts/m7-debate-llm.md).

## Technical Context

**Language/Version**: Python 3.10+ (CI 3.11); `from __future__ import annotations`

**Primary Dependencies**: `requests` (đã có) cho **cả** Gemini và GLM REST.
`pyyaml` đọc `config/llm.yaml`. **Không** thêm Google GenAI / zai-sdk / dependency
LLM mới. Package `openai`/`anthropic` hiện có **không** dùng cho feature này
(Q3:A).

**Storage**:
- Cache debate: `data/llm_cache/` (local; MUST gitignore; không commit)
- Config: `config/llm.yaml` (N5) — mở rộng providers gemini/glm, model ids, order,
  retry, cache path, prompt version
- Secrets: chỉ env `GEMINI_API_KEY`, `ZAI_API_KEY` (+ `.env` gitignored)
- Snapshots đọc-only cho batch/smoke (ví dụ `data/snapshots_ext*`)

**Testing**: `pytest` offline — mock `requests` (không mạng, không cần khóa).
Suite mới: `tests/test_m7_debate*.py`, `tests/test_llm_*.py`, mở rộng
`tests/test_m8_*.py` cho `debate_ungrounded` + regex refs. Smoke provider +
batch ≥10 ticker = acceptance **sau** implement (không chạy trong pass plan).

**Target Platform**: Local CLI / CI (Windows + Linux). Debate gắn trong M7
`run`; batch qua `scripts/run_debate_batch.py`.

**Project Type**: Single-repo Python — module M7 debate + package `stockai.llm`
+ config + M8 warn + batch script + offline tests.

**Performance Goals**: Một lần `run_debate` offline (cache/template) vài ms–vài
trăm ms; live LLM phụ thuộc mạng (timeout cấu hình). Cache hit → 0 HTTP.
Batch 10 mã: không crash hàng loạt; báo cáo ok/fallback/cache.

**Constraints**:
- **Q1:B** — không sửa `schemas.py`; implement thêm 1 dòng `CONTRACTS.md`
- **Q2:B** — `refs: string[]`; metric `^m[0-9]+\.[A-Za-z0-9_]+$`; news `^n[0-9]+$`;
  M8 classify bằng regex; tests bắt buộc
- **Q3:A** — Gemini + GLM chỉ `requests` REST; không SDK mới trong `requirements.txt`
- MUST NOT sửa `scoring.py`, `config/scoring.yaml`, M1–M6, `pipeline.py`, `main.py`
- LLM không sinh số / không đặt giá mục tiêu; chỉ diễn giải từ upstream + news
- Payload compact: không dump `prices.rows` đầy đủ
- Quality gate `scored == false` → giữ bull/bear quality_gate; **không** gọi LLM
- Bí mật không in / không commit
- Không commit/push trong pass plan; không gọi API live trong plan

**Scale/Scope**: 1 stub debate → LLM+fallback; 2 providers REST; 1 cache dir;
1 batch script; M8 warn mới; không đổi công thức điểm / contracts schema.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Gate | Status |
|-----------|------|--------|
| I. Data contract is law | Giữ `result` validate; `refs` extra props đã pass schema; **không** sửa `schemas.py`; 1 dòng CONTRACTS lúc implement | PASS |
| II. `as_of` integrity | Debate chỉ dùng snapshot/upstream đã lọc as_of; không tải giá/tin mới hơn as_of | PASS |
| III. Data honesty | Validator + M8 bắt refs resolve; thiếu/sai → retry/fallback/warn; không bịa số | PASS |
| IV. Numbers from code | Scoring/target không đụng; LLM chỉ text+refs; prompt cấm số/target tự bịa | PASS |
| V. Offline / reproducible | Pytest mock `requests`; template fallback deterministic; cache keyed ổn định | PASS |
| VI. Ownership / small diffs | N5: `m7_scoring/debate*`, `stockai/llm/`, `config/llm.yaml`, tests M7/llm. M8 warn = N6 (ghi PR). Script batch + 1 dòng CONTRACTS = deliverable feature (phối hợp N1 nếu cần) | PASS (xem Complexity) |

**Post-design re-check**: Gates vẫn PASS sau Phase 1. Không còn NEEDS
CLARIFICATION. Complexity Tracking ghi cross-ownership cần nêu trong PR.

## Project Structure

### Documentation (this feature)

```text
specs/009-m7-debate-llm/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── m7-debate-llm.md
├── checklists/
│   └── requirements.md
└── tasks.md                # /speckit-tasks (chưa tạo — ngoài pass plan)
```

### Source Code (repository root)

```text
src/stockai/m7_scoring/
├── debate.py                 # thay stub: orchestrate payload→LLM→validate→fallback
├── debate_validate.py        # (đề xuất) regex refs + resolve + length 2–4
└── debate_template.py        # (đề xuất) fallback xác định từ upstream

src/stockai/llm/              # NEW — lớp provider thống nhất
├── __init__.py
├── generate.py               # generate_json(...) -> dict
├── providers/
│   ├── gemini_rest.py        # POST generateContent via requests
│   └── glm_rest.py           # POST .../chat/completions via requests
├── cache.py                  # disk cache data/llm_cache/
└── payload.py                # compact debate payload + id map nK / mN.name

src/stockai/m8_validate/
└── run.py                    # thêm _check_debate_grounding → debate_ungrounded

config/
└── llm.yaml                  # mở rộng: providers, models, order, retry, cache, prompt_version

scripts/
└── run_debate_batch.py       # batch ≥10 ticker; báo cáo ok/fallback/cache

data/
└── llm_cache/                # local only; gitignore

tests/
├── test_m7_debate*.py        # run_debate, validator, retry, fallback, quality_gate
├── test_llm_*.py             # generate_json, cache, missing key, mock HTTP
└── test_m8_*.py              # debate_ungrounded + regex classify (mở rộng)
```

**Structure Decision**: Giữ chỗ gọi `run_debate` trong `m7_scoring/run.py`; thay
thân `debate.py` + helper cùng package. Provider tách `stockai.llm` (dùng lại
cho M5 sau này nếu cần). M8 chỉ thêm kiểm tra grounding; không đổi fail công thức.
Không đổi `pipeline.py`.

## Complexity Tracking

| Violation / tension | Why Needed | Simpler Alternative Rejected Because |
|---------------------|------------|--------------------------------------|
| Sửa `m8_validate/` (N6) trong feature M7 (N5) | FR-013 / SC-004 — warn `debate_ungrounded` bắt buộc | Chỉ validate trong M7 → M8 vẫn im lặng khi result ungrounded lọt xuống |
| Script dưới `scripts/` (OWNERSHIP N1) | FR-011 / SC-007 batch acceptance | Chỉ pytest → không chứng minh batch 10 mã ops |
| 1 dòng `docs/CONTRACTS.md` (thường N1) lúc implement | Q1:B / FR-016 — convention docs không đổi schema | Sửa `schemas.py` → rejected (Q1:B) |
