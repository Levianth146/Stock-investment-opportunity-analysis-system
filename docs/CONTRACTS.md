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
| M7 | cả 5 module trên + `cfg.profile` | `result` | copy `target` từ M4, không tự đặt; đọc `quality_tier_*` trên snapshot; điểm v2 centered (dưới) |
| M8 | snapshot + `upstream["m7"]` | `validation` (`pass/warn/fail`) | lỗi nặng -> `fail` nhưng vẫn xuất PDF kèm cảnh báo; bỏ qua kiểm tra công thức điểm, ngưỡng khuyến nghị và so `target` với M4 khi `quality_gate.scored == false` |
| M9 | tất cả | `{"pdf_path": ...}` | `score` có thể `null` — không format float khi không xếp hạng |

### M7 `result` và cổng chất lượng
- Snapshot có thể mang `meta.flags`: `quality_tier_{full|limited|insufficient}` và `quality_<lý do>` (M1 gắn sẵn).
- `insufficient` → `score: null`, `rating: "Không xếp hạng"`, `target: null`, `quality_gate: {tier, scored: false, reasons}` — **không** đưa vào khuyến nghị giao dịch (không mang giá mục tiêu khi không xếp hạng).

- `limited` / `full` / thiếu tier (legacy → `absent`) → vẫn chấm điểm; `limited` phải lộ `reasons` trên `flags` / `quality_gate`.
- `score` kiểu `number | null`; thêm enum rating `"Không xếp hạng"`.
- Mỗi luận điểm `bull`/`bear` (nhánh scored) có `text` và `refs` (mảng chuỗi): metric `mN.name` (vd. `m4.pe`), tin `nK` (vd. `n12`) — convention docs, không đổi JSON Schema.
- Ánh xạ `nK` (ổn định, 1-based): rebuild từ `upstream["m5"]["evidence"]` có `news_id` (đã lọc polarity / tối đa 6 tin trong compact payload) — **không** lấy 12 tin đầu `snapshot.news`. Validator và M8 `_check_debate_grounding` resolve qua `news_ref_map` do `build_debate_payload` tạo lại cùng quy tắc. Payload còn có `module_polarity` `{F,T,V,S,R}` = `contributions` từ `compute_score` (đóng góp so với mức trung tính 50) để LLM/template không đảo Bull/Bear.
- **Công thức điểm M7 (feature 010, v2):** `Score = clamp(50 + Σ w_k·(X_k − 50) − λ_R·(R − R_ref), 0, 100)` với `R_ref = risk_reference` (mặc định 50) trong `config/scoring.yaml`. **50 = mức trung tính.** `contributions[k] = w_k·(X_k−50)`, `contributions["R"] = −λ_R·(R−R_ref)`; khi chưa clamp: `score = 50 + Σ contributions`. Trọng số / `λ_R` / ngưỡng rating / risk gate không đổi trong 010.

## Phép tính hiện triển khai trong M2–M7
- M2 giữ công thức trên nhánh tích hợp: doanh nghiệp dùng ROE, tăng trưởng lợi nhuận, nợ/vốn chủ, CFO/NI và khả năng trả lãi; ngân hàng dùng ROE, tăng trưởng lợi nhuận, NIM, CIR và cho vay/tiền gửi. Tỷ trọng được chuẩn hóa trên các chỉ tiêu có dữ liệu; các tỷ suất trong metrics dùng đơn vị ratio. Không có BCTC năm hợp lệ thì trả status=error, score=null.
- M3 chấm T từ MA20/50/200, RSI14 và động lượng 20 phiên trên giá điều chỉnh.
- M4 chấm V từ PE (phi ngân hàng) hoặc PB (ngân hàng); khi có peers hợp lệ, dùng bội số trung vị để ước tính giá mục tiêu. Không có peer thì chỉ hiển thị điểm tham khảo theo bội số hiện tại, không tự sinh giá mục tiêu.
- M5 chấm S bằng từ khóa tích cực/tiêu cực minh bạch trên tiêu đề và tóm tắt tin. Cần tối thiểu 3 tin được phân loại; đây là heuristic, không thay thế phân tích ngôn ngữ chuyên sâu.
- M6 chấm R (rủi ro, càng cao càng xấu) từ biến động năm hóa và drawdown, đồng thời báo beta so với chỉ số khi tính được.
- Module dùng `partial` khi dữ liệu chưa đủ độ phủ chuẩn; điểm chỉ có khi có đủ chỉ tiêu để tính. `null` và `flags` biểu thị dữ liệu không có, không thay bằng điểm trung tính.
- M7 tạo luận điểm Bull/Bear từ bằng chứng module/tin có tham chiếu; mức điểm chỉ là heuristic, chưa phải khuyến nghị đầu tư đã được hiệu chuẩn.

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
