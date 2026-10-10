# Implementation Plan: Vietnamese Financial News Portals (M1)

**Branch**: `003-news-portals` | **Date**: 2026-10-10 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/003-news-portals/spec.md` (clarifications 2026-10-10 locked).

## Summary

Bổ sung bước lấy tin trực tiếp từ CafeF, VnEconomy, TinNhanhChungKhoan vào M1 khi
`news_portals_enabled` (mặc định **false**) và `universe_name` ∈ {VN30, VN100}
`--tickers`/`--tickers-file` → `universe_name=custom` (không portal). Spike thật từng
cổng → fixture HTML thật; cổng cần JS → loại khỏi phạm vi. Gộp với Google/vnstock:
URL rỗng/`n/a` không làm khóa trùng (chỉ title); URL hợp lệ → URL hoặc title;
ưu tiên bản cổng; sắp mới nhất rồi cắt `max_news`. Cờ ok/empty theo số bài **sau lọc
ngày/trùng, trước cắt trần**. Ngày đủ độ phân giải ngày; look-ahead
`published_at[:10] <= as_of`; lookback = `nstart` tin Google (`news_months`), không
`window_start` 5 năm. Không đổi `schemas.py` / M2–M9. Chi tiết: [research.md](./research.md).

## Technical Context

**Language/Version**: Python 3.10+ (CI 3.11); `from __future__ import annotations`

**Primary Dependencies**: stdlib (`urllib`, `html.parser` / `xml`, `re`, `json`);
reuse `news_extra.http_get` pattern. Optional `trafilatura` **only if** stdlib
extraction proves insufficient after fixture spike — prefer no new dep.

**Storage**: Snapshot JSON; article cache on disk keyed by URL (under existing
`data/raw*` / dedicated cache dir, gitignored); HTML fixtures under `tests/fixtures/news_portals/`

**Testing**: `pytest` offline only — inject fetch stubs + saved HTML; no network in CI

**Target Platform**: Local CLI / CI (Windows + Linux)

**Project Type**: Single-repo Python CLI pipeline; change surface = M1 + config + tests

**Performance Goals**: Per-ticker portal fetch with configurable delay/retry; batch
VN30/VN100 acceptable with resume cache (no rigid SLA beyond FR-005)

**Constraints**:
- M1 only (`src/stockai/m1_data/`, `config/`, `scripts/fetch_universe.py` if needed for universe name, `tests/test_m1_*.py`)
- MUST NOT edit `src/stockai/contracts/schemas.py` or M2–M9
- No embedded secrets; env vars only if a portal needs a key
- Default off: VN30 behavior unchanged when flag false
- Fixtures = real HTML from spike; check robots/terms; drop JS-only portals
- THIRD_PARTY_NOTICES if reusing vn-annual-report-miner code

**Scale/Scope**: Up to 3 portals (post-spike) × VN30/VN100; merge into existing `max_news` (config currently 800)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Gate | Status |
|-----------|------|--------|
| I. Data contract is law | News items match existing schema; no schema change | PASS |
| II. `as_of` integrity | Drop undated / year-only; filter `published_at[:10] <= as_of`; same news lookback as Google path | PASS |
| III. Data honesty | No invented dates/hours; flags for fail/empty/dropped; prefer portal URL over Google redirect | PASS |
| IV. Numbers from code | N/A for news text; quality_tier still code-computed from counts | PASS |
| V. Offline / reproducible | Fixture HTML + stubbed HTTP in tests | PASS |
| VI. Ownership / small diffs | N2 M1 + config only | PASS |

**Post-design re-check**: Gates hold. Complexity Tracking empty — one new module + wiring
into `fetch_news` is YAGNI-appropriate vs scattering scrapers in `fetch.py`.

## Project Structure

### Documentation (this feature)

```text
specs/003-news-portals/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── news-portals.md
└── tasks.md             # created via /speckit-tasks
```

### Source Code (repository root)

```text
config/data_sources.yaml          # news_portals_enabled: false (+ delay/retry/cache keys)
config/THIRD_PARTY_NOTICES.txt    # if code reused

src/stockai/m1_data/
├── news_portals.py               # NEW: search+article parse, cache, merge helpers
├── news_extra.py                 # unchanged Google RSS (reuse http_get if useful)
├── fetch.py                      # fetch_news: call portals when enabled + universe allow
├── quality.py                    # re-assess after merged news count (if not already post-merge)
└── universe.py / scripts/fetch_universe.py  # pass universe name into cfg for FR-004

tests/
├── fixtures/news_portals/        # HTML search + article pages per portal
└── test_m1_news_portals.py       # offline unit/integration

# OUT OF SCOPE
src/stockai/contracts/schemas.py
src/stockai/m2_* … m9_*
```

**Structure Decision**: New `news_portals.py` beside `news_extra.py`; thin hook in
`fetch_news` after Google/RSS collection, before final `[:max_news]` trim.

## Complexity Tracking

> No constitution violations requiring justification.
