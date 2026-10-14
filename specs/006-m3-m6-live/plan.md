# Implementation Plan: M3 + M6 Live on HOSE+HNX Snapshots

**Branch**: `006-m3-m6-live` | **Date**: 2026-10-13 | **Spec**: [spec.md](./spec.md)

**Feature dir**: `specs/006-m3-m6-live/`

**Input**: Feature specification from `/specs/006-m3-m6-live/spec.md`
(clarification Q1:B locked — R HIGH = RISK HIGH).

## Summary

Port hành vi M3 (điểm T) và M6 (điểm R) từ StockAI tham chiếu chỉ-đọc sang stub
hiện tại, giữ chữ ký `run(snapshot, upstream, cfg) -> dict` và `validate(..., "module_out")`.
Công thức đo chỉ số (MA/RSI/MACD/…; beta/vol/MDD/VaR/CVaR) giữ nguyên StockAI.
**Chỉ đảo mapping chấm điểm R** để khớp `docs/CONTRACTS.md` / M7 (`− lambda*R`,
`risk_gate`): R cao = rủi ro cao. M6 `status` = `ok` khi đủ điều kiện chấm (không
hard-code `partial`). Ngưỡng rubric T và hệ số mapping R nằm trong cấu hình
(`config/technical.yaml` ưu tiên theo OWNERSHIP N4). TDD fail-first offline; sau
implement smoke ~235 mã full+limited. Không sửa m1_data, pipeline, contracts,
CONTRACTS.md, M7; không commit/push trong pass này.

Chi tiết: [research.md](./research.md). Hợp đồng hành vi: [contracts/m3-m6-live.md](./contracts/m3-m6-live.md).

## Technical Context

**Language/Version**: Python 3.10+ (CI 3.11); `from __future__ import annotations`

**Primary Dependencies**: `pandas` (M3 rolling/EWM như StockAI); stdlib
`math`/`statistics`/`datetime` (M6). Không thêm thư viện mới vào
`requirements.txt` (N1). Tham chiếu chỉ-đọc:
`D:\Projects\StockAI\src\stockai\m3_technical\run.py`,
`D:\Projects\StockAI\src\stockai\m6_risk\run.py`.

**Storage**: Đọc snapshot JSON sẵn có (`data/snapshots_ext` / fixture tạm trong
test). Không ghi schema mới; không persist state module.

**Testing**: `pytest` offline — snapshot dựng tay (temp dir); MAY skip 1–2 case
snapshot thật nếu thiếu `data/snapshots_ext`. Bộ polarity-lock M6 bắt buộc.
Smoke batch ~235 mã là bước vận hành sau implement (không mạng trong CI).

**Target Platform**: Local CLI / CI (Windows + Linux); chạy module độc lập hoặc
qua pipeline hiện có (pipeline không sửa).

**Project Type**: Single-repo Python analysis modules (M3, M6) + tests + optional
config.

**Performance Goals**: Một lần `run` trên một snapshot đủ lịch sử trong vài trăm
ms–vài giây (pandas); smoke 235 mã tuần tự chấp nhận được trên máy dev.

**Constraints**:
- Scope file: `src/stockai/m3_technical/`, `src/stockai/m6_risk/`,
  `tests/test_m3_*.py`, `tests/test_m6_*.py`, và (nếu cần)
  `config/technical.yaml` và/hoặc `config/scoring.yaml`
- MUST NOT sửa `m1_data/*`, `pipeline.py`, `contracts/*`, `docs/CONTRACTS.md`, M7
- as_of: không dùng `date > as_of`; không forward-fill ngày thiếu (M6)
- Thiếu dữ liệu → `score=null` + flags; không bịa số
- Ngưỡng không hard-code trong mã nguồn (đọc cfg / technical.yaml)
- Q1:B: R cao = rủi ro cao; polarity-lock tests; docstring+config ghi phần đảo
- Không commit / push / Co-authored-by trong giai đoạn plan/implement trừ khi
  người dùng yêu cầu sau

**Scale/Scope**: 2 module stub → live; ~235 mã smoke (full+limited HOSE+HNX);
universe rộng hơn VN30 nhưng không đổi M1.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Gate | Status |
|-----------|------|--------|
| I. Data contract is law | Giữ `run(...)` + `validate(out, "module_out")`; không sửa schemas/CONTRACTS | PASS |
| II. `as_of` integrity | M3/M6 bỏ `date > as_of`; không forward-fill; fixture lookahead phải fail dùng | PASS |
| III. Data honesty | Thiếu lịch sử / chưa eligible → `score=null` + flags; không bịa điểm | PASS |
| IV. Numbers from code | T/R và mọi metrics do code tính; không LLM | PASS |
| V. Offline / reproducible | Test dựng tay offline; cùng snap+cfg → cùng score | PASS |
| VI. Ownership / small diffs | N4: chỉ `m3_technical/`, `m6_risk/`, tests, config technical (scoring chỉ nếu cần) | PASS |

**Post-design re-check**: Gates vẫn PASS. Complexity Tracking trống — không vi phạm
cần biện minh. Lệch có chủ đích so với StockAI (cực tính R; M6 status `ok`) đã
ghi trong Assumptions spec và [research.md](./research.md) R0/R1; không đụng M7.

## Project Structure

### Documentation (this feature)

```text
specs/006-m3-m6-live/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── m3-m6-live.md
├── checklists/
│   └── requirements.md
└── tasks.md                # /speckit-tasks (chưa tạo)
```

### Source Code (repository root)

```text
src/stockai/m3_technical/
└── run.py                  # port M3 live (thay stub)

src/stockai/m6_risk/
└── run.py                  # port M6 live + inverted R mapping (thay stub)

config/
└── technical.yaml          # ngưỡng rubric T + lookback/min_obs + mapping R (đã đảo)
# config/scoring.yaml       # chỉ đọc / ghi chú cực tính nếu thật sự cần; mặc định KHÔNG sửa (N5)

tests/
├── test_m3_technical.py    # fail-first: history, as_of, OHLC, stale, empty
└── test_m6_risk.py         # fail-first: align, beta≈1, eligible, polarity-lock
```

**Structure Decision**: Giữ layout module hiện có; không thêm package mới. Config
ngưỡng M3/M6 thuộc N4 → `config/technical.yaml` (tạo mới). `config/scoring.yaml`
giữ nguyên trừ khi implement chứng minh cần khóa chia sẻ — ưu tiên không đụng N5.

## Complexity Tracking

> Empty — no constitution violations requiring justification.
