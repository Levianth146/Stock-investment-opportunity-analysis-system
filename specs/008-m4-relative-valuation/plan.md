# Implementation Plan: M4 Relative Valuation (điểm V)

**Branch**: `008-m4-relative-valuation` (git ưu tiên tạo `008-m4-valuation` từ `develop` khi implement) | **Date**: 2026-10-13 | **Spec**: [spec.md](./spec.md)

**Feature dir**: `specs/008-m4-relative-valuation/`

**Input**: Feature specification from `/specs/008-m4-relative-valuation/spec.md`
(survey khóa PE/PB từ snapshot; EPS TTM ≤4Q; VND thô; sector ICB; bank `is_bank`;
score null → M7 `V_missing_used_neutral`; sector stats prebuilt JSON).

## Summary

Thay stub `src/stockai/m4_valuation/run.py` bằng định giá tương đối PE/PB so
**median ngành** (winsorize) từ `data/valuation_sector_stats.json` do
`scripts/build_m4_sector_stats.py` sinh từ universe full+limited cùng `as_of`.
Điểm **V cao = rẻ/hấp dẫn** (percentile / map phân vị cấu hình). Ngân hàng
(`company.is_bank`): **P/B chân chính**. Thiếu dữ liệu → `score=null` + flags;
**MUST NOT** ép 50 (M7 gắn `V_missing_used_neutral`). `target` từ relative
multiples; DCF tắt mặc định. Giữ `run(snapshot, upstream, cfg) -> dict` +
`validate(..., "module_out")`. Không sửa M1, contracts, M3/M5/M6, pipeline.
TDD fail-first; smoke ~235; không commit/push trong pass plan.

Chi tiết: [research.md](./research.md). Hợp đồng hành vi:
[contracts/m4-relative-valuation.md](./contracts/m4-relative-valuation.md).

## Technical Context

**Language/Version**: Python 3.10+ (CI 3.11); `from __future__ import annotations`

**Primary Dependencies**: stdlib + `pandas`/`pyyaml` đã có trong repo (pattern
giống M3 load YAML). Không thêm thư viện mới vào `requirements.txt` (N1).
Không phụ thuộc LLM. `upstream["m2"]` tùy chọn — relative V không bắt buộc điểm F.

**Storage**:
- Đọc snapshot JSON (`data/snapshots_ext` / fixture test)
- Đọc/ghi artifact prebuilt `data/valuation_sector_stats.json` (sinh bởi script;
  có thể gitignore nếu lớn)
- Config: `config/valuation.yaml` (OWNERSHIP N3)

**Testing**: `pytest` offline — snapshot dựng tay (temp); case 5 mã thật
VCB/FPT/HPG/VIC/SSI skip nếu thiếu file. Smoke ~235 full+limited là bước ops
sau implement (không mạng trong CI).

**Target Platform**: Local CLI / CI (Windows + Linux); chạy M4 độc lập hoặc qua
pipeline hiện có (pipeline **không** sửa).

**Project Type**: Single-repo Python analysis module (M4) + config + build script
+ tests + optional smoke.

**Performance Goals**: Một lần `run` trên một snapshot trong vài chục–vài trăm ms
(không tối ưu nặng); build sector stats trên ~235 mã chấp nhận được trên máy
dev; smoke 235 tuần tự OK.

**Constraints**:
- Scope: `src/stockai/m4_valuation/`, `tests/test_m4_*.py`,
  `config/valuation.yaml`, `scripts/build_m4_sector_stats.py`,
  `data/valuation_sector_stats.json` (generated), optional smoke script
- MUST NOT sửa `m1_data/*`, `contracts/*`, `pipeline.py`, `main.py`, M3, M5, M6,
  `docs/CONTRACTS.md`
- as_of: không dùng `date`/`published_at` > `as_of`
- Thiếu dữ liệu → `score=null` + flags; không bịa số; không ép 50
- Ngưỡng winsorize / trọng số bank / stale / min sample đọc từ config
- Evidence tiếng Việt; `news_id` không bắt buộc
- Không commit / push / Co-authored-by trừ khi người dùng yêu cầu sau

**Scale/Scope**: 1 module stub → live relative valuation; sector stats cache cho
universe FL (~235); smoke cùng tập; không đổi M1/contracts.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Gate | Status |
|-----------|------|--------|
| I. Data contract is law | Giữ `run(...)` + `validate(out, "module_out")` + `target`; không sửa schemas/CONTRACTS | PASS |
| II. `as_of` integrity | Lọc giá `date<=as_of`, BCTC `published_at<=as_of`; fixture lookahead không vào PE/PB | PASS |
| III. Data honesty | Thiếu input / thiếu median ngành → `score=null` + flags; không bịa median từ peers im lặng | PASS |
| IV. Numbers from code | PE/PB/V/target do code tính; DCF off mặc định; không LLM | PASS |
| V. Offline / reproducible | Fixture tay offline; cùng snap+cfg+sector stats → cùng V; pytest không mạng | PASS |
| VI. Ownership / small diffs | N3: chỉ `m4_valuation/`, tests M4, `config/valuation.yaml`, script build + artifact | PASS |

**Post-design re-check**: Gates vẫn PASS sau Phase 1. Complexity Tracking trống —
không vi phạm cần biện minh. Tương tác M7 (`V_missing_used_neutral`) chỉ đọc
hành vi hiện có; **không** sửa M7.

## Project Structure

### Documentation (this feature)

```text
specs/008-m4-relative-valuation/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── m4-relative-valuation.md
├── checklists/
│   └── requirements.md
└── tasks.md                # /speckit-tasks (chưa tạo)
```

### Source Code (repository root)

```text
src/stockai/m4_valuation/
└── run.py                      # live relative PE/PB → điểm V + target (thay stub)

config/
└── valuation.yaml              # winsorize, trọng số bank/non-bank, stale, min_n, DCF off

scripts/
├── build_m4_sector_stats.py    # sinh data/valuation_sector_stats.json từ FL + as_of
└── smoke_m4_batch.py           # optional: phân bố V trên ~235 mã

data/
└── valuation_sector_stats.json # artifact generated (local; MAY gitignore)

tests/
└── test_m4_*.py                # fail-first: polarity rẻ→cao, bank PB, null≠50, as_of, stale, fallback EPS
```

**Structure Decision**: Giữ package `m4_valuation` hiện có; thêm config N3 + script
build thống kê ngành. Không đổi contracts/schemas. Không import M3/M5/M6.

## Complexity Tracking

> Empty — no constitution violations requiring justification.
