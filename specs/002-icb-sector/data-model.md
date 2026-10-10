# Data Model: ICB Sector Enrichment (002)

## Entities

### IcbSectorMap (config)

File: `config/icb_sector_map.yaml`

| Field | Type | Notes |
|-------|------|-------|
| `listing_csv` | path | Relative to repo root |
| `min_peer_group_size` | int | Default 10 |
| `exchange_aliases` | map | e.g. HOSE→HSX, UPCOM→UpCoM |
| `supersector_to_en` | map VI→EN | L2 → `company.sector` |
| `supersector_parent_en` | map VI or EN→EN | Parent peers; **authoritative** |
| `financial_sectors` | string[] | Exactly `Banks`, `Insurance`, `Financial Services` |

**Rules**:
- Parent `Financials` MUST appear for bank/insurance/broker supersectors.
- `Real Estate` (L2) MUST map parent → `Real Estate` (not `Financials`).
- CSV column ICB L1 is **not** used to resolve parent for peers.
- Legacy `industry_to_en` MAY remain for display/debug but MUST NOT drive peer parent
  if it conflicts with `supersector_parent_en`.

### ListingRow (derived, in-memory)

From `listing_icb.csv` + map:

| Field | Type | Notes |
|-------|------|-------|
| `ticker` | str | Uppercase |
| `l2_vi` | str | Supersector VI |
| `l1_vi` | str | Industry VI (source only; not peer parent) |
| `sector_en` | str \| None | From `supersector_to_en`; None if unmapped |
| `parent_en` | str \| None | From `supersector_parent_en` |
| `exchange` | str \| None | After aliases |

### CompanySectorState (on snapshot)

| Field | Location | Rules |
|-------|----------|-------|
| `sector` | `company.sector` | Non-empty EN from vnstock **or** ICB fill; else `""` (never JSON null) |
| `exchange` | `company.exchange` | Fill/normalize from listing when empty / alias |
| flags | `meta.flags` | See [contracts/icb-sector-flags.md](./contracts/icb-sector-flags.md) |

**Fill / compare**:
1. No listing row + empty vnstock → `""` + `icb_ticker_not_found`
2. Listing row, no `sector_en` + empty vnstock → `""` + `icb_sector_unmapped`
3. Empty vnstock + mapped → set EN + `icb_sector_filled`
4. Non-empty vnstock ≠ mapped → **keep vnstock** + `icb_sector_mismatch`
5. Non-empty vnstock + no row / unmapped → **keep vnstock** + `icb_ticker_not_found` or `icb_sector_unmapped`

### PeerAssignment (universe)

| Field | Notes |
|-------|-------|
| `peers[]` | Same-universe tickers with multiples; exclude self; exclude `sector == ""` |
| `sector_small_group` | Set when left pure L2 group |
| `peers_finance_nonfinance_blocked` | Set when finance filter yields empty peer list |
| Path | **VN30 current**: legacy assign (no ICB cascade). **Wide + `icb_sector_enabled`**: cascade R3/R4 |

## Relationships

```text
listing_icb.csv ──► ListingRow ──► apply_to_company ──► company.sector / flags
                         │
                         └── parent_en (YAML) ──► resolve_peer_group ──► peers[] + flags
```

## State: peer cascade (wide universe only)

```text
same L2 in universe (size includes self)
        │
   size >= min? ──yes──► peers = L2 others (no sector_small_group)
        │ no
        ▼
 parent != sector AND |parent group| >= min?
        │ yes                    │ no
        ▼                        ▼
 peers = parent others      peers = market others
 + sector_small_group       + sector_small_group
        │                        │
        └──────────┬─────────────┘
                   ▼
         filter finance vs non-finance
                   │
            empty? ──yes──► peers=[] + peers_finance_nonfinance_blocked
                   │ no
                   ▼
              _closest(..., max_peers)
```

Special: target `sector == ""` → skip L2/parent; treat as market path + `sector_small_group`
(then finance filter by… if no sector, treat as non-finance **or** skip finance membership —
**Decision in tasks**: empty sector is non-member of financial set → only non-finance peers;
if none, blocked flag).

## Validation rules

- Snapshot with `sector == ""` MUST still pass `validate(snap, "snapshot")`.
- No Vietnamese string written to `company.sector` by ICB fill path.
- BCM, VHM, VIC, VRE never appear in `peers` of a `Banks` ticker (and reverse) under
  wide ICB cascade tests.
