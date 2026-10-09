# Stock Investment Opportunity Analysis System

Hệ thống phân tích cơ hội đầu tư cổ phiếu: nhập **mã + hồ sơ nhà đầu tư** (`long_term` / `swing`), tự thu thập dữ liệu, chấm điểm, ra khuyến nghị 5 mức và xuất **báo cáo PDF**.

```
Mã + as_of + profile
   │
[M1 Dữ liệu] ──► snapshot (có nguồn, ngày công bố, không look-ahead)
   ├─► M2 Cơ bản  → F        ├─► M3 Kỹ thuật → T
   ├─► M4 Định giá → V + giá mục tiêu
   ├─► M5 Tin tức  → S       └─► M6 Rủi ro   → R (penalty)
   ▼
[M7] Score = Σ w·(F,T,V,S) − λ·R → 5 mức + Bull/Bear
   ▼
[M8 Kiểm chứng số liệu] ──► [M9 Xuất PDF]
```

**Nguyên tắc:** số liệu do code tính từ snapshot; LLM chỉ phân loại tin và diễn giải, không sinh số, không đặt giá mục tiêu.

## Bắt đầu (cả nhóm)
```bash
git clone https://github.com/Levianth146/Stock-investment-opportunity-analysis-system.git
cd Stock-investment-opportunity-analysis-system
git checkout develop
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python main.py DEMO --profile long_term --snapshot fixtures/snapshot_DEMO.json
pytest -q
```
Rồi: `git checkout feat/<module-của-bạn>` và đọc [`docs/GIT_WORKFLOW.md`](docs/GIT_WORKFLOW.md), [`docs/OWNERSHIP.md`](docs/OWNERSHIP.md), [`docs/CONTRACTS.md`](docs/CONTRACTS.md).

## Cấu trúc
```
config/            scoring.yaml (trọng số, 5 mức) · data_sources.yaml · llm.yaml
fixtures/          snapshot_DEMO.json (dữ liệu GIẢ để code song song)
data/snapshots/    snapshot thật đã chốt (commit để chạy lại cho kết quả giống nhau)
src/stockai/
  contracts/       schema + helper dùng chung (N1)
  m1_data/ … m9_report/   mỗi module một thư mục, một file run.py
  pipeline.py      điều phối, module lỗi không làm sập cả hệ thống
main.py            CLI
tests/             test theo module + e2e
```

## Tiêu chí đảm bảo
Chính xác dữ liệu (nguồn + ngày công bố cho từng số, chặn look-ahead, M8 đối chiếu) · Đánh giá hợp lý (công thức điểm minh bạch, risk gate, 2 hồ sơ) · Sáng tạo (Bull/Bear, hồ sơ nhà đầu tư, kiểm chứng trong PDF).

> Báo cáo phục vụ học tập/nghiên cứu, không phải lời khuyên đầu tư.
