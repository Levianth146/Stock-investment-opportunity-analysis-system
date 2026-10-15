# Kiểm tra dữ liệu cổ phiếu ngày 15/10/2026

Nguồn đang phục vụ: `data/snapshots`, ngày snapshot `2026-10-08`, hồ sơ `long_term`.

Đã đọc snapshot và chạy hàm phân tích API (`analyze_snapshot`) cho toàn bộ 707 mã; sau khi sửa, gọi HTTP `POST /api/analyze` cho cả 707 mã cũng trả 200, không có lỗi đổi mã/ngày snapshot hay lệch metadata catalog. Có dữ liệu snapshot không đồng nghĩa đủ điều kiện xếp hạng.

| Tình trạng | Số mã |
| --- | ---: |
| Tổng số có snapshot | 707 |
| Chất lượng đầy đủ (`full`) | 146 |
| Chất lượng hạn chế (`limited`), vẫn được xếp hạng | 89 |
| Không đủ điều kiện xếp hạng (`insufficient`) | 472 |
| Có giá đóng cửa trong snapshot | 704 |
| Chưa có giá: ATP, BCH, MDD | 3 |

472 mã không có điểm tổng hợp và giá mục tiêu là kết quả của quality gate hiện tại, không phải 472 lỗi API. Trong nhóm này, 459 mã mang cờ thanh khoản không đạt ngưỡng; 27 mã mang cờ lịch sử giá dưới 750 phiên. Các nguyên nhân có thể chồng lấp. Lần thu thập rộng dùng chế độ nhanh đã gắn `fetch_skipped_early` cho những trường hợp dừng sớm, vì vậy nhiều snapshot chỉ có doanh nghiệp/giá/chỉ số/peers, chưa lấy BCTC và tin tức.

## Hai mã được phản ánh

| Mã | Doanh nghiệp | Giá gần nhất (VND/cổ phiếu) | Ngày giá | Số phiên giá nguồn | BCTC năm/quý | Tin tức |
| --- | --- | ---: | --- | ---: | --- | --- |
| ABR | Công ty Cổ phần Đầu tư Nhãn Hiệu Việt | 10.350 | 2026-10-07 | 1.217 | 0 / 0 | Chưa thu thập |
| AMC | Công ty Cổ phần Khoáng sản Á Châu | 12.900 | 2026-10-07 | 1.202 | 0 / 0 | Chưa thu thập |

Cả hai có cờ `quality_illiquid`, `quality_tier_insufficient` và `fetch_skipped_early`. API vẫn trả thông tin doanh nghiệp và tối đa 252 phiên giá. `score`, `scores` tổng hợp và `target_price` trả `null` theo quy tắc, không được thay bằng điểm trung tính hay dữ liệu của FPT.

## Điều chỉnh hiển thị

- API bổ sung `data_availability`: số phiên giá, số BCTC năm/quý có thể công bố, số tin nguồn, ngày giá và trạng thái thu thập dừng sớm. Catalog bổ sung bậc chất lượng, nguyên nhân và cờ thu thập chưa đầy đủ.
- Giao diện báo rõ lý do chưa xếp hạng, phần nào có/chưa có dữ liệu và ngày giá thực tế nếu khác ngày snapshot.
- Với mã không xếp hạng, các thẻ hiển thị điểm riêng của mô-đun đã tính được (ví dụ kỹ thuật/rủi ro), ghi rõ “Điểm riêng · Chưa xếp hạng”. Các điểm này không thay đổi kết luận của quality gate.
- Danh sách tìm kiếm đánh dấu mã chưa xếp hạng trước khi chọn.
- Loại các dòng giá đóng cửa không hợp lệ trước khi chọn giá mới nhất, thống nhất với catalog.

Chưa tải bổ sung BCTC/tin tức và chưa sửa các snapshot nguồn trong lần kiểm tra này. Muốn có thêm BCTC cần chạy thu thập sâu có mục tiêu bằng tính năng `--deep` của `scripts/fetch_universe.py`; việc bổ sung dữ liệu không đảm bảo mã sẽ được xếp hạng nếu vẫn không đạt tiêu chí thanh khoản. Cần gán lại peers theo hướng dẫn của script và khởi động lại API sau khi thay snapshot. Không trộn dữ liệu ngày khác để lấp chỗ trống.

Bản chi tiết theo mã của lần rà soát lưu tại `data/web_preview/ticker-audit.json` trên máy (artifact sinh ra, không commit).
