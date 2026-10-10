# Contract: M1 news portals (wire format & ops)

**Owner**: N2 (M1). **Does not** change `src/stockai/contracts/schemas.py`.
News array items MUST still validate under existing `snapshot.news` schema.

## Configuration

| Key | Default | Meaning |
|-----|---------|---------|
| `news_portals_enabled` | `false` | Enable portal fetch |
| `news_portals_active` | `[cafef]` | Slugs `fetch_portals` runs; flags only for these |
| `universe_name` | runner-set | Portals only if `VN30` or `VN100` |
| `max_news` | existing | Cap after merge |
| `news_months` | existing | Contributes to `nstart` lookback with Google path |

## Portal slugs (canonical in flags)

| Slug | Display `source` (example) | Scope |
|------|----------------------------|-------|
| `cafef` | CafeF | **Active mặc định** (`tim-kiem.chn?keywords=` + lọc `\\bTICKER\\b`; ưu tiên title nhắc mã) |
| `vneconomy` | VnEconomy | Parser giữ; **không active** — HTML tĩnh search cùng link mọi mã / kết quả JS |
| `tinnhanhchungkhoan` | TinNhanhChungKhoan | Parser giữ; **không active** — chuyên mục không theo mã |

Re-enable VE/TNCK only when a per-ticker search endpoint or RSS exists; add slug to `news_portals_active`.

## `source_id` / `sources[]`

Each portal that contributes ≥1 article SHOULD register e.g.:

- `id`: `src_news_cafef` (pattern `src_news_<slug>`)
- `name` / `url` / `fetched_at` / optional `note`

## Flags (`meta.flags`)

See [data-model.md](../data-model.md). Tokens are opaque strings for M2–M9.

## Internal function sketch (non-normative for schemas)

```text
fetch_portals(ticker, company_name, nstart, as_of, cfg, fetch=...) 
  -> (articles: list[dict], flags: list[str])

merge_news(existing, portal_articles, max_news) 
  -> list[dict]   # contract news items
```

Tests inject `fetch` to return fixture HTML bytes (no network).

## Dedup

1. If URL is empty or `"n/a"` (case-insensitive) → **do not** use URL as a key; compare normalized title only  
2. Else if URL normalized equal → duplicate  
3. Else if title normalized equal → duplicate  
4. Prefer portal item over Google/vnstock item  

## Flags (ok vs empty)

Chỉ gắn cho slug trong `news_portals_active` (không gọi / không cờ cho cổng ngoài danh sách):

- `news_portal_ok:<slug>`: ≥1 kept article from that portal after date/dedupe filters, **before** `max_news` truncate  
- `news_portal_empty:<slug>`: success path with 0 articles after those filters  
- `news_portal_failed:<slug>`: network/parse only  

## Universe gate

Portals run only when `news_portals_enabled` and `universe_name in {"VN30","VN100"}`.
CLI `--tickers` / `--tickers-file` MUST set `universe_name="custom"`.
Within that gate, only slugs in `news_portals_active` are fetched.

## Fixtures

HTML under `tests/fixtures/news_portals/` MUST be captured from real pages during spike;
do not hand-author markup. Portals requiring JS rendering are out of scope for this version.

## published_at comparison

Look-ahead and window: compare `published_at[:10]` to `as_of` / `nstart` as `YYYY-MM-DD` strings.
