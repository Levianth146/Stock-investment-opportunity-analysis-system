# Quickstart: M7 Debate LLM (009)

Validation guide after implementation. Offline CI first; live provider smoke +
batch ≥10 tickers only when keys present (ops — not CI).

## Prerequisites

- Feature dir: `specs/009-m7-debate-llm/`
- Read [spec.md](./spec.md), [contracts/m7-debate-llm.md](./contracts/m7-debate-llm.md),
  [research.md](./research.md), [data-model.md](./data-model.md)
- `PYTHONPATH=src`; Python 3.10+
- Config: `config/llm.yaml` (gemini/glm models, order, cache_dir, prompt_version)
- Secrets (ops only): `GEMINI_API_KEY`, `ZAI_API_KEY` in env or local `.env`
  (gitignored) — never commit or print
- Cache dir: `data/llm_cache/` (gitignored)
- Implement deliverable: one line in `docs/CONTRACTS.md` for `refs` convention;
  `schemas.py` unchanged

## 1. Fail-first (before live debate)

```powershell
$env:PYTHONPATH = "src"
python -m pytest -q tests/test_m7_debate.py tests/test_llm_generate.py tests/test_m8_run.py -k "debate or refs or ungrounded"
```

Expect (trước implement đủ): **failures** trên stub thiếu `refs` / chưa có
`debate_ungrounded` — TDD red. Sau implement: cùng scope **green**.

## 2. Offline suite (after implement)

```powershell
$env:PYTHONPATH = "src"
python -m pytest -q tests/test_m7_debate*.py tests/test_llm_*.py tests/test_m8_*.py
python -m pytest -q
```

Expect:

- Mock `requests` only; không cần khóa env
- 2–4 bull/bear; `refs` regex + resolve
- Retry → template fallback không crash
- Cache hit → 0 HTTP
- M8: fixture ungrounded có `debate_ungrounded`; grounded không có
- Score/rating M7 không đổi so baseline scoring
- Toàn bộ pytest green offline

## 3. Manual single-ticker debate (optional, mock or live)

```powershell
$env:PYTHONPATH = "src"
python -c @"
from stockai.m7_scoring.debate import run_debate
# load snapshot + upstream fixtures locally; call run_debate; print len(bull/bear) and refs
"@
```

Expect: không exception; mỗi item có `text` + `refs`; `validate(result, "result")`
pass khi gắn vào result mẫu.

## 4. Smoke providers (ops / SC-006 — có khóa)

Chỉ khi đã set env keys. Gọi `generate_json` một lần từng provider qua
`requests` REST; thiếu khóa → ghi nhận lỗi rõ, không crash CI.

Expect: ≥1 lần JSON debate parse được **hoặc** message thiếu/invalid key rõ ràng.

## 5. Batch ≥10 tickers (ops / SC-007)

```powershell
$env:PYTHONPATH = "src"
python scripts/run_debate_batch.py --as-of 2026-10-08 --limit 10
```

Expect: không crash hàng loạt; báo cáo llm_ok / fallback / cache_hit; ≥1 mã
bull/bear khác `[stub]`.

## 6. Contract / docs check (SC-009)

- `git diff -- src/stockai/contracts/schemas.py` → empty for this feature
- `docs/CONTRACTS.md` có đúng một dòng/bullet convention `refs` (`mN.name` / `nK`)

## Out of scope for this quickstart

- Sửa scoring weights / risk_gate
- Gọi mạng trong pytest
- Commit cache hoặc `.env`
