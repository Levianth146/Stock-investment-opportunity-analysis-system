# Feature Specification: M4 Relative Valuation (điểm V)

**Feature Branch**: `008-m4-valuation` (ưu tiên tạo sau từ `develop`; **chưa** tạo trong pass specify — không có `before_specify` hook / `.specify/extensions.yml`)

**Feature dir**: `specs/008-m4-relative-valuation/`

**Created**: 2026-10-13

**Status**: Draft — sẵn sàng `/speckit-plan`

**Input**: User description: "Feature 008: M4 relative valuation. Module `src/stockai/m4_valuation/run.py` đang stub. Cần M4 live theo contract (module_out: status, score 0–100 hoặc null, metrics, evidence, flags + target). Điểm cao = định giá rẻ/hấp dẫn. Offline trên `data/snapshots_ext` (~713 file, as_of 2026-10-08; smoke full+limited ~235). Không sửa M1, contracts, M3/M5/M6. Khóa thiết kế: PE/PB, median ngành từ `data/valuation_sector_stats.json` (script build), winsorize, ngân hàng ưu tiên P/B, chấm percentile, DCF tắt mặc định, cờ gồm stale, evidence tiếng Việt không bắt buộc news_id, không look-ahead. Score null MUST NOT ép thành 50 ở M4 — M7 xử lý `V_missing_used_neutral`. Test: fixture tay; 5 mã thật VCB/FPT/HPG/VIC/SSI; smoke 235; pytest -q xanh. Không commit/push. Pass này chỉ SPEC."

## Survey Snapshot (bắt buộc — đã chạy thật trước khi khóa field)

Khảo sát `data/snapshots_ext/*_2026-10-08.json` (709 file mã; 2 file `_summary_*` không phải snapshot mã). Tập smoke **full+limited = 235** (full 146 + limited 89). Script đọc: `scripts/dev_/_survey_m4_fields.py`.

### (a) Field tồn tại (ánh xạ khóa)

| Nhu cầu M4 | Khóa snapshot | Ghi chú khảo sát |
|---|---|---|
| Giá | `prices` là **object** `{adjusted, source_id, rows[]}`; giá đóng = `rows[*].close` phiên cuối `date <= as_of` | Không có khóa top-level `price`. FL: 235/235 có close. |
| EPS (năm / quý) | `financials.annual[].items.eps`, `financials.quarterly[].items.eps` | **Không** có field sẵn `eps_ttm`. TTM = tổng EPS 4 quý gần nhất có `published_at <= as_of` (và có số). |
| Vốn chủ / book | `financials.*.items.total_equity` | Ưu tiên quý mới nhất ≤ as_of; fallback năm. FL: 235/235. |
| Số CP lưu hành | `company.shares_outstanding` | Không có `shares` top-level. FL: 235/235. Insufficient thường null. |
| Doanh thu | `financials.*.items.revenue` | FL annual 235/235; quarterly thiếu 1 (TDM = null từng quý). |
| Lãi / earnings | `net_income`, `net_income_parent` trong `items` | FL annual cả hai 235/235. |
| Peers | `peers[]`: `{ticker, pe, pb, roe, market_cap, source_id}` | FL: 235/235 non-empty; mọi peer list có ít nhất một `pe`/`pb` số. |

### (b) Đơn vị

- `financials.unit` = **`VND`** (707/709; FL 235/235). Số BCTC là **đồng VND thô** (ví dụ FPT `total_equity` ≈ 4.37e13), **không** phải nghìn/tỷ đã scale sẵn trong field.
- Giá: **VND / cổ phiếu** (FPT close 59700 ngày 2026-10-08). Cờ phổ biến: `prices_scaled_x1000_to_VND`.
- EPS: **VND / cổ phiếu** (FPT annual eps 5216 → PE ≈ 11.4).
- Book/share suy ra = `total_equity / shares_outstanding` (cùng đơn vị VND).
- Peer `market_cap` cũng theo VND thô (cùng hệ với `price * shares`).

### (c) Thiếu field (đếm + ví dụ)

**Trên full+limited (235)** — gần đủ cho relative PE/PB:

| Field | Có | Thiếu | Ví dụ thiếu |
|---|---:|---:|---|
| `price_close` | 235 | 0 | — |
| `shares_outstanding` | 235 | 0 | — |
| `eps` annual | 235 | 0 | — |
| `eps` quarterly latest | 234 | 1 | `TDM` (mọi quý `eps` = null; vẫn có annual) |
| EPS TTM (sum 4Q) | 234 | 1 | `TDM` |
| `total_equity` annual/quarterly | 235 | 0 | — |
| `revenue` annual | 235 | 0 | — |
| `revenue` quarterly | 234 | 1 | `TDM` |
| `net_income` / `net_income_parent` annual | 235 | 0 | — |
| `peers` non-empty + pe/pb | 235 | 0 | — |
| `company.sector` | 235 | 0 | — |

**Khả năng tính bội số trên FL**: P/B tính được **235/235**; P/E tính được **232/235**. Không P/E: `GKM`, `HSG`, `NVB` (EPS annual/TTM = 0 → chia 0). Vẫn P/B được → vẫn chấm được nếu ngân hàng/phi ngân hàng chấp nhận một chân P/B.

**Lưu ý dữ liệu EPS quý = 0**: nhiều mã (ví dụ `SSI`) có quarterly `eps` = 0.0 trong khi annual có số thật → TTM sum4q = 0 **không** tin được; MUST fallback EPS năm mới nhất ≤ as_of và gắn cờ (ví dụ `m4_eps_ttm_fallback_annual`).

**Ngoài FL (insufficient ~472)**: thiếu hàng loạt `shares_outstanding` / BCTC / EPS (~469–472 mã). M4 vẫn MUST không crash; `score` = null + cờ thiếu dữ liệu. Không thuộc smoke bắt buộc.

### (d) Sector từ đâu

- Runtime: `company.sector` (tiếng Anh, ví dụ `Banks`, `Technology`, `Basic Resources`).
- Nguồn map: M1 đọc **`config/icb_sector_map.yaml`** (+ `config/listing_icb.csv`) qua `icb_sector` — Supersector ICB → `sector_en`. Feature 008 **không** sửa map; chỉ **đọc** `company.sector` đã có trên snapshot.
- Median ngành cho chấm điểm: file prebuilt **`data/valuation_sector_stats.json`** (sinh bởi `scripts/build_m4_sector_stats.py` từ universe FL cùng as_of), **không** suy median chỉ từ `peers[]` của một mã (peers có pe/pb sẵn nhưng là nhóm peer snapshot, không thay median ngành chuẩn hóa).

### (e) Ngân hàng

- Nhận diện: **`company.is_bank`** (boolean; M1 gắn từ danh sách `cfg.banks`).
- FL: **23** ngân hàng (`ACB`, `BID`, `BVB`, `CTG`, `EIB`, `HDB`, `KLB`, `LPB`, `MBB`, `MSB`, `NAB`, `NVB`, `OCB`, `SHB`, `SSB`, `STB`, `TCB`, `TPB`, `VAB`, `VBB`, `VCB`, `VIB`, `VPB`). `BAB` = bank nhưng `quality_tier_insufficient` (không trong 235).
- Với `is_bank == true`: **P/B là chân chính**; P/E phụ hoặc bỏ qua khi EPS ≤ 0 / không tin cậy (khớp CONTRACTS: M2/M4 rẽ nhánh bank).

### Hợp đồng M4 / tương tác M7 (đã đọc `docs/CONTRACTS.md`)

- M4 đọc: financials, prices, shares (`company.shares_outstanding`), peers; MAY đọc `upstream["m2"]` nhưng **không bắt buộc** để chấm V relative.
- Đầu ra: `module_out` (score = **V**) + `target{base,bull,bear,method,assumptions}` (giá mục tiêu **chỉ** M4).
- `score` kiểu `number | null`. Thiếu dữ liệu → null + flags; **không** bịa số.
- M7: khi `V` null → gán `neutral_score_when_missing` và cờ **`V_missing_used_neutral`**. **Assumption khóa**: M4 MUST NOT tự ép Score V = 50; để null để M7 trung tính — không xung đột blocking với CONTRACTS.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Chấm điểm V bằng định giá tương đối PE/PB so ngành (Priority: P1)

Người phân tích (hoặc pipeline) đưa snapshot HOSE/HNX (as_of đã đóng cửa) vào M4. Hệ thống chỉ dùng giá và BCTC có ngày ≤ `as_of` (không look-ahead). Tính P/E và/hoặc P/B từ giá đóng, EPS (TTM ưu tiên với fallback năm), vốn chủ và số CP lưu hành. So với **median ngành** đã winsorize trong bảng thống kê ngành prebuilt theo `company.sector`. Chấm điểm **percentile** (hoặc quy tắc tương đương documented) sao cho **điểm cao = rẻ / hấp dẫn**. **Điểm V chỉ là định giá tương đối** (rẻ/đắt so ngành); **không** phản ánh chất lượng kinh doanh. Ngân hàng (`company.is_bank`): **P/B là chân chính**. Đủ dữ liệu → `score` số 0–100, `status` = `ok` (hoặc `partial` nếu còn cờ thiếu/suy giảm dữ liệu thật — không ép partial vì cờ thông tin như minority equity / weight default / bank primary PB). Thiếu dữ liệu chặn chấm → `score` = **null**, không ép 50.

**Why this priority**: Điểm V là đầu vào trọng số M7; stub hiện tại không phản ánh định giá thật.

**Independent Test**: Snapshot dựng tay (rẻ vs đắt cùng ngành; bank; thiếu EPS; thiếu equity; giá sau as_of bị loại) + 5 mã thật VCB/FPT/HPG/VIC/SSI nếu có dưới `data/snapshots_ext`. Chạy M4 độc lập; không cần M3/M5/M6.

**Acceptance Scenarios**:

1. **Given** snapshot phi ngân hàng đủ giá, EPS tin cậy, equity, shares và có median ngành cho `company.sector`, **When** chạy M4, **Then** trả `module_out` hợp lệ với `score` số trong [0, 100], `status` = `ok` hoặc `partial` có giải thích, metrics gồm ít nhất PE và/hoặc PB của mã, median ngành tương ứng, và thành phần điểm; **điểm cao hơn** tương ứng bội số thấp hơn (rẻ hơn) trên cùng khung so sánh fixture.
2. **Given** `company.is_bank` = true và đủ P/B, **When** chạy M4, **Then** chân chính là P/B; thiếu/không tin P/E MUST NOT chặn chấm nếu P/B đủ; gắn cờ/note làm rõ trọng số bank.
3. **Given** không đủ dữ liệu để tính bất kỳ chân định giá nào được cấu hình (ví dụ thiếu giá hoặc thiếu book và không có PE), **When** chạy M4, **Then** `score` = `null`, có cờ thiếu dữ liệu, **MUST NOT** gán 50.
4. **Given** hàng giá hoặc kỳ BCTC có `date` / `published_at` > `as_of`, **When** chạy M4, **Then** dữ liệu đó không vào PE/PB/điểm; có đếm hoặc cờ loại look-ahead nếu phát sinh.
5. **Given** phiên giá cuối hợp lệ cách `as_of` vượt ngưỡng stale cấu hình (mặc định 7 ngày lịch, cùng tinh thần M3), **When** chạy M4, **Then** gắn cờ stale (ví dụ `m4_stale_price_data`); hành vi score (vẫn chấm hoặc null) theo cấu hình đã ghi Assumptions — mặc định: vẫn chấm kèm cờ nếu còn đủ input khác.
6. **Given** EPS TTM = 0 hoặc không đủ 4 quý trong khi EPS năm có số ≠ 0, **When** chạy M4, **Then** dùng fallback EPS năm + cờ fallback; không crash; không dùng TTM = 0 để bịa PE vô hạn.

---

### User Story 2 - Bảng thống kê ngành, winsorize, target tương đối, DCF tắt mặc định (Priority: P1)

Người phát triển (hoặc bước chuẩn bị dữ liệu) sinh / cập nhật `data/valuation_sector_stats.json` bằng `scripts/build_m4_sector_stats.py` từ tập mã full+limited cùng as_of (winsorize phân vị cấu hình trước khi lấy median PE/PB theo `company.sector`). M4 đọc bảng này (hoặc cache config tương đương) để so sánh. `target` (base/bull/bear) suy từ phương pháp **relative multiples** (implied price từ median × EPS hoặc book/share), `method` và `assumptions` tiếng Việt/Anh rõ ràng. **DCF tắt mặc định** (`enable_dcf: false`); bật sau chỉ khi cấu hình cho phép — không bắt buộc trong MVP. Evidence bằng tiếng Việt, **không** bắt buộc `news_id` (M4 không chấm tin).

**Why this priority**: Median ngành ổn định và tái lập được; target chỉ thuộc M4 theo CONTRACTS; DCF phức tạp nên để tùy chọn.

**Independent Test**: File thống kê ngành có đủ sector của 5 mã mẫu; thiếu sector trong bảng → cờ + null hoặc partial theo Assumptions; DCF off → không có nhánh DCF trong metrics/method trừ khi bật.

**Acceptance Scenarios**:

1. **Given** đã có `data/valuation_sector_stats.json` (hoặc đường dẫn cấu hình trỏ tới file tương đương) cho các sector của universe smoke, **When** chạy M4 trên mã thuộc sector đó, **Then** metrics lộ median ngành đã dùng và nguồn/phiên bản thống kê (note hoặc flag).
2. **Given** sector của mã không có trong bảng thống kê hoặc sample size dưới ngưỡng tối thiểu cấu hình, **When** chạy M4, **Then** không bịa median; `score` = null hoặc chỉ dùng được chân còn lại theo quy tắc đã ghi; gắn cờ thiếu thống kê ngành.
3. **Given** đủ để implied price, **When** chạy M4, **Then** `target` ≠ null với `base`/`bull`/`bear`/`method`/`assumptions`; method phản ánh relative (không nhận là DCF khi DCF off).
4. **Given** `enable_dcf` = false (mặc định), **When** chạy M4, **Then** không tính DCF; không phụ thuộc giả định tăng trưởng dài hạn.
5. **Given** mọi evidence của M4, **When** kiểm tra schema, **Then** mỗi mục có `text` tiếng Việt; `news_id` không bắt buộc (MAY bỏ trống / không có khóa).

---

### User Story 3 - TDD offline, 5 mã thật, smoke ~235, pytest xanh (Priority: P1)

Người phát triển viết test trước (fail trên stub `status=stub`), rồi triển khai. Test chính: snapshot dựng tay. Bắt buộc thêm case đọc 5 snapshot thật `VCB`/`FPT`/`HPG`/`VIC`/`SSI` (as_of 2026-10-08) nếu file tồn tại — bỏ qua có điều kiện nếu thiếu. Sau implement: `python -m pytest -q` toàn dự án; smoke M4 trên ~235 mã full+limited; in phân bố điểm V, số ok/partial, số score null, số bank dùng P/B. Phạm vi: `src/stockai/m4_valuation/`, tests `tests/test_m4_*.py`, config mới (ví dụ `config/valuation.yaml`), script build sector stats + optional smoke script. **MUST NOT** sửa M1, contracts, M3/M5/M6, pipeline. Không commit/push trong feature trừ khi người dùng yêu cầu sau.

**Why this priority**: Stub luôn giả; TDD + smoke chứng minh V chạy trên dữ liệu repo.

**Independent Test**: Fail-first; sau đó pytest sạch; smoke có bảng phân bố trong báo cáo hoàn thành implement.

**Acceptance Scenarios**:

1. **Given** stub M4 hiện tại, **When** chạy bộ test mới, **Then** test hành vi thật **fail trước** khi có code live.
2. **Given** đã implement, **When** chạy toàn bộ pytest dự án offline, **Then** pass; số test được báo cáo.
3. **Given** 5 mã VCB/FPT/HPG/VIC/SSI có file snapshot, **When** chạy M4, **Then** không crash; bank VCB ưu tiên P/B; các mã còn lại có PE và/hoặc PB trong metrics khi dữ liệu cho phép.
4. **Given** ~235 mã full+limited, **When** chạy smoke M4, **Then** không crash hàng loạt; in phân bố score V, đếm status, đếm score null; dán vào báo cáo hoàn thành.
5. **Given** mọi thay đổi feature, **When** xem diff, **Then** không có sửa `m1_data/*`, `contracts/*`, `pipeline.py`, `main.py`, M3/M5/M6; không commit/push trừ khi được yêu cầu.

---

### Edge Cases

- `meta.synthetic` = true: gắn cờ synthetic; không dùng làm báo cáo thật.
- EPS ≤ 0 hoặc book ≤ 0: không tính chân tương ứng; gắn cờ; vẫn chấm nếu chân còn lại đủ.
- `SSI`-like: quarterly eps toàn 0 nhưng annual > 0 → fallback annual + cờ.
- `GKM`/`HSG`/`NVB`: EPS 0 → không PE; vẫn P/B.
- `TDM`: thiếu EPS/revenue quý → dùng annual cho PE nếu cần.
- Thiếu `valuation_sector_stats.json`: null + cờ cấu hình/thiếu bảng; không crash.
- Mã insufficient / thiếu shares: score null, không exception.
- Peer list rỗng: không dùng peers làm median thay thế im lặng; dựa bảng ngành.
- `upstream["m2"]` thiếu: M4 relative vẫn chạy (không bắt buộc điểm F).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: M4 MUST giữ chữ ký `run(snapshot, upstream, cfg) -> dict` và đầu ra MUST hợp lệ `module_out` theo contract hiện có (kèm `target` chỉ thuộc M4). MUST NOT đổi `src/stockai/contracts/*` hay `docs/CONTRACTS.md`.
- **FR-002**: Phạm vi sửa MUST giới hạn ở `src/stockai/m4_valuation/`, `tests/test_m4_*.py`, cấu hình valuation mới, `scripts/build_m4_sector_stats.py`, artifact `data/valuation_sector_stats.json` (local/gitignore nếu lớn), và optional smoke script. MUST NOT sửa `m1_data/*`, `pipeline.py`, `main.py`, `contracts/*`, M3, M5, M6.
- **FR-003**: Điểm V MUST phản ánh định giá tương đối: **cao = rẻ/hấp dẫn**, thấp = đắt. Công thức percentile (hoặc map phân vị → 0–100) MUST đọc tham số từ cấu hình; MUST NOT hard-code ngưỡng nghiệp vụ trong mã nguồn.
- **FR-004**: M4 MUST tính PE và/hoặc PB từ: giá `prices.rows` (close, `date <= as_of`), EPS (TTM = tổng tối đa 4 quý `published_at <= as_of` khi đủ và tổng ≠ 0; else EPS năm mới nhất ≤ as_of), `total_equity`, `company.shares_outstanding`. Đơn vị tính MUST nhất quán VND (theo `financials.unit` và giá đã scale).
- **FR-005**: So sánh MUST dùng median ngành (winsorize trước khi median) từ `data/valuation_sector_stats.json` (hoặc đường dẫn cfg tương đương) theo khóa `company.sector`. Script build MUST tái lập được từ tập full+limited cùng as_of.
- **FR-006**: Khi `company.is_bank` = true, P/B MUST là chân chính cho điểm; P/E chỉ phụ hoặc bỏ qua nếu không hợp lệ.
- **FR-007**: Khi không chấm được V, `score` MUST là `null` kèm flags. MUST NOT gán 50 (hay bất kỳ điểm trung tính nào) bên trong M4. Trung tính để M7 gắn `V_missing_used_neutral`.
- **FR-008**: M4 MUST NOT dùng dữ liệu có `date`/`published_at` > `as_of` (no look-ahead). MUST gắn cờ stale giá khi phiên cuối vượt ngưỡng cấu hình.
- **FR-009**: `target` MUST được điền khi suy được giá implied từ relative multiples; `method`/`assumptions` MUST mô tả rõ. DCF MUST tắt mặc định.
- **FR-010**: `metrics` MUST dùng dạng `{value, unit, note?}`; evidence MUST tiếng Việt, không bắt buộc `news_id`.
- **FR-011**: Flags MUST gồm (khi phát sinh) thiếu dữ liệu, thiếu thống kê ngành, stale giá, fallback EPS, bank-primary-PB, synthetic, và các cờ cấu hình thiếu khóa nếu cần.
- **FR-012**: Kiểm thử MUST fail-first trên stub; offline bằng fixture tay; gồm polarity “rẻ hơn → V cao hơn”; gồm 5 mã thật VCB/FPT/HPG/VIC/SSI (skip nếu thiếu file); sau implement pytest toàn dự án xanh và smoke ~235 với bảng phân bố.
- **FR-013**: Trong giai đoạn specify/plan/implement của feature này (trừ khi người dùng yêu cầu rõ sau): MUST NOT commit, MUST NOT push.

### Key Entities

- **Valuation Module Output (M4)**: `module_out` với score V (cao = rẻ), metrics PE/PB/median/implied, evidence tiếng Việt, flags, `target`.
- **Sector Valuation Stats**: Bảng theo `sector` → median PE/PB (sau winsorize), cỡ mẫu, as_of build, phiên bản.
- **Relative Multiple Inputs**: Giá đóng, EPS (TTM hoặc năm), book/share, sector, `is_bank`.
- **Peer Snapshot Row**: Tham chiếu phụ (`peers[].pe/pb`); không thay median ngành chuẩn.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Với fixture tay “rẻ hơn” cùng ngành, điểm V **cao hơn** fixture “đắt hơn” trên cùng cấu hình.
- **SC-002**: Khi thiếu input chặn định giá, người dùng nhận `score` trống (null) và cờ rõ — không nhận điểm 50 từ M4.
- **SC-003**: Không có giá/BCTC sau ngày đánh giá nào lọt vào PE/PB/điểm/target (fixture có ngày tương lai giả).
- **SC-004**: Ngân hàng đủ P/B nhận điểm số dựa trên P/B dù P/E không tính được.
- **SC-005**: Năm mã mẫu VCB/FPT/HPG/VIC/SSI chạy không exception khi file snapshot có trong repo.
- **SC-006**: Toàn bộ kiểm thử offline dự án pass sau implement; số test được báo cáo.
- **SC-007**: Smoke ~235 full+limited hoàn tất không crash hàng loạt; bảng phân bố V / ok / partial / null được in và dán vào báo cáo hoàn thành.
- **SC-008**: Diff phạm vi đúng: không đổi M1, contracts, pipeline, M3/M5/M6.

## Assumptions

- **Nhánh git**: Ưu tiên `008-m4-valuation` cắt từ `develop` ở bước plan/implement. Pass specify **không** tạo nhánh (không có `.specify/extensions.yml` / hook `before_specify`).
- Universe smoke = mã có `quality_tier_full` hoặc `quality_tier_limited` trên as_of 2026-10-08 (**235** mã đã đo).
- Field mapping khóa theo Survey ở trên; không invent khóa financials mới (cần khóa mới → báo N1).
- Median ngành lấy từ file prebuilt winsorize, không từ trung vị ad-hoc của `peers[]` từng mã (peers chỉ evidence/đối chiếu).
- Winsorize mặc định: cắt phân vị thấp/cao cấu hình (ví dụ 5%/95%) trước median — chỉnh được bằng config.
- Stale giá mặc định: > 7 ngày lịch so `as_of` → cờ; vẫn cho phép chấm nếu đủ multiple.
- DCF `enable_dcf: false` mặc định; không nằm MVP chấm điểm.
- **Score null ↔ M7**: M4 để `score: null` khi không chấm được; M7 đã có `neutral_score_when_missing` + `V_missing_used_neutral`. Không ép 50 tại M4. Không cần đổi M7 trong feature này.
- `upstream["m2"]` tùy chọn; relative V không phụ thuộc điểm F để chạy.
- Hiến chương I–VI áp dụng: as_of, null+flags, số do code tính, test offline, ownership M4 (N3).
- Artifact `data/valuation_sector_stats.json` và snapshot_ext có thể nằm ngoài commit (gitignore); script build MUST chạy được local trước smoke.
- Pass specify chỉ tạo SPEC + checklist + `feature.json` — **chưa** implement M4.

## Constraints

- Không commit / không push / không Co-authored-by trừ khi người dùng yêu cầu rõ sau.
- MUST NOT sửa M1, contracts, M3, M5, M6, pipeline, `docs/CONTRACTS.md` trong feature này.
- Không implement code M4 trong pass specify (trừ script khảo sát chỉ-đọc đã dùng).
