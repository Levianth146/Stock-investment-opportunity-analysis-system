# Research: M5 Sentiment Live

## R0 — Chuẩn hóa tiếng Việt giữ chữ đ

**Decision**: Chuẩn hóa bằng `unicodedata.normalize("NFC", ...)` rồi lower-case;
khi fold dấu để khớp lexicon ASCII-ish: NFD → bỏ Mn → **map `đ`/`Đ` → `d`
trước hoặc thay vì** `replace("?", "d")` trên chuỗi đã mất đ. Lexicon lưu dạng
đã fold (không dấu) HOẶC khớp trên bản NFC có đ với cụm gốc có đ.

**Rationale**: StockAI `normalize` NFD + strip Mn rồi `replace("?","d")` — sau
khi bỏ combining marks, chữ **đ** (U+0111) không còn thành `?` nên bị mất,
“điều tra” → “ieu tra”. Không copy hàm đó.

**Alternatives**: Giữ nguyên Unicode NFC và lexicon có dấu đầy đủ — cũng OK;
chọn fold có kiểm soát để lexicon ASCII dễ chỉnh.

## R1 — Chỉ tiêu đề, không summary

**Decision**: Polarity chỉ từ `title`. Không đọc `summary` để chấm.

**Rationale**: Đo thực tế: Google News summary lặp tiêu đề; vnstock/VCI summary
null / url “n/a”. Spec FR-005.

## R2 — Bộ lọc liên quan

**Decision** (thứ tự):
1. Parse `published_at`; loại nếu null/`> as_of`/`age > lookback`
2. Chuẩn hóa title; loại rỗng
3. Khớp ticker (word boundary) hoặc tên công ty / alias từ `news_aliases.yaml`
4. Loại chứng quyền (regex cấu hình: `CW`, `chứng quyền`, …)
5. Loại tiêu đề liệt kê nhiều mã (số token mã ≥ ngưỡng cấu hình)
6. Nếu ticker ∈ `ambiguous_tickers`: yêu cầu thêm finance keyword hoặc company
   name match (không chỉ token mã)
7. Khử trùng theo title đã chuẩn hóa

**Rationale**: Spec FR-005/006; tránh hard-code FPT (đưa ngoại lệ vào aliases
nếu cần sau).

## R3 — Ambiguous seed + scan proposal

**Decision**: Config chỉ `CEO`, `HCM`, `VND`, `AAA`. Scan đề xuất (exclude
vnstock/VCI; chỉ Google News trong lookback; ≥8 GN; ≥30% thiếu finance kw)
chỉ in danh sách — không ghi config. DRC không vào seed (false-positive cũ).

**Rationale**: Quyết định người dùng 2026-10-13.

## R4 — Công thức S

**Decision**:
```
weight_i = exp(-ln(2) * age_i / half_life_days)
weighted_polarity = sum(w_i * p_i) / sum(w_i)   # trên tin directional
confidence = min(1, n_dir/12, coverage/0.35)
S = clamp(50 + 35 * weighted_polarity * confidence, 0, 100)
```
Ready khi: không synthetic; `as_of` hợp lệ; `n_relevant >= min_relevant_news`
(8); `n_directional >= min_directional_news` (4).

Defaults: `lookback_days=30`, `half_life_days=14`. Smoke đo thêm lookback=60
không đổi default.

**Rationale**: Spec Assumptions; half-life 14 theo yêu cầu smoke; StockAI dùng
10 — tham số hóa.

## R5 — Status / flags / evidence

**Decision**:
- Ready + score số → `status=ok`
- Không ready → `status=partial`, `score=null`, flag `m5_insufficient_news`
  (alias nội bộ có thể giữ `m5_insufficient_news_for_score` nhưng smoke đếm
  prefix `m5_insufficient_news`)
- Evidence: 1 câu tổng hợp + tối đa 6 tiêu đề mạnh kèm `news_id`
- `llm_enabled: false`; không gọi mạng

**Rationale**: Anti-pattern StockAI `status=partial` luôn; FR-009/010.

## R6 — Config files

**Decision**:
- `config/sentiment.yaml` — thresholds, ambiguous list, S coeffs, llm flag
- `config/sentiment_lexicon.yaml` — positive/negative phrases
- `config/news_aliases.yaml` — company aliases, finance keywords, CW patterns
- `fixtures/m5_gold_labels.csv` — columns ticker,title,label (label trống)

**Rationale**: User scope; tách lexicon/aliases để chỉnh không đụng thresholds.

## R7 — TDD + smoke

**Decision**: Fail-first tests trên stub; implement; full pytest; smoke script
in histogram S, ok/partial, null, off-topic filtered, insufficient_news @30
và @60.

**Rationale**: Spec US3 / SC-006/007.
