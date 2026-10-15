# Mô hình dữ liệu

## Thực thể
- **Bank** `bank_id` (agribank, mb, tcb, bidv, vcb), tên, site, app_search, apple_id, play_id.
- **Document** `bank, year (2020–2025), doc_type (bctn|bcptbv|bctc|other), url, file, sha256, fetched_at`. `bctn` và `bctc` bắt buộc; `bcptbv` tùy chọn.
- **SourceStatus** (cột `notes` của `sources.csv` khi `url` trống): `tích hợp trong BCTN` | `không công bố` | `chưa tìm thấy`.
- **Page** `bank, year, doc_type, page, engine, junk, text` (dòng của `data/text/*.jsonl`).
- **Criterion** `code (K1..D4 và các mã 24 tiêu chí), pillar, name, keywords[], rubric[0..4]` (anchors trong `rubric_anchors.csv`).
- **EvidenceCandidate** `criterion, bank, year, doc_type, page, keyword, snippet, read_priority, valid (người chấm điền)`.
- **Coding** `criterion, bank, year, final (0–4 hoặc trống), auto_score, scoring_method, rules_version, rules_hash, status, evidence_file, evidence_page, evidence_quote, supporting_evidence, notes` trong `coding_auto.xlsx`.
- **ScoringManifest** phiên bản/hash thuật toán, tham số lọc/cửa sổ, hash JSONL đầu vào; không có bước hòa giải/kappa trong phương pháp mới.
- **DTIBound** (`config/dti_bounds.yaml`): `variable, L, U, unit, direction (higher_better|lower_better), source_citation, rationale`. Khóa trước khi chạy 10.
- **DTIInput** `bank, year, variable (K-Q1..C-Q2 và biến dẫn xuất), value, unit, source_file, page, confirmed_by, note`. Chỉ số không công bố: để trống `value`, `note = not_disclosed` (hoặc tương đương).
- **PillarScore** `bank, year, pillar, dbi, dti, p, data_confidence`.
- **ScoreTotal** `bank, year, score_total, maturity_level, rank`.
- **TextMiningMetric** `bank, year, criterion, bm25, coverage, quantified_ratio`.
- **AvailabilityCell** (ma trận FR-12): `bank, year, indicator_or_doc, status ∈ {có dữ liệu, tích hợp trong BCTN, không công bố, chưa tìm thấy}`.

## Quan hệ
Bank 1–n Document 1–n Page. Criterion 1–n EvidenceCandidate → Coding (chọn bằng chứng làm căn cứ). Coding n–1 ScoringManifest. DTIInput n–1 Bank; DTIBound 1–1 biến DTI. PillarScore / ScoreTotal tổng hợp từ Coding (DBI) và DTIInput+DTIBound (DTI). AvailabilityCell đọc từ `sources.csv` + chỗ trống trong `dti_inputs`.

## Quy tắc
- Năm phân tích / báo cáo: **2020–2025**; 2020 phục vụ số đầu kỳ cho chỉ số bình quân năm 2021 khi cần.
- `coding.final ∈ {0,1,2,3,4}`; điểm tiêu chí % = final × 25.
- DBI_k = trung bình điểm % của các tiêu chí trụ cột k; P_k = 0,8·DBI_k + 0,2·DTI_k; thiếu DTI → P_k = DBI_k; P_6 = DBI_6 (không có DTI).
- Score = (1/6) Σ P_k.
- Thuật toán 09c ghi final trong coding_auto.xlsx; thiếu văn bản để trống. Mỗi final có phiên bản và bằng chứng; dữ liệu coding_sheet cũ được lưu trữ.
- Một dòng `sources.csv` không có `url` phải có `notes` thuộc SourceStatus. `tích hợp trong BCTN` không tính là thiếu dữ liệu ESG.
- `DTIInput` với không công bố: `value` trống, không bao giờ chuyển thành 0.
- Chuẩn hóa DTI: z = 100·min{1; max[0; (x−L)/(U−L)]} theo hướng chỉ số (lower_better thì đảo hoặc đặt L/U tương ứng); riêng K-Q3 (rating): z = (r−1)/4·100 trừ khi `dti_bounds` quy định khác và ghi nguồn.
- `data_confidence` = (số chỉ tiêu DTI có `value`) / 11, báo cạnh mọi điểm DTI / tổng hợp liên quan.
- Mức trưởng thành (QĐ 2158): <25 Khởi động · 25–50 Bắt đầu · 50–75 Hình thành · 75–<100 Nâng cao · =100 Dẫn dắt.
- Thứ hạng “vững”: giữ nguyên trong ≥ 80% kịch bản độ nhạy.
