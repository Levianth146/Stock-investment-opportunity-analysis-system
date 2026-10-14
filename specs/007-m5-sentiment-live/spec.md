# Feature Specification: M5 Sentiment Live (điểm S)

**Feature Branch**: `007-m5-sentiment` (đã tạo local từ `develop`; không push)

**Feature dir**: `specs/007-m5-sentiment-live/`

**Created**: 2026-10-13

**Updated**: 2026-10-13 — khóa seed ambiguous đã duyệt; sửa quy tắc đề xuất scan; lookback mặc định 30; smoke đo insufficient_news ở 30 và 60

**Status**: Spec locked — sẵn sàng `/speckit-plan` → `/speckit-tasks` → `/speckit-implement`

**Input**: User description: "Feature 007: M5 sentiment live (điểm S). Nhánh mới 007-m5-sentiment từ develop. KHÔNG commit/push. Tham chiếu chỉ-đọc StockAI m5; tái dùng ý tưởng từ điển, KHÔNG sao chép code (lỗi mã hóa đ; xử lý riêng FPT; status=partial cứng). Cơ sở đo 235 mã: news list {id,title,url,source,published_at,summary}; ≥8 tin/mã, trung vị 59; không tin sau as_of nhưng ~12.000 tin >90 ngày; chỉ chấm theo TIÊU ĐỀ; lọc lạc đề (AAA/CEO/HCM/VND, tiêu đề nhiều mã, chứng quyền, trùng đăng). Yêu cầu: chữ ký module_out; chỉ m5_sentiment/ + config mới; không LLM; NFC giữ đ; bộ lọc liên quan; lexicon cụm từ; công thức S; readiness min_stories; metrics/flags/evidence; gold CSV nhãn trống; TDD rồi smoke 235."

## Clarifications

### Resolved — danh sách mã ticker mơ hồ (2026-10-13)

- **APPROVED seed (ghi config)**: `CEO`, `HCM`, `VND`, `AAA` only.
- **REJECTED**: `DRC` — tin DRC là tin thật; lần scan trước là false-positive vì chưa loại nguồn `vnstock/VCI` (filing) khỏi mẫu % lạc đề.
- Config `ambiguous_tickers` / tương đương MUST chỉ chứa seed đã duyệt ở trên cho đến khi người dùng duyệt thêm mã từ đề xuất scan mới.
- Mọi mã bổ sung MUST được đề xuất theo **Quy tắc đề xuất scan (corrected)** bên dưới và **được người dùng duyệt** trước khi ghi config; MUST NOT tự thêm im lặng.

### Quy tắc đề xuất scan (corrected) — dùng khi đề xuất, ghi trong spec

Khi tính % tiêu đề chứa mã nhưng thiếu từ khóa tài chính (ngưỡng đề xuất ≥30%):

1. **EXCLUDE** mọi tin nguồn `vnstock/VCI` (và biến thể tương đương package VCI) — coi là liên quan theo định nghĩa (filing/công bố).
2. **EXCLUDE** tin ngoài cửa sổ lookback (so với `as_of` của snapshot) và tin `published_at` > `as_of`.
3. Chỉ đánh giá mã có **≥ 8 tin Google News** (không phải vnstock/VCI) **bên trong** cửa sổ lookback.
4. Đầu ra scan chỉ là **danh sách đề xuất** cho người dùng duyệt — MUST NOT ghi im lặng vào config.

Lookback dùng cho scan đề xuất trong pass này: **30 ngày** (khớp mặc định config). Kết quả re-scan đính kèm báo cáo implement / Clarifications cập nhật.

### Smoke measurement (sau implement)

Sau khi implement: trên ~235 mã `full`+`limited`, báo cáo số mã có cờ `m5_insufficient_news` (hoặc tương đương `m5_insufficient_news_for_score`) với:

- `lookback_days=30`, `half_life_days=14`
- `lookback_days=60`, `half_life_days=14`

**MUST NOT** đổi mặc định config `lookback_days` khỏi **30** trừ khi người dùng yêu cầu rõ — chỉ đo và báo cáo cả hai số.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Chấm điểm S từ tiêu đề tin trong cửa sổ as_of (Priority: P1)

Người phân tích (hoặc pipeline) đưa snapshot HOSE/HNX có `snapshot.news` (danh sách tin `{id, title, url, source, published_at, summary}`) vào M5. Hệ thống chỉ dùng tin có ngày công bố ≤ `as_of`, trong cửa sổ lookback cấu hình, **chỉ chấm theo tiêu đề** (không dựa summary — Google News lặp tiêu đề; tin công bố doanh nghiệp thường summary null). Chuẩn hóa tiếng Việt bằng NFC và **giữ chữ đ** (không làm “điều tra” thành “ieu tra”). Áp dụng bộ lọc liên quan (mã/tên công ty, loại tin lạc đề/chứng quyền/tiêu đề nhiều mã, mã ticker mơ hồ đã duyệt, khử trùng tiêu đề). Chấm polarity bằng lexicon cụm từ (không LLM). Khi đủ điều kiện sẵn sàng (`min_stories` / ngưỡng tin liên quan–có hướng cấu hình) → điểm S số 0–100 và `status` = `ok`; thiếu → `score` = `null` + cờ, không bịa điểm. Mỗi nhận định evidence có tin MUST kèm `news_id`.

**Why this priority**: Điểm S là đầu vào trọng số của M7; stub hiện tại không phản ánh tin thật trên universe rộng.

**Independent Test**: Snapshot dựng tay trong thư mục tạm (đủ tin hướng; thiếu tin; tin sau as_of; tiêu đề trùng; chứng quyền; mã mơ hồ; cụm “điều tra”) + 1–2 snapshot thật nếu có dưới `data/snapshots_ext` (thiếu thì bỏ qua). Chạy M5 độc lập; không cần M2–M4/M6.

**Acceptance Scenarios**:

1. **Given** snapshot có đủ tin tiêu đề liên quan trong lookback và đủ tin có polarity ≠ 0 theo ngưỡng cấu hình, **When** chạy M5, **Then** trả `module_out` hợp lệ với `score` số trong [0, 100], `status` = `ok`, metrics đếm tin vào/liên quan/hướng/positive/negative/neutral/trùng/loại, evidence có ít nhất một mục tổng hợp và các mục tiêu đề mạnh kèm `news_id` khi có id.
2. **Given** số tin liên quan hoặc tin có hướng dưới ngưỡng sẵn sàng, **When** chạy M5, **Then** `score` = `null`, gắn cờ chưa sẵn sàng / thiếu tin (`m5_insufficient_news` hoặc tương đương), không bịa điểm; `status` phản ánh thiếu (`partial`).
3. **Given** tin có `published_at` > `as_of`, **When** chạy M5, **Then** tin đó không vào polarity hay điểm; có đếm/cờ loại tin tương lai nếu phát sinh.
4. **Given** tiêu đề chứa cụm có chữ **đ** (ví dụ “điều tra”), **When** chuẩn hóa và khớp lexicon, **Then** cụm vẫn khớp được (NFC / quy tắc giữ đ); MUST NOT dùng phép thay thế làm mất đ.
5. **Given** cùng một tiêu đề (sau chuẩn hóa) lặp từ nhiều nguồn, **When** chạy M5, **Then** chỉ giữ một bản; đếm trùng và gắn cờ khử trùng khi có.
6. **Given** tiêu đề chứng quyền / liệt kê nhiều mã / mã nằm trong danh sách mơ hồ đã duyệt mà không đủ tín hiệu tài chính cấu hình, **When** chạy M5, **Then** tin bị loại khỏi tập liên quan (hoặc xử lý theo quy tắc mã mơ hồ đã ghi config sau duyệt), không làm sập module.

---

### User Story 2 - Cấu hình lexicon, ngưỡng sẵn sàng và gold CSV nhãn trống (Priority: P1)

Người phát triển đưa lexicon cụm dương/âm, lookback, `min_stories` (và ngưỡng tin liên quan / tin có hướng tương đương), danh sách mã mơ hồ đã duyệt (`CEO`, `HCM`, `VND`, `AAA`), và tham số công thức S vào **file cấu hình mới** thuộc phạm vi M5 (không hard-code ngưỡng trong mã nguồn). Tạo (hoặc cập nhật) bộ gold CSV với cột nhãn trống để gắn nhãn tay sau — kiểm thử tự động không yêu cầu nhãn đã điền trong feature này. Không gọi LLM; không sửa contracts/pipeline/M7.

**Why this priority**: Tách cấu hình giúp hiệu chỉnh lexicon/ngưỡng sau smoke 235 mà không đụng schema; gold CSV chuẩn bị đánh giá lexicon sau này.

**Independent Test**: Thiếu khóa cấu hình → mặc định an toàn + cờ; gold CSV tồn tại với schema cột đã nêu và nhãn trống; chạy M5 không phụ thuộc dịch vụ LLM.

**Acceptance Scenarios**:

1. **Given** file cấu hình M5 có lexicon và ngưỡng, **When** chạy M5, **Then** mọi ngưỡng điểm / lookback / min_stories / danh sách mơ hồ đọc từ cấu hình, không hard-code giá trị nghiệp vụ trong mã nguồn.
2. **Given** thiếu khóa cấu hình không bắt buộc, **When** chạy M5, **Then** dùng mặc định đã ghi trong Assumptions và gắn cờ cấu hình nếu cần; không crash.
3. **Given** bộ gold CSV của feature, **When** mở file, **Then** có cột nhãn (hoặc tương đương) **trống**; không yêu cầu nhãn đã điền để pass test offline của feature.
4. **Given** bất kỳ lần chạy M5, **When** quan sát phụ thuộc ngoài, **Then** không có gọi LLM / API sinh văn bản để chấm polarity.

---

### User Story 3 - TDD offline rồi smoke ~235 mã full+limited (Priority: P1)

Người phát triển viết kiểm thử trước (fail trên stub `status=stub`), rồi mới triển khai heuristic. Test chính offline bằng snapshot dựng tay; MAY thêm 1–2 case snapshot thật. Sau implement: toàn bộ pytest dự án; smoke M5 trên ~235 mã `full`+`limited` và in phân bố điểm S, số `ok`/`partial`, số `score` = `null`, tỷ lệ tin bị lọc, **và số mã có `m5_insufficient_news` ở lookback 30 và 60** (half-life 14; mặc định config giữ 30). Phạm vi file: chỉ `src/stockai/m5_sentiment/`, tests `tests/test_m5_*.py`, và file cấu hình mới cho M5 (và gold CSV nếu đặt dưới `fixtures/` hoặc `config/` theo plan); optional `scripts/smoke_m5_batch.py` local. Không commit/push trong phạm vi feature trừ khi người dùng yêu cầu sau.

**Why this priority**: Stub luôn giả; TDD + smoke batch chứng minh S chạy thật trên dữ liệu repo.

**Independent Test**: Fail-first trên stub; sau implement pytest sạch; smoke có bảng phân bố dán vào báo cáo hoàn thành implement.

**Acceptance Scenarios**:

1. **Given** stub M5 hiện tại, **When** chạy bộ test mới của feature, **Then** các test hành vi thật **fail trước** khi có code live.
2. **Given** đã implement xong, **When** chạy toàn bộ kiểm thử dự án offline, **Then** pass; số test được báo cáo.
3. **Given** thư mục snapshot HOSE+HNX với mã full+limited (~235), **When** chạy smoke M5, **Then** không crash hàng loạt; in phân bố score S, đếm status ok/partial, đếm score null; đếm `m5_insufficient_news` với lookback=30 và lookback=60 (half-life=14); kết quả dán vào báo cáo hoàn thành.
4. **Given** mọi thay đổi của feature, **When** xem phạm vi file, **Then** chỉ đụng `m5_sentiment/`, tests M5, config mới M5 (+ gold CSV nếu có, + optional smoke script); MUST NOT sửa `m1_data/*`, `pipeline.py`, `contracts/*`, `docs/CONTRACTS.md`, M7, hay module M2–M4/M6/M8/M9.

---

### Edge Cases

- `meta.synthetic` = true: gắn cờ synthetic; không đủ điều kiện chấm điểm thật → `score` = null.
- `news` thiếu / không phải list / phần tử không phải dict: không crash; cờ thiếu/lỗi; score null nếu không đủ tin hợp lệ.
- `published_at` / `as_of` không parse được: loại hoặc gắn cờ ngày không hợp lệ; không dùng tin đó vào điểm.
- Tiêu đề rỗng sau chuẩn hóa: loại khỏi tập liên quan.
- Mã trong danh sách mơ hồ đã duyệt (`CEO`, `HCM`, `VND`, `AAA`): áp quy tắc lọc chặt hơn (ví dụ yêu cầu thêm từ khóa tài chính / tên công ty) — chi tiết tham số nằm ở config.
- Tiêu đề có mã nhưng là chứng quyền hoặc liệt kê nhiều mã: loại theo quy tắc cấu hình.
- Summary null hoặc lặp tiêu đề: không ảnh hưởng vì chỉ chấm tiêu đề.
- Lexicon: không dùng đơn từ mơ hồ đơn lẻ kiểu “tăng”/“giảm”/“mua”/“bán”/“lãi”/“lỗ” đứng một mình (chỉ cụm đủ nghĩa).
- Khi `score` = null: M7 (ngoài phạm vi sửa) sẽ thay bằng điểm trung tính 50 và gắn `S_missing_used_neutral` — xem Assumptions / báo cáo M7; feature này không đổi M7.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: M5 MUST giữ chữ ký `run(snapshot, upstream, cfg) -> dict` và đầu ra MUST hợp lệ `module_out` (validate theo contract hiện có). MUST NOT đổi schema/contracts. `module` = `m5`; `score` là điểm **S** (0–100 hoặc null).
- **FR-002**: Phạm vi sửa MUST giới hạn ở `src/stockai/m5_sentiment/`, `tests/test_m5_*.py`, và **file cấu hình mới** cho sentiment/lexicon/ngưỡng (và gold CSV nhãn trống nếu đặt trong repo; optional `scripts/smoke_m5_batch.py`). MUST NOT sửa `src/stockai/m1_data/*`, `pipeline.py`, `src/stockai/contracts/*`, `docs/CONTRACTS.md`, M7, hay thư mục module khác.
- **FR-003**: Polarity và điểm S MUST tính bằng heuristic lexicon / quy tắc cấu hình. MUST NOT dùng LLM hay mô hình sinh văn bản để chấm tin. `m5.llm_enabled` MUST là `false` (hoặc tương đương).
- **FR-004**: Chuẩn hóa tiêu đề tiếng Việt MUST dùng dạng tương thích **NFC** và MUST **bảo toàn chữ đ**. MUST NOT áp dụng chuỗi xử lý kiểu tách dấu rồi thay thế ký tự làm mất đ (anti-pattern tham chiếu StockAI: sau NFD, `replace("?","d")` làm “điều tra” → “ieu tra”).
- **FR-005**: Hệ thống MUST chỉ dùng tin có ngày công bố ≤ `as_of` và trong lookback cấu hình; MUST chỉ chấm **tiêu đề** (không lấy polarity từ summary). MUST loại tin không liên quan theo bộ lọc: khớp mã/tên công ty; khử trùng tiêu đề; chứng quyền; tiêu đề liệt kê nhiều mã; mã ticker mơ hồ theo danh sách đã duyệt + quy tắc bổ sung cấu hình.
- **FR-006**: Danh sách mã ticker mơ hồ trong config MUST = seed đã duyệt: `CEO`, `HCM`, `VND`, `AAA`. Mọi mã bổ sung MUST được đề xuất theo quy tắc scan corrected và **được người dùng duyệt** trước khi ghi config; MUST NOT tự thêm im lặng. MUST NOT thêm `DRC` trừ khi người dùng duyệt lại sau này.
- **FR-007**: Lexicon MUST là cụm từ (phrase) dương/âm có trọng số trong cấu hình; MUST lộ các cụm khớp trên evidence/metrics phù hợp. MUST NOT chấm bằng đơn từ quá mơ hồ đã loại trừ trong Assumptions.
- **FR-008**: Công thức điểm S MUST đọc tham số từ cấu hình (lookback, half-life, ngưỡng sẵn sàng, hệ số ánh xạ polarity → S). Hành vi mặc định (Assumptions): trung tính 50; điều chỉnh theo polarity có trọng số thời gian và độ bao phủ tin có hướng; clamp [0, 100]. Khi chưa đủ sẵn sàng: `score` = null.
- **FR-009**: Điều kiện sẵn sàng (`min_stories` / tối thiểu tin liên quan và tin có hướng — tên khóa cấu hình chốt ở plan) MUST nằm trong config. Đủ điều kiện và tính được điểm → `status` = `ok`. Thiếu → `score` = null, `status` = `partial`, kèm cờ (`m5_insufficient_news` / tương đương). MUST NOT gắn cứng `status` = `partial` cho mọi lần chạy (anti-pattern StockAI). MUST NOT hard-code xử lý riêng một mã kiểu FPT trong mã nguồn (anti-pattern tham chiếu); nếu cần ngoại lệ, đưa vào config đã duyệt.
- **FR-010**: Đầu ra MUST gồm metrics đếm tin (input / relevant / directional / positive / negative / neutral / duplicate / excluded-by-reason), flags nhất quán tiền tố `m5_…`, và evidence: (a) câu tổng hợp; (b) các tiêu đề mạnh đã phân loại kèm `news_id` khi có — khớp CONTRACTS “mọi nhận định truy về `news.id`”. Evidence tiêu đề mạnh tối đa **6** mục.
- **FR-011**: Feature MUST cung cấp gold CSV với **nhãn trống** (cột label/rỗng) để gắn nhãn tay sau; bộ test offline MUST NOT phụ thuộc nhãn đã điền. Kiểm thử MUST viết trước (fail trên stub), offline bằng fixture dựng tay; MAY thêm snapshot thật có skip nếu thiếu. Sau implement: pytest toàn dự án + smoke ~235 mã full+limited với bảng phân bố S / ok / partial / null và đếm insufficient_news ở lookback 30 vs 60. MUST NOT commit/push/Co-authored-by trừ khi người dùng yêu cầu rõ sau.

### Key Entities

- **Sentiment Module Output (M5)**: `module_out` với score S, metrics đếm tin và polarity/confidence, evidence gắn `news_id`, flags sẵn sàng/lọc/cấu hình.
- **News Item**: Phần tử `snapshot.news` với `id`, `title`, `url`, `source`, `published_at`, `summary` (summary không dùng để chấm).
- **Relevant Story Set**: Tập tin sau lọc as_of / lookback / liên quan / khử trùng — đầu vào lexicon.
- **Sentiment Config**: File cấu hình mới (lexicon, lookback, half-life, min_stories / ngưỡng hướng, danh sách mã mơ hồ đã duyệt, hệ số công thức S, aliases).
- **Gold Label Rows**: CSV mẫu với trường nhãn trống cho đánh giá lexicon sau này.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Với snapshot dựng tay đủ tin tiêu đề liên quan và đủ tin có hướng, người dùng nhận được điểm S số trong 0–100 và trạng thái thành công từ M5 trong một lần chạy module.
- **SC-002**: Với snapshot dựng tay thiếu tin dưới ngưỡng sẵn sàng, M5 trả điểm trống (null) kèm cờ — không bịa điểm.
- **SC-003**: Không có tin có ngày công bố sau ngày đánh giá nào lọt vào polarity hoặc điểm S (kiểm chứng bằng fixture có tin “tương lai”).
- **SC-004**: Fixture tiêu đề chứa “điều tra” (hoặc cụm lexicon có đ tương đương) vẫn được khớp lexicon — chứng minh giữ chữ đ.
- **SC-005**: Tiêu đề trùng / chứng quyền / tiêu đề nhiều mã / mã mơ hồ (theo seed đã cấu hình) bị loại khỏi tập liên quan theo quy tắc đã nêu; module không crash.
- **SC-006**: Toàn bộ kiểm thử tự động offline của dự án pass sau implement; số test được báo cáo trong báo cáo hoàn thành.
- **SC-007** (vận hành sau implement): Smoke trên khoảng 235 mã full+limited hoàn tất không crash hàng loạt; bảng phân bố điểm S, số ok/partial, số score null, và số mã `m5_insufficient_news` ở lookback 30 và 60 (half-life 14) được in và dán vào báo cáo hoàn thành; mặc định config lookback giữ 30.
- **SC-008**: Diff phạm vi đúng: không thay đổi `m1_data`, `pipeline.py`, `contracts`, `docs/CONTRACTS.md`, M7, hay module khác ngoài M5 + config/gold mới của feature (+ optional smoke script).

## Assumptions

- **Nhánh git**: `007-m5-sentiment` từ `develop`. Repo không có `.specify/extensions.yml` — không auto-hook tạo nhánh. Không force-checkout nếu dirty work trên nhánh khác.
- Snapshot đầu vào đã có `news` theo đo thực tế (~≥8 tin/mã, trung vị ~59 trên tập full+limited); smoke ≈ 235 mã `quality_tier_full` + `quality_tier_limited` trong `data/snapshots_ext` (hoặc tương đương).
- **Chỉ tiêu đề**: summary không đáng tin để chấm (Google News lặp tiêu đề; VCI/vnstock summary null / url “n/a”).
- **Mặc định cấu hình** (có thể chỉnh sau, không hỏi lại trừ khi đổi hành vi lớn):
  - `lookback_days` = **30** (giữ mặc định; smoke thêm đo 60 nhưng không đổi default).
  - `half_life_days` = **14**.
  - Ngưỡng sẵn sàng: tối thiểu tin liên quan = 8 (`min_stories` / `min_relevant_news`); tối thiểu tin có hướng = 4.
  - Công thức S mặc định (ý tưởng tham chiếu, tham số hóa): polarity có trọng số suy giảm theo tuổi tin; `S = clamp(50 + 35 * weighted_polarity * confidence, 0, 100)` với `confidence` giới hạn bởi số tin có hướng và tỷ lệ bao phủ hướng; chi tiết khóa config chốt ở `/speckit-plan`.
  - `ambiguous_tickers` = [`CEO`, `HCM`, `VND`, `AAA`].
  - `m5.llm_enabled` = false.
- **M7 và `score` null (chỉ đọc — không sửa M7)**: Khi M5 trả `score: null` (hoặc upstream thiếu / `status == "error"`), M7 `sc("m5")` nhận `None` và `compute_score` thay bằng `neutral_score_when_missing` (**50**) kèm cờ `S_missing_used_neutral`. Khi M5 trả số, M7 dùng nguyên số đó trong trọng số `w_S`. Feature 007 chấp nhận hành vi này; không đổi M7/CONTRACTS trong feature này.
- Bản tham chiếu StockAI chỉ đọc để lấy ý tưởng lexicon/lọc; **không** copy code. Anti-pattern MUST tránh: (1) mất chữ đ khi chuẩn hóa; (2) hard-code lọc FPT; (3) `status="partial"` cứng mọi lần chạy.
- `upstream` có thể rỗng với M5 (không phụ thuộc F/T/V/R).
- Hiến chương / bất biến dự án: as_of, thiếu → null + flags, số do code tính, test offline, phạm vi sở hữu module (N5: `m5_sentiment/`).

## Constraints

- Không commit / không push / không Co-authored-by trừ khi người dùng yêu cầu rõ sau; `specs/` giữ local.
- MUST NOT sửa `docs/CONTRACTS.md` hay M7 trong feature này.
- Không ghi mã mơ hồ ngoài seed đã duyệt vào config cho đến khi người dùng duyệt đề xuất scan mới.
