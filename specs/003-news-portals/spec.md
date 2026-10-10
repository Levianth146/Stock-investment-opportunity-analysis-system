# Feature Specification: Vietnamese Financial News Portals (M1)

**Feature Branch**: `003-news-portals`

**Created**: 2026-10-10

**Status**: Draft

**Input**: User description: "Feature 003: Lấy tin tức từ cổng tin tài chính Việt Nam cho M1 (news portals). Thêm CafeF, VnEconomy, TinNhanhChungKhoan; ngày đăng chính xác đến ngày; URL gốc; bật/tắt news_portals_enabled; chỉ VN30/VN100; tôn trọng rate limit/cache; đúng contract news; cờ chất lượng; không khóa trong repo; ghi THIRD_PARTY_NOTICES nếu tái dùng code."

## Clarifications

### Session 2026-10-10

- Q: Khi tìm tin trên các cổng, bài cũ nhất được phép lấy so với `as_of` là bao xa? → A: Cùng cửa sổ tin M1 hiện hành (cùng cấu hình lookback với luồng Google News, không dùng cửa sổ 5 năm của BCTC)
- Q: Sau khi lọc ngày và loại trùng, mỗi mã được giữ tối đa bao nhiêu bài tin từ các cổng (tổng hoặc theo từng cổng)? → A: Gộp Google News + cổng, loại trùng, sắp mới nhất trước rồi cắt theo hạn mức tin M1 hiện hành; khi trùng giữa hai nguồn giữ bản cổng (URL gốc, ngày đăng chính xác)
- Q: Khi một cổng được gọi thành công nhưng không còn bài nào sau lọc ngày/trùng, cờ nào phải gắn? → A: `news_portal_ok:<cổng>` khi ≥1 bài hợp lệ sau lọc ngày/trùng (**trước** cắt trần `max_news`); `news_portal_empty:<cổng>` khi gọi thành công nhưng 0 bài sau lọc; `news_portal_failed:<cổng>` chỉ khi lỗi mạng/parse; cờ empty không làm hạ `quality_tier`
- Q: Khi cổng không có đoạn tóm tắt riêng nhưng có nội dung bài, trường `summary` trong tin snapshot phải chứa gì? → A: Cắt đoạn đầu body theo **đúng** giới hạn độ dài summary của luồng tin M1 hiện có; không null nếu đã có body
- Q: Khi chỉ biết được ngày đăng (không có giờ), `published_at` phải ghi như thế nào để vẫn đủ độ phân giải ngày và so sánh với `as_of`? → A: Có giờ thật → ISO đầy đủ như nguồn hiện có; chỉ ngày → `YYYY-MM-DD`; không bịa giờ; lọc look-ahead theo `published_at[:10] <= as_of`; test bài đúng ngày `as_of` có giờ và không giờ
- Q: Fixture HTML và cổng cần JS / robots? → A: Spike thật từng cổng (1 mã), lưu HTML thật làm fixture; kiểm robots.txt/điều khoản; cổng bắt buộc render JS → ghi nhận và **loại khỏi phạm vi**
- Q: URL rỗng/`n/a` khi dedupe? → A: Không dùng làm khóa trùng; chỉ so tiêu đề chuẩn hóa (tin vnstock/VCI thường `url="n/a"`)
- Q: `--tickers` / `--tickers-file` bật portal? → A: Đặt `universe_name="custom"` → không bật portal

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Bổ sung tin từ cổng Việt Nam cho mã thiếu tin (Priority: P1)

Nhà phân tích chạy thu thập dữ liệu cho một mã thuộc VN30 hoặc VN100 tại ngày `as_of`. Google News trả ít tin hoặc URL redirect. Hệ thống (khi bật cổng tin) tìm bài trên các cổng trong `news_portals_active` (mặc định chỉ CafeF; VnEconomy/TNCK tắt vì không phục vụ tìm theo mã) theo mã (và tên công ty nếu cần), lấy tiêu đề, URL gốc, ngày đăng đủ ngày, tên nguồn và tóm tắt/nội dung chính; chỉ giữ bài có ngày đăng xác định và không sau `as_of`; gộp với tin Google sau khi loại trùng.

**Why this priority**: Trực tiếp giải quyết thiếu tin / `quality_news_few` — giá trị cốt lõi của tính năng.

**Independent Test**: Với fixture HTML offline cho từng cổng và snapshot có sẵn Google News, sau bước thu tin: có bài cổng với URL gốc, `published_at` đủ ngày ≤ `as_of`, không bài không-ngày; trùng với Google bị loại; cờ cổng thành công xuất hiện.

**Acceptance Scenarios**:

1. **Given** `news_portals_enabled` bật, mã thuộc VN30/VN100, fixture có ≥1 bài hợp lệ mỗi cổng **còn trong phạm vi** (trong cửa sổ `as_of`), **When** chạy thu tin M1, **Then** snapshot có thêm tin từ cổng với URL gốc (không URL redirect Google), đủ trường contract news, và `source_id`/nguồn gắn đúng cổng.
2. **Given** bài không xác định được ngày đăng đủ ngày, **When** xử lý kết quả cổng, **Then** bài bị bỏ, tăng đếm cờ `news_portal_no_date_dropped`, không gán ngày ước đoán/năm.
3. **Given** bài có ngày đăng sau `as_of` (so `published_at[:10]`), **When** lọc theo `as_of`, **Then** bài không vào snapshot (không look-ahead).
4. **Given** bài đăng đúng ngày `as_of` (một bản chỉ `YYYY-MM-DD`, một bản ISO có giờ thật), **When** lọc, **Then** cả hai được giữ nếu ngày ≤ `as_of`; không bịa giờ cho bản chỉ có ngày.
5. **Given** cùng bài đã có từ Google News (URL chuẩn hóa trùng hoặc tiêu đề gần giống sau chuẩn hóa), **When** gộp nguồn, **Then** chỉ giữ bản từ cổng (URL gốc, ngày đăng chính xác); sau đó sắp theo ngày mới nhất trước và cắt theo hạn mức tin M1 hiện hành.

---

### User Story 2 - Bật/tắt an toàn và giới hạn phạm vi universe (Priority: P2)

Người vận hành muốn thử cổng tin trên VN30/VN100 mà không đổi hành vi mặc định. Cờ cấu hình `news_portals_enabled` mặc định tắt. Khi tắt, luồng tin Google và kết quả VN30 giữ nguyên. Khi bật, chỉ áp dụng cho universe VN30 và VN100; universe rộng hơn (HOSE/HNX/UPCOM/ALL) không chạy cổng tin trong phạm vi này.

**Why this priority**: Bảo vệ hồi quy và kiểm soát chi phí/truy cập cổng tin.

**Independent Test**: Chạy cùng fixture với cờ tắt → không gọi/logic cổng, snapshot tin giống baseline; cờ bật + universe ngoài VN30/VN100 → không bổ sung tin cổng.

**Acceptance Scenarios**:

1. **Given** `news_portals_enabled` = false, **When** thu thập mã VN30, **Then** tập tin và cờ liên quan cổng không xuất hiện; hành vi tin Google như hiện tại.
2. **Given** cờ bật nhưng universe không phải VN30/VN100 (gồm `universe_name=custom` từ `--tickers` / `--tickers-file`), **When** thu thập, **Then** không bổ sung tin từ các cổng trong phạm vi (Google News vẫn theo cấu hình hiện có).

---

### User Story 3 - Chịu lỗi từng cổng và tái chạy không cào lại (Priority: P3)

Khi một cổng lỗi mạng/timeout/HTML đổi, snapshot vẫn hoàn tất với cờ thất bại cổng đó; các cổng còn lại và Google News tiếp tục. Bài đã lấy được cache theo URL để lần chạy `--resume` không tải lại. Hệ thống tôn trọng khoảng nghỉ giữa request và giới hạn số lần thử lại.

**Why this priority**: Ổn định vận hành batch; không chặn chất lượng toàn snapshot vì một cổng.

**Independent Test**: Fixture mô phỏng một cổng lỗi → snapshot vẫn hợp lệ + `news_portal_failed:<cổng>`; lần hai với cache đã có → không “tải lại” URL đã cache (kiểm chứng offline bằng spy/đếm).

**Acceptance Scenarios**:

1. **Given** một cổng trong phạm vi thất bại, **When** hoàn tất thu tin, **Then** snapshot vẫn lưu được; có `news_portal_failed:<tên>`; cổng gọi thành công có `news_portal_ok:<tên>` nếu ≥1 bài hợp lệ sau lọc ngày/trùng (trước cắt trần), hoặc `news_portal_empty:<tên>` nếu 0 bài sau lọc (empty không hạ `quality_tier`).
2. **Given** URL đã có trong cache bài, **When** chạy lại với resume, **Then** không phát sinh request mạng mới cho URL đó trong kiểm thử (offline: cache hit).

---

### Edge Cases

- Cổng trả kết quả tìm kiếm nhưng trang bài thiếu metadata ngày → bỏ bài + đếm `news_portal_no_date_dropped`.
- Tất cả cổng trong phạm vi thất bại → chỉ còn tin Google (nếu có); cờ failed cho từng cổng; `quality_tier` tính lại theo số tin cuối.
- Không tìm thấy bài nào cho mã trên một cổng (sau lọc) → `news_portal_empty:<cổng>`; không bịa tin; không hạ `quality_tier` chỉ vì cờ empty.
- Tiêu đề trùng gần giống nhưng URL khác → coi là trùng theo quy tắc chuẩn hóa tiêu đề (Assumptions); giữ một bản.
- URL rỗng/`"n/a"` khi dedupe → xem **FR-003** (không lặp quy tắc tại đây).
- Cổng yêu cầu render JS (phát hiện ở spike) → ngoài phạm vi phiên bản này; ghi nhận trong spec/plan sau spike.
- Có tóm tắt riêng → dùng tóm tắt (cắt theo hạn mức summary hiện hành). Không tóm tắt nhưng có body → `summary` = đoạn đầu body cùng hạn mức; chỉ null khi không có text nào.
- Khóa/API (nếu cổng hoặc thư viện tham khảo cần) chỉ từ biến môi trường người dùng; không nhúng trong repo.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Hệ thống MUST bổ sung bước lấy tin trực tiếp từ các cổng trong `news_portals_active` (mặc định `[cafef]`). Phạm vi hiện tại = **CafeF** (tìm theo mã qua `tim-kiem.chn?keywords=`). VnEconomy và TinNhanhChungKhoan **không** chạy mặc định: VnEconomy search HTML tĩnh trả cùng ~5 link cho mọi mã (kết quả thật nạp bằng JS); TNCK chỉ có chuyên mục không theo mã (probe 30/30 bài irrelevant). Parser hai cổng đó được giữ; chỉ bật lại khi có endpoint tìm kiếm theo mã hoặc RSS theo mã. Cổng JS-only khác vẫn bị loại theo FR-010. MUST tìm theo mã cổ phiếu (và tên công ty khi cần); thu thập tiêu đề, URL gốc, ngày đăng, tên nguồn, và tóm tắt hoặc nội dung chính.
- **FR-002**: Hệ thống MUST xác định ngày đăng chính xác đến **ngày** (từ trang bài hoặc metadata). Bài không xác định được ngày đủ độ phân giải ngày MUST bị loại và ghi nhận bằng cờ; MUST NOT đoán ngày; MUST NOT dùng độ phân giải chỉ năm. `published_at`: có giờ thật → ISO đầy đủ như nguồn tin hiện có; chỉ có ngày → `YYYY-MM-DD` (MUST NOT bịa giờ). Lọc look-ahead MUST so theo phần ngày `published_at[:10] <= as_of` (không so cả chuỗi). Chỉ giữ bài trong cửa sổ tin M1 hiện hành (cùng lookback Google News; không dùng `window_start` 5 năm BCTC). Kiểm thử MUST gồm bài đúng ngày `as_of` có giờ và không giờ.
- **FR-003**: Hệ thống MUST lưu URL gốc của cổng tin (không URL redirect Google). MUST gộp tin Google/vnstock với tin cổng: nếu URL hợp lệ (không rỗng, không `"n/a"`) thì loại trùng theo URL chuẩn hóa **hoặc** tiêu đề chuẩn hóa; nếu URL rỗng/`n/a` thì **chỉ** so tiêu đề chuẩn hóa. Khi trùng MUST giữ bản cổng. Sau đó MUST sắp theo `published_at` mới nhất trước và cắt theo **hạn mức tin M1 hiện hành** (`max_news`).
- **FR-004**: Hệ thống MUST cung cấp cờ cấu hình `news_portals_enabled` (mặc định **false**). Khi bật, bước cổng tin MUST chỉ áp dụng khi `universe_name` ∈ {`VN30`,`VN100`}. `--tickers` / `--tickers-file` MUST đặt `universe_name="custom"` (không bật portal). Khi tắt, hành vi tin hiện tại MUST không đổi.
- **FR-005**: Hệ thống MUST tôn trọng giới hạn truy cập: khoảng nghỉ giữa request, số lần thử lại có hạn, và cache bài theo URL để chạy lại/resume không cào lại URL đã có. Thất bại một cổng MUST NOT làm hỏng toàn bộ snapshot: ghi cờ và tiếp tục.
- **FR-006**: Mỗi tin cổng MUST tuân thủ contract `news` hiện có (id, title, url, source, published_at; summary optional/null). MUST NOT đổi schema hợp đồng. `summary` MUST dùng đoạn tóm tắt cổng nếu có, không thì đoạn đầu nội dung chính, cắt theo **cùng giới hạn độ dài** luồng tin M1 hiện hành; MUST NOT để null khi đã lấy được body/text. Mỗi tin MUST gắn `source_id` riêng theo cổng và mục trong `sources`. Nếu cần trường mới → dừng và hỏi N1.
- **FR-007**: Hệ thống MUST gắn cờ theo cổng: `news_portal_ok:<tên>` khi ≥1 bài hợp lệ từ cổng đó **sau lọc ngày/trùng và trước cắt trần** `max_news`; `news_portal_empty:<tên>` khi gọi thành công nhưng 0 bài sau lọc ngày/trùng; `news_portal_failed:<tên>` chỉ khi lỗi mạng hoặc parse thất bại; cộng `news_portal_no_date_dropped:<số>` khi bỏ vì thiếu ngày. Cờ `empty` MUST NOT tự làm hạ `quality_tier`. Bậc chất lượng MUST tính lại theo **số lượng tin cuối** (sau cắt trần).
- **FR-008**: Hệ thống MUST NOT nhúng token/khóa trong repo; mọi khóa (nếu cần) lấy từ biến môi trường của người dùng.
- **FR-009**: Nếu tái sử dụng mã từ dự án tham khảo (vn-annual-report-miner, MIT), hệ thống MUST ghi nhận trong `config/THIRD_PARTY_NOTICES.txt`.
- **FR-010**: Trước khi khóa fixture/parser, MUST có spike: thử thật từng cổng ứng viên với 1 mã, lưu HTML thật làm fixture offline; kiểm `robots.txt`/điều khoản; cổng bắt buộc JS render MUST được ghi nhận và loại khỏi phạm vi phiên bản này.

### Key Entities

- **News Item**: Một bài tin trong snapshot — id, title, url gốc, source (tên hiển thị), published_at (ngày đủ), summary tùy chọn; truy vết qua `news.id` + `url` và `sources` qua `source_id`.
- **News Portal**: Một cổng trong `news_portals_active` (mặc định CafeF). VnEconomy/TNCK có code parser nhưng ngoài danh sách active cho đến khi có tìm kiếm/RSS theo mã — trạng thái ok/empty/failed chỉ gắn cho cổng đã chạy.
- **Article Cache Entry**: Bản ghi theo URL gốc đã lấy thành công để tránh tải lại khi resume.
- **Dedup Key**: URL chuẩn hóa (chỉ khi URL hợp lệ — không rỗng, không `"n/a"`) và/hoặc tiêu đề chuẩn hóa dùng để loại trùng với Google/vnstock (chi tiết **FR-003**).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Trên bộ fixture offline cố định (HTML CafeF trong phạm vi active hiện tại; fixture VnEconomy/TNCK chỉ để giữ parser/gzip), ≥ 90% bài có ngày đủ ngày và ≤ `as_of` trong fixture active được đưa vào snapshot với URL gốc đúng cổng.
- **SC-002**: 100% bài thiếu ngày đủ độ phân giải ngày bị loại; 100% bài có `published_at[:10] > as_of` bị loại; không bài nào chỉ có năm được giữ bằng cách suy đoán ngày; bài đúng `as_of` (có giờ và chỉ ngày) đều được giữ trên fixture kiểm chứng.
- **SC-003**: Với cờ tắt, kết quả tin của kịch bản VN30 baseline offline khớp hành vi hiện tại (không hồi quy số lượng/URL Google so với fixture kiểm chứng).
- **SC-004**: Khi một cổng được mô phỏng lỗi, snapshot vẫn hoàn tất và có đúng cờ `news_portal_failed` cho cổng đó; các nguồn khác vẫn đóng góp tin nếu fixture cho phép.
- **SC-005**: Sau gộp tin, nếu số tin đủ ngưỡng chất lượng tin hiện hành thì không còn gắn `quality_news_few` chỉ vì thiếu Google News (trên fixture thiết kế để vượt ngưỡng nhờ cổng).
- **SC-006**: Kiểm thử chấp nhận chạy hoàn toàn offline (fixture HTML/cache giả); không phụ thuộc mạng trong CI.

## Assumptions

- Tên cổng CafeF, VnEconomy, TinNhanhChungKhoan là thực thể miền (nguồn tin), không phải lựa chọn stack.
- “Tiêu đề gần giống”: sau chuẩn hóa (chữ thường, gộp khoảng trắng, bỏ dấu câu đầu/cuối) — trùng chuỗi thì coi là trùng; không bắt buộc fuzzy phức tạp ở phiên bản này.
- Khi trùng Google vs cổng: giữ bản cổng (URL gốc, ngày đăng chính xác), bỏ bản Google tương ứng — quy tắc dedupe URL/`n/a` xem **FR-003**.
- Không trần riêng theo cổng; trần áp dụng **sau gộp**: sắp mới nhất trước rồi cắt theo hạn mức tin M1 hiện hành.
- Bộ cờ cổng: ok (≥1 bài sau lọc ngày/trùng, **trước** cắt trần `max_news`), empty (0 bài sau lọc, thành công), failed (lỗi); empty ≠ tín hiệu chất lượng xấu.
- `summary`: cùng trần độ dài với tin hiện có; ưu tiên tóm tắt cổng, else đầu body; null chỉ khi không có text.
- `published_at`: ISO đầy đủ nếu có giờ thật; không thì `YYYY-MM-DD`; look-ahead theo `[:10]`.
- `news_portals_enabled` mặc định false; `news_portals_active` mặc định `[cafef]` trong cấu hình dùng chung.
- Universe “VN30” / “VN100” xác định theo `cfg["universe_name"]`; `--tickers` / `--tickers-file` → `universe_name="custom"` → không bật portal.
- Fixture HTML MUST lấy từ trang thật (spike), không tự viết HTML giả cho parser/fixture tests.
- Phạm vi chạy = `news_portals_active` (hiện CafeF); VE/TNCK tắt vì search không theo mã / chuyên mục lệch mã (không chỉ vì JS-only).
- Ngưỡng số tin cho `quality_news_few` / `quality_tier` giữ như cổng chất lượng M1 hiện hành; chỉ đổi đầu vào là số tin sau gộp.
- Google News vẫn là nguồn tin song song khi bật; cổng tin là bổ sung, không thay thế bắt buộc.
- Cửa sổ ngày cổng tin = cùng lookback với Google News trong cấu hình M1 hiện hành (ví dụ số ngày cửa sổ tin Google), không phải cửa sổ giá/BCTC 5 năm.
- Ngoài phạm vi: UPCOM/HNX/HOSE toàn sàn, phân tích cảm xúc (M5), mọi thay đổi chấm điểm (M2–M9), đổi schema news.
- Thư viện bổ sung chỉ được cân nhắc nhẹ (ví dụ tách nội dung HTML) nếu thật sự cần; ưu tiên stdlib + HTML fixture.
