#!/usr/bin/env python3
"""Smoke M4 trên universe full+limited cùng as_of — offline, không mạng."""
from __future__ import annotations

import argparse
import json
import math
import sys
from collections import Counter
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_ROOT / "src"))

from stockai.contracts.helpers import quality_tier  # noqa: E402
from stockai.m4_valuation.multiples import derive_multiples  # noqa: E402
from stockai.m4_valuation.run import run as run_m4  # noqa: E402

_ALLOWED = {"full", "limited"}


def _hist_bucket(score: float | None) -> str:
    if score is None:
        return "null"
    if score < 20:
        return "0-19"
    if score < 40:
        return "20-39"
    if score < 60:
        return "40-59"
    if score < 80:
        return "60-79"
    return "80-100"


def _decile(score: float) -> int:
    """0..9; score 100 → decile 9."""
    if score >= 100:
        return 9
    return min(9, max(0, int(score // 10)))


def _old_eps_sum_quarters(snap: dict) -> float | None:
    """Công thức cũ (sai): sum items.eps 4 quý mới nhất published_at<=as_of."""
    from datetime import date

    meta = snap.get("meta") or {}
    try:
        as_of = date.fromisoformat(str(meta.get("as_of"))[:10])
    except (TypeError, ValueError):
        return None
    fins = snap.get("financials") or {}
    quarterly = fins.get("quarterly") if isinstance(fins.get("quarterly"), list) else []
    usable: list[tuple] = []
    for p in quarterly:
        if not isinstance(p, dict):
            continue
        try:
            pub = date.fromisoformat(str(p.get("published_at"))[:10])
        except (TypeError, ValueError):
            continue
        if pub > as_of:
            continue
        items = p.get("items") if isinstance(p.get("items"), dict) else {}
        try:
            eps = float(items.get("eps"))
        except (TypeError, ValueError):
            continue
        if not math.isfinite(eps):
            continue
        usable.append((pub, str(p.get("period") or ""), eps))
    if len(usable) < 4:
        return None
    usable.sort(key=lambda t: (t[0], t[1]))
    s = sum(x[2] for x in usable[-4:])
    return s if s != 0 else None


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--as-of", default="2026-10-08")
    ap.add_argument("--snapshots-dir", default="data/snapshots_ext")
    ap.add_argument("--stats", default="data/valuation_sector_stats.json")
    ap.add_argument("--top", type=int, default=10)
    args = ap.parse_args(argv)

    snaps_dir = Path(args.snapshots_dir)
    if not snaps_dir.is_absolute():
        snaps_dir = _ROOT / snaps_dir
    stats = Path(args.stats)
    if not stats.is_absolute():
        stats = _ROOT / stats

    if not snaps_dir.is_dir():
        print(f"MISSING snapshots dir: {snaps_dir}")
        return 2
    if not stats.is_file():
        print(f"MISSING sector stats: {stats}")
        return 2

    suffix = f"_{args.as_of}.json"
    paths = sorted(p for p in snaps_dir.glob(f"*{suffix}") if not p.name.startswith("_"))
    cfg = {"m4": {"sector_stats_path": str(stats)}}

    status_c: Counter[str] = Counter()
    hist: Counter[str] = Counter()
    decile_c: Counter[int] = Counter()
    fallback_n = 0
    pb_dropped_n = 0
    bank_pb_n = 0
    weight_default_n = 0
    scored: list[tuple[str, float]] = []
    null_tickers: list[str] = []
    errors: list[str] = []
    pe_deltas: list[tuple[str, float, float, float]] = []  # ticker, old_pe, new_pe, abs_delta
    sectors_seen: Counter[str] = Counter()

    for path in paths:
        try:
            snap = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as e:
            errors.append(f"{path.name}: {e}")
            continue
        if quality_tier(snap) not in _ALLOWED:
            continue
        ticker = (snap.get("meta") or {}).get("ticker") or path.stem.split("_")[0]
        sector = (snap.get("company") or {}).get("sector") or "?"
        sectors_seen[str(sector)] += 1
        try:
            out = run_m4(snap, {}, cfg)
            mi = derive_multiples(snap)
        except Exception as e:  # noqa: BLE001 — smoke báo lỗi từng mã
            errors.append(f"{ticker}: {type(e).__name__}: {e}")
            status_c["exception"] += 1
            continue
        st = out.get("status") or "?"
        status_c[st] += 1
        sc = out.get("score")
        hist[_hist_bucket(sc if isinstance(sc, (int, float)) else None)] += 1
        flags = out.get("flags") or []
        if "m4_sector_fallback" in flags:
            fallback_n += 1
        if "m4_pb_leg_dropped" in flags:
            pb_dropped_n += 1
        if "m4_sector_weight_default" in flags:
            weight_default_n += 1
        if "m4_bank_primary_pb" in flags and sc is not None:
            bank_pb_n += 1
        if sc is None:
            null_tickers.append(ticker)
            status_c["score_null"] += 1
        else:
            scored.append((ticker, float(sc)))
            decile_c[_decile(float(sc))] += 1

        # Old vs new PE (cùng giá)
        old_eps = _old_eps_sum_quarters(snap)
        price = mi.price_close
        new_pe = mi.pe
        if (
            old_eps is not None
            and old_eps > 0
            and price is not None
            and price > 0
            and new_pe is not None
            and new_pe > 0
        ):
            old_pe = price / old_eps
            pe_deltas.append((ticker, old_pe, new_pe, abs(new_pe - old_pe)))

    n_ok = status_c.get("ok", 0)
    n_partial = status_c.get("partial", 0)
    n_error = status_c.get("error", 0) + status_c.get("exception", 0)
    n_null = status_c.get("score_null", 0)
    processed = n_ok + n_partial + n_error

    print("=== M4 smoke batch ===")
    print(f"as_of={args.as_of} snapshots={snaps_dir} stats={stats.name}")
    print(f"processed={processed} ok={n_ok} partial={n_partial} error={n_error} score_null={n_null}")
    print(
        f"bank_primary_pb_scored={bank_pb_n} sector_fallback={fallback_n} "
        f"m4_pb_leg_dropped={pb_dropped_n} sector_weight_default={weight_default_n}"
    )
    print("histogram_V:")
    for k in ("null", "0-19", "20-39", "40-59", "60-79", "80-100"):
        print(f"  {k}: {hist.get(k, 0)}")

    n_scored = max(1, len(scored))
    print("score_decile (% of scored; aim ~5-15% each):")
    for d in range(10):
        n = decile_c.get(d, 0)
        pct = 100.0 * n / n_scored
        print(f"  D{d} [{d*10}-{d*10+9}]: {n} ({pct:.1f}%)")

    scored_sorted = sorted(scored, key=lambda x: x[1], reverse=True)
    top_n = max(1, int(args.top))
    print(f"top{top_n}_cheap (high V):")
    for t, s in scored_sorted[:top_n]:
        print(f"  {t}: {s}")
    print(f"bottom{top_n}_expensive (low V):")
    for t, s in scored_sorted[-top_n:][::-1]:
        print(f"  {t}: {s}")

    pe_deltas.sort(key=lambda x: x[3], reverse=True)
    print(f"pe_delta_top{top_n} (|new-old| largest; old=sum eps 4Q):")
    for t, old_pe, new_pe, delta in pe_deltas[:top_n]:
        print(f"  {t}: old_pe={old_pe:.2f} new_pe={new_pe:.2f} delta={delta:.2f}")

    print("sectors_seen:")
    for sec, n in sorted(sectors_seen.items(), key=lambda x: (-x[1], x[0])):
        print(f"  {sec}: {n}")

    if null_tickers:
        print(f"null_score_sample ({len(null_tickers)}): {', '.join(null_tickers[:20])}")
    if errors:
        print(f"errors ({len(errors)}):")
        for e in errors[:10]:
            print(f"  {e}")
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
