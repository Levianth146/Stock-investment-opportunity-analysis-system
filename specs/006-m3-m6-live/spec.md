# Feature Specification: M3 + M6 Live on HOSE+HNX Snapshots

**Feature Branch**: `006-m3-m6-live`

**Feature dir**: `specs/006-m3-m6-live/`

**Created**: 2026-10-13

**Status**: Draft — sẵn sàng `/speckit-plan`

**Input**: User description: "Tính năng 006: M3 (kỹ thuật) và M6 (rủi ro) chạy thật trên snapshot HOSE+HNX. Port logic từ StockAI tham chiếu, giữ chữ ký run(snapshot, upstream, cfg) -> module_out. Chỉ sửa m3_technical/, m6_risk/, tests, và (nếu cần) config/scoring.yaml. Không sửa m1_data, pipeline, contracts. TDD fail-first; smoke 235 mã full+limited. Không commit/push."

## Clarifications

### Session 2026-10-13

- Q1 (cực tính điểm R): **B** — R 0–100, **R cao = rủi ro cao**, khớp `docs/CONTRACTS.md` và công thức M7 (`− lambda*R`, `risk_gate`). Port nguyên công thức đo lường (beta, volatility, MDD, VaR95, CVaR95) từ StockAI; **chỉ đảo mapping chấm điểm** (chỉ số xấu hơn → R cao hơn). MUST NOT đổi công thức chỉ số. Docstring + config MUST ghi rõ ngưỡng → R và phần rubric nào đã đảo so với StockAI. Test: (1) mã biến động cao / drawdown sâu MUST có R cao hơn mã ổn định; (2) polarity-lock fail nếu ai đảo lại cực tính. MUST NOT sửa `CONTRACTS.md` hay M7 trong feature này. Báo cáo cuối MUST nêu M6 khớp contract và liệt kê phần scoring StockAI đã đảo.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - M3 chấm điểm kỹ thuật T từ giá đã điều chỉnh (Priority: P1)

Người phân tích (hoặc pipeline) đưa một snapshot HOSE/HNX có chuỗi giá ngày đã quy về VND vào M3. Hệ thống chỉ dùng phiên có `date <= as_of`, loại dòng OHLC lỗi (đếm và gắn cờ), tính MA20/50/200, RSI14 (Wilder), MACD(12,26,9), tỷ lệ khối lượng 20 phiên, ATR14, rồi ra điểm T 0–100 theo rubric tham chiếu với ngưỡng lấy từ cấu hình (không hard-code). Đủ lịch sử (≥ 200 phiên cho MA200) và tính đủ → `status` = `ok` kèm điểm; thiếu → `score` = `null` kèm cờ; phiên cuối cách `as_of` hơn 7 ngày → gắn `m3_stale_price_data`. Mã không có giá (ví dụ ATP, BCH, MDD) không làm sập module.

**Why this priority**: Không có điểm T thật thì M7/pipeline không dùng được tín hiệu kỹ thuật trên universe rộng.

**Independent Test**: Snapshot dựng tay trong thư mục tạm (đủ / thiếu phiên / có dòng OHLC lỗi / có phiên sau `as_of` / giá cũ / rỗng) + 1–2 snapshot thật nếu có trong `data/snapshots_ext` (thiếu thì bỏ qua). Chạy M3 độc lập; kiểm tra score/status/cờ; không cần M6.

**Acceptance Scenarios**:

1. **Given** snapshot có ≥ 200 phiên hợp lệ `date <= as_of` và OHLC đủ, **When** chạy M3, **Then** trả `module_out` hợp lệ với `score` số trong [0, 100], `status` = `ok` khi không còn cờ thiếu/lỗi liên quan tính điểm, metrics gồm MA20/50/200, RSI14, MACD(+signal+histogram), volume_ratio_20, ATR14 (đơn vị giá VND).
2. **Given** số phiên hợp lệ < 200, **When** chạy M3, **Then** `score` = `null`, gắn cờ thiếu lịch sử MA200, `status` = `partial`.
3. **Given** snapshot có dòng `date > as_of`, **When** chạy M3, **Then** các dòng đó không được dùng vào chỉ số hay điểm.
4. **Given** snapshot có dòng OHLC lỗi (thiếu trường, high < low, volume âm, giá không hữu hạn), **When** chạy M3, **Then** dòng đó bị loại, có cờ loại dòng lỗi (kèm đếm), module không crash.
5. **Given** phiên cuối hợp lệ cách `as_of` hơn 7 ngày lịch, **When** chạy M3, **Then** gắn cờ `m3_stale_price_data`.
6. **Given** mã không có hàng giá (ATP/BCH/MDD hoặc `rows` rỗng), **When** chạy M3, **Then** không exception; `score` = `null`; có cờ thiếu dữ liệu; `status` phù hợp thiếu dữ liệu (`partial`).

---

### User Story 2 - M6 chấm điểm rủi ro R từ lợi suất căn ngày với VNINDEX (Priority: P1)

Người phân tích đưa snapshot có giá cổ phiếu và chỉ số (VNINDEX) vào M6. Hệ thống căn lợi suất theo **cùng ngày** (giao ngày chung), **không** forward-fill ngày thiếu; tính beta, độ biến động năm hóa, max drawdown, VaR95, CVaR95 **theo đúng công thức đo của StockAI**; ra điểm R 0–100 với quy ước **R cao = rủi ro cao** (khớp CONTRACTS và M7). Mapping chấm điểm từ chỉ số đo → R MUST đảo so với StockAI (chỉ số xấu hơn → R cao hơn); công thức chỉ số MUST NOT đổi. Chỉ khi đủ điều kiện chấm (đủ quan sát căn ngày, giá đã điều chỉnh, phiên căn cuối cách `as_of` ≤ 10 ngày, và các điều kiện sẵn sàng điểm theo tham chiếu) thì gán `score` số và `status` = `ok`. **Không** gán cứng `status` = `partial` mọi lúc. Chuỗi giá cổ phiếu trùng hoàn toàn với chỉ số → beta ≈ 1. Mã biến động cao / drawdown sâu MUST có R cao hơn mã ổn định trên cùng khung so sánh.

**Why this priority**: Điểm R là đầu vào phạt/cổng rủi ro của xếp hạng tổng; sai căn ngày hoặc sai cực tính làm méo khuyến nghị.

**Independent Test**: Snapshot dựng tay (chuỗi trùng chỉ số; thiếu quan sát; có ngày lệch; giá chưa điều chỉnh; phiên cũ; cặp high-vol vs stable) + snapshot thật nếu có. Chạy M6 độc lập. Gồm polarity-lock.

**Acceptance Scenarios**:

1. **Given** đủ quan sát căn ngày, `prices.adjusted` = true, phiên căn cuối cách `as_of` ≤ 10 ngày, **When** chạy M6, **Then** `score` số trong [0, 100], `status` = `ok`, metrics gồm beta, annualized volatility, max drawdown, VaR95, CVaR95.
2. **Given** thiếu quan sát căn ngày dưới ngưỡng tối thiểu cấu hình, **When** chạy M6, **Then** `score` = `null`, gắn cờ chưa sẵn sàng / thiếu dữ liệu; **không** bịa điểm.
3. **Given** chuỗi giá cổ phiếu và chỉ số lệch ngày (một bên thiếu phiên), **When** chạy M6, **Then** chỉ dùng ngày chung; không suy diễn giá ngày thiếu bằng forward-fill.
4. **Given** chuỗi cổ phiếu trùng hoàn toàn chuỗi chỉ số trên các ngày dùng, **When** chạy M6, **Then** beta bằng 1 (trong sai số số học hợp lý).
5. **Given** giá chưa điều chỉnh hoặc không đủ điều kiện chấm, **When** chạy M6, **Then** không gán điểm số; `status` không bị hard-code `partial` nếu đủ điều kiện `ok` ở case khác (status phản ánh đúng trạng thái từng lần chạy).
6. **Given** hai snapshot dựng tay cùng khung (một biến động cao + drawdown sâu, một ổn định), **When** chạy M6 trên cả hai, **Then** mã rủi ro cao hơn MUST có điểm R **cao hơn** mã ổn định.
7. **Given** bộ test polarity-lock của M6, **When** chạy, **Then** test **fail** nếu cực tính bị đảo lại thành “R cao = rủi ro thấp” (khóa khớp CONTRACTS: R cao = rủi ro cao).

---

### User Story 3 - TDD offline rồi xác minh hàng loạt trên mã full+limited (Priority: P1)

Người phát triển viết kiểm thử trước (thấy fail trên stub hiện tại), rồi mới port logic. Kiểm thử chính dùng snapshot dựng tay offline; thêm 1–2 case snapshot thật trong `data/snapshots_ext` nếu có, bỏ qua nếu không. Sau khi implement, chạy toàn bộ bộ kiểm thử dự án; chạy thử M3+M6 trên khoảng 235 mã `full`+`limited` của HOSE+HNX và in bảng phân bố điểm T/R, số mã `ok`/`partial`, số mã `score` = `null`. Báo cáo hoàn thành MUST nêu M6 khớp CONTRACTS (R cao = rủi ro cao) và liệt kê các phần scoring StockAI đã đảo. Spec và artifact nằm local — không commit/push trong phạm vi feature này trừ khi người dùng yêu cầu sau.

**Why this priority**: Stub hiện tại luôn “ok giả”; TDD và smoke batch là cách duy nhất chứng minh module chạy thật trên dữ liệu repo.

**Independent Test**: Fail-first trên stub; sau implement kiểm thử toàn dự án sạch; smoke batch có bảng phân bố dán vào báo cáo hoàn thành.

**Acceptance Scenarios**:

1. **Given** stub M3/M6 hiện tại, **When** chạy bộ test mới của feature, **Then** các test hành vi thật **fail trước** khi có code port.
2. **Given** đã port xong, **When** chạy toàn bộ kiểm thử dự án offline, **Then** pass; số test được báo cáo.
3. **Given** thư mục snapshot HOSE+HNX với mã full+limited (~235), **When** chạy smoke M3+M6, **Then** không crash hàng loạt; in phân bố score T và R, đếm status ok/partial, đếm score null; kết quả được dán vào báo cáo hoàn thành implement.
4. **Given** mọi thay đổi của feature, **When** xem phạm vi file, **Then** chỉ đụng `m3_technical/`, `m6_risk/`, tests liên quan, và (nếu cần) `config/scoring.yaml`; **không** sửa `m1_data/*`, `pipeline.py`, `contracts/*`, hay M7.

---

### Edge Cases

- Snapshot `meta.synthetic` = true: M3/M6 gắn cờ synthetic; M6 không đủ điều kiện chấm điểm thật.
- Giá có `adjusted` ≠ true: M3 gắn cờ unadjusted; M6 không chấm điểm.
- Trùng ngày trong `prices.rows` / `index.rows`: loại/ghi nhận theo quy tắc tham chiếu (không crash).
- Khoảng cách lịch giữa hai phiên căn > 7 ngày: loại quan sát lợi suất đó (M6), gắn cờ khoảng trống dài nếu có.
- Chỉ số thiếu hoặc rỗng trong khi cổ phiếu đủ: M6 `score` = null, không crash.
- Ngưỡng rubric T / hệ số phụ điểm R nằm trong cấu hình; thiếu khóa cấu hình → dùng mặc định an toàn đã ghi trong Assumptions và gắn cờ cấu hình nếu cần.
- Mã illiquid / early-exit stub thiếu giá dài: cả M3 và M6 trả null + cờ, không exception.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: M3 và M6 MUST giữ chữ ký `run(snapshot, upstream, cfg) -> dict` và đầu ra MUST hợp lệ `module_out` (validate theo contract hiện có). MUST NOT đổi schema/contracts.
- **FR-002**: Phạm vi sửa MUST giới hạn ở `src/stockai/m3_technical/`, `src/stockai/m6_risk/`, tests liên quan, và (nếu cần) `config/scoring.yaml`. MUST NOT sửa `src/stockai/m1_data/*`, `pipeline.py`, `src/stockai/contracts/*`, `docs/CONTRACTS.md`, hay M7.
- **FR-003**: Logic hành vi MUST port từ bản tham chiếu chỉ-đọc `D:\Projects\StockAI\src\stockai\m3_technical\run.py` và `...\m6_risk\run.py` (không copy nguyên khối vào repo; không sửa file tham chiếu). Khi yêu cầu người dùng lệch tham chiếu (status M6; **cực tính mapping điểm R**), ưu tiên yêu cầu người dùng và ghi rõ trong Assumptions / docstring / config.
- **FR-004**: M3 MUST chỉ dùng `prices.rows` có `date <= as_of`; MUST loại dòng OHLC lỗi, đếm và gắn cờ loại; MUST cần ≥ 200 phiên hợp lệ cho MA200 — thiếu thì `score` = `null` kèm cờ.
- **FR-005**: M3 MUST tính và lộ metrics: MA20, MA50, MA200, RSI14 (Wilder), MACD(12,26,9) kèm signal và histogram, tỷ lệ khối lượng 20 phiên, ATR14. Đơn vị giá MUST là VND (snapshot đã quy về VND).
- **FR-006**: M3 MUST chấm điểm T 0–100 theo rubric tham chiếu (trend / momentum / volume / volatility); mọi ngưỡng điểm MUST đọc từ cấu hình, MUST NOT hard-code trong mã nguồn.
- **FR-007**: M3 `status` MUST là `ok` khi tính đủ không còn cờ thiếu/lỗi chặn; `partial` khi thiếu dữ liệu hoặc còn cờ liên quan thiếu sót. MUST gắn `m3_stale_price_data` khi phiên cuối hợp lệ cách `as_of` hơn 7 ngày lịch.
- **FR-008**: M6 MUST căn lợi suất cổ phiếu và VNINDEX theo cùng ngày giao; MUST NOT forward-fill ngày thiếu. MUST tính beta, độ biến động năm hóa, max drawdown, VaR95, CVaR95 (historical) **giữ nguyên công thức đo của StockAI** (MUST NOT đổi công thức chỉ số).
- **FR-009**: M6 MUST trả điểm R 0–100 với cực tính **R cao = rủi ro cao** (khớp `docs/CONTRACTS.md` và M7: `− lambda*R`, `risk_gate`). Mapping từ chỉ số đo → điểm R MUST đảo so với StockAI (chỉ số xấu hơn → R cao hơn). Docstring module và config MUST ghi rõ: ngưỡng nào map sang R nào, và rubric/subscore nào đã đảo so với StockAI. *(Resolved Q1:B — lịch sử: StockAI “R cao = rủi ro thấp”; đã chốt theo CONTRACTS.)*
- **FR-010**: M6 MUST gán `status` = `ok` khi đủ điều kiện chấm điểm (đủ quan sát căn ngày theo ngưỡng cấu hình, giá đã điều chỉnh, phiên căn cuối cách `as_of` ≤ 10 ngày, và các điều kiện sẵn sàng điểm tương đương tham chiếu). MUST NOT gán cứng `status` = `partial` cho mọi lần chạy. Khi chưa đủ điều kiện: `score` = `null` và status/cờ phản ánh thiếu sẵn sàng.
- **FR-011**: Mã không có giá / thiếu chỉ số MUST không làm crash M3 hay M6.
- **FR-012**: Kiểm thử MUST viết trước (fail trên stub), offline bằng snapshot dựng tay trong thư mục tạm; MAY thêm 1–2 test snapshot thật dưới `data/snapshots_ext` với bỏ qua nếu không có. Bộ test MUST phủ: đủ dữ liệu → score + status ok; thiếu phiên → score null; không dùng dữ liệu sau `as_of`; OHLC lỗi bị loại + có cờ; giá cũ → stale; mã ATP/BCH/MDD (hoặc tương đương rỗng) không crash; M6 căn đúng ngày; beta chuỗi trùng chỉ số = 1; **mã high-vol/deep-drawdown có R cao hơn mã ổn định**; **polarity-lock fail nếu cực tính R bị đảo lại**.
- **FR-013**: Sau implement, MUST chạy toàn bộ kiểm thử dự án và báo số test; MUST chạy smoke trên ~235 mã full+limited, in phân bố score T và R, số mã status ok/partial, số mã score null, và dán kết quả vào báo cáo hoàn thành. Báo cáo cuối MUST nêu M6 khớp CONTRACTS (R cao = rủi ro cao) và liệt kê các phần scoring StockAI đã đảo.
- **FR-014**: Trong giai đoạn specify/plan/implement của feature này (trừ khi người dùng yêu cầu rõ sau): MUST NOT commit, MUST NOT push, MUST NOT thêm trailer `Co-authored-by` / attribution; giữ `specs/` local.

### Key Entities

- **Technical Module Output (M3)**: `module_out` với score T, metrics chỉ báo kỹ thuật, evidence, flags (stale, invalid rows, insufficient history, …).
- **Risk Module Output (M6)**: `module_out` với score R (**cao = rủi ro cao**), metrics rủi ro căn ngày (beta, vol, MDD, VaR, CVaR — công thức đo như StockAI), evidence, flags (not ready, unadjusted, insufficient aligned, …).
- **Aligned Return Series**: Tập lợi suất cổ phiếu–chỉ số chỉ trên ngày chung, không forward-fill.
- **Scoring Thresholds Config**: Ngưỡng rubric T và tham số phụ điểm R / lookback / min observations / bảng mapping chỉ số→R (đã đảo so với StockAI) nằm trong cấu hình (ưu tiên mở rộng `config/scoring.yaml` hoặc khóa `cfg` tương đương), không hard-code; config MUST ghi chú phần đã đảo.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Với snapshot dựng tay đủ lịch sử giá hợp lệ, người dùng nhận được điểm T số trong 0–100 và trạng thái thành công từ M3 trong một lần chạy module.
- **SC-002**: Với snapshot dựng tay thiếu phiên cho MA200, M3 trả điểm trống (null) kèm cờ thiếu lịch sử — không bịa điểm.
- **SC-003**: Không có phiên giao dịch sau ngày đánh giá nào lọt vào chỉ số hoặc điểm của M3/M6 (kiểm chứng bằng fixture có ngày tương lai giả).
- **SC-004**: Với snapshot đủ điều kiện rủi ro, M6 trả điểm R số và trạng thái thành công; chuỗi giá trùng chỉ số cho beta = 1 trong sai số chấp nhận được.
- **SC-005**: Snapshot dựng tay biến động cao / drawdown sâu có điểm R **cao hơn** snapshot ổn định cùng khung; polarity-lock chứng minh cực tính R cao = rủi ro cao (test fail nếu bị đảo).
- **SC-006**: Toàn bộ kiểm thử tự động offline của dự án pass sau implement; số test được báo cáo công khai trong báo cáo hoàn thành.
- **SC-007** (vận hành sau implement): Smoke trên khoảng 235 mã full+limited hoàn tất không crash hàng loạt; bảng phân bố điểm T và R, số ok/partial, số score null được in và dán vào báo cáo hoàn thành; báo cáo nêu M6 khớp CONTRACTS và liệt kê phần scoring StockAI đã đảo.
- **SC-008**: Diff phạm vi đúng: không có thay đổi trong `m1_data`, `pipeline.py`, `contracts`, `docs/CONTRACTS.md`, hay M7.

## Assumptions

- Snapshot đầu vào đã (hoặc sẽ) có `prices` và `index` theo contract hiện có; universe mục tiêu là HOSE+HNX đã thu thập trong repo (`data/snapshots_ext` / tương đương), tập đánh giá smoke ≈ 235 mã `quality_tier_full` + `quality_tier_limited`.
- Bản tham chiếu StockAI chỉ đọc để port hành vi; lệch có chủ đích:
  1. M6 **không** hard-code `status="partial"` (tham chiếu hiện gán cứng) — `ok` khi đủ điều kiện chấm.
  2. **Cực tính R**: StockAI “R cao = rủi ro thấp”; feature này theo CONTRACTS — **R cao = rủi ro cao** (Resolved Q1:B). Chỉ đảo mapping chấm điểm; giữ nguyên công thức đo chỉ số.
- Ngưỡng rubric T và tham số M6 (lookback, min observations, annual sessions, hệ số/bảng mapping phụ điểm) mặc định bám tham chiếu (sau đảo mapping R) nhưng MUST đặt trong cấu hình để chỉnh sau này; docstring + config MUST ghi rõ phần đảo.
- `upstream` có thể rỗng với M3/M6 (không phụ thuộc điểm F/V/S để chạy).
- Hiến chương I–VI áp dụng: as_of, trung thực null+flags, số do code tính, test offline, phạm vi sở hữu module.
- M7 và `config/scoring.yaml` hiện đã giả định R cao = rủi ro cao (`− lambda*R`, `risk_gate`); feature này **không** sửa M7 — chỉ đảm bảo M6 khớp cùng cực tính.

## Constraints

- Không commit / không push / không Co-authored-by trừ khi người dùng yêu cầu rõ sau; `specs/` giữ local.
- MUST NOT sửa `docs/CONTRACTS.md` hay M7 trong feature này.
- Không implement code M3/M6 trong pass specify — chỉ đặc tả, checklist, `feature.json`.
