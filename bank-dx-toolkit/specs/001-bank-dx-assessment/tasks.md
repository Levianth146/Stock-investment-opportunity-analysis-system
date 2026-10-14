# Tasks: 001-bank-dx-assessment

Ký hiệu: **[P]** làm song song · **[US#]** câu chuyện người dùng · ✅ đã có / đã xong · ⬜ chưa làm

Phạm vi năm: **2020–2025**. Mọi task sửa `scripts/common.py`, `02_extract_text.py`, `03_locate_evidence.py`, `04_extract_numbers.py`, hoặc `07_text_mining.py` phải kết thúc bằng:

`cd scripts && python ../tests/smoke_test.py` → `TẤT CẢ OK`.

Hợp đồng cột: `contracts/outputs.md`. Mô hình: `data-model.md`.

---

## Giai đoạn 1 — Nền tảng (đã có, offline)

- ✅ **T001** [US1] Cấu trúc repo: `scripts/common.py`, `config/banks.yaml`, `config/keywords.yaml`, `config/rubric_anchors.csv`, `config/sources.csv`
- ✅ **T002** [US1] `scripts/00_make_templates.py` (coding_sheet, manual_audit, dti_inputs, sources)
- ✅ **T003** [US1] `scripts/01_download.py` → `data/raw/`, `data/raw/manifest.csv` (robots, delay ≥ 3 s, magic byte)
- ✅ **T004** [US1] `scripts/02_extract_text.py` → `data/text/*.jsonl`, `out/extraction_report.csv`
- ✅ **T005** [US2] `scripts/03_locate_evidence.py` → `out/evidence_candidates.csv`
- ✅ **T006** [US3] `scripts/04_extract_numbers.py` (`--bctc`, `--kpi`) → `out/financial_candidates.csv`, `out/kpi_candidates.csv`
- ✅ **T007** [P] [US3] `scripts/05_app_ratings.py` → `out/app_ratings.csv`
- ✅ **T008** [P] [US3] `scripts/06_probe_web.py` → `data/web/`
- ✅ **T009** [US4] `scripts/07_text_mining.py` → `out/tm_criterion.csv`, `out/tm_pillar.csv`
- ✅ **T010** [P] [US5] `scripts/08_lda_topics.py` → `out/lda_topics.csv`
- ✅ **T011** [P] [US5] `scripts/09_phobert.py` → `out/phobert_predictions.csv` (luồng code; chưa thử trọng số PhoBERT thật)
- ✅ **T012** `tests/smoke_test.py`, `AGENTS.md`, `.cursor/rules/*`

---

## Giai đoạn 2 — Xác thực trên dữ liệu thật [US1, US3]

Làm **T021 → T023** trước khi mở rộng toàn bộ năm/ngân hàng.

- ✅ **T020** Làm rõ mục 8 spec (`/speckit.clarify`) + checklist clarify trong `checklists/requirements.md` (năm 2020–2025; L/U chuẩn ngành; 2+1 người chấm)
- ✅ **T021** [US1] Techcombank 2024: `sources.csv` đã có URL; chạy `01`→`04 --bctc --kpi` với `--bank tcb --year 2024`. Kết quả: BCTN+BCTC flag OK; 517 evidence / 24 tiêu chí; 20 financial + 83 KPI candidates. Chi tiết mục **Phát hiện**
- ✅ **T022** [US3] Nhãn EN BCTC (TCB 2024) đã có trong `04_extract_numbers.py` + ca smoke ô-mỗi-dòng (TOI/opex/equity/net_profit_parent). `software_gross_cost` vẫn đọc tay (cột bảng). Smoke: chạy lại khi đụng 04/common.
- ✅ **T023** [US3] Đối chiếu tay TOI/CIR/ROE tcb 2024 (± 0,1%, SC-02): TOI=46,990,397 (=IX+VIII, diff 0); CIR=32.708%; ROE parent=15.612%. Đã điền `out/dti_inputs.csv` (14 biến có số + 2 để trống: digital_customers, tech_staff). Chi tiết **Phát hiện**.
- ✅ **T026** [P theo NH] [US1] Điền đủ `config/sources.csv` cho 5 NH × **2020–2025**: BCTN + BCTC bắt buộc; BCPTBV link riêng hoặc `notes` ∈ {`tích hợp trong BCTN`, `không công bố`, `chưa tìm thấy`}; không dán trùng PDF; mỗi dòng thiếu `url` phải có `notes` — **2026-10-08**: 23 dòng BCPTBV thiếu url đã gắn notes (agribank/mb/tcb/vcb → `tích hợp trong BCTN`; bidv 2020–22 → `chưa tìm thấy`); các năm đã có url SR giữ nguyên.
- ⬜ **T024** [P theo NH] [US1] Pipeline 01→04 + `12_appendix` đã chạy cho 5 NH (có URL). Còn mở: OCR tệp `CẦN KIỂM`; VCB BCTN vài năm `robots.txt`; đo thời gian NFR-03. BCPTBV notes → xem T026. Chi tiết **Phát hiện**
- ✅ **T025** [P] [US3] Cập nhật `config/banks.yaml` (apple_id / play_id): `scripts/05_app_ratings.py --discover` rồi `--collect` → `out/app_ratings.csv` — **2026-10-08**: đã điền 5 NH; thu rating ngày 2026-10-08 (xem Phát hiện)
- ⬜ **T027** [P] [US1] Cập nhật `scripts/00_make_templates.py` (và template liên quan): cột Coding đủ `coder1`, `coder2`, `final`, `evidence_ref`; tạo mẫu trống `out/adjudication_log.csv` theo `contracts/outputs.md`

---

## Giai đoạn 3 — Phương án cũ đã ngừng áp dụng (chấm tay/kappa)

Các task T030/T031/T034/T032 dưới đây là lịch sử, không còn điều kiện bắt buộc kể từ quyết định nhóm ngày 2026-10-12. Thay bằng 09c, kiểm thử thuật toán và truy vết phiên bản theo `algorithm-scoring.md`.

- ⬜ **T030** [US2] Hai người chấm độc lập ≥ 20% mẫu (tiêu chí × NH × năm) trên `out/coding_sheet.xlsx` (hoặc template từ 00); **không** để script ghi cột `final`
- ⬜ **T031** [US2] Tính Cohen's κ có trọng số trên cặp `(coder1, coder2)` **trước** hòa giải; nếu κ < 0,6 → họp thống nhất rubric (`config/rubric_anchors.csv`) rồi chấm lại mẫu
- ⬜ **T034** [US2] Hòa giải bất đồng: lệch ≥ 2 bậc hoặc thảo luận không xong → **người thứ ba** quyết `final`; ghi `out/adjudication_log.csv` (criterion, bank, year, score_coder1, score_coder2, score_final, adjudicator, reason, resolved_at)
- ⬜ **T032** [US2] Chấm đủ 24 tiêu chí × 5 NH × **6 năm 2020–2025** (720 dòng trong `out/coding_sheet.xlsx`; chốt 2026-10-08); điền `final` + `evidence_ref` (trỏ `out/evidence_candidates.csv`)
- ⬜ **T033** [P] [US5] Đánh dấu cột `valid` trên `out/evidence_candidates.csv` (≥ ~30 câu/tiêu chí nếu dùng PhoBERT)

---

## Giai đoạn 4 — Điểm và độ nhạy [US6]

**Không** chạy điểm chính thức khi chưa có `config/dti_bounds.yaml` và chưa có `final` (trừ test giả ở T043).

- ⬜ **T040** [US6] Chốt L, U 11 chỉ số DTI theo chuẩn ngành; tạo `config/dti_bounds.yaml` (mỗi biến: `L`, `U`, `unit`, `direction`, `source_citation`, `rationale`) — Hiến chương V
  - 2026-10-08: đã có bản nháp `config/dti_bounds.yaml` (locked=false): 2 sourced, 3 natural/derived, 6 needs_source. Còn tìm nguồn / quyết định cho 6 chỉ số trước khi khóa.
- ⬜ **T041** [US6] Viết `scripts/10_score.py`: đọc coding + `out/dti_inputs.csv` + `config/dti_bounds.yaml` → `out/scores.csv` (pillar, dbi, dti, p, data_confidence, score_total, maturity_level, rank). Thiếu DTI → P_k = DBI_k; P_6 = DBI_6; không điền 0 cho thiếu số; **không** ghi `final` vào coding_sheet
- ⬜ **T042** [US6] Viết `scripts/11_sensitivity.py` → `out/sensitivity.csv`: kịch bản 100/0, 80/20, 70/30, 60/40; Dirichlet MC trọng số trụ; Kendall τ, Spearman; `rank_stable_pct` (≥ 80% = vững)
- ⬜ **T043** [US6] Kiểm thử đơn vị cho T041/T042 (2 NH giả, số tay) trong `tests/` (file mới hoặc mở rộng smoke nếu phù hợp); công thức khớp `data-model.md`

---

## Giai đoạn 5 — Đối chiếu và xuất [US4, US5, US7]

- ⬜ **T050** [P] [US4][US5] Chạy `scripts/07_text_mining.py --compare`, `08_lda_topics.py`, `09_phobert.py`; diễn giải kèm cảnh báo n = 5. Nếu sửa 07: **bắt buộc** smoke test
- ⬜ **T051** [US7] Viết `scripts/12_appendix.py` → `out/availability_matrix.csv` + `out/evidence_appendix.csv` (hoặc xlsx): đọc `config/sources.csv` + coding; `tích hợp trong BCTN` ≠ `không công bố`
- ⬜ **T052** [US7] Cập nhật báo cáo đề tài (docx) bằng `out/scores.csv`, `out/sensitivity.csv`, ma trận sẵn có dữ liệu

---

## Thứ tự gợi ý (critical path)

```
T020 ✅ → T021 → T022(+smoke) → T023
                ↘ T026 [P] → T024 → T025 [P]
09c thuật toán → kiểm thử/quét bằng chứng → coding_auto.xlsx; T033 chỉ khi dùng PhoBERT phụ trợ
T040 → T041 → T042 → T043 → T051 → T052
T050 [P] sau khi có final (hoặc chạy TM không --compare sớm hơn)
```

---

## Phát hiện khi chạy dữ liệu thật

(mẫu: `YYYY-MM-DD | bank | file | vấn đề | sửa ở đâu`)

- `2026-10-07 | tcb | 2024_bctn/bctc/bcptbv.pdf | T021 chạy xong: download ok; BCTN 132tr OK junk=0.0106 lang=en; BCTC 91tr OK junk=0.0089 lang=en; BCPTBV 15tr NGHI LỖI FONT junk=0.067 lang=en | OCR tùy chọn cho BCPTBV (T024); cân nhắc thêm link bản VI nếu chấm bằng từ khóa Việt`
- `2026-10-07 | tcb | 02_extract_text.py | Windows cp1252 crash khi print flag tiếng Việt | đã sửa stdout UTF-8 + smoke OK`
- `2026-10-07 | — | tests/smoke_test.py | subprocess text=True decode cp1252 → NoneType | đã đọc bytes + decode utf-8; smoke TẤT CẢ OK`
- `2026-10-07 | tcb | 2024_bctc.pdf | financial_candidates thiếu biến cho TOI/CIR/ROE đầy đủ: có total_assets, opex, net_interest_income, net_profit, deposits/CASA; chưa thấy op_profit_before_provision / equity / software_gross_cost | T022 bổ sung nhãn EN trong 04/common; T023 đối chiếu tay`
- `2026-10-07 | tcb | evidence_candidates.csv | 517 đoạn, đủ 24 tiêu chí (PDF là bản EN) | OK cho pilot; khi mở rộng ưu tiên nguồn VI nếu có`
- `2026-10-07 | tcb | 2024_bctc.pdf | T023: TOI=46,990,397 (=IX 31,620,662 + VIII 15,369,735, diff 0); CIR=32.708%; ROE parent=15.612% (LNST CĐ mẹ 21,522,928 / avg equity parent 137,859,193.5). software_gross_cost Cost=6,514,231 (p50). CASA BCTC Current accounts/deposits=35.94% vs BCTN ratio 40.9% (khác phạm vi). digital_customers & tech_staff: không công bố → để trống + note | dti_inputs đã điền`
- `2026-10-07 | agribank | 01_download | T024: 12/12 BCTN+BCTC 2020–2025 tải ok; 6 BCPTBV thiếu url/notes | tiếp 02–04`
- `2026-10-07 | 5NH | T024 pipeline | 01 ok (trừ VCB BCTN 2020–23+2025 + BCPTBV 2024: robots.txt); 02/03/04 chạy; evidence 6673 / financial 182 / kpi 1148. Nhiều BCTC (agribank/mb/bidv/vcb) flag CẦN KIỂM / avg_chars≈0 → cần OCR. 12_appendix → availability_matrix.csv (tcb 2024 data_conf=0.875)`
- `2026-10-08 | — | extraction_report.csv | 12_appendix ParserError: header cũ 11 cột, dòng mới 12 (thêm bad_pages) — không phải dấu phẩy trong flag | 02: chuẩn hóa REPORT_COLS khi ghi; 12: rd_extraction_report + rd fallback engine=python`
- `2026-10-08 | — | tests/smoke_test.py | copytree mang cả data/raw PDF thật → 02 --force treo ~12 phút | ignore data/out; smoke TẤT CẢ OK (~10s); 12_appendix OK (tcb2024 data_conf=0.875)`
- `2026-10-08 | 5NH | dti_inputs.csv | Điền BCTC ưu tiên 2020/2023/2025 (+ một phần 2021/22/24): 244/480 ô có số. Fin ưu tiên ~8–9/10/NH (thiếu phổ biến: software_gross_cost đọc tay cột bảng; vài CASA/equity OCR). KPI hầu hết trống + note not_disclosed (không đoán). Giữ nguyên tcb2024 manual-t023. Helper: scripts/_fill_dti_inputs.py, _patch_dti_manual.py | tiếp: OCR/đối chiếu software + vá 2021/22/24 còn thiếu (đặc biệt vcb)`
- `2026-10-08 | 5NH | 03_locate_evidence.py | Chạy lại toàn bộ → evidence_candidates.csv **7260** đoạn; 24/24 tiêu chí có hit. VCB BCTN 2020–23+2025 trước thiếu text (PDF đã có trong raw) → đã chạy `02 --bank vcb --type bctn` rồi 03 lại. Coverage tiêu chí/NH-năm: tcb/bidv/mb cao (thường 17–24/24); agribank 8–20/24; vcb sau extract ~15–22/24 | chưa sửa 04/common → chưa smoke`
- `2026-10-08 | 5NH | 13_check_dti + 14_triage_dti | Trước triage: 40 cảnh báo / 37 ô nghi / 244 ô có số. `--apply`: xóa 28 KPI heuristic; 202 auto→auto-unverified; gắn CẦN KIỂM. Sau sửa PDF+confirm: còn **27 cảnh báo / 26 ô nghi** (nhiều CHEO_NAM lệch nhỏ / false positive). Backup: `out/dti_inputs.backup_*.csv` | tiếp đối chiếu ô còn lại nếu cần`
- `2026-10-08 | mb/agribank/bidv/vcb/tcb | dti_inputs sửa tay | Ưu tiên: mb2024 total_assets 1.128.801.062; mb fee/opex 2020–21; agribank CASA 2021–25; bidv2021 net_profit attributable; vcb2022 CASA 402.103.803; tcb2023 net_profit parent. Xóa bidv2024 CASA (placements). Điền FIN 2020/23/25 + software TCB/BIDV/Agri/MB; KPI BCTN ~27 ô năm ưu tiên. Ô có số ~267/480 | còn thiếu: nhiều KPI 2021/22/24; VCB OCR; software VCB; CASA bidv2020/24/25; mb CASA`
- `2026-10-08 | 5NH | banks.yaml + 05_app_ratings | discover→apple/play id chính chủ; collect 2026-10-08: Agribank 3.800; MB 4.746; TCB 4.758; BIDV 3.968; VCB 3.817 (gộp trọng số). Điểm chỉ đúng ngày thu | T025 ✅`
- `2026-10-08 | sources.csv | T026 BCPTBV | 23 dòng thiếu url: notes ∈ {tích hợp trong BCTN, chưa tìm thấy}; không dùng «không công bố» lần này (BIDV 2020–22 = chưa tìm thấy) | T026 ✅`
- `2026-10-08 | dti_inputs | Sửa 9 ô PDF + dọn auto-unverified + KPI 2023/2025 | (1) mb22 fee=4.135.568; mb25 CASA=not_disclosed; agri22 opex=27.554.481; tcb22/21/25 net_profit=parent; mb23 software=3.020.072 (BCTC24 p59); vcb25 fee giữ+note giảm; agri TGKH 20/21/22 từ CĐKT. (2) auto-unverified 160→0 (confirm nam; sửa agri20 CASA=150.572.893). (3) KPI 2023+2025: 34/60 ô có số (prio 17/40); tech_staff hầu hết not_disclosed. 13_check: 22 cảnh báo (CHEO_NAM false-positive agri TGKH / tcb PAT). Ô có số ~281/480 | tiếp: tech_staff; KPI năm khác; cải thiện CHEO_NAM second_col`
- `2026-10-08 | Bước B sample15 seed1 | 15 ô range-checked: **14 khớp / 1 sai**. Sai: mb2022 opex nhầm CP HĐ DV 10.108.188 → TỔNG CHI PHÍ HĐ **14.815.628** (p13). agribank2021 equity giá trị đúng (parent 74.920.400); p90 là CĐKT nợ/VSH (OCR), front p7–9 ảnh trống — không phải bảng rủi ro. Confirm nam: 15 ô. MB chỉ 1 lỗi → không mở rộng sample 30`
- `2026-10-08 | sources.csv BCPTBV | Kiểm tay BCTN: Agri 2022 có mục PTBV (p60+); VCB 2020 «TỔNG QUAN PTBV»; VCB 2021 Chương 5 PTBV → **giữ tích hợp**. Agri 2020–2021 không có mục PTBV riêng → notes **chưa tìm thấy**. Matrix sync`
- `2026-10-08 | vcb 2024_bcptbv | 02 extract OK (61tr, junk=0.0039); 03 → evidence cập nhật. Matrix bcptbv: đã tải chưa trích → **OK**`
- `2026-10-08 | CẦN KIỂM | tcb2024 bcptbv: EN readable, junk cao do chữ cách cover — **không cần OCR**. bidv2025 bcptbv/bctn: EN chủ đạo, bad_pages chủ yếu trang ngắn/bìa — nội dung đọc được, OCR tùy chọn. bidv2025 bctc đã OCR trước (OK có OCR)`
- `2026-10-08 | software_gross_cost | Agri 2020/21/22/24 điền từ TM TSCĐ VH (2024 = BCTC riêng). VCB mọi năm: BCTC không tách cột Phần mềm (chỉ Bản quyền/bằng sáng chế) → để trống + note, không đoán`
- `2026-10-08 | tech_staff + KPI định nghĩa | tech_staff 2023+2025: tìm BCTN — chỉ mb2025 có ~2500 (approx); còn lại not_disclosed. D: xóa mb2025 digital_customers (trùng total 35M); xóa bidv2025 digital_txn_share 78% (định nghĩa SP số hóa → note). approx: vcb2023 headcount, bidv2025 training, mb2025 tech_staff. Đơn vị giờ/người: bidv2023=98,70h; mb2025=82,91h — đã đối chiếu nguồn`
- `2026-10-08 | dti_inputs Bước 2–7 | (2) Sửa+confirm nam: tcb2020 total_customers **8.4M** (p27; 5M là mốc lịch sử); mb2024 NII giữ **41.152.219** (BCTC24; BCTC25 comparative 41.162.219 lệch ~10k); agri2021 total_assets **1.694.320.049** (BCTC22 p8 — OCR từng đọc nhầm 1.604…); mb2021 equity **62.486.023** (tổng VCSH gồm NCI). (3) training: MB 30/43/35/70.73; BIDV 16.2/87.12/59; VCB2024=36.1; TCB20–23 not_collected; Agri+VCB20–22 not_disclosed. (4) digital: Agri 6.6M/14.5M/16M (+total 20.17M/20M); TCB22 e-banking 6.2M + total 10.8M; TCB21 total 9.6M. (5) tech_staff: TCB22 “531” = certified ≠ tổng NS; còn lại not_disclosed. (6) FIN 2021/22/24 ưu tiên: op_profit/fee/deposits đủ 30/30; software MB21–22 + BIDV21/22/24. (7) headcount MB21/22/24, TCB21/22, VCB20/24, BIDV24; digital_txn MB21/22/24. Ô có số **338/480**. Helper `_patch_step2/_steps345/_digital_tech/_fin_kpi/_step7.py` | còn: nhiều digital/total/headcount/txn 2021–24; tech_staff; software VCB; Agri training`
- `2026-10-08 | dti_inputs Bước 2→6 (ảnh) | (a) tcb2022 digital_customers def **active→registered** (p35 6.2M e-banking + p8 registered Mobile); bidv2021–23 training **days_x6h giữ**. (b) mb2023 digital_customer_share=**86%** (BCTN p9 digital platforms; note app); tcb2024 digital_customers **not_disclosed**. (c) NCI+equity→parent: Agri 2020/23/25 (+22/24 comparative), BIDV2022, MB2020–25 (MB2021 parent **59.574.235**=62.486.023−2.911.788), VCB2020/21/23 (+2022 comparative); ô đã parent không đụng. (d) headcount BIDV20–22; software MB2020=1.169.487 / BIDV2020=1.654.829; bidv2021–22 digital_txn 66.9%/75.9% + total_customers 2022. (e) bidv2024 training **giữ 59** (note biểu đồ 87); vcb2023 training **giữ 41** (note BCPTBV2024=35). Ô có số **~378/540**; still not_collected ~68 (chủ yếu digital_customer_share + digital_customers + FIN TODO). Helper `_patch_steps2to6.py` | còn: share/KH số nhiều năm; FIN CASA/NII/opex; TCB training 20–23`
- `2026-10-08 | dti_inputs Bước 3→5 | (3) 8 ô rủi ro cao: mb2020 nci **giữ 2.152.881** (BCTC20; restated 2.192.991 ghi note); mb2021 nci **2.911.788** (BCTC22 p11, không 2.911.188); agri2021 nci **1.166.940** p90 đúng CĐKT; agri2020 headcount **~40k** giữ approx; bidv HC 26.752/27.223/28.435; bidv2022 total **15.5M lower_bound**. (4) `--confirm` 8 ô --by nam. (5) Điền: vcb HC 21.670/22.599; agri HC 40.909/42.278 (+2021 not_disclosed); agri txn 91%/96% (BCTN24 p30); bidv total 11.9M/22.5M (+2021 not_disclosed); VCB total+txn 20–22/24 + agri20–21 txn + agri24 total + bidv24 txn → not_disclosed. Ô có số **389/540**. Helper `_patch_steps345.py` | còn: MB total_customers 20–22/24; TCB digital_txn 20–22; digital_customer_share nhiều năm`
- `2026-10-08 | dti_inputs Bước 1→3 (FIN+sample+KPI) | (1) Điền **16 ô FIN** hợp nhất năm nay, confirmed_by=nam: VCB21 TA/NII/opex/NP_parent; VCB22 NII/opex; VCB24 TA/NII/opex; BIDV22 NII/opex/NP_parent; MB22 TA; MB21/22/24 CASA KKH (TM22). (2) `15_relabel --sample 15 --seed 1`: **14 khớp / 1 sai** — vcb2020 net_profit PAT 18.472.518 → parent **18.451.311**; confirm nam cả 15 → coi range-checked còn lại tin cậy (1 lỗi có hệ thống PAT≠parent). (3) TCB training: 71/not_disclosed/70/82 (2020–23); digital_txn: not_disclosed/81%/86% (2020–22, phạm vi GD chuyển tiền trong nước). MB total_customers: 6.0M/12.9M/20.0M/30.2M (2020/21/22/24; def cumulative/total). digital_customer_share + digital_customers còn lại **giữ not_collected**. Không sửa common/02–04/07 → không smoke | còn: ~29 share + ~22 digital_customers + tech_staff/software/CASA bidv…`
- `2026-10-08 | dti_inputs Bước 1→3 (net_profit parent) | (1) 9 ô net_profit → LN cổ đông mẹ (hoặc giữ nếu chỉ 1 dòng PAT): agri21/24 **giữ** 11.611.119 / 21.884.431; mb21–24 **12.697.075 / 17.482.735 / 20.676.788 / 22.633.757**; bidv24/25 **25.140.037 / 29.904.264**; vcb22 **29.899.014**. `14_triage --apply --confirm` 9 ô --by nam → **OK**. (2) definition TCB: digital_txn 2021/22=`remit_domestic`; training 2020/22/23=`avg_hours`. (3) mb2025 total_assets **giữ** 1.615.763.927 (CĐKT p10 đúng; BCTN p65: +43% do tín dụng +37%, không M&A). Không đụng common/02–04/07 → không smoke`
- `2026-10-08 | dti_inputs Bước 1→2 (net_profit còn sai) | (1) vcb2024 **33.853.117→33.831.386** (XV cổ đông NH, bỏ PAT); vcb2025 **35.197.940→35.177.663**; mb2020 **8.606.039→8.262.659** (LN ròng, bỏ PAT). `14_triage --apply --confirm` 3 ô --by nam → **OK** (3 ô được nam xác nhận). (2) tcb2020 net_profit **khớp** 12.324.991 (Bank shareholders; PAT 12.582.467) — chỉ sửa note; bidv2023 **giữ** 21.504.918, note bỏ «giữ tạm» → cổ đông mẹ bỏ PAT 21.977.141. Không đụng common/02–04/07 → không smoke`
- `2026-10-08 | dti_inputs 16 ô opex/op_profit | Đối chiếu PDF (TCB native text; BIDV/MB/VCB OCR `data/text`): **16/16 khớp** — không sửa value. opex=Total operating expenses / CHI PHÍ HĐ (không CP DV/CP lãi); op_profit=Net profit before provision (không trước thuế). Restatement ghi nhận (không lỗi): TCB2023 prior opex 13.023.129 ≠ TCB2022 cell 13.398.018; BIDV2025 prior opex 27.979.504 ≠ BIDV2024 27.966.817. `14_triage --apply --confirm` 16 ô --by nam → **OK** (16 ô được nam). Không đụng common/02–04/07 → không smoke`
