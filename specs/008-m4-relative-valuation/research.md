# Research: M4 Relative Valuation (008)

**Scope**: Khóa thiết kế implement M4 relative PE/PB từ snapshot offline.
Survey thật `data/snapshots_ext` as_of 2026-10-08 + `scripts/_survey_m4_fields.py`
đã nhúng trong [spec.md](./spec.md). Không còn NEEDS CLARIFICATION.

## R0 — Ánh xạ field snapshot → input định giá

**Decision**:

| Input | Nguồn khóa | Quy tắc |
|-------|------------|---------|
| `as_of` | `meta.as_of` | Bắt buộc parse được; thiếu → null score + flag |
| Giá đóng | `prices.rows[*].close` | Chỉ `date <= as_of`, close finite > 0; lấy phiên **mới nhất** sau lọc |
| EPS TTM | `sum(net_income_parent\|net_income)` 4 quý liên tiếp / `shares` | Xem R1 — **không** cộng `items.eps` quý |
| EPS năm | `financials.annual[].items.eps` | Fallback khi thiếu 4Q NI liên tiếp; `eps_source=annual` |
| Vốn chủ | `financials.*.items.total_equity` | Gồm minority; ưu tiên quý mới nhất ≤ as_of; kế hoạch chuyển `parent_equity` khi M1 có |
| Shares | `company.shares_outstanding` | Finite > 0 |
| Sector | `company.sector` | Khóa lookup bảng ngành (ICB → EN đã gắn M1) |
| Bank | `company.is_bank` | `True` → nhánh trọng số bank |
| Unit | `financials.unit` | Kỳ vọng `"VND"`; số BCTC **VND thô** (không chia 1000 trong M4) |
| Peers | `peers[]` | Chỉ evidence/đối chiếu; **không** thay median ngành |

**PE** = `price_close / eps_used` khi `eps_used > 0`.
**PB** = `price_close / (total_equity / shares_outstanding)` khi book/share > 0.
**Book/share** cùng đơn vị VND với giá.

**Rationale**: Survey FL 235/235 có close, shares, equity; PE tính được 232/235;
không invent khóa financials mới (CONTRACTS).

**Alternatives considered**:
- Dùng `peers[].pe/pb` làm bội số mã → rejected (peers là nhóm khác; median ngành chuẩn từ prebuilt).
- Top-level `price` / `eps_ttm` → không tồn tại trên snapshot.

## R1 — Quy tắc EPS TTM và fallback năm (fix round 1)

**Decision**:

1. Lọc quý: `published_at` parse được và `<= as_of`; period dạng `YYYYQn`.
2. Dedup theo period; lấy **4 quý mới nhất**; bắt buộc **liên tiếp** (period tiến đúng 1 quý, không lỗ). Không liên tiếp / thiếu 4 → flag `m4_eps_quarter_gap`.
3. `eps_ttm = sum(net_income_parent else net_income của 4Q) / shares_outstanding` khi đủ NI từng quý và shares > 0. **`eps_source=ttm_ni`**. **STOP** cộng `items.eps` quý (thường 0 hoặc mang EPS năm — ví dụ HPG `[1781,0,1973,0]`).
4. Ngược lại: dùng **EPS năm** mới nhất `published_at <= as_of` và `eps != 0`; gắn `m4_eps_ttm_fallback_annual`; `eps_source=annual`.
5. Nếu cả TTM và năm không cho `eps_used > 0` → không tính PE; flag `m4_pe_unavailable`; vẫn có thể chấm bằng PB.
6. Không dùng quý/năm `published_at > as_of` (lookahead).

**Rationale**: Sum EPS quý lệch >15% trên 63/191 mã vs NI-based; HPG PE 5.37 (sai) vs ~7.3 (NI).

**Alternatives considered**:
- Cộng `items.eps` 4Q → rejected (dữ liệu quý bẩn).
- TTM với `<4` quý (annualize ×4/n) → bịa số → rejected (III).
- Coi TTM = 0 là PE vô hạn → crash / điểm méo → rejected.

## R2 — Winsorize và median ngành (prebuilt)

**Decision**:

- Script `scripts/build_m4_sector_stats.py` đọc universe **full+limited** cùng `as_of`,
  tính PE/PB từng mã bằng **cùng quy tắc R0/R1** (shared helpers hoặc copy có test).
- Theo `company.sector`: thu thập mẫu PE hợp lệ (`eps_used > 0`) và PB hợp lệ (`book > 0`).
- **Winsorize** trước median: cắt phân vị thấp/cao cấu hình (mặc định **5% / 95%**)
  trên từng phân phối PE và PB **trong sector**; rồi lấy **median**.
- Ghi `n_pe`, `n_pb`, `median_pe`, `median_pb`, `as_of`, `version`, tham số winsor.
- Runtime M4 **chỉ đọc** JSON; không tự tính median từ `peers[]`.
- `min_sector_n` (mặc định đề xuất **5**): nếu `n` chân đang dùng < ngưỡng → không dùng median chân đó; flag thiếu thống kê.

**Rationale**: Spec FR-005 / US2; tái lập được; tránh median lệch outlier.

**Alternatives considered**:
- Median ad-hoc từ peers mỗi mã → không chuẩn hóa ngành → rejected.
- Mean thay median → nhạy outlier hơn sau winsor → rejected cho MVP.

## R3 — Trọng số ngân hàng vs phi ngân hàng + chấm percentile

**Decision**:

| Nhóm | Trọng số mặc định (config) | Ghi chú |
|------|----------------------------|---------|
| `is_bank == true` | `w_pb = 1.0`, `w_pe = 0.0` | P/B chân chính; PE bỏ qua trừ khi config bật phụ |
| Non-bank | `w_pe = 0.5`, `w_pb = 0.5` | Chuẩn hóa lại nếu một chân thiếu |

**Chấm điểm (cao = rẻ) — fix round 1 = percentile**:

1. Sector stats lưu `pe_sorted` / `pb_sorted` (winsorize) — runtime **không** quét lại snapshots.
2. Điểm chân = `100 * (1 - percentile_midrank(multiple, sorted_vals))` (multiple thấp → điểm cao).
3. Evidence vẫn dạng "P/E = x so median ngành y (z% …)".
4. `V = round(sum(w_i * score_leg_i) / sum(w_i), 2)` trên các chân còn hiệu lực.
5. Sector `n < min_sector_n`: fallback median/phân phối `__market__`; **chỉ chân PE** (`w_pb=0`); flags `m4_sector_fallback` + `m4_pb_leg_dropped`.
6. Trọng số theo `company.sector` trong `config/valuation.yaml` (`weights.by_sector`); bank `is_bank` → pe0/pb1.
7. P/B dùng `total_equity` (gồm minority); flag `m4_pb_uses_total_equity` khi `|NI_parent-NI|/|NI|>5%`.
8. **Ý nghĩa điểm V**: chỉ **định giá tương đối** (rẻ/đắt so median ngành qua PE/PB). **Không** phản ánh chất lượng kinh doanh, tăng trưởng, hay rủi ro vận hành.
9. `by_sector` trong yaml map tường minh cả ngành cân bằng 0.5/0.5 (`Industrial Goods & Services`, `Chemicals`, `Media`, `Travel & Leisure`). Flag `m4_sector_weight_default` **chỉ** khi `company.sector` không có trong `by_sector` (và không phải bank).

Khi bank thiếu PE: vẫn chấm nếu PB đủ. Khi non-bank chỉ còn một chân: renormalize
trọng số chân còn lại.

**Rationale**: Spec FR-003/006; CONTRACTS rẽ nhánh bank; SC-001/SC-004.

**Alternatives considered**:
- Ép cả bank dùng PE → nhiễu EPS ngân hàng / EPS≤0 → rejected.
- Hard-code ngưỡng trong Python → lệch FR-003 / VI YAGNI config.

## R4 — Định dạng cache `data/valuation_sector_stats.json`

**Decision** (schema logic — không đổi `contracts/schemas.py`):

```json
{
  "version": 1,
  "as_of": "2026-10-08",
  "built_at": "2026-10-13T00:00:00+07:00",
  "universe": "full+limited",
  "winsor": {"low_pct": 0.05, "high_pct": 0.95},
  "min_sector_n": 5,
  "sectors": {
    "Banks": {
      "n_pe": 18,
      "n_pb": 23,
      "median_pe": 8.5,
      "median_pb": 1.4,
      "flags": []
    },
    "Technology": {
      "n_pe": 12,
      "n_pb": 12,
      "median_pe": 15.2,
      "median_pb": 3.1,
      "flags": []
    }
  }
}
```

- Đường dẫn mặc định: `data/valuation_sector_stats.json`; override bằng
  `cfg.valuation.sector_stats_path` hoặc khóa trong `config/valuation.yaml`.
- Thiếu file / JSON lỗi / sector vắng / `n < min_sector_n` → không bịa median;
  `score=null` hoặc chỉ chân còn median hợp lệ; flags `m4_sector_stats_missing` /
  `m4_sector_median_unavailable`.
- Script build MUST idempotent cho cùng input snapshots + cfg winsor.

**Rationale**: Spec US2; artifact tách runtime khỏi thu thập M1.

**Alternatives considered**:
- Embed stats trong `valuation.yaml` → khó tái build theo as_of → rejected.
- SQLite/pickle → phức tạp + pickle bị gitignore policy → rejected.

## R5 — Stale giá, lookahead, synthetic, status

**Decision**:

| Điều kiện | Hành vi | Flag |
|-----------|---------|------|
| `date`/`published_at` > `as_of` | Bỏ qua im lặng khỏi tính toán | Đếm → MAY `m4_lookahead_rows_excluded` nếu count>0 |
| Phiên giá cuối hợp lệ cách `as_of` > `stale_calendar_days` (mặc định **7**) | **Vẫn chấm** nếu đủ multiple (mặc định) | `m4_stale_price_data` |
| `meta.synthetic == true` | Vẫn chạy fixture; không dùng báo cáo thật | `m4_synthetic_data` |
| Không đủ bất kỳ chân nào + median | `score=null`, `target=null` | flags thiếu dữ liệu / sector |
| Đủ chấm, chỉ cờ thông tin | `score` số; `status=ok` | `m4_pb_uses_total_equity`, `m4_bank_primary_pb`, `m4_sector_weight_default` |
| Đủ chấm + cờ thiếu/suy giảm dữ liệu | `score` số; `status=partial` | stale, EPS fallback/gap, sector_fallback, pb_leg_dropped, pe unavailable khi w_pe>0, missing shares/equity |
| `score` không chấm được | **MUST NOT** gán 50 | M7: `V_missing_used_neutral` |

**Ví dụ**: VIC đủ PE/PB, chỉ còn `m4_pb_uses_total_equity` (minority) → `status=ok`.

**Rationale**: Spec FR-007/008; Assumptions stale; M7 `scoring.py` dòng null→50 +
`{k}_missing_used_neutral`. Partial chỉ cho gap/degradation thật — không phạt cờ mô tả mapping/equity.

**Alternatives considered**:
- Stale → null score bắt buộc → quá chặt so Assumptions spec → rejected.
- Ép V=50 trong M4 khi thiếu → xung đột FR-007 / M7 → rejected.

## R6 — Target relative + DCF off

**Decision**:

- Khi có `eps_used` và `median_pe`: `implied_base_pe = median_pe * eps_used`.
- Khi có book/share và `median_pb`: `implied_base_pb = median_pb * book_ps`.
- `target.base`: blend theo cùng trọng số chân đang dùng (bank → PB).
- `bull` / `bear`: nhân `base` với hệ số cấu hình (ví dụ 1.15 / 0.85) — đọc yaml.
- `method`: chuỗi kiểu `"relative_multiples_pe_pb"` (không ghi DCF khi off).
- `assumptions`: mảng tiếng Việt/Anh mô tả median sector, winsor, EPS nguồn (TTM/năm), trọng số.
- `enable_dcf: false` mặc định — không nhánh DCF trong MVP.

**Rationale**: Spec FR-009; giá mục tiêu chỉ M4 (IV).

**Alternatives considered**: DCF MVP → ngoài scope / phức tạp → rejected.

## R7 — Metrics / evidence / flags catalog (canonical)

**Metrics** (mỗi khóa `{value, unit[, note]}`) — tối thiểu khi có:

- `pe`, `pb`, `eps_used`, `book_per_share`, `price_close`
- `sector_median_pe`, `sector_median_pb`
- `v_pe_leg`, `v_pb_leg`, `score_V` (hoặc chỉ lộ qua `score`)
- `sector_stats_version` / `sector_n_pe` / `sector_n_pb` (value số hoặc note)

**Evidence**: `text` tiếng Việt; MAY `source_id` từ `prices.source_id`; **không** bắt buộc `news_id`.

**Flags** (khi phát sinh):

| Flag | When |
|------|------|
| `m4_invalid_snapshot` / `m4_missing_as_of` | input hỏng |
| `m4_no_valid_price` | không còn close ≤ as_of |
| `m4_missing_shares` / `m4_missing_equity` | thiếu book inputs |
| `m4_pe_unavailable` | không tính PE |
| `m4_pb_unavailable` | không tính PB |
| `m4_eps_ttm_fallback_annual` | dùng EPS năm |
| `m4_sector_stats_missing` | thiếu/lỗi file JSON |
| `m4_sector_median_unavailable` | sector/min_n |
| `m4_stale_price_data` | stale > ngưỡng |
| `m4_lookahead_rows_excluded` | có dòng > as_of bị bỏ |
| `m4_bank_primary_pb` | nhánh bank |
| `m4_synthetic_data` | synthetic |
| `m4_config_defaulted` | thiếu khóa yaml → default |
| `m4_insufficient_for_score` | không chân nào chấm được → score null |

## R8 — Phạm vi file và ownership

**Decision**: Chỉ N3 paths — `m4_valuation/`, `tests/test_m4_*.py`,
`config/valuation.yaml`, `scripts/build_m4_sector_stats.py`,
`data/valuation_sector_stats.json`, optional `scripts/smoke_m4_batch.py`.
MUST NOT sửa M1, contracts, M3, M5, M6, pipeline, main, CONTRACTS.md, M7.
Không commit/push trong plan/implement trừ khi user yêu cầu.

**Rationale**: Spec FR-002/013; OWNERSHIP N3; constitution VI.

## R9 — Config skeleton (`config/valuation.yaml`)

**Decision** (khóa đề xuất — implement MAY tinh chỉnh tên miễn documented + test):

```yaml
m4:
  sector_stats_path: data/valuation_sector_stats.json
  stale_calendar_days: 7
  winsor: {low_pct: 0.05, high_pct: 0.95}   # dùng khi build; runtime đọc version trong JSON
  min_sector_n: 5
  weights:
    bank: {pe: 0.0, pb: 1.0}
    non_bank: {pe: 0.5, pb: 0.5}
  cheapness_map: {r_low: 0.5, r_high: 1.5}  # r=multiple/median → điểm chân
  target_bands: {bull_mult: 1.15, bear_mult: 0.85}
  enable_dcf: false
```

Load pattern giống M3: merge `cfg.m4` overlay lên file; thiếu → defaults +
`m4_config_defaulted`.

---

**Phase 0 complete**: mọi unknown Technical Context đã resolve; sẵn sàng Phase 1.
