# Quickstart: M5 Sentiment Live

## Prerequisites

- Python 3.10+, `PYTHONPATH=src` (hoặc `python -m pytest` từ root như CI)
- Snapshot fixtures dựng tay trong tests; smoke cần `data/snapshots_ext/*.json`
- Không cần mạng / LLM / API key

## Offline tests (TDD)

```powershell
# Fail-first trên stub (trước implement):
python -m pytest -q tests/test_m5_sentiment.py

# Sau implement — full suite:
python -m pytest -q
```

Kỳ vọng sau implement: toàn bộ pass; test M5 phủ đủ tin / thiếu tin / future /
điều tra (giữ đ) / duplicate / CW / ambiguous seed / validate module_out.

## Single-ticker dry run

```powershell
$env:PYTHONPATH='src'
python -c @"
from stockai.m5_sentiment.run import run
import json
snap=json.load(open('data/snapshots_ext/HPG_2026-10-08.json',encoding='utf-8'))
out=run(snap, {}, {})
print(out['status'], out['score'], out['flags'][:5])
"@
```

## Smoke ~235 full+limited

```powershell
python scripts/smoke_m5_batch.py
```

In: crashes, ok/partial, S histogram, top10/bottom10 (+2 headlines),
off-topic filtered, `m5_insufficient_news` count với lookback **30** và **60**
(half-life=14). Default config lookback giữ **30**.

## Ambiguous proposal scan (không ghi config)

```powershell
python scripts/_scan_ambiguous_m5.py
```

Chỉ in danh sách đề xuất theo quy tắc corrected; config chỉ giữ seed đã duyệt.

## Scope check

```powershell
git diff --stat --ignore-space-at-eol
```

Chỉ `m5_sentiment/`, `tests/test_m5_*`, config sentiment*, gold CSV, optional smoke.
Không commit/push trừ khi user yêu cầu.
