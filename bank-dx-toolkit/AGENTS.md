# AGENTS.md — bank_dx_toolkit

## Dự án là gì
Bộ công cụ thu thập và text mining dữ liệu công khai để chấm điểm, xếp hạng chuyển đổi số của 5 ngân hàng
(Agribank, MB, Techcombank, BIDV, Vietcombank) theo mô hình **DBI thích ứng (80%) + DTI (20%)**: 6 trụ cột, 24 tiêu chí
rubric 0–4, 11 chỉ số DTI. Theo quyết định của nhóm ngày 2026-10-12, **09c chấm DBI bằng thuật toán quy tắc**, thay quy trình chấm tay và kappa.
Điểm thuật toán cùng bằng chứng/phiên bản nằm trong `out/coding_auto.xlsx`; bước 10 đọc file này mặc định.
Rubric (`config/rubric_anchors.csv`) là khung tham chiếu; quy tắc vận hành hóa phải được mô tả và kiểm chứng riêng.
Text mining (07 BM25, 08 LDA, 09 PhoBERT) là chỉ số phụ để đối chiếu, không phải điểm chính.

## Cấu trúc
- `config/` banks.yaml, keywords.yaml (24 tiêu chí), rubric_anchors.csv (96 mô tả mức), sources.csv
- `scripts/` 00–09, chạy **từ thư mục `scripts/`**; `common.py` giữ đường dẫn và hàm dùng chung
- `data/raw|text|web` đầu vào/trung gian (không commit); `out/` kết quả; `models/` PhoBERT đã tinh chỉnh (không commit)
- `specs/001-bank-dx-assessment/` đặc tả, kế hoạch, task (Spec Kit); `.specify/memory/constitution.md` nguyên tắc dự án

## Luật cứng (không được vi phạm khi sửa code)
1. Chỉ thu thập dữ liệu công khai. Tôn trọng robots.txt, giữ delay ≥ 3 giây giữa các request, không đăng nhập, không scrape bên trong app, không vượt paywall/captcha.
2. Không bao giờ điền 0 cho chỉ tiêu ngân hàng không công bố; để trống và tính độ tin cậy dữ liệu (số chỉ tiêu có dữ liệu / 11). Thiếu DTI của trụ cột → P_k = DBI_k.
2b. BCPTBV (báo cáo phát triển bền vững) là tùy chọn, nhiều ngân hàng tích hợp trong BCTN: không coi là thiếu dữ liệu, không dán trùng một PDF vào hai loại báo cáo.
2c. Báo cáo có cả tiếng Việt lẫn tiếng Anh. Từ khóa (`keywords.yaml`), nhãn BCTC và mẫu KPI phải giữ cả hai thứ tiếng. Chỉ số text mining so sánh trong cùng ngôn ngữ; LDA/PhoBERT chỉ cho tiếng Việt. Không xóa từ khóa tiếng Anh khi dọn từ điển.
3. Script được ghi điểm thuật toán vào `coding_auto.xlsx` cột `final`, kèm phương pháp/phiên bản/bằng chứng. Giữ `coding_sheet.xlsx` cũ làm dữ liệu lưu trữ, không ghi đè. Không yêu cầu coder1/coder2 hoặc kappa trong pipeline mới.
3b. Thiếu văn bản đọc được → DBI để trống. Điểm 0 `no_mention` chỉ nghĩa là thuật toán không tìm thấy đề cập trong tài liệu đã quét; không được gọi là ngân hàng không công bố.
4. Mọi con số trích ra phải kèm tệp nguồn, số trang, và (nếu có) đoạn trích gốc.
5. Không đổi thang chuẩn hóa: z = 100·min{1; max[0; (x−L)/(U−L)]}, L và U cố định TRƯỚC khi chấm, không dùng MAX của 5 ngân hàng.

## Những chỗ KHÔNG tự ý sửa (có lý do)
- `common.compile_kw`: acronym IN HOA ≤ 6 ký tự khớp phân biệt hoa/thường; từ dài khớp mờ theo khoảng trắng (PDF tiếng Việt hay tách chữ).
- `common.squeeze` + khớp nhãn BCTC: nhãn bị xuống dòng 2–3 dòng, nên so sánh bỏ khoảng trắng.
- Công thức dẫn xuất: TOI = (mục IX) + (mục VIII); CIR = chi phí hoạt động / TOI; ROE, ROA theo bình quân đầu–cuối kỳ; CASA = tiền gửi KKH / tiền gửi khách hàng.
- `04_extract_numbers.py`: bỏ số 4 chữ số dạng năm (19xx/20xx) khi bắt KPI.

## Cách chạy / kiểm tra
```
cd scripts
python ../tests/smoke_test.py      # kiểm tra nhanh toàn bộ pipeline trên PDF mẫu
```
Sau mỗi thay đổi ở `common.py`, 02, 03, 04, 07: chạy smoke test. Không báo "đã sửa xong" nếu smoke test chưa chạy.

## Phong cách
Tiếng Việt cho chú thích, docstring, thông báo; tên biến/hàm tiếng Anh. Python 3.10+. Không thêm thư viện mới nếu chưa cần
(PhoBERT/torch chỉ cho script 09). Ghi kết quả vào `out/` bằng UTF-8-BOM (`utf-8-sig`) để Excel mở đúng tiếng Việt.
