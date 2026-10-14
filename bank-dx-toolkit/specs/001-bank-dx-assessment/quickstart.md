# Quickstart kiểm chứng

## A. Kiểm tra offline (~10 phút)
1. `python -m venv .venv`, kích hoạt, `pip install -r requirements.txt`.
2. `cd scripts && python ../tests/smoke_test.py` → phải ra `TẤT CẢ OK`.
3. `python 00_make_templates.py` — tạo template coding / audit / dti / sources nếu chưa có.

## B. Một ngân hàng × một năm (trước khi mở rộng 2020–2025)
1. Điền `config/sources.csv`: **BCTN + BCTC** có `url`; nếu không có BCPTBV riêng thì `url` trống và `notes` = `tích hợp trong BCTN` / `không công bố` / `chưa tìm thấy` (không dán trùng PDF).
2. `python 01_download.py && python 02_extract_text.py` → `out/extraction_report.csv`, cột `flag` phải OK (hoặc chạy OCR nếu gắn cờ).
3. `python 03_locate_evidence.py` → đọc thử ~20 dòng `out/evidence_candidates.csv`.
4. `python 04_extract_numbers.py --bctc --kpi` → đối chiếu tay TOI, CIR, ROE với BCTC (± 0,1%, SC-02).
5. Nếu lệch: ghi vào `tasks.md` mục **Phát hiện** rồi mới sửa regex / thêm ca smoke.

## C. Mở rộng và chấm
1. Điền đủ sources cho 5 ngân hàng × **2020–2025** (2020 = năm cơ sở số đầu kỳ).
2. Chạy lại 01–04 (và 05/06 khi cần bằng chứng app/web).
3. `python 09c_auto_score.py` → `coding_auto.xlsx` cùng phiên bản và bằng chứng; không yêu cầu chấm kép/kappa.
4. Chốt `config/dti_bounds.yaml` (L, U + nguồn chuẩn ngành) **trước** khi tính điểm.
5. `python 12_appendix.py --bundle` → `python 10_score.py --weight-scenarios`. Nếu L/U chưa khóa thì dùng `--draft`; chưa coi là kết quả chính thức.

## D. Text mining (phụ, không vào điểm chính)
`python 07_text_mining.py` (có `--compare` khi đã có coding_auto.xlsx) · `08_lda_topics.py` · `09_phobert.py` (cần GPU/mạng lần đầu; ≥ ~30 câu `valid`/tiêu chí thì mới tin cậy).

## Lệnh thường dùng
```
cd scripts
python ../tests/smoke_test.py
python 01_download.py
python 02_extract_text.py
python 03_locate_evidence.py
python 04_extract_numbers.py --bctc --kpi
python 09c_auto_score.py
python 12_appendix.py --bundle
python 10_score.py --draft --weight-scenarios
```
