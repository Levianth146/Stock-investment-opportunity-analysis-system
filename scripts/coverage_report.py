"""Báo cáo phủ dữ liệu / lý do không xếp hạng theo mã.

  python scripts/coverage_report.py --as-of 2026-10-08 --snap-dir data/snapshots_ext

Ghi CSV ``data/reports/coverage_<asof>.csv`` và in histogram lý do.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from stockai.contracts.helpers import quality_reasons, quality_tier  # noqa: E402

# Cột pillar / trường bắt buộc để chấm (gần với quality gate M1)
_REQUIRED_ANNUAL_KEYS = ("revenue", "net_income", "total_assets", "total_equity", "cfo")


def _pillar_presence(snap: dict) -> dict[str, bool]:
    """Ước lượng pillar có dữ liệu đầu vào (không chạy M2–M6)."""
    prices = (snap.get("prices") or {}).get("rows") or []
    ann = (snap.get("financials") or {}).get("annual") or []
    news = snap.get("news") or []
    items0 = (ann[0].get("items") if ann else {}) or {}
    has_fin = len(ann) >= 3 and any(items0.get(k) is not None for k in _REQUIRED_ANNUAL_KEYS)
    return {
        "F": has_fin,
        "T": len(prices) >= 200,
        "V": has_fin and any(items0.get(k) is not None for k in ("net_income", "total_equity")),
        "S": len(news) > 0,
        "R": len(prices) >= 60,
    }


def _missing_fields(snap: dict) -> list[str]:
    ann = (snap.get("financials") or {}).get("annual") or []
    if not ann:
        return ["annual_empty"]
    items = (ann[0].get("items") or {}) if isinstance(ann[0], dict) else {}
    miss = [k for k in _REQUIRED_ANNUAL_KEYS if items.get(k) is None]
    prices = (snap.get("prices") or {}).get("rows") or []
    if len(prices) < 750:
        miss.append("prices_lt_750")
    if len(ann) < 3:
        miss.append("annual_lt_3")
    return miss


def analyze_dir(snap_dir: Path, as_of: str) -> list[dict]:
    rows: list[dict] = []
    for fp in sorted(snap_dir.glob(f"*_{as_of}.json")):
        if fp.name.startswith("_"):
            continue
        try:
            snap = json.loads(fp.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        ticker = (snap.get("meta") or {}).get("ticker") or fp.name.split("_")[0]
        tier = quality_tier(snap) or "absent"
        reasons = quality_reasons(snap)
        pillars = _pillar_presence(snap)
        missing_pillars = [k for k, ok in pillars.items() if not ok]
        ann = (snap.get("financials") or {}).get("annual") or []
        scored = tier != "insufficient"
        primary_reason = reasons[0] if reasons else ("insufficient" if not scored else "ok")
        rows.append(
            {
                "ticker": ticker,
                "scored": scored,
                "tier": tier,
                "primary_reason": primary_reason,
                "reasons": "|".join(reasons),
                "pillars_present": "|".join(k for k, ok in pillars.items() if ok),
                "pillars_missing": "|".join(missing_pillars),
                "missing_fields": "|".join(_missing_fields(snap)),
                "n_annual": len(ann),
                "n_prices": len((snap.get("prices") or {}).get("rows") or []),
                "n_news": len(snap.get("news") or []),
            }
        )
    return rows


def main(argv: list[str] | None = None) -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    except Exception:
        pass
    ap = argparse.ArgumentParser()
    ap.add_argument("--as-of", required=True)
    ap.add_argument("--snap-dir", default="data/snapshots_ext")
    ap.add_argument("--out", default=None, help="CSV path (mặc định data/reports/coverage_<asof>.csv)")
    args = ap.parse_args(argv)

    snap_dir = Path(args.snap_dir)
    rows = analyze_dir(snap_dir, args.as_of)
    out = Path(args.out) if args.out else Path("data/reports") / f"coverage_{args.as_of}.csv"
    out.parent.mkdir(parents=True, exist_ok=True)

    fields = [
        "ticker",
        "scored",
        "tier",
        "primary_reason",
        "reasons",
        "pillars_present",
        "pillars_missing",
        "missing_fields",
        "n_annual",
        "n_prices",
        "n_news",
    ]
    with out.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in rows:
            w.writerow(r)

    scored_n = sum(1 for r in rows if r["scored"])
    unscored = [r for r in rows if not r["scored"]]
    hist = Counter()
    for r in unscored:
        rs = [x for x in str(r["reasons"]).split("|") if x]
        if not rs:
            hist["(no_reason)"] += 1
        else:
            for x in rs:
                hist[x] += 1

    print(f"as_of={args.as_of} snap_dir={snap_dir}")
    print(f"tickers={len(rows)} scored={scored_n} unranked={len(unscored)}")
    print(f"wrote {out}")
    print("=== histogram lý do (mỗi cờ quality_* trên mã unranked) ===")
    for k, v in hist.most_common():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
