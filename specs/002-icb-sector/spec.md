# Feature Specification: ICB Sector Enrichment

**Feature Branch**: `002-icb-sector`

**Created**: 2026-10-10

**Status**: Draft → Implementing

**Input**: Nạp ngành ICB từ `config/listing_icb.csv` (vn-annual-report-miner, MIT) để điền `company.sector` khi vnstock thiếu hoặc universe ngoài VN30.

## Clarifications

### Session 2026-10-10

- Q: Khi nhóm cùng Supersector (ICB cấp 2) trong universe hiện tại có ít hơn 10 mã, hệ thống phải chọn peers theo thứ tự nào? → A: Cascade L2 → L1 → toàn universe, với 3 điều kiện: (1) chỉ rơi lên L1 khi L1 khác L2 và L1 đủ ≥10 mã; nếu L1 trùng L2 hoặc vẫn &lt;10 thì xuống toàn universe; luôn gắn `sector_small_group` khi đã rời L2; (2) không bao giờ gộp tài chính (ngân hàng, bảo hiểm, chứng khoán) với phi tài chính ở bước L1 hay toàn universe — không có peer hợp lệ thì `peers` trống + cờ; (3) hành vi peers VN30 hiện tại giữ nguyên; cascade chỉ khi `icb_sector_enabled` cho universe rộng.
- Q: Để cấm gộp tài chính với phi tài chính khi chọn peers, mã nào được coi là “tài chính”? → A: Sector EN ∈ {`Banks`, `Insurance`, `Financial Services`}; parent `Financials` định nghĩa trong `icb_sector_map.yaml` (không lấy từ cột ICB cấp 1 CSV). `Real Estate` là phi tài chính, có parent riêng, không gộp vào `Financials` dù CSV xếp L1 “Tài chính”. Test: BCM, VHM, VIC, VRE không bao giờ là peer của ngân hàng và ngược lại.
- Q: Khi mã không có trong CSV hoặc Supersector chưa map và vnstock cũng không có ngành, `company.sector` phải mang giá trị gì? → A: `company.sector = ""` + cờ `icb_ticker_not_found` hoặc `icb_sector_unmapped`; không dùng JSON null; không đổi `schemas.py`. (1) vnstock đã có sector → giữ vnstock, vẫn ghi cờ khi CSV không có mã / chưa ánh xạ; (2) mã `sector == ""` không được làm peer cho ai, và bản thân rơi toàn universe + `sector_small_group`; (3) test offline: mã không trong CSV → snapshot vẫn `validate(..., "snapshot")`.
- Q: Parent tiếng Anh trong `icb_sector_map.yaml` cho Supersector `Real Estate` nên là gì (khác `Financials`)? → A: Parent = `Real Estate` (trùng sector; khi L2 &lt; 10 thì bỏ bước parent → toàn universe + `sector_small_group`).
- Q: Khi bộ lọc tài chính/phi tài chính khiến không còn peer hợp lệ và `peers` phải để trống, cờ nào phải được gắn? → A: `peers_finance_nonfinance_blocked`

## Scope

- **In**: M1 only (`src/stockai/m1_data/`), `config/` mapping + listing CSV (already present).
- **Out**: `contracts/` / `schemas.py`, M2–M9. Spec id **002** (001 reserved for quality-gate PR).
- **Out (peers)**: Đổi danh sách peers của universe VN30 đã nộp; short-circuit / đổi logic peers VN30 khi chưa bật ICB cho universe rộng.
- **Out (parent)**: Suy parent peers từ cột ICB cấp 1 của CSV khi xung đột với bảng YAML (BĐS → Tài chính).

## Requirements

1. Dùng ICB **cấp 2 (Supersector)** làm khóa ngành — không dùng cấp 1 CSV làm khóa peers (BĐS bị gom “Tài chính” trên CSV).
2. Ánh xạ cấp 2 → tên tiếng Anh snapshot (`Banks`, `Real Estate`, …) qua bảng `config/`; không ghi chữ Việt vào `company.sector`.
3. Chuẩn hóa sàn: `HOSE`→`HSX`, `UPCOM`→`UpCoM`.
4. **Parent peers:** Parent (nhóm cha khi cascade) MUST lấy từ `config/icb_sector_map.yaml` (ví dụ `industry_to_en` / bảng parent theo Supersector), **không** lấy trực tiếp từ cột ICB cấp 1 của listing CSV. Parent `Financials` MUST được định nghĩa trong YAML. Supersector `Real Estate` MUST có parent = `Real Estate` (trùng L2, **không** phải `Financials`); khi nhóm L2 &lt; 10, bước parent bị bỏ (trùng L2) → toàn universe + `sector_small_group`.
5. **Peer group (chỉ khi `icb_sector_enabled` và universe rộng, không phải đường VN30 hiện hành):** Đếm trong universe đang chạy. Cùng Supersector (L2); nếu kích thước nhóm (gồm chính mã) &lt; 10 thì mở rộng:
   - Chỉ dùng parent (YAML) khi **parent khác L2** và nhóm parent đủ **≥ 10** mã; gắn `sector_small_group`.
   - Nếu parent trùng L2, hoặc parent vẫn &lt; 10 → peers = toàn universe (sau bộ lọc tài chính ở mục 6); gắn `sector_small_group`.
   - Luôn gắn `sector_small_group` khi đã rời nhóm L2 thuần.
6. **Tách tài chính / phi tài chính:** Nhóm tài chính = đúng 3 sector `{Banks, Insurance, Financial Services}` (và peer-group parent `Financials` khi đang cascade theo parent đó). `Real Estate` là **phi tài chính**. Ở bước rơi parent hoặc toàn universe, MUST NOT gộp tài chính với phi tài chính. Nếu sau bộ lọc không còn peer hợp lệ → `peers` rỗng + cờ `peers_finance_nonfinance_blocked` (không lấy chéo; không chỉ dựa vào `peers_none_in_universe_same_sector` / `sector_small_group`).
7. **Thiếu ngành:** Không có trong CSV hoặc Supersector chưa map, và không có ngành từ vnstock → `company.sector = ""` + cờ `icb_ticker_not_found` hoặc `icb_sector_unmapped`. MUST NOT dùng JSON `null`; MUST NOT đổi `schemas.py`.
8. **Giữ vnstock:** Nếu vnstock đã có `sector` non-empty → **giữ**; gắn cờ khi lệch map (`icb_sector_mismatch`), **hoặc** khi CSV không có mã / chưa ánh xạ được (vẫn giữ chuỗi vnstock).
9. **Peers với sector rỗng:** Mã có `sector == ""` MUST NOT được chọn làm peer của bất kỳ mã nào. Bản thân mã đó (khi cascade ICB universe rộng) MUST rơi về nhóm toàn universe (sau lọc tài chính) + `sector_small_group`.
10. Offline tests: 30 mã VN30 có ngành; map khớp 100% snapshot VN30 hiện có; không đoán số/ngành. Hành vi peers VN30 giữ nguyên khi không áp cascade. MUST có test: BCM, VHM, VIC, VRE ↛ peer của `Banks` và ngược lại. MUST có test: mã không trong CSV → `sector == ""` + cờ, snapshot vẫn qua `validate(..., "snapshot")`.

## Edge Cases

- L2 &lt; 10, parent trùng tên/khóa với L2 → bỏ qua parent, xuống toàn universe (có lọc tài chính) + `sector_small_group`.
- L2 &lt; 10, parent khác L2 nhưng nhóm parent &lt; 10 → toàn universe (có lọc) + `sector_small_group`.
- Mã tài chính trong universe chỉ toàn phi tài chính còn lại (sau lọc) → `peers` trống + `peers_finance_nonfinance_blocked`; không lấy peer phi tài chính.
- BĐS (BCM, VHM, VIC, VRE, …) dù CSV ghi L1 “Tài chính” → parent YAML = `Real Estate` (không `Financials`); không làm peer ngân hàng; cascade L2 nhỏ → bỏ parent trùng → market (có lọc).
- `sector == ""` → không vào danh sách peer của mã khác; chính nó dùng toàn universe + `sector_small_group`.
- Universe VN30 / đường peers hiện hành → không áp cascade ICB ở trên; giữ danh sách peers như snapshot đã nộp.

## Assumptions

- Listing CSV không point-in-time (đã ghi trong `THIRD_PARTY_NOTICES.txt`).
- Peers vẫn gán trong `universe.fill_peers`; cascade ICB chỉ đổi chọn nhóm khi `icb_sector_enabled` trên universe rộng.
- Ngưỡng kích thước nhóm peers mặc định: 10 (có thể cấu hình `min_peer_group_size`).
- Cột ICB cấp 1 CSV chỉ tham khảo / hiển thị nguồn; parent peers lấy từ YAML.
