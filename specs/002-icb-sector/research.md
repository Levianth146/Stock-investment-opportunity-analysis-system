# Research: ICB Sector Enrichment (002)

**Scope**: M1 + `config/` only. Clarifications 2026-10-10 are binding.

## R1 — Khóa ngành: Supersector (L2), không Industry CSV (L1)

**Decision**: `company.sector` và nhóm peers “cùng ngành” dùng tên tiếng Anh map từ
**ICB cấp 2 (Supersector)**. Không dùng cột ICB cấp 1 CSV làm khóa peers.

**Rationale**: Trên listing, BĐS thường nằm dưới L1 “Tài chính” — nếu dùng L1 sẽ
gộp BĐS với ngân hàng (vi phạm yêu cầu sản phẩm và clarify).

**Alternatives considered**:
- Dùng ICB L3 (Industry group) → quá mảnh, peer group thường &lt; 10.
- Giữ chuỗi Việt trong snapshot → lệch convention VN30 hiện có (Banks, Real Estate).

## R2 — Parent peers từ YAML theo Supersector, không từ CSV L1

**Decision**: Thêm / dùng bảng parent trong `icb_sector_map.yaml` keyed bởi
**Supersector tiếng Việt hoặc sector EN** (ví dụ `supersector_parent_en`), trong đó:
- `Financials` là parent của Banks / Insurance / Financial Services
- `Real Estate` → parent **`Real Estate`** (trùng L2)
- Không đọc cột L1 CSV để quyết định parent peers

**Rationale**: Clarify khóa parent `Financials` trong YAML; BĐS phải tách khỏi
Financials dù CSV ghi L1 “Tài chính”.

**Alternatives considered**:
- `industry_to_en[CSV L1]` (code hiện tại) → rejected: BĐS → Financials.
- Hard-code parent trong Python → khó bảo trì; YAML đã là nguồn map.

## R3 — Cascade peer khi nhóm L2 &lt; min_size (chỉ universe rộng)

**Decision**:
1. Cùng L2 (đếm trong universe đang chạy, gồm chính mã).
2. Nếu &lt; `min_peer_group_size` (mặc định 10): dùng parent YAML **chỉ khi**
   `parent != sector` **và** kích thước nhóm parent ≥ 10; gắn `sector_small_group`.
3. Nếu parent trùng L2, hoặc parent vẫn &lt; 10 → toàn universe (sau lọc R4);
   gắn `sector_small_group`.
4. Cascade **chỉ** khi `icb_sector_enabled` và đường **universe rộng**.
   Universe VN30 / peers đã nộp: **không** áp cascade — giữ danh sách peers hiện hành.

**Rationale**: Khớp clarify; Real Estate parent trùng L2 → luôn nhảy market khi
L2 nhỏ; tránh hồi quy VN30.

**Alternatives considered**:
- Luôn cascade kể cả VN30 → đổi peers đã nộp (bị reject).
- Bỏ thẳng market khi L2 &lt; 10 (không thử parent) → mất peer cùng Industry hợp lệ
  (Banks dưới Financials khi đủ lớn).

## R4 — Tách tài chính / phi tài chính

**Decision**: Tập tài chính = đúng `{Banks, Insurance, Financial Services}`.
Khi đang ở bước parent `Financials` hoặc toàn market, chỉ giữ peer cùng “phía”
(tài chính vs phi tài chính) với mã đích. `Real Estate` = phi tài chính.
Nếu sau lọc không còn peer → `peers = []` + **`peers_finance_nonfinance_blocked`**.

**Rationale**: Clarify + test BCM/VHM/VIC/VRE ↛ ngân hàng.

**Alternatives considered**:
- Dùng `is_bank` only → thiếu bảo hiểm / chứng khoán.
- Dùng CSV L1 “Tài chính” → kéo theo BĐS (reject).

## R5 — `company.sector` thiếu = `""`, không null

**Decision**: Thiếu CSV / unmapped và không có ngành vnstock → `sector = ""` +
`icb_ticker_not_found` hoặc `icb_sector_unmapped`. Có vnstock → giữ chuỗi vnstock,
vẫn gắn cờ thiếu/unmapped/mismatch khi cần. Không sửa `schemas.py`.

**Rationale**: Snapshot schema yêu cầu `sector: string`; null fail validate.

**Alternatives considered**: JSON null + đổi schema (N1) → out of scope.

## R6 — Sector rỗng và peers

**Decision**: Mã `sector == ""` không được chọn làm peer của ai. Chính mã đó trên
đường cascade rộng → market (sau lọc R4) + `sector_small_group`.

**Rationale**: Clarify; tránh peer “không ngành” làm nhiễu multiples.

## R7 — Nguồn listing & license

**Decision**: Giữ `config/listing_icb.csv` + `THIRD_PARTY_NOTICES.txt` (MIT,
vn-annual-report-miner). Không point-in-time — disclose, không bịa lịch sử ngành.

**Rationale**: Constitution III + assumptions spec.

## R8 — Gap implementation order

**Decision**: (1) Sửa YAML parent theo Supersector + Real Estate; (2) sửa
`resolve_peer_group` + finance filter + flags; (3) gate VN30 vs wide trong
`universe.fill_peers`; (4) tests clarify (Banks↔BĐS, empty CSV validate, VN30
peer regression).

**Rationale**: Parent sai làm mọi cascade/test tài chính–BĐS fail trước.
