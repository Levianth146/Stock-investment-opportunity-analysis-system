# BIÊN BẢN KIỂM TRA CHẤT LƯỢNG PDF & TIẾNG VIỆT (QA13)

- Người kiểm thử: N6
- Người duyệt: N1
- Môi trường kiểm thử: Windows 11, Python 3.12, xhtml2pdf / Jinja2

## Danh sách ca kiểm thử trên 3 mã cổ phiếu VN30:
| Mã | Loại báo cáo | Hiển thị tiếng Việt | Ngắt trang (Page Break) | Tràn bảng / Lỗi layout | Trạng thái |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **HPG** | Tóm tắt (2 trang) | Đạt (font Roboto/DejaVu rõ ràng) | Đạt | Không tràn | PASS |
| **HPG** | Chi tiết (10 trang) | Đạt | Đạt (các bảng BCTC chia trang đẹp) | Không tràn | PASS |
| **FPT** | Tóm tắt (3 trang) | Đạt | Đạt | Không tràn | PASS |
| **FPT** | Chi tiết (12 trang) | Đạt | Đạt | Không tràn | PASS |
| **VCB** | Tóm tắt (2 trang) | Đạt | Đạt | Không tràn | PASS |
| **VCB** | Chi tiết (11 trang) | Đạt | Đạt | Không tràn | PASS |

## Kết luận:
100% tài liệu xuất ra đọc tốt tiếng Việt có dấu, ngày tháng định dạng đúng chuẩn Việt Nam, có đầy đủ snapshot hash và disclaimer.