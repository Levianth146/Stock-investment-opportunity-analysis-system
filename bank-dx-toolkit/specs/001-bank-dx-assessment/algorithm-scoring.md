# Phương pháp chấm DBI bằng thuật toán quy tắc

Ngày quyết định: 2026-10-12. Nhóm thay quy trình chấm tay, hòa giải và kappa bằng thuật toán xác định trong `scripts/09c_auto_score.py`. Phiên bản đầu: `rule-based-v1`. Khung DBI 80% + DTI 20%, sáu trụ cột và chuẩn hóa DTI giữ nguyên.

## Quy tắc hiện thực

Từ khóa song ngữ định vị cửa sổ văn bản (mặc định ±300 ký tự). Thuật toán kiểm tra động từ hành động, con số kèm đơn vị và điều kiện bổ sung của từng tiêu chí trong bảng L4 của script.

| Trạng thái | Điểm | Ý nghĩa của phép đo |
|---|---|---|
| no_document | Trống | Không có văn bản đọc được sau bộ lọc; không suy ra điểm 0 |
| no_mention | 0 | Có văn bản đọc được nhưng không tìm thấy từ khóa; không chứng minh ngân hàng không công bố |
| scored | 1 | Có đề cập nhưng chưa bắt được hành động thực hiện |
| scored | 2 | Bắt được hành động thực hiện, loại câu tương lai/phủ định nhận diện được |
| scored | 3 | Hành động và con số kèm đơn vị trong cùng cửa sổ |
| scored | 4 | Có mức 3 và đủ điều kiện L4 theo tiêu chí: dấu hiệu kiểm chứng, đa kỳ, quản trị, lộ trình, KPI hoặc chứng nhận |

Điều kiện đa kỳ sử dụng cửa sổ ba năm trước hoặc dấu hiệu nhiều năm trong văn bản. Lọc năm đầu ra không loại tài liệu lịch sử cần cho điều kiện này. Chỉ dùng trang có chữ và chất lượng trích xuất chấp nhận được; BCPTBV tùy chọn.

## Truy vết và tái lập

- `auto_scores.csv`: điểm, trạng thái, đặc trưng, tệp/trang/đoạn trích đại diện và `supporting_evidence` JSON chứa các bằng chứng dùng để chấm, kể cả tài liệu năm trước.
- `coding_auto.xlsx`: điểm thuật toán trong `final`, cùng metadata; đầu vào mặc định của bước 10. Bản hiển thị loại ký tự điều khiển XML từ PDF, đoạn gốc vẫn giữ trong CSV. Bằng chứng vượt giới hạn độ dài ô Excel được thay bằng tham chiếu dòng tương ứng trong auto_scores.csv, không cắt nội dung. Không ghi đè bảng chấm tay lưu trữ.
- `auto_scoring_manifest.json`: phiên bản/hash code 09c + common và keywords, hash JSONL cùng cấu hình lưới ngân hàng/năm, tham số cửa sổ/bộ lọc. Giữ manifest cùng kết quả khi công bố.
- `confidence` chỉ là nhãn mức hỗ trợ dựa trên số đoạn, không phải xác suất điểm đúng.

## Kiểm chứng chất lượng

Không dùng kappa giữa người chấm như điều kiện của pipeline mới. Cần kiểm thử ca mức 0–4, phủ định/tương lai, thiếu tài liệu, bộ lọc và tái lập. Kiểm tra mẫu bằng chứng, độ phủ tài liệu và độ nhạy khi đổi cửa sổ/từ khóa; chưa tuyên bố độ chính xác nếu chưa có đánh giá độc lập phù hợp.

Quy tắc hiện tại là phép vận hành hóa khung rubric từ dấu hiệu văn bản. Động từ, số liệu hay tên tổ chức trong cùng cửa sổ có thể nói về chủ đề khác; dấu hiệu chứng nhận không tự chứng minh chứng nhận còn hiệu lực. Lỗi OCR, ngôn ngữ và cách ngân hàng viết báo cáo có thể đổi điểm. Báo cáo nghiên cứu phải mô tả giới hạn này; không tuyên bố điểm thuật toán tương đương đánh giá chuyên gia hoặc mức triển khai thực tế đã được xác minh.

## Chạy

Chạy từ thư mục `scripts/`:

```powershell
python 09c_auto_score.py
python 12_appendix.py --bundle
python 10_score.py --draft --weight-scenarios
```

Khi L/U đã chốt và khóa, DBI đủ dữ liệu thì bỏ `--draft`. Thiếu DTI vẫn để trống; trụ cột không có DTI dùng P_k = DBI_k.
