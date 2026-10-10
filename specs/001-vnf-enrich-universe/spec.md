# Feature Specification: VNF Enrich & Wide Universe

**Feature Branch**: `001-vnf-enrich-universe`

**Created**: 2026-10-10

**Status**: Partial — remaining work is scoring/report enforcement only (FR-008, FR-009)

**Input**: User description: "Thêm nguồn vnfinancialdata để điền BCTC thiếu trong snapshot và đối chiếu với vnstock; Cho phép universe ngoài VN30 với cổng chất lượng full/limited/insufficient; Bổ sung bước enrich snapshot từ vnfinancialdata: điền mục BCTC trống, đối chiếu lệch với nguồn chính, gắn flags khi mismatch hoặc không tìm thấy mã"

**Implementation note (2026-10-10)**: FR-001..007, FR-010, FR-011 đã có trong M1
(`src/stockai/m1_data/vnf_source.py`, `quality.py`, `universe.py`; tests
`tests/test_m1_vnf.py`, `tests/test_m1_wide.py`). **Không đổi code M1** trong
phạm vi còn lại. Phần cần làm: FR-008 và FR-009 ở pipeline chấm điểm / báo cáo
(downstream của M1).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Điền BCTC thiếu và đối chiếu nguồn phụ (Priority: P1) — ĐÃ TRIỂN KHAI

Nhà phân tích đã có snapshot theo mã và ngày `as_of` từ nguồn chính (vnstock). Nhiều khoản mục báo cáo tài chính còn trống. Họ chạy bước làm giàu (enrich) từ nguồn phụ vnfinancialdata: hệ thống chỉ điền các mục đang trống, đối chiếu các mục cả hai nguồn đều có, và gắn cờ khi lệch hoặc khi không tìm thấy mã trên nguồn phụ — không bịa số và không im lặng ghi đè nguồn chính.

**Status**: Done (M1 VNF enrich + tests). Không thuộc backlog còn lại.

**Why this priority**: Độ đầy đủ và trung thực của BCTC quyết định chất lượng chấm điểm cơ bản và định giá; đây là giá trị cốt lõi của tính năng.

**Independent Test**: Với một snapshot có mục trống và bộ dữ liệu nguồn phụ cố định (offline), sau enrich có thể kiểm tra: mục trống được điền khi nguồn phụ có số; mục đã có từ nguồn chính không bị đổi khi lệch; flags phản ánh mismatch hoặc ticker không tìm thấy.

**Acceptance Scenarios**:

1. **Given** snapshot có ít nhất một khoản mục BCTC trống và nguồn phụ có giá trị hợp lệ cho mã đó trong phạm vi `as_of`, **When** chạy enrich, **Then** mục trống được điền, gắn nguồn phụ, và không tạo số giả.
2. **Given** cùng một khoản mục có số ở cả nguồn chính và nguồn phụ nhưng khác nhau, **When** chạy enrich, **Then** giá trị nguồn chính được giữ, và có flag báo lệch (mismatch) cho khoản mục/năm tương ứng.
3. **Given** mã không tồn tại trên nguồn phụ, **When** chạy enrich, **Then** snapshot không bị bịa số và có flag báo không tìm thấy mã; các mục trống vẫn để trống kèm flag thiếu dữ liệu nếu chưa có sẵn.
4. **Given** nguồn phụ chỉ có dữ liệu sau `as_of` (hoặc ngày công bố sau `as_of`), **When** chạy enrich, **Then** dữ liệu đó không được dùng để điền snapshot.

---

### User Story 2 - Universe ngoài VN30 với cổng chất lượng (Priority: P2) — MỘT PHẦN

Người vận hành muốn phân tích tập mã rộng hơn VN30. Hệ thống chấp nhận danh sách universe mở rộng và gán mỗi mã một mức chất lượng dữ liệu: `full`, `limited`, hoặc `insufficient`. Chỉ mã đủ điều kiện mới đi vào chấm điểm; mã `insufficient` bị loại khỏi scoring và được ghi nhận rõ.

**Status**: Gán nhãn chất lượng + universe rộng (scenario 1) **đã có ở M1**.
Scenarios 2–3 (loại khỏi scoring / nêu hạn chế trên báo cáo) = **FR-008, FR-009 còn lại** — làm ở pipeline/báo cáo, **không đổi M1**.

**Why this priority**: Mở rộng coverage thị trường nhưng vẫn bảo vệ độ tin cậy của khuyến nghị — phụ thuộc vào enrich/đối chiếu ở P1 để phân loại chất lượng.

**Independent Test**: Với một universe gồm mã đủ dữ liệu, mã thiếu một phần, và mã thiếu nghiêm trọng, cổng chất lượng gán đúng nhãn và chỉ các mã không `insufficient` được đưa vào bước chấm điểm.

**Acceptance Scenarios**:

1. **Given** universe gồm mã ngoài VN30, **When** hệ thống đánh giá chất lượng dữ liệu snapshot theo `as_of`, **Then** mỗi mã nhận đúng một trong `full` | `limited` | `insufficient`. *(ĐÃ TRIỂN KHAI — M1)*
2. **Given** mã được gán `insufficient`, **When** chạy pipeline chấm điểm, **Then** mã đó không được chấm điểm và lý do loại được ghi nhận (flags/báo cáo). *(CÒN LẠI — FR-008)*
3. **Given** mã `full` hoặc `limited`, **When** chạy pipeline, **Then** mã được chấm điểm; với `limited`, báo cáo nêu rõ hạn chế dữ liệu đã biết. *(CÒN LẠI — FR-009)*

---

### User Story 3 - Theo dõi kết quả enrich hàng loạt (Priority: P3) — ĐÃ TRIỂN KHAI

Người vận hành chạy enrich cho nhiều mã trong một ngày `as_of` và cần tóm tắt: bao nhiêu năm được bổ sung, bao nhiêu khoản mục được điền, bao nhiêu lệch đối chiếu, và các flag nổi bật — để biết nguồn phụ có hữu ích và chỗ nào cần xem lại thủ công.

**Status**: Done (M1 enrich summary). Không thuộc backlog còn lại.

**Why this priority**: Hỗ trợ vận hành và kiểm soát chất lượng; không chặn MVP nếu P1/P2 đã hoạt động đúng từng mã.

**Independent Test**: Sau enrich một tập mã cố định, bản tóm tắt theo mã khớp với số mục đã điền và số mismatch đã gắn flag.

**Acceptance Scenarios**:

1. **Given** enrich hoàn tất cho N mã, **When** xem kết quả tóm tắt, **Then** mỗi mã có số liệu điền/lệch/flag chính và trạng thái tổng (ví dụ thành công, không tìm thấy mã, có mismatch).
2. **Given** một mã không thay đổi sau enrich (không điền, không lệch), **When** xem tóm tắt, **Then** kết quả phản ánh “không đổi” chứ không báo lỗi giả.

---

### Edge Cases

- Nguồn phụ trả về mã hợp lệ nhưng không có năm BCTC nào trong cửa sổ cần thiết → không điền; gắn flag thiếu dữ liệu nguồn phụ.
- Chỉ một phần khoản mục có thể điền (một số trống được lấp, một số vẫn trống) → điền phần có; mục còn trống giữ `null` + flag thiếu.
- Universe rỗng hoặc chỉ gồm mã `insufficient` → không có mã nào được chấm điểm; hệ thống báo rõ, không crash im lặng.
- Trùng lặp mã trong universe → xử lý một lần cho mỗi mã (không nhân đôi kết quả).
- Snapshot đã đầy đủ từ nguồn chính → enrich có thể chỉ chạy đối chiếu; mismatch vẫn gắn flag, không ghi đè.

## Requirements *(mandatory)*

### Functional Requirements

#### Đã triển khai (M1 — không đổi trong backlog còn lại)

Evidence: `src/stockai/m1_data/vnf_source.py`, `quality.py`, `universe.py`;
`tests/test_m1_vnf.py`, `tests/test_m1_wide.py`.

- **FR-001** ✅ ĐÃ TRIỂN KHAI: Hệ thống MUST cho phép đăng ký vnfinancialdata như nguồn dữ liệu phụ trong snapshot (có thể truy vết qua định danh nguồn), tách biệt nguồn chính vnstock.
- **FR-002** ✅ ĐÃ TRIỂN KHAI: Hệ thống MUST cung cấp bước enrich snapshot theo `as_of` dùng nguồn phụ để điền các khoản mục BCTC đang trống (null/thiếu), không điền bằng số ước đoán tự bịa.
- **FR-003** ✅ ĐÃ TRIỂN KHAI: Khi điền từ nguồn phụ, mỗi giá trị điền MUST gắn nguồn truy vết về nguồn phụ; MUST tôn trọng ràng buộc không look-ahead theo `as_of` (không dùng dữ liệu công bố/giao dịch sau `as_of`).
- **FR-004** ✅ ĐÃ TRIỂN KHAI: Khi cả nguồn chính và nguồn phụ đều có cùng khoản mục/kỳ và giá trị lệch nhau, hệ thống MUST giữ giá trị nguồn chính và MUST gắn flag mismatch (chỉ rõ khoản mục và kỳ khi có thể).
- **FR-005** ✅ ĐÃ TRIỂN KHAI: Khi mã không có trên nguồn phụ, hệ thống MUST gắn flag không tìm thấy mã và MUST NOT bịa số cho mã đó từ nguồn phụ.
- **FR-006** ✅ ĐÃ TRIỂN KHAI: Hệ thống MUST hỗ trợ universe gồm mã ngoài VN30 (danh sách cấu hình hoặc đầu vào tường minh), không bị giới hạn cứng chỉ VN30.
- **FR-007** ✅ ĐÃ TRIỂN KHAI: Hệ thống MUST gán mỗi mã trong universe một cổng chất lượng duy nhất thuộc {`full`, `limited`, `insufficient`} dựa trên mức đầy đủ/đáng tin của dữ liệu snapshot tại `as_of`.
- **FR-010** ✅ ĐÃ TRIỂN KHAI: Bước enrich MUST có thể chạy độc lập sau khi đã có snapshot nguồn chính, và MUST có thể kiểm chứng bằng kịch bản offline (fixture/dữ liệu giả cố định) không phụ thuộc mạng.
- **FR-011** ✅ ĐÃ TRIỂN KHAI: Hệ thống MUST cung cấp tóm tắt kết quả enrich theo mã (số mục điền, số lệch, flag chính) đủ để người vận hành rà soát nhanh.

#### Còn lại (không đụng M1)

- **FR-008** 🔲 CẦN LÀM: Mã `insufficient` MUST NOT được đưa vào chấm điểm; lý do loại MUST được ghi nhận để xuất hiện trong kết quả/báo cáo.
- **FR-009** 🔲 CẦN LÀM: Mã `limited` MUST vẫn có thể được chấm điểm, và hạn chế dữ liệu đã biết MUST được nêu trong kết quả/báo cáo (không che giấu).

### Key Entities

- **Snapshot**: Hồ sơ dữ liệu một mã tại một `as_of`, gồm BCTC theo kỳ, nguồn, flags, và siêu dữ liệu chất lượng.
- **Data Source**: Định danh nguồn (chính vs phụ); mỗi số liệu truy về một nguồn.
- **Financial Line Item**: Một khoản mục BCTC theo kỳ (năm/quý); có thể trống, đã điền từ chính, hoặc đã điền từ phụ.
- **Enrichment Result**: Kết quả làm giàu một mã: mục đã điền, mismatch, flags (`mismatch`, `ticker_not_found`, thiếu dữ liệu, v.v.).
- **Universe Member**: Một mã trong tập phân tích kèm nhãn chất lượng `full` | `limited` | `insufficient`.
- **Quality Gate**: Quy tắc phân loại mức đầy đủ dữ liệu quyết định có được chấm điểm hay không.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001** ✅ (covered by M1 tests): Trên bộ kiểm thử offline cố định gồm ít nhất 5 mã có mục trống có thể điền từ nguồn phụ, sau enrich ≥ 90% các mục trống có sẵn trên nguồn phụ được điền đúng (khớp giá trị fixture), không có mục đã có từ nguồn chính bị ghi đè khi mismatch.
- **SC-002** ✅ (covered by M1 tests): Trong mọi trường hợp mismatch trên bộ kiểm thử, 100% giữ nguồn chính và 100% có flag mismatch có thể đọc được trong kết quả.
- **SC-003** 🔲 (FR-008/009): 100% mã gắn `insufficient` trong bộ kiểm thử bị loại khỏi chấm điểm; 100% mã `full`/`limited` vẫn đi vào chấm điểm khi các bước khác thành công; mã `limited` có hạn chế lộ trên kết quả/báo cáo.
- **SC-004** ✅ (covered by M1 ops path): Người vận hành hoàn thành một vòng enrich + xem tóm tắt cho một ngày `as_of` và một universe ≤ 30 mã trong một phiên làm việc liên tục (không cần sửa tay từng file snapshot để gắn nguồn/flag).
- **SC-005**: Pipeline end-to-end trên snapshot demo chuẩn vẫn chạy trọn và không hồi quy hành vi chấm điểm khi hoàn tất FR-008/009 (và khi enrich không đổi dữ liệu).

## Assumptions

- Nguồn chính mặc định vẫn là vnstock; vnfinancialdata chỉ đóng vai trò điền chỗ trống và đối chiếu, không thay thế nguồn chính khi lệch.
- Nhãn chất lượng `full` / `limited` / `insufficient` đã được M1 gán; backlog còn lại chỉ **tiêu thụ** nhãn đó ở bước chấm điểm và báo cáo — **không sửa** `m1_data/`.
- Universe ngoài VN30 có thể cấu hình tường minh; không yêu cầu universe point-in-time trong phạm vi tính năng này (phù hợp hiến chương hiện hành).
- Enrich áp dụng BCTC năm (và các khoản mục đã có trong hợp đồng dữ liệu hiện tại); không mở rộng sang sản phẩm/phái sinh mới trong scope này.
- Kiểm thử chấp nhận dùng fixture/dữ liệu giả bắt chước nguồn phụ; không phụ thuộc gọi mạng trong CI.
- Báo cáo cuối (PDF) chỉ cần phản ánh flags/hạn chế đã gắn; không yêu cầu giao diện web mới.
