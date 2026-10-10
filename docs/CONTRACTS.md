# Hợp đồng dữ liệu (nguồn thật: `src/stockai/contracts/schemas.py`)

Luồng: **M1 → snapshot → M2…M6 → M7 → M8 → M9**. Mọi module có `run(snapshot, upstream, cfg) -> dict`.

| Module | Đọc | Trả về | Ghi chú |
|---|---|---|---|
| M1 `build_snapshot(ticker, as_of, cfg)` | nguồn ngoài | `snapshot` | chặn dữ liệu có ngày > `as_of` |
| M2 | `snapshot.financials`, `company`, `peers` | `module_out` (score = **F**) | ngân hàng rẽ nhánh theo `company.is_bank` |
| M3 | `snapshot.prices` | `module_out` (score = **T**) | chỉ dùng giá đã điều chỉnh |
| M4 | financials, prices, shares, peers; `upstream["m2"]` | `module_out` (score = **V**) + `target{base,bull,bear,method,assumptions}` | giá mục tiêu CHỈ do M4 tính |
| M5 | `snapshot.news` | `module_out` (score = **S**) | mỗi nhận định phải có `news_id` |
| M6 | prices + index | `module_out` (score = **R**, penalty) | R cao = rủi ro cao |
| M7 | cả 5 module trên + `cfg.profile` | `result` | copy `target` từ M4, không tự đặt; đọc `quality_tier_*` trên snapshot |
| M8 | snapshot + `upstream["m7"]` | `validation` (`pass/warn/fail`) | lỗi nặng -> `fail` nhưng vẫn xuất PDF kèm cảnh báo; bỏ qua kiểm tra công thức điểm, ngưỡng khuyến nghị và so `target` với M4 khi `quality_gate.scored == false` |
| M9 | tất cả | `{"pdf_path": ...}` | `score` có thể `null` — không format float khi không xếp hạng |

### M7 `result` và cổng chất lượng
- Snapshot có thể mang `meta.flags`: `quality_tier_{full|limited|insufficient}` và `quality_<lý do>` (M1 gắn sẵn).
- `insufficient` → `score: null`, `rating: "Không xếp hạng"`, `target: null`, `quality_gate: {tier, scored: false, reasons}` — **không** đưa vào khuyến nghị giao dịch (không mang giá mục tiêu khi không xếp hạng).

- `limited` / `full` / thiếu tier (legacy → `absent`) → vẫn chấm điểm; `limited` phải lộ `reasons` trên `flags` / `quality_gate`.
- `score` kiểu `number | null`; thêm enum rating `"Không xếp hạng"`.

## Quy tắc bất biến
- `as_of`: không dùng dữ liệu có `published_at`/`date` > `as_of`. Báo cáo tài chính tính theo **ngày công bố**.
- Thiếu dữ liệu -> `null` + `flags`. Không điền số ước đoán. Module lỗi -> pipeline dùng điểm trung tính 50 và gắn cờ.
- `meta.synthetic = true` là dữ liệu giả (fixture), không đưa vào báo cáo thật.
- Số liệu truy được về `snapshot.sources` qua `source_id`; tin truy về `news.id` + `url`.

## Tên chỉ tiêu tài chính (`financials.*.items`)
Đơn vị khai ở `financials.unit`. Thiếu thì `null`, đừng đổi tên khóa.

**Phi ngân hàng:** `revenue, gross_profit, ebit, net_income, net_income_parent, total_assets, total_equity, total_liabilities, current_assets, current_liabilities, inventory, cash, short_term_debt, long_term_debt, cfo, cfi, cff, capex, eps, interest_expense, depreciation`

**Ngân hàng (thêm/khác):** `net_interest_income, total_operating_income, provision_expense, customer_loans, customer_deposits, npl_ratio, car, nim, cir`

Cần thêm khóa -> nhắn N1 (N2 và N3 thống nhất tên trước).

## Chạy thử
```bash
pip install -r requirements.txt
python main.py DEMO --profile long_term --snapshot fixtures/snapshot_DEMO.json
pytest -q
```
Bảng trạng thái in ra cho biết module nào còn `stub` (chưa làm) và module nào `ok`/`error`.
