# Quickstart: M4 Relative Valuation (008)

Validation after implementation. Offline CI first; build sector stats + batch smoke after.

## Prerequisites

- Feature dir: `specs/008-m4-relative-valuation/`
- Read [spec.md](./spec.md), [contracts/m4-relative-valuation.md](./contracts/m4-relative-valuation.md),
  [research.md](./research.md), [data-model.md](./data-model.md)
- `PYTHONPATH=src`; Python 3.10+
- Ops: snapshots under `data/snapshots_ext` (as_of 2026-10-08; full+limited ≈ 235)
- Config: `config/valuation.yaml` (created at implement)

## 1. Fail-first (before live M4)

```powershell
$env:PYTHONPATH = "src"
python -m pytest -q tests/test_m4_valuation.py tests/test_m4_sector_stats_build.py
```

Expect (trước live scoring): **failures** trên stub (`status=stub`) — TDD red.
Sau implement: cùng lệnh phải **green**. Suite liên quan: `tests/test_m4_*.py`.

## 2. Build sector stats (ops / local, before smoke)

```powershell
$env:PYTHONPATH = "src"
python scripts/build_m4_sector_stats.py --as-of 2026-10-08 --snapshots-dir data/snapshots_ext --out data/valuation_sector_stats.json
```

Expect: file JSON có `sectors` đủ cho Banks/Technology/… của 5 mã mẫu; `median_pe`/`median_pb`
sau winsorize; `universe` = full+limited.

## 3. Offline suite (after implement)

```powershell
$env:PYTHONPATH = "src"
python -m pytest -q tests/test_m4_*.py
python -m pytest -q
```

Expect: green; cover polarity rẻ→V cao, bank PB, score null≠50, as_of, stale,
EPS fallback, missing sector stats. Report total test count in completion note.

## 4. Manual five-ticker check (optional)

```powershell
$env:PYTHONPATH = "src"
python -c @"
import json
from pathlib import Path
from stockai.m4_valuation.run import run as run_m4
from stockai.contracts.schemas import validate

p = Path('data/snapshots_ext')
for t in ['VCB','FPT','HPG','VIC','SSI']:
    cands = sorted(p.glob(f'{t}_*.json')) if p.exists() else []
    if not cands:
        print(t, 'SKIP')
        continue
    snap = json.loads(cands[-1].read_text(encoding='utf-8'))
    out = run_m4(snap, {}, {})
    validate(out, 'module_out')
    print(t, out['status'], out['score'], out.get('flags', [])[:6],
          'bank' if (snap.get('company') or {}).get('is_bank') else 'nonbank')
"@
```

Expect: no exception; VCB ưu tiên PB; các mã khác lộ PE và/hoặc PB trong metrics khi đủ dữ liệu.

## 5. Smoke batch ~235 full+limited (ops / SC-007)

```powershell
$env:PYTHONPATH = "src"
python scripts/smoke_m4_batch.py --as-of 2026-10-08
```

Lọc `quality_tier_full`/`limited`, gọi M4, in histogram V, đếm ok/partial/null,
đếm bank PB primary + sector_fallback, top10/bottom10. Dán bảng vào báo cáo hoàn thành.

## Expected outcomes checklist

| Check | Pass criteria |
|-------|----------------|
| Fail-first đỏ trên stub | pre-implement |
| Sector stats JSON build được | sectors + medians |
| pytest M4 + full suite xanh | count reported |
| Polarity: rẻ hơn → V cao hơn | fixture tay |
| Bank: PB primary dù PE fail | VCB / fixture bank |
| Missing → `score is None` (không 50) | flags thiếu |
| Không dùng date/published_at > as_of | fixture lookahead |
| Stale >7d → `m4_stale_price_data` | vẫn chấm nếu đủ (default) |
| Smoke ~235 không crash hàng loạt | distribution printed |
| Diff không đụng M1/contracts/M3/M5/M6/pipeline | review |

## Non-goals (this feature)

- Không sửa M1, contracts, M3, M5, M6, M7, pipeline, `docs/CONTRACTS.md`
- Không bật DCF (`enable_dcf: false`)
- Không commit / push trừ khi người dùng yêu cầu sau
