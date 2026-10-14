# Data Model: M4 Relative Valuation (008)

No new JSON Schema types in `src/stockai/contracts/schemas.py`. Inputs stay under
existing `snapshot`; output stays `module_out` (+ M4 `target`).

## Entities

### 1. Valuation Module Output (M4)

| Field | Type | Rules |
|-------|------|-------|
| `module` | string | `"m4"` |
| `status` | enum | `ok` \| `partial` \| `error` (không còn `stub` sau implement) |
| `score` | number\|null | **V** ∈ [0, 100]; **cao = rẻ**; thiếu dữ liệu chặn → **`null` (không 50)** |
| `metrics` | object | Keys xem [research.md](./research.md) R7; mỗi value `{value, unit[, note]}` |
| `evidence` | array | `text` tiếng Việt; `news_id` không bắt buộc |
| `flags` | string[] | Catalog research R7 |
| `target` | object\|null | `{base, bull, bear, method, assumptions}` khi suy được implied price |

**Relationships**: Đọc `meta`, `company`, `prices`, `financials`, `peers` (phụ),
`sources` (trace). `upstream["m2"]` optional — không bắt buộc để chấm V relative.

### 2. Relative Multiple Inputs (internal)

Derived inside `run` / build script; không persist vào snapshot.

| Field | Source | Validation |
|-------|--------|------------|
| `as_of` | `meta.as_of` | parse date |
| `price_close` | last `prices.rows` với `date<=as_of`, close>0 | else PE/PB fail |
| `eps_used` | TTM 4Q hoặc annual fallback (R1) | phải `> 0` để PE |
| `eps_source` | `"ttm_4q"` \| `"annual"` | gắn note/flag |
| `total_equity` | quý ưu tiên rồi năm, `published_at<=as_of` | finite |
| `shares` | `company.shares_outstanding` | `> 0` |
| `book_ps` | `total_equity / shares` | `> 0` để PB |
| `pe` / `pb` | price/eps, price/book_ps | bỏ chân nếu ≤0 hoặc chia 0 |
| `sector` | `company.sector` | string EN |
| `is_bank` | `company.is_bank is True` | chọn trọng số |

### 3. Sector Valuation Stats (persisted JSON)

File: `data/valuation_sector_stats.json` (path override qua config).

| Field | Type | Rules |
|-------|------|-------|
| `version` | int | tăng khi đổi công thức build |
| `as_of` | string | ngày universe build |
| `built_at` | string | ISO timestamp |
| `universe` | string | e.g. `"full+limited"` |
| `winsor.low_pct` / `high_pct` | number | mặc định 0.05 / 0.95 |
| `min_sector_n` | int | ngưỡng mẫu |
| `sectors.<name>.n_pe` / `n_pb` | int | cỡ mẫu sau lọc hợp lệ |
| `sectors.<name>.median_pe` / `median_pb` | number\|null | median sau winsorize; null nếu không đủ |

**Relationships**: Build script **ghi**; M4 runtime **chỉ đọc**. Khóa sector =
`company.sector` trên snapshot (ICB map đã gắn M1 — feature này không sửa map).

### 4. Valuation Config

Persisted as `config/valuation.yaml` (N3). Runtime merge `cfg.m4` overlay.

| Section | Purpose |
|---------|---------|
| `sector_stats_path` | đường dẫn JSON |
| `stale_calendar_days` | cờ stale giá |
| `winsor` / `min_sector_n` | build + validate runtime |
| `weights.bank` / `weights.non_bank` | blend PE/PB |
| `cheapness_map` | map ratio → điểm chân (cao = rẻ) |
| `target_bands` | bull/bear multipliers |
| `enable_dcf` | mặc định `false` |

### 5. Peer Snapshot Row (reference only)

| Field | Use in M4 |
|-------|-----------|
| `peers[].pe` / `pb` | OPTIONAL evidence note; MUST NOT replace sector median |
| `peers[].ticker` | OPTIONAL so sánh phụ |

## Validation rules (from requirements)

1. Không dùng `date` / `published_at` > `as_of`.
2. Đơn vị tính nhất quán **VND thô** (`financials.unit` + giá đã scale M1).
3. `score=null` khi không còn chân + median hợp lệ; **không** gán 50.
4. Bank: PB primary — thiếu PE không chặn nếu PB đủ.
5. `target.method` phản ánh relative khi DCF off.
6. Mọi metrics value qua `{value, unit}`; validate `module_out`.

## State transitions (M4 `run`)

```text
start → validate snapshot / meta.as_of
  → load valuation.yaml + sector stats JSON
  → filter prices & financials by as_of
  → derive pe/pb (TTM/annual, equity, shares)
  → resolve sector medians
  → no usable legs ──────────► score=null, target=null, partial + flags
  → compute leg scores (cheapness) + blend weights
  → fill metrics, evidence (VI), target relative
  → flags empty ─────────────► status=ok, score=V
  → flags phụ (stale/fallback) ► status=partial, score=V (nếu vẫn chấm được)
```

## Flag catalog

Xem bảng đầy đủ [research.md](./research.md) R7 — canonical tokens dùng chung
test + smoke + docs feature.
