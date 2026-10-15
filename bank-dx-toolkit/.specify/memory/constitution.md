# Hiến chương dự án (Constitution) — Đánh giá chuyển đổi số ngân hàng

Phiên bản 2.0 (2026-10-12: nhóm quyết định thay chấm tay/kappa bằng thuật toán quy tắc) · Mọi spec, plan, task và đoạn code phải tuân thủ các nguyên tắc dưới đây. Sửa hiến chương cần ghi lý do và tăng phiên bản.

## I. Thuật toán quyết định điểm DBI
Điểm DBI 0–4 được tạo bằng quy tắc xác định trong `09c_auto_score.py`, lưu vào `coding_auto.xlsx`; bước 10 dùng làm đầu vào chính. Không yêu cầu chấm kép hoặc kappa. Mỗi kết quả phải kèm phiên bản quy tắc, hash đầu vào và bằng chứng. Quy tắc là phép vận hành hóa rubric cần đánh giá chất lượng, không tuyên bố mặc nhiên tương đương đánh giá chuyên gia. Text mining (BM25, LDA, PhoBERT) là chỉ số phụ để đối chiếu và kiểm tra độ nhạy, không đi vào công thức điểm.

## II. Dữ liệu công khai, có đạo đức
Chỉ thu thập dữ liệu công khai. Tôn trọng robots.txt, delay ≥ 3 giây, không đăng nhập, không vượt paywall/captcha, không scrape bên trong ứng dụng. Ghi User-Agent nêu mục đích nghiên cứu.

## III. Truy vết được
Mọi con số và mọi điểm phải lần ngược được tới: tệp nguồn, số trang, đoạn trích gốc, ngày thu thập (hash sha256 của PDF trong `manifest.csv`). Không có nguồn thì không có số.

## IV. Trung thực với dữ liệu thiếu
Không điền 0 cho chỉ tiêu DTI không công bố hoặc DBI thiếu văn bản đọc được. DBI=0/no_mention là không phát hiện đề cập bằng thuật toán trong văn bản đã quét, không chứng minh ngân hàng không công bố. Thiếu DTI của một trụ cột thì P_k = DBI_k. Báo cáo điểm tin cậy dữ liệu (số chỉ tiêu có dữ liệu / 11) cạnh mọi điểm DTI.

## V. Công thức khóa trước khi chấm
Thang chuẩn hóa z = 100·min{1; max[0; (x−L)/(U−L)]} với L và U cố định trước khi chấm, không lấy MAX của 5 ngân hàng. Trọng số 80/20 và 1/6 mỗi trụ cột là mặc định; mọi thay đổi phải đi qua kịch bản độ nhạy, không sửa lặng lẽ.

## VI. Độ nhạy và thống kê trung thực
n = 5 ngân hàng nên chỉ mô tả. Luôn báo kịch bản độ nhạy (DBI/DTI 100/0, 80/20, 70/30, 60/40; Dirichlet Monte Carlo trên trọng số trụ cột; Kendall τ, Spearman). Một thứ hạng chỉ gọi là "vững" nếu giữ nguyên trong ≥ 80% kịch bản.

## VII. Kiểm thử trước khi tuyên bố
Sau khi sửa `common.py`, 02, 03, 04, 07 phải chạy `tests/smoke_test.py`. Không báo hoàn thành khi chưa chạy. Điều chỉnh regex theo PDF thật phải kèm trường hợp kiểm thử mới.

## VIII. Đơn giản và tái lập
Python thuần, ít phụ thuộc (torch chỉ cho PhoBERT). Mọi bước chạy lại được từ `scripts/` với cùng đầu vào cho cùng đầu ra. Seed cố định cho LDA và PhoBERT.

## IX. Ngôn ngữ
Tiếng Việt cho tài liệu, chú thích, thông báo; tên biến/hàm tiếng Anh. Tệp CSV ghi `utf-8-sig`.
