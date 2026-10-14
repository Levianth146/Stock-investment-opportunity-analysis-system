# Đặc tả: Đánh giá và xếp hạng chuyển đổi số 5 ngân hàng (DBI thích ứng + DTI)

**Nhánh**: 001-bank-dx-assessment · **Trạng thái**: Bản nháp 2 (2026-10-12: thuật toán thay chấm tay/kappa) · **Ngôn ngữ**: Tiếng Việt

## 1. Bối cảnh và mục tiêu
Đề tài đánh giá, xếp hạng mức độ chuyển đổi số của Agribank, MB, Techcombank, BIDV, Vietcombank bằng dữ liệu công khai,
dựa trên khung DBI (QĐ 2158/QĐ-BTTTT, 07/11/2023) làm chính, DTI bổ trợ. Mục tiêu: một kết quả **truy vết được, tái lập được, trung thực với dữ liệu thiếu**.

## 2. Câu chuyện người dùng
- **US1 (P1)** Là nhà nghiên cứu, tôi tải báo cáo công khai của 5 ngân hàng theo năm và trích text có chỉ báo chất lượng, để có kho văn bản đáng tin.
- **US2 (P1)** Tôi chạy thuật toán quy tắc để chấm 24 tiêu chí DBI 0–4, nhận điểm kèm bằng chứng và phiên bản để tái lập.
- **US3 (P1)** Tôi lấy được 11 chỉ số DTI (số liệu BCTC, KPI từ BCTN, rating app) kèm nguồn, để tính lớp B.
- **US4 (P2)** Tôi chạy text mining (BM25, độ phủ, tỷ lệ câu định lượng) và đối chiếu với điểm thuật toán, để kiểm tra độ nhất quán.
- **US5 (P2)** Tôi dùng LDA xem mỗi ngân hàng viết về chủ đề nào, và PhoBERT để lọc câu bằng chứng sai.
- **US6 (P1)** Tôi tính điểm trụ cột, điểm tổng, mức trưởng thành, và bảng độ nhạy, để xuất kết quả và thứ hạng.
- **US7 (P3)** Tôi sinh phụ lục (bảng bằng chứng, ma trận sẵn có dữ liệu) cho báo cáo đề tài.

## 3. Yêu cầu chức năng
- **FR-01** Tải PDF từ `config/sources.csv` cho 5 ngân hàng × các năm **2020–2025**, kiểm tra robots.txt, delay ≥ 3 s, kiểm tra magic byte PDF, ghi `manifest.csv` (sha256, ngày tải). **BCTN và BCTC bắt buộc; BCPTBV (báo cáo phát triển bền vững/ESG) tùy chọn**: nhiều ngân hàng tích hợp nội dung này trong BCTN. Mỗi dòng `sources.csv` hoặc có `url`, hoặc có `notes` mang một trạng thái chuẩn: `tích hợp trong BCTN` · `không công bố` · `chưa tìm thấy`. Không dán cùng một PDF vào hai dòng (tránh đếm đôi từ khóa); script 01 cảnh báo dòng vừa thiếu `url` vừa thiếu `notes`.
- **FR-02** Trích text theo trang bằng nhiều engine, chọn theo điểm rác thấp nhất; gắn cờ tệp nghi lỗi font/ảnh; hỗ trợ OCR tùy chọn.
- **FR-03** Tìm câu chứa từ khóa của 24 tiêu chí (khớp mờ khoảng trắng; acronym ngắn khớp phân biệt hoa/thường), xuất ứng viên kèm trang, đoạn trích, độ ưu tiên đọc.
- **FR-04** Trích số từ BCTC (nhãn bị xuống dòng, đơn vị) và KPI từ BCTN; dẫn xuất TOI, CIR, ROE, ROA, CASA.
- **FR-05** Lấy rating app iOS và Android qua API công khai, tính rating gia quyền theo số lượt đánh giá.
- **FR-06** Chụp snapshot trang công khai (developer portal, chính sách bảo mật) làm bằng chứng.
- **FR-07** Text mining: BM25, độ phủ, tỷ lệ câu định lượng, TF-IDF, mở rộng từ điển, so sánh Spearman với điểm chấm tay.
- **FR-08** LDA: quét K, nhiều seed, độ ổn định, gán chủ đề vào trụ cột, tỷ trọng theo ngân hàng-năm.
- **FR-09** PhoBERT: dựng tập huấn luyện từ cột `valid`, tinh chỉnh có CV, dự đoán, và chế độ neo rubric không cần huấn luyện.
- **FR-10** Tính điểm: P_k = 0,8·DBI_k + 0,2·DTI_k; Score = (1/6)ΣP_k; trụ cột 6 không có DTI (P_6 = DBI_6); quy đổi 5 mức theo QĐ 2158. Chuẩn hóa DTI theo z = 100·min{1; max[0; (x−L)/(U−L)]} với **L, U chốt trước khi chấm** theo **chuẩn ngành / tham chiếu công bố** (NHNN, DBI/DTI, báo cáo ngành…), ghi vào `config/dti_bounds.yaml` kèm nguồn từng chỉ số; không lấy MAX của 5 ngân hàng; không dùng phân vị mẫu làm nguồn chính.
- **FR-11** Độ nhạy: 4 tổ hợp trọng số DBI/DTI, Dirichlet Monte Carlo trên trọng số trụ cột, Kendall τ, Spearman, tỷ lệ kịch bản giữ hạng.
- **FR-14** Mọi script 01–04 và 07–09 hỗ trợ lọc `--bank`, `--year`, `--type`, `--only-lang` để chạy từng phần (kiểm thử 1 ngân hàng × 1 năm) mà không phải sửa `sources.csv`.
- **FR-12** Báo cáo điểm tin cậy dữ liệu và ma trận sẵn có dữ liệu (ngân hàng × chỉ số × năm). Ma trận phân biệt `có dữ liệu` · `tích hợp trong BCTN` · `không công bố` · `chưa tìm thấy`; trạng thái `tích hợp trong BCTN` KHÔNG được tính là thiếu dữ liệu ESG.
- **FR-13** Chấm DBI bằng thuật toán quy tắc 09c; xuất `auto_scores.csv`, `coding_auto.xlsx` và manifest gồm phiên bản/hash/quy tắc lọc. Không yêu cầu người chấm hoặc kappa. Thiếu văn bản để trống; no_mention=0 chỉ nghĩa không phát hiện đề cập trong tài liệu đã quét.

## 4. Yêu cầu phi chức năng
- **NFR-01** Đạo đức thu thập: theo Hiến chương II.
- **NFR-02** Tái lập: cùng đầu vào, cùng seed → cùng đầu ra.
- **NFR-03** Hiệu năng: 5 ngân hàng × 3–5 năm xử lý trong vài phút (không tính OCR/PhoBERT).
- **NFR-04** Tương thích Excel: CSV `utf-8-sig`.

## 5. Tiêu chí chấp nhận
- **SC-01** Smoke test `tests/smoke_test.py` chạy sạch trên PDF mẫu.
- **SC-02** Với ≥ 1 ngân hàng thật × 1 năm: 02 trích text không bị gắn cờ, 03 cho ≥ 1 ứng viên cho đa số 24 tiêu chí, 04 khớp tay ± 0,1% với BCTC trên TOI, CIR, ROE.
- **SC-03** Kiểm thử quy tắc mức 0–4, câu tương lai/phủ định, bộ lọc, dữ liệu thiếu và tái lập; truy vết đủ bằng chứng cho điều kiện mức 4. Đánh giá độ phủ tài liệu và độ nhạy; không dùng kappa làm tiêu chí chấp nhận.
- **SC-04** Mọi điểm trong bảng kết quả lần ngược được tới tệp, trang, đoạn trích.
- **SC-05** Bảng độ nhạy cho biết thứ hạng nào "vững" (≥ 80% kịch bản).

## 6. Ngoài phạm vi
Dữ liệu nội bộ ngân hàng; đăng nhập app; scrape trong app; suy diễn nhân quả; dự báo.

## 7. Giả định và rủi ro
- **Năm phân tích chính thức: 2020–2025** (6 năm; 2020 là năm cơ sở để tính biến động và bình quân đầu–cuối kỳ cho 2021). Thứ hạng và bảng kết quả báo theo từng năm; thiếu báo cáo năm nào thì để trống ô tương ứng và ghi vào ma trận sẵn có dữ liệu (không điền 0).
- **L, U của 11 chỉ số DTI**: lấy từ chuẩn ngành / tài liệu công bố; mỗi chỉ số ghi nguồn trong `dti_bounds.yaml`. Chỉ số chưa có chuẩn ngành rõ phải ghi nguồn thay thế công bố và lý do trước khi chấm (không tự lấy MAX mẫu).
- **Chấm điểm**: quy tắc cố định, có phiên bản; xem `algorithm-scoring.md`. Thuật toán đo dấu hiệu trong báo cáo, cần ghi rõ giới hạn và kiểm chứng chất lượng.
- **Ngôn ngữ báo cáo không đồng nhất** (đã chốt hướng song ngữ): nhiều BCTN/BCTC là bản tiếng Anh (MB, Techcombank, một số năm BIDV). Từ khóa, nhãn BCTC và mẫu KPI hỗ trợ cả tiếng Việt lẫn tiếng Anh. Mỗi văn bản được gắn `lang` (vi/en/unknown) lúc trích text. Chấm DBI bằng quy tắc hỗ trợ cả hai ngôn ngữ, cần đánh giá lỗi từ khóa/nhãn riêng từng ngôn ngữ; **chỉ số text mining chỉ so sánh được trong cùng ngôn ngữ** (07 chuẩn hóa riêng từng ngôn ngữ; LDA và PhoBERT chỉ chạy trên tiếng Việt). Từ khóa/nhãn tiếng Anh chưa kiểm thử trên báo cáo thật.
- Link báo cáo do người dùng điền; script không tự dò link. BCPTBV có thể không tồn tại riêng (nằm trong BCTN): khi đó nội dung ESG được đọc từ BCTN và vẫn tính đủ cho các tiêu chí văn hóa, dữ liệu, bảo mật.
- Chưa thử nghiệm trên báo cáo thật và web thật (sandbox phát triển không ra được Internet); regex nhãn BCTC có thể cần chỉnh theo từng ngân hàng.
- PhoBERT cần ≥ ~30 câu đã gán nhãn mỗi tiêu chí; dưới đó chỉ tham khảo.
- n = 5: không suy diễn thống kê.

## 8. Điểm cần làm rõ (xử lý bằng `/speckit.clarify`)
- [x] Năm phân tích chính thức: **2020–2025** (đã chốt).
- [x] **Chấm DBI đủ 6 năm 2020–2025**: 24 × 5 × 6 = 720 ô trong `coding_auto.xlsx`, không nội suy. Quyết định ngày 2026-10-12 thay phương án 2+1 người chấm bằng thuật toán; giữ trống năm thiếu văn bản.
- [x] Giới hạn L, U DTI: **chuẩn ngành / tham chiếu công bố** (đã chốt); ghi `config/dti_bounds.yaml` kèm nguồn.
- [x] Chấm điểm: **thuật toán quy tắc**, thay người chấm và kappa theo FR-13 (2026-10-12).
