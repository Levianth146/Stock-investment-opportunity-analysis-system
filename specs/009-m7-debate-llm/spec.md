# Feature Specification: M7 Debate (Bull/Bear) qua LLM

**Feature Branch**: `009-m7-debate-llm` (ưu tiên tạo sau từ `develop`; **chưa** tạo trong pass specify — không có `before_specify` hook / `.specify/extensions.yml`)

**Feature dir**: `specs/009-m7-debate-llm/`

**Created**: 2026-10-13

**Updated**: 2026-10-13 — khóa clarifications Q1–Q3

**Status**: Spec locked — sẵn sàng `/speckit-plan`

**Input**: User description: "Feature 009: M7 debate (Bull/Bear) via LLM, replace stub `debate.py`. Provider layer `src/stockai/llm/`. Không đổi scoring formula/thresholds, M1–M6, pipeline. Design: generate_json; gemini+glm; env keys only; compact payload; bull/bear 2–4 items text+refs; prompt bans; code validator+retry; deterministic template fallback; disk cache; run_debate_batch.py; offline tests mock; schema refs → propose N1 nếu block (không edit contracts trong specify); M8 warning debate_ungrounded; smoke providers + batch 10 tickers = Success Criteria sau implement — không gọi API trong specify."

## Clarifications

### Resolved — Q1 / Q2 / Q3 (2026-10-13)

| Q | Quyết định | Ý nghĩa |
|---|---|---|
| **Q1: B** | **Không** sửa `src/stockai/contracts/schemas.py`. Convention `refs` ghi trong spec này; lúc implement thêm **một dòng** vào `docs/CONTRACTS.md` mô tả convention (không đổi schema). | `refs` vẫn hợp lệ nhờ `additionalProperties` mặc định trên item `bull`/`bear`. |
| **Q2: B** | `refs` là **mảng chuỗi phẳng**. Metric: `m<number>.<name>` (vd. `m4.pe`). Tin: `n<number>` (vd. `n12`). M8 phân loại bằng **regex**. | Validator + test bắt buộc theo convention; M8 `debate_ungrounded` dùng cùng quy tắc. |
| **Q3: A** | HTTP chỉ qua **`requests` REST** cho **cả** Gemini và GLM. **Không** thêm SDK mới vào `requirements.txt`. | Gemini: `generateContent` REST; GLM: chat completions REST (OpenAI-compatible URL, gọi bằng `requests`). |

### Convention `refs` (khóa)

Mỗi phần tử trong `bull[]` / `bear[]`:

```json
{"text": "…", "refs": ["m4.pe", "n12", "m2.roe"]}
```

| Loại | Regex (ý nghĩa) | Ví dụ | Resolve khi validate / M8 |
|---|---|---|---|
| Metric / module field | `^m[0-9]+\.[A-Za-z0-9_]+$` | `m4.pe`, `m2.roe`, `m6.beta` | Phải tương ứng metric (hoặc khóa tương đương đã expose trong compact payload / upstream `metrics`) của module `mN` |
| News id | `^n[0-9]+$` | `n12` | Phải map tới `snapshot.news[].id` theo quy ước ổn định đã dùng khi build payload (cùng id mà LLM được phép trích) |

- Chuỗi không khớp regex → **ungrounded**.
- Khớp regex nhưng không resolve được trong snapshot/upstream → **ungrounded**.
- Mỗi luận điểm scored MUST có `refs` non-empty và mọi phần tử grounded; thiếu → fail validator (retry) hoặc M8 `debate_ungrounded` nếu lọt xuống result.
- **MUST** có unit test cho regex phân loại + resolve (metric vs news) và cho cảnh báo M8.

### Deliverable tài liệu (implement — không làm trong specify)

- Thêm **một dòng** vào `docs/CONTRACTS.md` (mục M7): mỗi mục `bull`/`bear` có `text` + `refs` (mảng chuỗi `mN.name` / `nK`); **không** đổi `schemas.py`.

## Survey Snapshot (bắt buộc — đã chạy thật trước khi khóa field)

### (a) Schema `module_out` / `result` / validation liên quan debate

Nguồn: `src/stockai/contracts/schemas.py` (Draft202012Validator).

| Schema | Vai trò debate | Item schema |
|---|---|---|
| `MODULE_OUT_SCHEMA` (`module_out`) | Không chứa `bull`/`bear`. Evidence pattern cho M2–M6: `{text` bắt buộc; `source_id`, `news_id` tùy chọn} | `additionalProperties` không đặt `false` → field thừa được chấp nhận |
| `RESULT_SCHEMA` (`result`) | **Đây là chỗ M7 ghi debate**: `bull` và `bear` là mảng bắt buộc | Mỗi phần tử: `{"type":"object","required":["text"]}` — **không** khai `properties`, **không** `additionalProperties: false` |
| `VALIDATION_SCHEMA` (`validation`) | M8: `status` + `issues[{severity,message,where?}]` | Có thể gắn cảnh báo mới (ví dụ `debate_ungrounded`) mà **không** cần đổi schema validation |

**Thử nghiệm validator (2026-10-13)**: object `{"text":"ok","refs":["m4.pe","n12"]}` **pass** `Draft202012Validator` trên item schema hiện tại (danh sách lỗi rỗng).

**Kết luận schema (đã khóa Q1:B)**:

- `refs` **được phép** mà **không đổi** `schemas.py`.
- Feature **MUST NOT** sửa `schemas.py`.
- Tài liệu convention: spec này + **một dòng** `CONTRACTS.md` lúc implement.

**M7 stub hiện tại**: `src/stockai/m7_scoring/debate.py` trả 1 bull + 1 bear dạng `{"text":"[stub] ..."}` — không có `refs`. `run.py` gọi `run_debate` sau scoring; nhánh `quality_gate.scored == false` tự gắn bull/bear quality_gate (không gọi LLM).

**`scoring.py` / `config/scoring.yaml`**: chỉ công thức điểm + rating — **ngoài phạm vi sửa** feature này.

**M8 hiện tại** (`src/stockai/m8_validate/run.py`): kiểm tra data, module evidence `source_id`/`news_id`, và công thức M7/target; **chưa** kiểm tra grounding `bull`/`bear`. Feature này **bổ sung** cảnh báo `debate_ungrounded` (severity `warn`) khi luận điểm thiếu `refs` hợp lệ / refs không resolve — **không** đổi hành vi scoring hay fail công thức. Phân loại ref bằng regex convention ở trên.

### (b) Tài liệu chính thức nhà cung cấp LLM (Oct 2026)

#### Google Gemini Flash

| Mục | Giá trị chính thức | Nguồn |
|---|---|---|
| Model ID ổn định | **`gemini-3.8-flash`** (GA, Sep 2026) | https://ai.google.dev/gemini-api/docs/models/gemini-3.8-flash |
| Endpoint generateContent (REST) | `POST https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent` | Docs models / generateContent |
| Structured output | Hỗ trợ Structured outputs (JSON schema trong generation config) | https://ai.google.dev/gemini-api/docs/generate-content/structured-output |
| Free-tier rate limits | RPM / TPM / RPD per project; số cụ thể xem AI Studio | https://ai.google.dev/gemini-api/docs/rate-limits |

#### Z.AI GLM Flash

| Mục | Giá trị chính thức | Nguồn |
|---|---|---|
| Model ID | **`glm-5.3-flash`** (biến thể `glm-5.3-flashx`) | https://docs.z.ai/guides/vlm/glm-5.3-flash |
| OpenAI-compatible base URL | **`https://api.z.ai/api/paas/v4/`** (`.../chat/completions`) | https://docs.z.ai/guides/develop/openai/python |
| JSON mode | `response_format: {"type": "json_object"}` | https://docs.z.ai/guides/capabilities/struct-output |

**Transport đã khóa (Q3:A)**: cả hai provider gọi bằng **`requests` REST** — không thêm package LLM mới.

**Pass specify**: không gọi API thật, không smoke provider.

### (c) `.gitignore` / dependencies

| Mục | Kết quả |
|---|---|
| `.env` trong `.gitignore` | **Có** |
| HTTP/SDK trong `requirements.txt` | `requests` (+ `anthropic`/`openai` sẵn có nhưng **feature 009 không phụ thuộc SDK mới**). Implement debate Gemini+GLM **chỉ** dùng `requests`. |
| Config sẵn | `config/llm.yaml` (N5) mở rộng cho gemini/glm. |

## Schema / refs — quyết định cuối (không patch schema)

- **`schemas.py`**: **không đổi**.
- **`refs`**: field bổ sung trên mỗi item `bull`/`bear` (schema hiện tại chấp nhận).
- **`docs/CONTRACTS.md`**: deliverable implement = **một dòng** mô tả convention `refs` (`mN.name` / `nK`); không mở rộng schema JSON.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Thay stub debate bằng luận điểm Bull/Bear grounded (Priority: P1)

Người phân tích chạy pipeline M7 trên snapshot đã có M2–M6. Hệ thống sinh **2–4** luận điểm bull và **2–4** bear, mỗi mục có `text` tiếng Việt và `refs` (mảng chuỗi `mN.name` / `nK`). LLM **không** đặt giá mục tiêu, **không** bịa số ngoài upstream. Khi LLM lỗi / JSON sai / không grounded sau retry → fallback template xác định từ số liệu upstream (vẫn đủ `text` + `refs` hợp lệ khi có thể, gắn cờ fallback). Scoring và rating **không đổi**.

**Why this priority**: Stub hiện tại vô nghĩa cho báo cáo; đây là giá trị cốt lõi feature.

**Independent Test**: Mock provider trả JSON hợp lệ / JSON xấu / thiếu refs / refs sai regex; gọi `run_debate` offline; assert độ dài 2–4, `text`, `refs` phẳng; validator+retry+fallback; score/rating không đổi.

**Acceptance Scenarios**:

1. **Given** upstream M2–M6 ok và mock LLM trả JSON đúng convention (`refs` chuỗi `m4.pe`, `n12`, …), **When** `run_debate`, **Then** `bull`/`bear` mỗi bên 2–4 phần tử, mỗi phần tử có `text` non-empty và `refs` non-empty đạt convention; `validate(..., "result")` pass khi gắn vào result mẫu.
2. **Given** mock LLM trả số liệu / giá mục tiêu tự bịa hoặc `refs` không khớp regex / không resolve, **When** validator chạy, **Then** từ chối; sau hết retry → fallback template + cờ (ví dụ `debate_fallback_template`).
3. **Given** `quality_gate.scored == false`, **When** M7 `run`, **Then** vẫn dùng bull/bear quality_gate hiện có; **không** bắt buộc gọi LLM.
4. **Given** cùng input scoring, **When** so điểm/rating trước/sau feature, **Then** công thức và ngưỡng không đổi.

---

### User Story 2 - Lớp provider LLM thống nhất qua `requests` + bí mật từ môi trường (Priority: P1)

Người vận hành cấu hình Gemini và/hoặc GLM qua config; khóa API **chỉ** từ biến môi trường / `.env` (đã gitignore). Giao diện thống nhất `generate_json(...) -> dict`. Cả Gemini và GLM gọi bằng **HTTP REST qua `requests`** (không SDK mới). Payload **gọn**. Cache đĩa theo khóa nội dung.

**Why this priority**: Tách provider, bảo mật khóa, tiết kiệm quota, không đụng `requirements.txt` của N1.

**Independent Test**: Unit test mock `requests`; thiếu env → fallback + cờ; cache hit không gọi mạng.

**Acceptance Scenarios**:

1. **Given** thiếu khóa môi trường cho provider đang chọn, **When** chạy debate, **Then** không đọc bí mật ngoài env; fallback template (hoặc provider khác nếu cấu hình) + cờ; không in khóa.
2. **Given** cùng payload+model đã cache, **When** chạy lại, **Then** dùng cache đĩa; mock đếm HTTP call = 0.
3. **Given** payload debate, **When** quan sát request body mock, **Then** không chứa toàn bộ `prices.rows`.
4. **Given** implement provider, **When** xem dependencies feature 009, **Then** không thêm package Gemini/GLM mới vào `requirements.txt`; chỉ dùng `requests`.

---

### User Story 3 - M8 `debate_ungrounded` + regex refs + batch/smoke sau implement (Priority: P2)

M8 gắn `warn` `debate_ungrounded` khi bull/bear thiếu refs hợp lệ (regex + resolve). Test bắt buộc cho convention. Sau implement: batch ~10 mã + smoke provider khi có khóa.

**Why this priority**: Truy nguồn là bất biến; smoke chứng minh live path.

**Independent Test**: Fixture ungrounded (thiếu refs / sai regex / id không tồn tại) → M8 `warn` + `debate_ungrounded`; fixture grounded → không có cảnh báo đó. Unit test regex `mN.name` vs `nK`.

**Acceptance Scenarios**:

1. **Given** phần tử bull/bear không grounded, **When** M8 `run`, **Then** issue severity `warn` chứa `debate_ungrounded`; không `fatal` chỉ vì thiếu refs.
2. **Given** mọi luận điểm grounded theo convention, **When** M8 `run`, **Then** không có `debate_ungrounded`.
3. **Given** chuỗi ref mẫu (`m4.pe`, `n12`, `bad`, `m4`, `nX`), **When** chạy bộ test phân loại regex, **Then** đúng metric / news / invalid theo bảng convention.
4. **Given** (sau implement, có khóa) batch ≥10 ticker, **When** chạy script batch, **Then** không crash hàng loạt; ≥1 mã non-stub — tiêu chí SC live.

---

### User Story 4 - Kiểm thử offline với mock (Priority: P1)

Toàn bộ pytest debate/provider dùng mock `requests`; không mạng. Phủ validator, regex refs, retry, fallback, cache, M8 warn.

**Why this priority**: CI offline bắt buộc.

**Acceptance Scenarios**:

1. **Given** bộ test feature 009, **When** chạy pytest, **Then** pass offline; không phụ thuộc khóa môi trường có giá trị.
2. **Given** stub cũ, **When** test hành vi grounded trước khi thay stub đủ, **Then** fail-first rồi xanh sau implement.

---

### Edge Cases

- LLM trả JSON không parse được / thiếu `bull`/`bear` → retry → fallback template.
- LLM trả >4 hoặc <2 luận điểm mỗi phía → chuẩn hóa hoặc reject+retry; không mảng rỗng trên nhánh scored.
- `refs` sai regex hoặc không resolve → ungrounded; M8 warn; debate MAY lọc/retry/fallback.
- Provider 429 / timeout → retry ngắn rồi fallback + cờ.
- Cache đĩa hỏng → bỏ qua cache + cờ, vẫn chạy.
- Snapshot `synthetic` → cho phép test offline; M8 warn synthetic riêng.
- Nhánh insufficient quality_gate → không ép LLM.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Hệ thống MUST thay stub `run_debate` bằng luồng debate thật (LLM hoặc fallback), giữ chữ ký trả `tuple[list[dict], list[dict]]` tương thích `m7_scoring/run.py`.
- **FR-002**: Hệ thống MUST cung cấp lớp provider thống nhất với giao diện tương đương `generate_json(...)` trả dict JSON cho debate.
- **FR-003**: Hệ thống MUST hỗ trợ Google Gemini **`gemini-3.8-flash`** và Z.AI **`glm-5.3-flash`** (failover/thứ tự theo config).
- **FR-004**: Hệ thống MUST đọc khóa API chỉ từ biến môi trường (và `.env` local đã gitignore); MUST NOT commit hoặc in giá trị khóa.
- **FR-005**: Hệ thống MUST gửi payload compact (scores/metrics/evidence tóm tắt, news id+title (±summary ngắn), không dump OHLCV đầy đủ).
- **FR-006**: Mỗi phía bull và bear MUST có từ 2 đến 4 luận điểm; mỗi luận điểm MUST có `text` (string non-empty) và `refs` là **mảng chuỗi phẳng** theo convention `m<number>.<name>` và/hoặc `n<number>`.
- **FR-007**: Prompt MUST cấm: bịa số không có trong upstream; tự đặt giá mục tiêu; khẳng định không có evidence; trích dẫn ref không tồn tại / sai convention.
- **FR-008**: Hệ thống MUST validate đầu ra bằng code (độ dài, `text`, `refs` regex + resolve, không số/target bịa); khi fail MUST retry LLM có giới hạn rồi fallback.
- **FR-009**: Khi LLM không dùng được / fail hết retry, hệ thống MUST sinh bull/bear từ **template xác định** dựa trên upstream (cùng input → cùng text), kèm flag fallback.
- **FR-010**: Hệ thống MUST cache kết quả debate trên đĩa theo khóa ổn định (ticker, as_of, hash payload/model/prompt-version) và tái sử dụng khi hit.
- **FR-011**: Repo MUST có script batch debate (ví dụ `scripts/run_debate_batch.py`) chạy nhiều mã từ snapshot + gọi provider khi bật; specify không chạy live.
- **FR-012**: Kiểm thử tự động MUST mock HTTP (`requests`); MUST NOT gọi mạng trong pytest; MUST có test riêng cho convention/regex `refs` và resolve metric vs news.
- **FR-013**: M8 MUST thêm cảnh báo `debate_ungrounded` (severity `warn`) khi bull/bear không grounded; phân loại ref bằng regex convention; MUST NOT đổi ngưỡng fail công thức điểm M7.
- **FR-014**: Feature MUST NOT sửa công thức/ngưỡng trong `scoring.py` / `config/scoring.yaml`; MUST NOT sửa M1–M6 hay `pipeline.py` / `main.py`.
- **FR-015**: Mọi `analysis_result` sau debate MUST vẫn pass `validate(result, "result")` với **`schemas.py` không đổi**.
- **FR-016**: Feature MUST NOT sửa `src/stockai/contracts/schemas.py`. Lúc implement MUST thêm **một dòng** vào `docs/CONTRACTS.md` mô tả convention `refs` của debate item (`mN.name` / `nK`).
- **FR-017**: `refs` MUST là `array` of `string` (không dùng object); metric keys MUST khớp `^m[0-9]+\.[A-Za-z0-9_]+$`; news ids MUST khớp `^n[0-9]+$`.
- **FR-018**: Cả Gemini và GLM MUST gọi qua **`requests` REST only**; MUST NOT thêm SDK Google GenAI / `zai-sdk` / dependency LLM mới vào `requirements.txt` cho feature này.

### Key Entities

- **DebateItem**: `{text: string, refs: string[]}` theo convention khóa.
- **DebatePayload (compact)**: bản tóm tắt đầu vào LLM từ snapshot + upstream M2–M6 (kèm id tin dạng `nK` và metric dạng `mN.name` để model trích đúng).
- **ProviderResult**: JSON thô từ LLM trước validator.
- **DebateCacheEntry**: bản ghi đĩa keyed theo nội dung + model.
- **ValidationIssue `debate_ungrounded`**: cảnh báo M8 khi thiếu grounding theo regex + resolve.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Trên đường đi mock đạt chuẩn, 100% mã scored trong fixture test có đúng 2–4 bull và 2–4 bear; mỗi mục có `text` non-empty và `refs` non-empty đạt convention.
- **SC-002**: 100% trường hợp mock JSON sai / ungrounded sau hết retry vẫn trả debate không rỗng qua template fallback (không crash M7).
- **SC-003**: Toàn bộ pytest dự án (gồm test debate mới) pass offline; 0 request mạng trong suite đó.
- **SC-004**: M8 gắn `debate_ungrounded` đúng trên fixture ungrounded và không gắn nhầm trên fixture grounded.
- **SC-005**: Bộ test convention `refs` phân loại đúng ≥ các case đại diện: metric hợp lệ, news hợp lệ, chuỗi invalid; resolve fail khi id/metric không tồn tại.
- **SC-006** *(Acceptance sau implement — có khóa)*: Smoke từng provider (REST `requests`) ≥1 lần `generate_json` debate hợp lệ hoặc ghi nhận lỗi môi trường rõ ràng.
- **SC-007** *(Acceptance sau implement)*: Batch ≥10 ticker hoàn thành không crash hàng loạt; báo cáo LLM ok / fallback / cache hit; ≥1 mã bull/bear khác `[stub]`.
- **SC-008**: Điểm số và rating M7 trên cùng fixture upstream **không đổi** so với baseline chỉ thay stub debate.
- **SC-009** *(sau implement)*: `docs/CONTRACTS.md` có đúng **một dòng** (hoặc một bullet tương đương) mô tả convention `refs`; `schemas.py` diff = không đổi vì feature này.

## Assumptions

- Pass specify **không** implement LLM, **không** gọi API, **không** chạy batch, **không** sửa `CONTRACTS.md` / `schemas.py` trong pass này (dòng CONTRACTS là việc implement).
- Schema hiện tại đủ cho `refs` string array; không cần patch N1 schema.
- Ánh xạ `nK` ↔ `snapshot.news[].id` được định nghĩa ổn định khi build compact payload (cùng quy ước LLM và M8 dùng chung) — chi tiết plan.
- Ánh xạ `mN.name` ↔ khóa trong `upstream[mN].metrics` (hoặc alias đã liệt kê trong payload) — chi tiết plan.
- Ngôn ngữ luận điểm: tiếng Việt.
- Retry LLM mặc định: tổng ≤3 lần rồi fallback — chi tiết ở plan.
- Cache dir dưới data/cache đã ignore hoặc đường dẫn local không commit.
- `config/llm.yaml` (N5) mở rộng cho gemini/glm.
- Không commit/push trong pass specify.

## Out of Scope

- Đổi trọng số / ngưỡng rating / risk_gate.
- Viết lại M9 PDF layout (ngoài việc tiêu thụ bull/bear mới).
- Fine-tune model / RAG ngoài snapshot+upstream.
- Sửa `src/stockai/contracts/schemas.py`.
- Thêm SDK LLM mới vào `requirements.txt`.
