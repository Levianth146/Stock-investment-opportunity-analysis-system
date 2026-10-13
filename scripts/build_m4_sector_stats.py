#!/usr/bin/env python3
"""Build data/valuation_sector_stats.json từ snapshots full+limited (offline).

Dùng cùng quy tắc PE/PB với M4 runtime (multiples.derive_multiples).
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_ROOT / "src"))

from stockai.contracts.helpers import quality_tier  # noqa: E402
from stockai.m4_valuation.config_loader import load_m4_cfg  # noqa: E402
from stockai.m4_valuation.multiples import derive_multiples  # noqa: E402
from stockai.m4_valuation.sector_stats import build_sectors_payload  # noqa: E402

_ALLOWED_TIERS = {"full", "limited"}


def _iter_snapshots(snapshots_dir: Path, as_of: str) -> list[Path]:
    """File {TICKER}_{as_of}.json trong thư mục (không đệ quy sâu test subdirs)."""
    out: list[Path] = []
    if not snapshots_dir.is_dir():
        return out
    suffix = f"_{as_of}.json"
    for p in sorted(snapshots_dir.glob(f"*{suffix}")):
        if p.name.startswith("_"):
            continue
        out.append(p)
    return out


def build(
    *,
    as_of: str,
    snapshots_dir: Path,
    out_path: Path,
    cfg: dict,
) -> dict:
    """Tính PE/PB từng mã FL, winsorize-median theo sector, ghi JSON."""
    winsor = cfg.get("winsor") or {}
    low = float(winsor.get("low_pct", 0.05))
    high = float(winsor.get("high_pct", 0.95))
    min_n = int(cfg.get("min_sector_n", 5))
    pe_max = cfg.get("pe_max_exclude")
    pe_max_f = float(pe_max) if pe_max is not None else None
    stale_d = int(cfg.get("stale_calendar_days", 7))
    stale_fin = int(cfg.get("stale_financials_days", 200))

    rows: list[dict] = []
    n_seen = 0
    n_used = 0
    for path in _iter_snapshots(snapshots_dir, as_of):
        n_seen += 1
        try:
            snap = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(snap, dict):
            continue
        tier = quality_tier(snap)
        if tier not in _ALLOWED_TIERS:
            continue
        mi = derive_multiples(
            snap,
            stale_calendar_days=stale_d,
            stale_financials_days=stale_fin,
        )
        n_used += 1
        rows.append(
            {
                "ticker": mi.ticker or path.stem.split("_")[0],
                "sector": mi.sector,
                "pe": mi.pe,
                "pb": mi.pb,
            }
        )

    payload = build_sectors_payload(
        rows,
        as_of=as_of,
        winsor_low=low,
        winsor_high=high,
        min_sector_n=min_n,
        pe_max_exclude=pe_max_f,
    )
    payload["built_at"] = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    payload["n_snapshots_seen"] = n_seen
    payload["n_universe"] = n_used

    out_path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    out_path.write_text(text, encoding="utf-8")
    return payload


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Build M4 sector valuation stats JSON")
    ap.add_argument("--as-of", required=True, help="YYYY-MM-DD")
    ap.add_argument("--snapshots-dir", default="data/snapshots_ext")
    ap.add_argument("--out", default="data/valuation_sector_stats.json")
    ap.add_argument("--config", default="config/valuation.yaml")
    args = ap.parse_args(argv)

    m4_cfg, _ = load_m4_cfg({})
    # Cho phép path config tùy chỉnh bằng cách đọc lại nếu khác default
    cfg_path = Path(args.config)
    if cfg_path.is_file() and cfg_path.resolve() != (_ROOT / "config" / "valuation.yaml").resolve():
        import yaml

        raw = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}
        from stockai.m4_valuation.config_loader import deep_merge, _DEFAULT_M4

        m4_cfg = deep_merge(_DEFAULT_M4, dict(raw.get("m4") or {}))

    snaps = Path(args.snapshots_dir)
    if not snaps.is_absolute():
        snaps = _ROOT / snaps
    out_path = Path(args.out)
    if not out_path.is_absolute():
        out_path = _ROOT / out_path

    payload = build(as_of=args.as_of, snapshots_dir=snaps, out_path=out_path, cfg=m4_cfg)
    n_sec = len((payload.get("sectors") or {}))
    print(
        f"Wrote {out_path} sectors={n_sec} universe={payload.get('n_universe')} "
        f"as_of={payload.get('as_of')}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
