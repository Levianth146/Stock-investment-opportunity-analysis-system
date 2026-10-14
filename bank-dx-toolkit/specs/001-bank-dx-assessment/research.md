# Nghiên cứu và quyết định kỹ thuật

| # | Quyết định | Lý do | Phương án đã loại |
|---|---|---|---|
| R1 | Nhiều engine PDF, chọn từng trang theo `junk_score` thấp nhất | PDF tiếng Việt hay lỗi `(cid:..)`, tách dấu | Một engine duy nhất |
| R2 | Khớp từ khóa mờ khoảng trắng; acronym ≤ 6 ký tự khớp phân biệt hoa/thường | "Tiề n", "RPA" khớp nhầm trong từ khác | Khớp chuỗi con thuần |
| R3 | Nhãn BCTC so sánh bằng `squeeze()` và gộp nhãn xuống dòng | Nhãn mục IX bị chia 2–3 dòng | Regex theo từng dòng |
| R4 | Chuẩn hóa DTI bằng L, U khóa trước | MAX của 5 ngân hàng làm điểm phụ thuộc mẫu | Min-max trong 5 ngân hàng (chỉ làm kịch bản độ nhạy tùy chọn, không phải mặc định) |
| R5 | BM25 + độ phủ + tỷ lệ câu định lượng | BM25 giảm ảnh hưởng báo cáo dài/lặp từ; độ phủ chống lặp một từ | Đếm từ khóa thô |
| R6 | LDA sklearn, UMass + nhiều seed + Jaccard | Không thêm phụ thuộc gensim; có kiểm soát ổn định | Chọn K chỉ theo perplexity |
| R7 | PhoBERT làm bộ lọc câu bằng chứng (đã chấm `valid`), không chấm điểm | Rubric cần phán đoán người; lọc sai-nghĩa là việc mô hình làm tốt | Dùng PhoBERT chấm 0–4 trực tiếp (dữ liệu quá ít) |
| R8 | Neo rubric (`--anchors`) chỉ để gợi ý | Embedding PhoBERT thô không huấn luyện cho tương đồng câu | Dùng làm điểm |
| R9 | Rating app = trung bình gia quyền App Store và Google Play | Hai kho khác số lượt đánh giá; iTunes `averageUserRating` là trung bình mọi phiên bản | Chỉ một kho |
| R10 | Cửa sổ năm chính thức **2020–2025**; 2020 là năm cơ sở (biến động, bình quân đầu–cuối kỳ cho 2021) | Đủ chuỗi thời gian + cần số đầu kỳ cho ROE/ROA/CASA năm 2021 | Chỉ 2023+2025; hoặc 2021–2025 không có năm cơ sở |
| R11 | L, U từ **chuẩn ngành / tài liệu công bố**; ghi nguồn từng chỉ số trong `dti_bounds.yaml` | Hiến chương V + biện minh học thuật; không neo theo mẫu n=5 | Phân vị lịch sử mẫu làm nguồn chính; lai phân vị+ngành (có thể xem xét sau nếu thiếu chuẩn) |
| R12 | Chấm: **2 người độc lập**; bất đồng (lệch ≥ 2 bậc hoặc thảo luận không xong) → **người thứ ba**; κ trên cặp độc lập **trước** hòa giải | Cân bằng chi phí và độ tin cậy; tránh đồng thuận lệch hệ thống | Chỉ thảo luận tới đồng thuận (A); 3 người + trung vị mọi tiêu chí (C) |
| R13 | BCPTBV **tùy chọn**; trạng thái `tích hợp trong BCTN` / `không công bố` / `chưa tìm thấy`; không dán trùng PDF | Nhiều NH gộp ESG vào BCTN; tránh đếm đôi từ khóa; `tích hợp` ≠ thiếu dữ liệu ESG | Bắt buộc file BCPTBV riêng mọi năm |

## Rủi ro mở
- **Chưa chạy trên báo cáo/web thật**: regex nhãn BCTC và KPI có thể cần chỉnh theo từng ngân hàng.
- **n = 5**: mọi so sánh Spearman/Kendall chỉ mô tả; không suy diễn nhân quả.
- **Chuẩn ngành thiếu cho một số chỉ số DTI**: phải ghi nguồn thay thế công bố + lý do trong `dti_bounds.yaml` trước khi chấm; không được fallback sang MAX mẫu.
- **Link sources chưa đủ**: checklist còn trống; 01 không tự dò link.
- **Thay đổi giao diện web ngân hàng**: `06_probe_web.py` chỉ snapshot; không phụ thuộc DOM sâu.
- **PhoBERT**: cần ≥ ~30 câu `valid`/tiêu chí; dưới đó chỉ tham khảo / dùng `--anchors`.
- **NFR-03 vs 6 năm**: đo lại thời gian xử lý trên máy thật sau T024.
