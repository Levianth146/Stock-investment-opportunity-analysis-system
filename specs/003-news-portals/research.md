# Research: Vietnamese Financial News Portals (003)

**Scope**: M1 news enrichment only. Clarifications 2026-10-10 are binding.

## R1 — Where to plug into M1

**Decision**: Extend `fetch_news` in `src/stockai/m1_data/fetch.py` to call a new
`news_portals` module **after** vnstock + Google/RSS collection, then unified
dedupe → sort → `[:max_news]`. Recompute quality flags after merge (existing
`quality.apply` on snapshot already sees final `news` length if ordered correctly
in `build_snapshot`).

**Rationale**: Mirrors how Google News is already bolted on; keeps one news list
contract for downstream M5.

**Alternatives considered**:
- Separate post-process script only → easy to skip in universe path; weaker.
- Replace Google News → out of scope; Google remains parallel.

## R2 — Lookback window

**Decision**: Use the same `nstart` already computed in `fetch_news`
(`max(window_start, as_of - news_months*30 days)`), **not** the 5-year price window
alone. Portal article dates must satisfy `nstart <= published_at[:10] <= as_of`.

**Rationale**: Clarification A; aligns with Google RSS coverage intent (`news_months`).

**Alternatives considered**: `news_google_window_days` only (30d chunks) as sole
bound → too short vs 12-month news coverage; rejected for portal merge window.

## R3 — Merge, dedupe, cap

**Decision**:
1. Normalize URL (strip tracking params / fragments; lowercase host path rules TBD in impl).
2. Empty URL or literal `"n/a"` (case-insensitive) is **not** a dedupe key — title-only compare (vnstock/VCI often emits `url="n/a"`).
3. Normalize title (lower, collapse space, strip edge punctuation) — exact match = dup.
4. On dup Google/vnstock vs portal → keep portal item.
5. Sort by `published_at` descending (string ISO / date-only comparable via `[:10]` then full string).
6. Truncate to `cfg["max_news"]` (project default in `data_sources.yaml`).

**Rationale**: Clarification B + URL `n/a` rule; matches current final trim in `fetch_news`.

## R4 — Portal flags

**Decision**: Flags chỉ cho slug trong `news_portals_active` (mặc định `cafef`):
- `news_portal_ok:<slug>` iff ≥1 article from that portal remains **after date + dedupe filters and before** `max_news` truncate (an article later cut by the cap still counts toward ok)
- `news_portal_empty:<slug>` iff HTTP/parse OK but 0 articles after date/dedupe (before cap)
- `news_portal_failed:<slug>` on network/parse failure
- `news_portal_no_date_dropped:<n>` aggregate count
Empty must not by itself lower `quality_tier`. `quality_tier` still uses **final** `len(news)` after cap.
Không gắn ok/empty/failed cho cổng ngoài danh sách active (không gọi fetch).

**Rationale**: Clarification C / FR-007 + chẩn đoán HPG/FPT (chỉ CafeF phục vụ theo mã).

## R5 — published_at & summary

**Decision**:
- Date+time from article → ISO like existing news (`YYYY-MM-DDTHH:MM:SS` local when known).
- Date only → `YYYY-MM-DD`; never invent midnight.
- Look-ahead: `published_at[:10] <= as_of`.
- `summary`: prefer portal teaser; else body prefix truncated to **same limit as current news path** (`normalize_news` uses 500 chars for dataframe summaries; Google RSS path uses 300 in `parse_rss` — **Decision**: use **500** to match `normalize_news` when building portal items, documented in contract).

**Rationale**: Clarifications on summary + published_at; prefer the higher existing truncate used when materializing snapshot news items.

## R6 — Enablement & universe gate

**Decision**: `news_portals_enabled: false` in `config/data_sources.yaml`.
`news_portals_active: [cafef]` — `fetch_portals` chỉ chạy slug trong danh sách.
`fetch_universe.py` / `fetch_all` sets `cfg["universe_name"]` from `--universe`.
When `--tickers` or `--tickers-file` is used, set `cfg["universe_name"]="custom"` so portals stay off.
Portals run only if enabled **and** `universe_name in {"VN30","VN100"}` **and** slug ∈ `news_portals_active`.

**Rationale**: FR-004 + assumptions + deactivation VE/TNCK.

## R7 — HTTP politeness & cache

**Decision**: Configurable `news_portal_interval_sec`, `news_portal_retries`, timeout;
cache article HTML/JSON by normalized URL under gitignored cache dir; resume hits cache.
Per-portal try/except → failed flag, continue.

**Rationale**: FR-005; same spirit as `news_google_interval_sec`.

## R8 — Spike, fixtures, HTML parsing stack

**Decision**: Before locking parsers, spike each portal with **1 ticker** (search + article):
save **real** HTML under `tests/fixtures/news_portals/`; check `robots.txt` and site terms;
if a portal requires JS rendering, document and **drop it from FR-001 scope** for this version.
Fixtures MUST NOT be hand-authored HTML. Parsing: start with stdlib `html.parser` +
meta/`time` extraction; add `trafilatura` only if body extraction fails on real fixtures
for portals still in scope.

**Rationale**: FR-010; constitution V (offline) + YAGNI.

### Spike outcome (2026-10-10, cập nhật sau chẩn đoán HPG/FPT)

- **CafeF**: `tim-kiem.chn?keywords=<TICKER>` trả HTML tĩnh có link bài `…-188….chn`.
  Lọc `\\bTICKER\\b`; ưu tiên tải link đã nhắc mã trên title/anchor (trần 30 giữ nguyên).
  **Active mặc định** (`news_portals_active: [cafef]`).
- **VnEconomy**: HTML tĩnh `tim-kiem.htm?keyword=` trả **cùng ~5 link** cho mọi mã;
  kết quả tìm kiếm thật nạp bằng JS → không phục vụ yêu cầu theo mã.
  Parser giữ lại; **ngoài active**. Thêm lại khi có endpoint tìm theo mã hoặc RSS theo mã.
- **TinNhanhChungKhoan**: `tim-kiem.htm` 404; chuyên mục `/ngan-hang/` không theo mã —
  probe 30/30 bài irrelevant sau lọc. Parser giữ lại; **ngoài active**.
  Thêm lại khi có tìm kiếm/RSS theo mã.

## R9 — Third-party notice

**Decision**: If any scraper logic is adapted from vn-annual-report-miner, append
MIT attribution to `config/THIRD_PARTY_NOTICES.txt` before merge.

**Rationale**: FR-009.
