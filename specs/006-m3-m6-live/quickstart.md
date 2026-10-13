# Quickstart: M3 + M6 Live (006)

Validation after implementation. Offline CI first; batch smoke after.

## Prerequisites

- Feature branch / docs dir: `specs/006-m3-m6-live/`
- Read [spec.md](./spec.md), [contracts/m3-m6-live.md](./contracts/m3-m6-live.md),
  [research.md](./research.md) (Q1:B polarity)
- `PYTHONPATH=src`; Python 3.10+
- Optional ops: snapshots under `data/snapshots_ext` (full+limited HOSE+HNX)

## 1. Fail-first (before port)

```powershell
$env:PYTHONPATH = "src"
python -m pytest -q tests/test_m3_technical.py tests/test_m6_risk.py
```

Expect: **failures** on stub (`status=stub`) — proves TDD red.

## 2. Offline suite (after port)

```powershell
$env:PYTHONPATH = "src"
python -m pytest -q tests/test_m3_*.py tests/test_m6_*.py
python -m pytest -q
```

Expect: green; cover SC-001…006 offline (history, as_of, OHLC, stale, align,
beta≈1, polarity-lock). Report total test count in completion note.

## 3. Manual single-ticker check (optional)

```powershell
$env:PYTHONPATH = "src"
python -c @"
import json
from pathlib import Path
from stockai.m3_technical.run import run as run_m3
from stockai.m6_risk.run import run as run_m6

p = Path('data/snapshots_ext')
cands = sorted(p.glob('HPG_*.json')) if p.exists() else []
if not cands:
    print('SKIP: no HPG snapshot')
else:
    snap = json.loads(cands[-1].read_text(encoding='utf-8'))
    t = run_m3(snap, {}, {})
    r = run_m6(snap, {}, {})
    print('T', t['status'], t['score'], t['flags'][:5])
    print('R', r['status'], r['score'], r['flags'][:5])
"@
```

Expect: no exception; if enough history/align → numeric scores; R polarity
documented high=risk.

## 4. Smoke batch ~235 full+limited (ops / SC-007)

```powershell
$env:PYTHONPATH = "src"
python scripts/smoke_m3_m6_batch.py
```

Script lọc `quality_tier_full` / `quality_tier_limited` dưới `data/snapshots_ext`
(hoặc `snapshots_ext_nonews` nếu thiếu); gọi M3+M6; in histogram T/R, đếm
ok/partial, score null. Kết quả mẫu: `COMPLETION_NOTE.md`.
Báo cáo MUST nêu: M6 khớp CONTRACTS (R cao = rủi ro cao) và liệt kê phần scoring
StockAI đã đảo (subscores + weights).

## Expected outcomes checklist

| Check | Pass |
|-------|------|
| Fail-first đỏ trên stub | x (pre-port) |
| pytest offline M3/M6 + full suite xanh | x (176 passed) |
| M3: ≥200 → score; `<200` → null + flag | x |
| M3: không dùng date > as_of; OHLC lỗi có cờ+đếm | x |
| M3: stale >7d → `m3_stale_price_data` | x |
| M6: no forward-fill; beta≈1 trên chuỗi trùng | x |
| M6: eligible → `status=ok` + score; else null | x |
| Polarity-lock: high-risk R > stable; flip fails | x |
| Diff scope: no m1_data / pipeline / contracts / CONTRACTS / M7 | x |
| Smoke 235: no mass crash; distributions pasted | x (see COMPLETION_NOTE.md) |
| Completion note lists inverted StockAI scoring parts | x |

## Non-goals for this quickstart

- Không implement trong pass plan.
- Không commit / push.
- Không sửa M7 hay `docs/CONTRACTS.md`.
