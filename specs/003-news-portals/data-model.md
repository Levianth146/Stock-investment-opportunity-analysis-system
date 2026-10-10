# Data Model: News Portals (003)

## Entities

### Config (data_sources.yaml additions)

| Key | Type | Default | Notes |
|-----|------|---------|-------|
| `news_portals_enabled` | bool | `false` | Master switch |
| `news_portals_active` | list[str] | `[cafef]` | Slugs to fetch; flags only for these |
| `news_portal_interval_sec` | float | e.g. 1.0 | Delay between requests |
| `news_portal_retries` | int | e.g. 2 | Limited retries |
| `news_portal_cache_dir` | path | under raw/cache | URL → cached payload |
| `universe_name` | str | set by runner | Gate VN30/VN100 |

Existing: `max_news`, `news_months`, `news_google_*` unchanged.

### PortalArticle (intermediate, pre-contract)

| Field | Type | Rules |
|-------|------|-------|
| `title` | str | required |
| `url` | str | canonical portal URL (not Google redirect) |
| `published_at` | str | ISO datetime **or** `YYYY-MM-DD` |
| `source` | str | display name (CafeF / VnEconomy / …) |
| `summary` | str \| null | teaser or body[:500]; null only if no text |
| `portal_slug` | str | `cafef` \| `vneconomy` \| `tinnhanhchungkhoan` |

**Drop if**: missing day-resolution date; year-only; `published_at[:10] > as_of`;
`published_at[:10] < nstart`.

### News Item (snapshot.news — existing contract)

| Field | Required | Notes |
|-------|----------|-------|
| `id` | yes | Stable id (hash of url or existing scheme) |
| `title` | yes | |
| `url` | yes | Portal origin URL |
| `source` | yes | Human outlet name |
| `published_at` | yes | Per R5 |
| `summary` | no | null only if no text |

Traceability: `sources[]` entry with `source_id` per portal (e.g. `src_news_cafef`).

### ArticleCacheEntry

| Field | Notes |
|-------|-------|
| key | Normalized URL |
| payload | HTML or extracted fields |
| fetched_at | optional |

### PortalRunResult

| Field | Notes |
|-------|-------|
| `articles` | list[PortalArticle] after date filter |
| `status` | `ok` \| `empty` \| `failed` |
| `no_date_dropped` | int |

## Merge pipeline

```text
vnstock news + Google/RSS items
        │
        ▼
portal articles (`news_portals_active` only, fault-isolated)
        │
        ▼
date filter + per-portal drop counts
        │
        ▼
dedupe — if URL empty/"n/a": title-only; else URL norm OR title norm;
prefer portal on conflict
        │
        ▼
emit ok/empty from post-filter pre-cap counts; failed from errors
        │
        ▼
sort published_at DESC → truncate to max_news
        │
        ▼
quality_tier from final len(news) (+ other quality rules)
```

## Flag rules

| Flag | When |
|------|------|
| `news_portal_ok:<slug>` | ≥1 article from slug after date/dedupe, **before** `max_news` cut |
| `news_portal_empty:<slug>` | Portal call succeeded; 0 articles after date/dedupe |
| `news_portal_failed:<slug>` | Network/parse failure |
| `news_portal_no_date_dropped:<n>` | Count of undated drops (aggregate) |

`empty` does not by itself change quality tier thresholds.

## Validation

- Fixtures = real HTML from spike (not hand-written).
- Cover: dated article, undated drop, as_of day with/without time,
  Google dup → portal wins, vnstock `url="n/a"` title-dup → portal wins,
  ok still set when articles exist pre-cap but are truncated out,
  one portal failed, flag off / `universe_name=custom` → no portal flags,
  inactive slug not fetched / no `news_portal_*` for that slug.
