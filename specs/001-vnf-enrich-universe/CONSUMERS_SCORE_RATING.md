# T020 — Call sites reading M7 `score` / `rating` (2026-10-10)

No Streamlit/`app/` UI found in repo.

| Location | Tolerates `score is None` / `"Không xếp hạng"`? | Notes |
|----------|--------------------------------------------------|-------|
| `src/stockai/m7_scoring/run.py` | Yes (producer) | Emits null / Không xếp hạng |
| `src/stockai/m8_validate/run.py` | Yes | Skips formula/threshold when `quality_gate.scored is False` |
| `src/stockai/m9_report/run.py` | Yes | `_score_text` / `_rating_text` null-safe |
| `main.py` | Yes (updated this slice) | Prints `n/a` when score null |
| `tests/test_m7_quality_gate.py` | Yes | Asserts both paths |
| `tests/test_m8_run.py` | Yes | Unscored skip + tamper on scored path |
| `tests/test_pipeline_e2e.py` | Yes | DEMO scored + insufficient e2e |
| `tests/test_m7_scoring.py` | N/A | Tests `compute_score` only, not M7 result |
| Module `o.get("score")` in M8 `_check_modules` | N/A | M2–M6 module_out scores, not M7 result |

Follow-up: none required for null-safety in current tree.
