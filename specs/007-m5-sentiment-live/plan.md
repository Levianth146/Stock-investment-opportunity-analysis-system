# Implementation Plan: M5 Sentiment Live (điểm S)

**Branch**: `007-m5-sentiment` | **Date**: 2026-10-13 | **Spec**: [spec.md](./spec.md)

**Feature dir**: `specs/007-m5-sentiment-live/`

**Input**: Feature specification from `/specs/007-m5-sentiment-live/spec.md`
(ambiguous seed locked CEO/HCM/VND/AAA; DRC rejected; scan rule corrected;
lookback default 30; smoke measures insufficient_news at 30 and 60).

## Summary

Thay stub M5 bằng heuristic chấm điểm S từ **tiêu đề tin** trong cửa sổ
`as_of`/`lookback`, giữ chữ ký `run(snapshot, upstream, cfg) -> dict` và
`validate(..., "module_out")`. Lexicon cụm từ + bộ lọc liên quan (mã/tên,
khử trùng, chứng quyền, tiêu đề nhiều mã, mã mơ hồ đã duyệt) đọc từ config
mới (`config/sentiment.yaml`, `sentiment_lexicon.yaml`, `news_aliases.yaml`).
Không LLM (`llm_enabled: false`). NFC giữ chữ **đ**. `status=ok` khi đủ
ready; thiếu → `score=null` + `m5_insufficient_news` + `partial`. TDD
fail-first; smoke ~235 full+limited; báo cáo insufficient_news lookback 30
vs 60 (half-life 14; default config giữ 30). Không sửa m1_data, pipeline,
contracts, CONTRACTS.md, M7; không commit/push.

Chi tiết: [research.md](./research.md). Hợp đồng hành vi:
[contracts/m5-sentiment-live.md](./contracts/m5-sentiment-live.md).

## Technical Context

**Language/Version**: Python 3.10+ (CI 3.11); `from __future__ import annotations`

**Primary Dependencies**: stdlib (`re`, `unicodedata`, `math`, `datetime`,
`collections`); `yaml` (đã có trong project như M3). Không thêm thư viện mới
vào `requirements.txt` (N1). Tham chiếu chỉ-đọc:
`D:\Projects\StockAI\src\stockai\m5_sentiment\run.py` — tái dùng ý tưởng,
**không copy** (lỗi encoding đ; status=partial cứng; hard-code FPT).

**Storage**: Đọc snapshot JSON sẵn có (`data/snapshots_ext` / fixture tạm).
Config mới dưới `config/`. Gold CSV nhãn trống dưới `fixtures/` hoặc
`config/`. Không persist state module.

**Testing**: `pytest` offline — snapshot dựng tay; MAY skip 1–2 case snapshot
thật nếu thiếu. Smoke batch ~235 mã sau implement (không mạng trong CI).

**Target Platform**: Local CLI / CI (Windows + Linux); chạy module độc lập
hoặc qua pipeline hiện có (pipeline không sửa).

**Project Type**: Single-repo Python analysis module (M5) + tests + config.

**Performance Goals**: Một lần `run` trên một snapshot trong vài trăm ms;
smoke 235 mã tuần tự chấp nhận được trên máy dev.

**Constraints**:
- Scope: `src/stockai/m5_sentiment/`, `tests/test_m5_*.py`,
  `config/sentiment.yaml`, `config/sentiment_lexicon.yaml`,
  `config/news_aliases.yaml`, gold CSV, optional `scripts/smoke_m5_batch.py`
- MUST NOT sửa `m1_data/*`, `pipeline.py`, `contracts/*`, `docs/CONTRACTS.md`, M7
- as_of: không dùng tin `published_at > as_of`
- Thiếu → `score=null` + flags; không bịa số; không LLM
- Ambiguous config = seed đã duyệt only; đề xuất scan chỉ in ra, không ghi im lặng
- Không commit / push / Co-authored-by

**Scale/Scope**: 1 module stub → live; ~235 mã smoke (full+limited HOSE+HNX).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Gate | Status |
|-----------|------|--------|
| I. Data contract is law | Giữ `run(...)` + `validate(out, "module_out")`; không sửa schemas/CONTRACTS | PASS |
| II. `as_of` integrity | Chỉ tin `published_at <= as_of` trong lookback; fixture future phải bị loại | PASS |
| III. Data honesty | Thiếu tin / chưa ready → `score=null` + flags; evidence có `news_id` | PASS |
| IV. Numbers from code | S và metrics do code/lexicon; `llm_enabled: false` | PASS |
| V. Offline / reproducible | Test dựng tay offline; cùng snap+cfg → cùng score | PASS |
| VI. Ownership / small diffs | N5: chỉ `m5_sentiment/`, tests M5, config sentiment mới | PASS |

**Post-design re-check**: Gates vẫn PASS. Complexity Tracking trống.

## Project Structure

### Documentation (this feature)

```text
specs/007-m5-sentiment-live/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── m5-sentiment-live.md
├── checklists/
│   └── requirements.md
└── tasks.md
```

### Source Code (repository root)

```text
src/stockai/m5_sentiment/
└── run.py                  # heuristic S live (thay stub)

config/
├── sentiment.yaml          # lookback, half-life, min_*, ambiguous, S coeffs, llm_enabled
├── sentiment_lexicon.yaml  # positive/negative phrases + weights
└── news_aliases.yaml       # company name aliases / finance keywords for ambiguous

fixtures/
└── m5_gold_labels.csv      # nhãn trống

tests/
└── test_m5_sentiment.py    # fail-first offline

scripts/
└── smoke_m5_batch.py       # optional local smoke (~235)
```

**Structure Decision**: Một file `run.py` (pattern M3/M6); config tách 3 file
theo yêu cầu user để chỉnh lexicon/aliases độc lập.

## Complexity Tracking

Không có vi phạm constitution cần biện minh.
