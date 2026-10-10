# Quickstart: ICB sector (002)

Offline validation after implementation (no network).

## Prerequisites

- Python 3.10+ with project deps / `PYTHONPATH=src`
- Feature files under `specs/002-icb-sector/` (this plan)
- Config: `config/icb_sector_map.yaml`, `config/listing_icb.csv`
- `use_icb_peer_cascade` defaults **False** in `fill_peers` / `fill_peers_dir`; `scripts/fetch_universe.py` sets **True** only when `--universe` ≠ `VN30`

## Run tests

```powershell
$env:PYTHONPATH = "src"
python -m pytest -q tests/test_m1_icb_sector.py tests/test_m1_universe.py tests/test_m1_build.py
python -m pytest -q
```

### Expected

- VN30 Supersector → English matches sectors on `data/snapshots/*_2026-10-08.json` (map check).
- BCM / VHM / VIC / VRE never peers of a Banks ticker (and reverse) under wide ICB cascade fixtures.
- Missing CSV ticker → `company.sector == ""` + `icb_ticker_not_found` (when no vnstock sector); snapshot passes `validate(..., "snapshot")`.
- VN30 peer-assignment regression (`use_icb_peer_cascade=False`): peer tickers match snapshots **element-wise and in order**.
- Full suite green (`python -m pytest -q`).

## Manual smoke (optional, network)

Only if you intentionally fetch:

```powershell
$env:PYTHONPATH = "src"
# Wide universe — fetch_universe bật use_icb_peer_cascade
python scripts/fetch_universe.py --universe VN100 --as-of 2026-10-08 --limit 5 --no-news
```

Do **not** use this as CI acceptance; offline tests above are the gate.

## References

- Spec: [spec.md](./spec.md)
- Plan / gaps: [plan.md](./plan.md)
- Flags: [contracts/icb-sector-flags.md](./contracts/icb-sector-flags.md)
- Data model: [data-model.md](./data-model.md)
