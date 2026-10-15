# Hợp đồng đầu ra (cột bắt buộc, UTF-8-BOM)

## Đầu vào cấu hình
| Tệp | Cột / khóa bắt buộc |
|---|---|
| `config/sources.csv` | bank, year, doc_type, url, notes. Khi `url` trống: `notes` ∈ {`tích hợp trong BCTN`, `không công bố`, `chưa tìm thấy`}. Phạm vi năm: 2020–2025. |
| `config/dti_bounds.yaml` | mỗi biến DTI: `L`, `U`, `unit`, `direction`, `source_citation`, `rationale`. Chốt trước khi chạy 10. |
| `config/banks.yaml` | bank_id, tên, site, app ids / search |
| `config/keywords.yaml` | 24 tiêu chí + từ khóa |
| `config/rubric_anchors.csv` | mã tiêu chí × mức 0–4 mô tả |

## Pipeline hiện có
| Tệp | Cột bắt buộc |
|---|---|
| `data/raw/manifest.csv` | bank, year, doc_type, url, file, sha256, bytes, accessed_at, status |
| `data/text/<bank>_<year>_<type>.jsonl` | bank, year, doc_type, page, engine, junk, text |
| `out/extraction_report.csv` | file, bank, year, doc_type, pages, pages_ocr, avg_chars, avg_junk, engines_used, flag |
| `out/evidence_candidates.csv` | criterion, bank, year, doc_type, page, keyword, snippet, read_priority(1-5) [, valid] |
| `out/financial_candidates.csv` | bank, year, page, variable, raw_line (+dòng kế), parsed_numbers(first4), n_numbers, where_to_check |
| `out/kpi_candidates.csv` | bank, year, doc_type, page, variable, numbers_found, sentence |
| `out/tm_criterion.csv` | bank, year, criterion, pillar, bm25, raw_hits, coverage, quantified_ratio, words |
| `out/tm_pillar.csv` | bank, year, pillar, bm25_0_100, coverage_0_100 |
| `out/lda_topics.csv` | topic, share_of_text, stability, assigned_pillar, top_terms |
| `out/phobert_predictions.csv` | bank, year, page, criterion, p_criterion, accepted, sentence |
| `out/dti_inputs.csv` | bank, year, variable, value, unit, source_file, page, confirmed_by, note |
| `out/app_ratings.csv` | date, bank, store, app_id, title, rating, rating_count, version, note |

## Chấm thuật toán (FR-13, quyết định 2026-10-12)
| Tệp | Cột bắt buộc |
|---|---|
| `out/auto_scores.csv` | criterion, bank, year, auto_score, status, evidence_file, evidence_page, evidence_quote, supporting_evidence, scoring_method, rules_version, rules_hash |
| `out/coding_auto.xlsx` | các cột auto_scores + final (0–4 hoặc trống), criterion_name, notes; đầu vào mặc định bước 10 |
| `out/auto_scoring_manifest.json` | scoring_method, rules_version, rules_hash, context, bộ lọc, input_hashes, missing_policy |
| `out/coding_sheet.xlsx` | bảng chấm tay cũ, chỉ lưu trữ; không ghi đè hoặc lấy làm mặc định |

## Điểm, độ nhạy, phụ lục (kế hoạch — scripts 10–12)
| Tệp | Cột bắt buộc |
|---|---|
| `out/scores.csv` | bank, year, pillar, dbi, dti, p, data_confidence, score_total, maturity_level, rank |
| `out/sensitivity.csv` | scenario, bank, year, score, rank, kendall_tau, spearman, rank_stable_pct |
| `out/availability_matrix.csv` | bank, year, item, status (`có dữ liệu` \| `tích hợp trong BCTN` \| `không công bố` \| `chưa tìm thấy`) |
| `out/evidence_appendix.csv` (hoặc sheet trong xlsx) | criterion, bank, year, final, evidence_ref, page, snippet |

## Quy tắc chung
- Mọi tệp ứng viên / số liệu phải có cột lần ngược nguồn (file hoặc doc_type + page + đoạn trích khi có).
- Ô thiếu dữ liệu: để trống, không ghi `0` thay cho “không công bố”.
- `tích hợp trong BCTN` trong ma trận **không** đếm vào thiếu ESG.
- Encoding: `utf-8-sig` cho CSV mở bằng Excel tiếng Việt.
