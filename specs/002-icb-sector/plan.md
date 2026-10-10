# Implementation Plan: ICB Sector Enrichment

**Branch**: `002-icb-sector` (git: `feat/icb-sector`) | **Date**: 2026-10-10 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/002-icb-sector/spec.md`

**Note**: Clarifications session 2026-10-10 đã khóa cascade peers, tách tài chính,
parent YAML (không CSV L1), `sector == ""`, và cờ `peers_finance_nonfinance_blocked`.
Skeleton `icb_sector.py` + wiring fetch/universe **đã có** nhưng **chưa đủ** so với
spec đã clarify — plan này đóng gap, không đụng `contracts/schemas.py` / M2–M9.

## Summary

Nạp ngành ICB Supersector (L2) từ `config/listing_icb.csv` qua
`config/icb_sector_map.yaml`, điền/đối chiếu `company.sector` (tiếng Anh) và
chuẩn hóa sàn trong M1; khi `icb_sector_enabled` trên **universe rộng**, gán peers
theo cascade L2 → parent YAML → market với tách tài chính/phi tài chính; **giữ
nguyên** danh sách peers VN30 hiện hành. Chi tiết quyết định: [research.md](./research.md).

## Technical Context

**Language/Version**: Python 3.10+ (CI 3.11); `from __future__ import annotations`

**Primary Dependencies**: stdlib `csv` + existing `pyyaml` / pytest; không thêm package

**Storage**: Config files (`listing_icb.csv`, `icb_sector_map.yaml`); snapshot JSON
on disk — no DB

**Testing**: `pytest` offline only (`tests/test_m1_icb_sector.py` + regression
`tests/test_m1_universe.py` / `tests/test_m1_build.py`); no network

**Target Platform**: Local CLI / CI (Windows + Linux)

**Project Type**: Single-repo Python CLI pipeline; change surface = M1 + config

**Performance Goals**: Load listing once (lru_cache); peer assign O(n²) worst-case
acceptable for VN100/HOSE batch with existing `fill_peers_dir` path

**Constraints**:
- M1 only (`src/stockai/m1_data/`, `config/`, `tests/test_m1_*.py`)
- MUST NOT edit `src/stockai/contracts/schemas.py` or M2–M9
- `company.sector` remains required **string** (`""` when missing, never JSON null)
- Không đoán ngành; thiếu map → `""` + flags
- Listing không point-in-time (đã ghi THIRD_PARTY_NOTICES)

**Scale/Scope**: ~toàn bộ mã niêm yết trong CSV; peers theo universe đang chạy;
ngưỡng `min_peer_group_size` mặc định 10

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Gate | Status |
|-----------|------|--------|
| I. Data contract is law | Không đổi schemas; `sector` vẫn string; snapshot vẫn `validate(..., "snapshot")` | PASS |
| II. `as_of` integrity | Listing tĩnh (không PIT) đã disclose; không dùng dữ liệu giao dịch sau `as_of` cho sector | PASS (bias đã ghi notices) |
| III. Data honesty | Không bịa ngành; giữ vnstock khi có; mismatch/missing → flags; không gộp tài chính–phi TC im lặng | PASS |
| IV. Numbers from code | Chỉ map config + logic peers; không LLM | PASS |
| V. Offline / reproducible | Tests fixture/map giả; không gọi mạng | PASS |
| VI. Ownership / small diffs | Chỉ N2 M1 + config; PR nhỏ theo gap | PASS |

**Post-design re-check**: Gates giữ nguyên. Complexity Tracking trống — thêm
bảng parent theo Supersector trong YAML là bắt buộc theo clarify (tránh CSV L1
gộp BĐS vào Tài chính), không phải abstraction thừa.

## Project Structure

### Documentation (this feature)

```text
specs/002-icb-sector/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── icb-sector-flags.md
└── tasks.md             # /speckit-tasks — not created here
```

### Source Code (repository root)

```text
config/
├── listing_icb.csv              # nguồn ICB (MIT) — đã có
├── icb_sector_map.yaml          # map L2→EN, parent theo Supersector, finance set, aliases
└── THIRD_PARTY_NOTICES.txt      # đã có
config/data_sources.yaml         # icb_sector_enabled, icb_sector_map

src/stockai/m1_data/
├── icb_sector.py                # load listing, apply_to_company, resolve_peer_group (+ finance filter)
├── fetch.py                     # gọi apply_to_company khi enabled
└── universe.py                  # fill_peers: VN30 path vs wide ICB cascade

tests/
├── test_m1_icb_sector.py        # map VN30, flags, Real Estate≠Banks, empty sector validate
└── test_m1_universe.py          # regression peers VN30 không đổi khi cascade tắt / path VN30
```

**Structure Decision**: Giữ layout M1 hiện có; mở rộng `icb_sector.py` + YAML
(parent theo Supersector) thay vì module mới.

## Complexity Tracking

> No constitution violations requiring justification.

## Gap vs code hiện tại (input cho `/speckit-tasks`)

| Spec (đã clarify) | Code hiện tại | Việc cần làm |
|-------------------|---------------|--------------|
| Parent từ YAML theo Supersector; Real Estate → parent `Real Estate` | `parent_en` từ `industry_to_en[CSV L1]` → BĐS thành `Financials` | Thêm `supersector_parent_en` (hoặc tương đương); bỏ phụ thuộc CSV L1 cho peers |
| Cascade: L1 chỉ khi parent ≠ L2 và \|parent\| ≥ 10 | Cascade gần đúng nhưng parent sai | Sửa `resolve_peer_group` theo rule clarify |
| Tách Banks/Insurance/Financial Services vs phi TC; cờ `peers_finance_nonfinance_blocked` | Chưa có | Thêm filter + cờ |
| `sector == ""` không làm peer; chính nó → market + `sector_small_group` | Chưa đủ | Enforce trong resolve/assign |
| VN30 peers giữ nguyên | `icb_sector_enabled` mặc định True có thể đổi peers VN30 | Gate: cascade ICB chỉ universe rộng; path VN30 giữ logic cũ |
| Test BCM/VHM/VIC/VRE ↛ Banks | Chưa có / chưa đủ | Thêm test |
| Snapshot mã ngoài CSV vẫn validate | Cần assert tường minh | Thêm test |
