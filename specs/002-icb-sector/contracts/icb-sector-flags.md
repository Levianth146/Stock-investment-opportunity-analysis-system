# Contract: ICB sector flags & peer outcomes (M1 wire format)

**Owner**: N2 (M1). **Does not** change `src/stockai/contracts/schemas.py`.
Consumers (M2–M9) MAY read flags as opaque strings; no new required snapshot keys.

## Config keys (`config/data_sources.yaml`)

| Key | Type | Default | Meaning |
|-----|------|---------|---------|
| `icb_sector_enabled` | bool | `true` | Apply ICB fill/compare on company; wide-universe peer cascade |
| `icb_sector_map` | path \| omit | `config/icb_sector_map.yaml` | Map file |

VN30 peer **lists** MUST remain unchanged vs submitted snapshots when using the
legacy VN30 peer path (cascade ICB peers only on wide universe runs).

## `company.sector`

| Value | Meaning |
|-------|---------|
| Non-empty English string | Canonical sector (vnstock kept or ICB-filled) |
| `""` | Missing / unmapped; **not** JSON `null` |

## Flags (`meta.flags` — append, do not invent numbers)

| Flag | When |
|------|------|
| `icb_sector_filled` | Filled empty sector from ICB L2 map |
| `icb_sector_mismatch` | Kept existing sector; differs from ICB EN |
| `icb_ticker_not_found` | Ticker absent from listing CSV |
| `icb_sector_unmapped` | In CSV but Supersector missing from `supersector_to_en` |
| `icb_exchange_filled` | Filled empty exchange from listing |
| `icb_exchange_mismatch` | Existing exchange ≠ normalized ICB exchange |
| `sector_small_group` | Peer group left pure L2 (parent or market fallback) |
| `peers_finance_nonfinance_blocked` | After finance/non-finance filter, no valid peers → `peers: []` |

Existing peer flags (`peers_none_in_universe_same_sector`,
`peers_cross_sector_vn30_nonbank_fallback`, …) remain for **VN30 legacy** path;
wide ICB path MUST use `peers_finance_nonfinance_blocked` when the finance
filter empties the list (do not rely only on the older flags).

## Peer selection interface (internal)

`icb_sector.resolve_peer_group(ticker, views, listing=..., min_size=...) -> (peer_tickers, used_small_group)`

- `views[t]`: `{sector, parent, met}` within current universe
- Excludes self and any `sector == ""` from being selected as peers
- Applies cascade + finance filter per [data-model.md](../data-model.md)

## Validation

Offline tests MUST assert:

1. All VN30 mapped sectors match existing snapshot sector strings (when ICB fill
   would apply / map check).
2. Banks ↛ {BCM, VHM, VIC, VRE} as peers and reverse (wide cascade fixture).
3. Ticker missing from CSV → `sector == ""` (or kept vnstock) + flag; snapshot
   still `validate(..., "snapshot")`.
