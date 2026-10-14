# Fix pass A–E (2026-10-13) — trước hoàn tất 007

## Đã làm
- Normalize: NFC + lower + gộp punct/ws; **giữ dấu + đ** (không fold ASCII).
- Lexicon YAML có dấu; bỏ hard-code trong `_classify_title`.
- Negation ≤3 token; subject/research issuer; market summary weight 0;
  flow ×0.5; VCI mặc định trung tính (+ announcements); multi-ticker ×0.3
  (universe file); story Jaccard clustering; metrics/flags mới; evidence VI.
- Defaults: lookback 60, half_life 14, min_relevant 3, min_directional 2.
- Gold: `tests/fixtures/m5_gold_headlines.csv` (120); xóa `fixtures/m5_gold_labels.csv`.
- Ambiguous seed **chỉ** CEO, HCM, VND, AAA.
- Top60 n-gram gap in ra để duyệt — **không** auto-add.

## Không
- Không commit / push / Co-authored-by.
- Không sửa m1_data, pipeline, contracts, M7, M8.
