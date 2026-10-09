# Ai sở hữu gì

| Người | Task trên board | Thư mục được sửa | Test của mình | Config |
|---|---|---|---|---|
| N1 | Tích hợp, QA, thuyết minh | `src/stockai/contracts/`, `pipeline.py`, `main.py`, `scripts/`, `fixtures/`, `.github/`, `requirements.txt` | `tests/test_contracts.py`, `tests/test_pipeline_e2e.py` | - |
| N2 | Thu thập dữ liệu (M1) | `src/stockai/m1_data/`, `data/snapshots/` | `tests/test_m1_*.py` | `config/data_sources.yaml` |
| N3 | Phân tích cơ bản + định giá (M2, M4) | `m2_fundamental/`, `m4_valuation/` | `tests/test_m2_*.py`, `tests/test_m4_*.py` | `config/valuation.yaml` (tự tạo nếu cần) |
| N4 | PTKT + rủi ro (M3, M6) | `m3_technical/`, `m6_risk/` | `tests/test_m3_*.py`, `tests/test_m6_*.py` | `config/technical.yaml` (tự tạo nếu cần) |
| N5 | Tin tức + tổng hợp điểm (M5, M7) | `m5_sentiment/`, `m7_scoring/` | `tests/test_m5_*.py`, `tests/test_m7_*.py` | `config/scoring.yaml`, `config/llm.yaml` |
| N6 | Kiểm chứng + PDF (M8, M9) | `m8_validate/`, `m9_report/` | `tests/test_m8_*.py`, `tests/test_m9_*.py` | `config/report.yaml` (tự tạo nếu cần) |

Mỗi module là **một file `run.py` có chữ ký cố định**: `run(snapshot, upstream, cfg) -> dict`.
Bên trong thư mục của mình bạn tự do thêm file, đổi tên hàm, import thư viện; bên ngoài thì không.
