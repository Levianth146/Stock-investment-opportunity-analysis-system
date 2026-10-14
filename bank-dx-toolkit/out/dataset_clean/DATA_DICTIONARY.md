# Từ điển dữ liệu bàn giao

Ngày tạo gói: 2026-10-14. Có 414 dòng số liệu đã xác nhận trên 600 dòng đầu vào.
Gói được tạo từ dữ liệu hiện tại; thông tin phạm vi, định nghĩa và ngoại lệ nằm trong note/definition của từng dòng.

- dti_inputs_confirmed.csv: số hữu hạn, có nguồn/trang, được người chấm đối chiếu PDF; loại range-checked và mọi nhãn tự động.
- dti_inputs_full.csv: toàn bộ đầu vào, gồm ô trống và lý do thiếu. Không thay đổi dữ liệu gốc.
- availability_matrix.csv: dti_ind_computable/data_conf là số tính được trước cổng; dti_ind_used/scoring_coverage là số dùng sau Bước 0 / 11.
- variable_availability_matrix.csv: Phụ lục B.3, ngân hàng × biến × năm, xác nhận/nguồn/trang và số ngân hàng thiếu biến.
- indicator_availability_matrix.csv và step0_gate.csv: khả năng tính chỉ số và quyết định giữ/loại chung từng năm; thiếu >=2 ngân hàng thì loại.
- coding_final.csv: các điểm thuật toán đã có từ coding_auto.xlsx, kèm phiên bản quy tắc và bằng chứng.
- app_ratings.csv: lịch sử thu thập; bước 10 chọn ngày mới nhất từng ngân hàng và dòng cuối cùng mỗi cửa hàng trong ngày đó.
- sources.csv: URL và ghi chú tài liệu; BCPTBV tùy chọn, có thể tích hợp trong BCTN.

Các cột đầu vào: bank, year, variable, value, unit, source_file, page, confirmed_by, note, definition.
Bước 19 bổ sung review_status (pending/resolved), reviewed_by, review_date (YYYY-MM-DD), review_evidence; gói giữ nguyên các cột này.
resolved chỉ giải quyết cờ ghi chú ở lớp C khi đủ người/ngày/bằng chứng; không thay thế xác nhận PDF hoặc kiểm tra phạm vi.
net_profit_parent dùng cho ROE với equity definition=parent; net_profit_consolidated dùng cho ROA với total_assets definition=consolidated. Không sao chép net_profit khi chưa xác nhận phạm vi.
page là số trang PDF từ 1. verification trong bản confirmed là đã đối chiếu PDF.
range-checked chỉ kiểm khoảng hợp lý, chưa đọc PDF; nằm trong bản full, chưa dùng tính điểm chính thức.
not_collected là chưa thu thập; not_disclosed là đã đọc và không có. Ô thiếu để trống, không điền 0.

| Biến | Đơn vị ghi trong đầu vào | Có số/tổng dòng | Đã đối chiếu đủ nguồn |
|---|---|---|---|
| casa_deposits | VND million | 25/30 | 25 |
| customer_deposits | VND million | 30/30 | 30 |
| digital_customer_share | % | 1/30 | 1 |
| digital_customers | customers | 8/30 | 8 |
| digital_txn_share | %, percent | 19/30 | 19 |
| equity | VND million | 30/30 | 30 |
| headcount | employees, persons | 28/30 | 28 |
| nci | VND million | 30/30 | 30 |
| net_fee_income | VND million | 30/30 | 30 |
| net_interest_income | VND million | 30/30 | 30 |
| net_profit | VND million | 29/30 | 29 |
| net_profit_consolidated | VND million | 0/30 | 0 |
| net_profit_parent | VND million | 0/30 | 0 |
| op_profit_before_provision | VND million | 30/30 | 30 |
| opex | VND million | 30/30 | 30 |
| software_gross_cost | VND million | 24/30 | 24 |
| tech_staff | persons | 1/30 | 1 |
| total_assets | VND million | 30/30 | 30 |
| total_customers | customers | 19/30 | 19 |
| training_hours_per_head | hours | 20/30 | 20 |

Công thức theo scripts/10_score.py; mốc đầu kỳ mặc định 2021, S-Q2/O-Q2 cần cách ít nhất 2 năm.
S-Q1 và S-Q2 cần cùng definition. CIR = abs(opex)/(abs(opex)+LN trước dự phòng); TOI = abs(opex)+LN trước dự phòng.
T-Q1 dùng tổng tài sản bình quân; O-Q2 dùng CBNV bình quân. Nếu thiếu năm trước, bước 10 ghi rõ trường hợp dùng cuối kỳ.
T-Q2 cần đủ 8 mã nền tảng duy nhất, giá trị 0/1. Rating/checklist chỉ áp dụng cho năm cuối được chọn.
z = 100·min{1; max[0; (x−L)/(U−L)]}; L/U cố định trong config/dti_bounds.yaml, phải khóa trước tính chính thức.
Nếu trụ cột thiếu DTI, P_k = DBI_k; trọng số cơ sở 80/20 và trung bình 6 trụ cột.
Bước 0 bắt buộc ở cấp chỉ số DTI theo từng năm; không xóa số gốc, không tự thay proxy. Cận L/U và mẫu số độ tin cậy 11 không đổi.
Rating/checklist chỉ áp cho năm cuối của dự án, không áp lùi khi chạy riêng một năm lịch sử. Bộ DTI giữ lại khác nhau giữa các năm.

Mọi số và điểm phải được truy vết tới nguồn gốc. Xem README.md, config và ghi chú từng dòng trước khi dùng kết quả.
