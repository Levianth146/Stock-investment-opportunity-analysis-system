# M9 reproducibility

This M9 redesign is integrated into the normal pipeline; it is not a manually assembled PDF.

## Reproduce the checked VNM report exactly
Run from repository root:

```bash
python main.py VNM --profile long_term --snapshot data/snapshots/VNM_2026-10-08.json --out reports
```

Execution order is the project's normal pipeline: M2 -> M3 -> M4 -> M5 -> M6 -> M7 -> M8 -> M9, using the frozen M1 snapshot in `data/snapshots`.

The expected PDF is:

`reports/VNM_2026-10-08_long_term.pdf`

## Run M1 live, then M2 -> M9

```bash
python main.py VNM --profile long_term --as-of 2026-10-08 --out reports
```

This calls M1 (`build_snapshot`) first and then runs M2 -> M9. Because M1 depends on external/live sources, a later live run may not be byte-for-byte identical to the frozen-snapshot report if upstream sources have changed. For exact reproducibility, use the committed snapshot command above.
