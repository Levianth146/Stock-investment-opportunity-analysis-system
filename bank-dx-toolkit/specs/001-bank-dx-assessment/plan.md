# Kế hoạch triển khai: 001-bank-dx-assessment

**Nhánh**: 001-bank-dx-assessment · **Cập nhật sau** `/speckit.clarify` · **Không viết code trong bước này**

## Tóm tắt kỹ thuật
Đánh giá chuyển đổi số 5 ngân hàng (agribank, mb, tcb, bidv, vcb) trên cửa sổ **2020–2025** bằng dữ liệu công khai: DBI thích ứng (24 tiêu chí 0–4 bằng thuật toán quy tắc) + DTI (11 chỉ số, chuẩn hóa L/U khóa trước theo chuẩn ngành). Script 00–09 đã có; còn lại xác thực trên PDF thật, chấm bằng 09c (quyết định 2026-10-12), rồi viết 10–12 (điểm, độ nhạy, phụ lục).

## Ngăn xếp
| Lớp | Công nghệ |
|---|---|
| Runtime | Python 3.10+ |
| Dữ liệu / bảng | pandas, openpyxl (Excel `utf-8-sig` / xlsx) |
| PDF | pdfplumber, PyMuPDF, pdftotext (poppler); Tesseract + `vie` (OCR tùy chọn) |
| HTTP / web | requests, BeautifulSoup; Playwright tùy chọn (trang JS) |
| App store | iTunes Search/Lookup API; `google-play-scraper` |
| Text mining | scikit-learn (TF-IDF, LDA); BM25 tự viết trong 07 |
| PhoBERT (tùy chọn) | torch, transformers, pyvi — chỉ script 09 |

Không thêm thư viện mới trừ khi plan/task ghi rõ và không vi phạm Hiến chương VIII.

## Kiểm tra Hiến chương
| Nguyên tắc | Đáp ứng bằng | Vi phạm? |
|---|---|---|
| I Thuật toán quyết định | 09c ghi final trong coding_auto.xlsx, kèm quy tắc/hash/bằng chứng; không yêu cầu kappa | Theo quyết định nhóm 2026-10-12 |
| II Công khai, đạo đức | `01_download.py` robots.txt, delay ≥ 3 s, User-Agent nghiên cứu; 05/06 API/trang công khai; không đăng nhập | Không |
| III Truy vết | `manifest.csv` (sha256); mọi ứng viên/số có file/page/snippet hoặc `source_file`+`page` | Không |
| IV Dữ liệu thiếu | Để trống, không điền 0; `data_confidence` = (số chỉ tiêu có dữ liệu)/11; thiếu DTI trụ → P_k = DBI_k; ma trận phân biệt `tích hợp trong BCTN` ≠ thiếu ESG | Không |
| V Công thức khóa | L, U trong `config/dti_bounds.yaml` (chuẩn ngành, chốt trước chấm); trọng số mặc định 80/20 và 1/6; thay đổi chỉ qua 11 | Không — số L/U cụ thể chưa điền (T040) |
| VI Độ nhạy | `11_sensitivity.py`: 100/0, 80/20, 70/30, 60/40; Dirichlet MC; Kendall τ, Spearman; “vững” ≥ 80% | Không — script chưa viết (T042) |
| VII Kiểm thử | Sau sửa `common.py`/02/03/04/07 → `tests/smoke_test.py`; ca mới khi chỉnh regex PDF thật | Không |
| VIII Đơn giản, tái lập | Seed cố định LDA/PhoBERT; chạy từ `scripts/` | Không |
| IX Ngôn ngữ | VI cho tài liệu/thông báo; EN cho tên biến; CSV `utf-8-sig` | Không |

**Ghi chú NFR-03**: spec nói “3–5 năm trong vài phút”; cửa sổ chính thức là **6 năm (2020–2025)**. Kế hoạch giữ mục tiêu “vài phút không tính OCR/PhoBERT”; nếu chậm, đo lại trên máy thật — không cắt năm để đạt NFR.

## Cấu trúc
```
config/     banks.yaml, keywords.yaml, rubric_anchors.csv, sources.csv,
            dti_bounds.yaml   ← tạo ở T040 (chưa có)
scripts/    00 mẫu · 01 tải · 02 text · 03 bằng chứng · 04 số · 05 app · 06 web
            07 TM · 08 LDA · 09 PhoBERT
            10_score.py · 11_sensitivity.py · 12_appendix.py   ← chưa viết
data/       raw/  text/  web/     (không commit)
out/        CSV/XLSX kết quả     (không commit dữ liệu thật nếu chứa PII — hiện không)
models/     PhoBERT tinh chỉnh   (không commit)
specs/001-bank-dx-assessment/   spec, plan, research, data-model, contracts, quickstart, tasks
tests/      smoke_test.py
```

## Luồng dữ liệu
```
config/sources.csv  (5 NH × 2020–2025; BCTN+BCTC bắt buộc; BCPTBV tùy chọn + notes trạng thái)
        │
        ▼
01_download ──► data/raw/*.pdf + manifest.csv
        │
        ▼
02_extract_text ──► data/text/*.jsonl + out/extraction_report.csv
        │
        ├──────────────────────┬──────────────────────┐
        ▼                      ▼                      ▼
03_locate_evidence      04_extract_numbers     07 / 08 / 09 (phụ)
out/evidence_candidates   --bctc / --kpi         tm_*, lda_*, phobert_*
        │                      │
        ▼                      ▼
[Người chấm ×2]          + 05_app_ratings
 coding_auto.xlsx          → out/dti_inputs.csv (người xác nhận)
 (+ người 3 nếu bất đồng)
        │                      │
        └──────────┬───────────┘
                   ▼
            10_score.py  + config/dti_bounds.yaml
                   │
                   ▼
            11_sensitivity.py
                   │
                   ▼
            12_appendix.py  (bằng chứng, ma trận sẵn có: có / tích hợp BCTN / không công bố / chưa tìm thấy)
```

- Không dán cùng PDF vào hai dòng `sources.csv` (tránh đếm đôi từ khóa).
- Dòng thiếu `url`: bắt buộc `notes` ∈ {`tích hợp trong BCTN`, `không công bố`, `chưa tìm thấy`}; 01 cảnh báo nếu cả hai trống.
- Text mining **không** vào công thức điểm chính.

## Giai đoạn
1. **Nền tảng (đã có)**: scripts 00–09 + smoke test offline.
2. **Xác thực dữ liệu thật**: 1 NH × 1 năm → chỉnh regex → mở rộng 5 × 2020–2025; điền sources (T021–T026).
3. **Chấm thuật toán (FR-13)**: chạy 09c, lưu phiên bản/hash/bằng chứng; kiểm thử mức 0–4 và dữ liệu thiếu, kiểm tra độ phủ/độ nhạy. Không yêu cầu chấm kép/kappa; `valid` chỉ dùng cho PhoBERT phụ trợ.
4. **Điểm và độ nhạy**: chốt L/U chuẩn ngành → `dti_bounds.yaml`; viết 10, 11 + unit test (T040–T043).
5. **Đối chiếu và xuất**: 07 `--compare`, 08, 09; `12_appendix.py`; cập nhật báo cáo đề tài (T050–T052).

## Rủi ro và giảm thiểu
Xem `research.md` (mục Rủi ro mở + quyết định R10–R13 sau clarify).

## Việc kế tiếp sau plan
- Cập nhật `tasks.md` nếu cần phản ánh FR-13 / biên bản bất đồng / năm 2020–2025 (khuyến nghị khi chạy `/speckit.tasks`).
- Không bắt đầu implement 10–12 khi chưa có L, U trong `dti_bounds.yaml` và chưa có ít nhất một vòng chấm có `final` (trừ viết khung + test giả).
