#!/usr/bin/env python3
"""Quét snapshot → CSV năm cổ tức bất thường (feature 014j F5)."""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from stockai.api.financials import dividends_implausible  # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--as-of", required=True)
    p.add_argument("--snapshots-dir", default=str(ROOT / "data" / "snapshots_ext"))
    p.add_argument(
        "--out",
        default="",
        help="Mặc định data/reports/dividend_anomalies_<asof>.csv",
    )
    args = p.parse_args()
    snap_dir = Path(args.snapshots_dir)
    out = Path(args.out) if args.out else ROOT / "data" / "reports" / f"dividend_anomalies_{args.as_of}.csv"
    out.parent.mkdir(parents=True, exist_ok=True)

    rows: list[dict] = []
    for fp in sorted(snap_dir.glob(f"*_{args.as_of}.json")):
        if fp.name.startswith("_"):
            continue
        ticker = fp.name.split("_")[0].upper()
        try:
            snap = json.loads(fp.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        fin = snap.get("financials") if isinstance(snap.get("financials"), dict) else {}
        for period in fin.get("annual") or []:
            if not isinstance(period, dict):
                continue
            items = period.get("items") if isinstance(period.get("items"), dict) else {}
            div = items.get("dividends_paid")
            nip = items.get("net_income_parent")
            if nip is None:
                nip = items.get("net_income")
            if not dividends_implausible(div, nip):
                continue
            rows.append(
                {
                    "ticker": ticker,
                    "year": period.get("period"),
                    "div": div,
                    "NI": nip,
                }
            )

    with out.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["ticker", "year", "div", "NI"])
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {out} rows={len(rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
