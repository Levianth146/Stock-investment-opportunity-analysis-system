#!/usr/bin/env python3
"""Phân bố điểm M7 trên snapshots_ext (offline, không LLM/mạng).

  python scripts/m7_score_distribution.py
  python scripts/m7_score_distribution.py --profile long_term --as-of 2026-10-08

Chạy M2–M7 (set_generate_fn raise), giữ score != None, timeout 15s/mã.
In: count, mean, std, percentiles, 5-label counts, corr F/T/V/S/R/score,
risk-gate blocked, top/bottom 10.
"""
from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from stockai.m2_fundamental.run import run as run_m2  # noqa: E402
from stockai.m3_technical.run import run as run_m3  # noqa: E402
from stockai.m4_valuation.run import run as run_m4  # noqa: E402
from stockai.m5_sentiment.run import run as run_m5  # noqa: E402
from stockai.m6_risk.run import run as run_m6  # noqa: E402
from stockai.m7_scoring.debate import set_generate_fn  # noqa: E402
from stockai.m7_scoring.run import run as run_m7  # noqa: E402
from stockai.pipeline import load_cfg  # noqa: E402

LABELS = ["Bán", "Giảm tỷ trọng", "Nắm giữ", "Mua", "Mua mạnh"]


def _percentile(sorted_vals: list[float], p: float) -> float:
    if not sorted_vals:
        return float("nan")
    if len(sorted_vals) == 1:
        return sorted_vals[0]
    k = (len(sorted_vals) - 1) * (p / 100.0)
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return sorted_vals[int(k)]
    return sorted_vals[f] * (c - k) + sorted_vals[c] * (k - f)


def _corr(xs: list[float], ys: list[float]) -> float:
    n = len(xs)
    if n < 2:
        return float("nan")
    mx = sum(xs) / n
    my = sum(ys) / n
    num = sum((a - mx) * (b - my) for a, b in zip(xs, ys))
    dx = math.sqrt(sum((a - mx) ** 2 for a in xs))
    dy = math.sqrt(sum((b - my) ** 2 for b in ys))
    if dx < 1e-12 or dy < 1e-12:
        return float("nan")
    return num / (dx * dy)


def _score_one(path: Path, profile: str, timeout_s: float) -> dict | None:
    def _work() -> dict | None:
        snap = json.loads(path.read_text(encoding="utf-8"))
        cfg = load_cfg(profile)
        cfg["out_dir"] = str(ROOT / "reports" / "_m7_dist_tmp")
        up: dict = {}
        for name, fn in (
            ("m2", run_m2),
            ("m3", run_m3),
            ("m4", run_m4),
            ("m5", run_m5),
            ("m6", run_m6),
        ):
            try:
                up[name] = fn(snap, up, cfg)
            except Exception as e:  # noqa: BLE001
                up[name] = {
                    "module": name,
                    "status": "error",
                    "score": None,
                    "metrics": {},
                    "evidence": [],
                    "flags": [f"{name}_crashed"],
                    "error": str(e)[:200],
                }
        m7 = run_m7(snap, up, cfg)
        if m7.get("score") is None:
            return None
        sc = m7.get("scores") or {}
        return {
            "ticker": m7.get("ticker") or path.stem.split("_")[0],
            "score": float(m7["score"]),
            "rating": m7.get("rating"),
            "F": sc.get("F"),
            "T": sc.get("T"),
            "V": sc.get("V"),
            "S": sc.get("S"),
            "R": sc.get("R"),
            "risk_gate": "rating_capped_by_risk_gate" in (m7.get("flags") or []),
        }

    with ThreadPoolExecutor(max_workers=1) as ex:
        fut = ex.submit(_work)
        try:
            return fut.result(timeout=timeout_s)
        except FuturesTimeout:
            return None
        except Exception:  # noqa: BLE001
            return None


def _print(s: str) -> None:
    sys.stdout.buffer.write((s + "\n").encode("utf-8", errors="replace"))
    sys.stdout.buffer.flush()


def run_profile(files: list[Path], profile: str, timeout_s: float) -> list[dict]:
    rows: list[dict] = []
    for i, path in enumerate(files, 1):
        row = _score_one(path, profile, timeout_s)
        if row is not None:
            rows.append(row)
        if i % 25 == 0 or i == len(files):
            _print(f"  [{profile}] {i}/{len(files)} scored_kept={len(rows)}")
    return rows


def summarize(rows: list[dict], profile: str) -> None:
    _print(f"\n======== {profile} (n={len(rows)}) ========")
    if not rows:
        _print("(empty)")
        return
    scores = [r["score"] for r in rows]
    scores_sorted = sorted(scores)
    mean = statistics.fmean(scores)
    std = statistics.pstdev(scores) if len(scores) > 1 else 0.0
    _print(f"count={len(scores)}  mean={mean:.4f}  std={std:.4f}")
    pcts = [5, 20, 40, 60, 80, 95]
    _print(
        "percentiles: "
        + "  ".join(f"p{p}={_percentile(scores_sorted, p):.2f}" for p in pcts)
    )
    from collections import Counter

    c = Counter(r["rating"] for r in rows)
    _print("labels: " + " / ".join(f"{lab}={c.get(lab, 0)}" for lab in LABELS))
    keys = ["F", "T", "V", "S", "R", "score"]
    _print("corr matrix (F,T,V,S,R,score):")
    header = "      " + "  ".join(f"{k:>7}" for k in keys)
    _print(header)
    full = [r for r in rows if all(r.get(k) is not None for k in keys)]
    for a in keys:
        cells = []
        for b in keys:
            xs = [float(r[a]) for r in full]
            ys = [float(r[b]) for r in full]
            cells.append(f"{_corr(xs, ys):7.3f}")
        _print(f"{a:>5} " + "  ".join(cells))
    blocked = sum(1 for r in rows if r.get("risk_gate"))
    _print(f"risk_gate_blocked={blocked}")
    ranked = sorted(rows, key=lambda r: r["score"], reverse=True)
    _print("TOP 10:")
    for r in ranked[:10]:
        _print(
            f"  {r['ticker']:6} score={r['score']:.2f} {r['rating']} "
            f"F={r['F']} T={r['T']} V={r['V']} S={r['S']} R={r['R']}"
        )
    _print("BOTTOM 10:")
    for r in ranked[-10:]:
        _print(
            f"  {r['ticker']:6} score={r['score']:.2f} {r['rating']} "
            f"F={r['F']} T={r['T']} V={r['V']} S={r['S']} R={r['R']}"
        )


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--as-of", default="2026-10-08")
    ap.add_argument("--snapshots-dir", default="data/snapshots_ext")
    ap.add_argument("--profile", choices=("long_term", "swing", "both"), default="both")
    ap.add_argument("--timeout", type=float, default=15.0)
    args = ap.parse_args(argv)

    set_generate_fn(lambda *a, **k: (_ for _ in ()).throw(RuntimeError("no LLM in m7_score_distribution")))

    snap_dir = Path(args.snapshots_dir)
    if not snap_dir.is_absolute():
        snap_dir = ROOT / snap_dir
    if not snap_dir.is_dir():
        _print(f"MISSING: {snap_dir}")
        return 2
    files = sorted(snap_dir.glob(f"*_{args.as_of}.json"))
    # bỏ thư mục con / file meta
    files = [p for p in files if p.is_file() and not p.name.startswith("_")]
    _print(f"snapshots={len(files)} dir={snap_dir} as_of={args.as_of}")

    profiles = ("long_term", "swing") if args.profile == "both" else (args.profile,)
    for profile in profiles:
        rows = run_profile(files, profile, args.timeout)
        summarize(rows, profile)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
