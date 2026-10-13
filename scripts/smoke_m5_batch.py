"""Smoke M5 trên ~235 mã quality_tier full+limited — local, không commit.

Dùng DEFAULT mới (lookback=60, min_relevant=3, min_directional=2).
In: crashes, ok/partial, S histogram, top10/bottom10 (+2 headlines),
insufficient count, 36 tiêu đề mẫu có hướng.
"""
from __future__ import annotations

import json
import random
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from stockai.m5_sentiment.run import classify_title, run  # noqa: E402

SNAP_DIR = ROOT / "data" / "snapshots_ext"


def _tier(snap: dict) -> str | None:
    for f in (snap.get("meta") or {}).get("flags") or []:
        if isinstance(f, str) and f.startswith("quality_tier_"):
            return f.replace("quality_tier_", "")
    return None


def _headlines(out: dict, n: int = 2) -> list[str]:
    texts = []
    for e in out.get("evidence") or []:
        if e.get("news_id") and e.get("text"):
            texts.append(str(e["text"])[:160])
        if len(texts) >= n:
            break
    return texts


def run_batch() -> dict:
    """Chạy với cfg mặc định từ sentiment.yaml (lookback 60, …)."""
    files = sorted(SNAP_DIR.glob("*.json"))
    status_c: Counter[str] = Counter()
    insuff = 0
    crashes = 0
    scores: list[tuple[str, float, dict]] = []
    null_score = 0
    offtopic_total = 0
    sample_pool: list[tuple[str, str, float]] = []

    for path in files:
        try:
            snap = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            crashes += 1
            continue
        tier = _tier(snap)
        if tier not in ("full", "limited"):
            continue
        ticker = str((snap.get("meta") or {}).get("ticker") or path.name.split("_")[0])
        try:
            out = run(snap, {}, {})
        except Exception as exc:  # noqa: BLE001
            crashes += 1
            print(f"CRASH {ticker}: {exc}")
            continue
        st = out.get("status") or "?"
        status_c[st] += 1
        flags = out.get("flags") or []
        if any(str(f).startswith("m5_insufficient_news") for f in flags):
            insuff += 1
        sc = out.get("score")
        if sc is None:
            null_score += 1
        else:
            scores.append((ticker, float(sc), out))
        m = out.get("metrics") or {}
        offtopic_total += int((m.get("news_offtopic_excluded") or {}).get("value") or 0)

        # Gom mẫu tiêu đề có hướng
        for art in (snap.get("news") or [])[:20]:
            if not isinstance(art, dict):
                continue
            title = str(art.get("title") or "")
            if not title:
                continue
            pol, _, _ = classify_title(
                title, ticker, source=str(art.get("source") or "")
            )
            if pol != 0:
                sample_pool.append((ticker, title, pol))

    return {
        "n": sum(status_c.values()),
        "crashes": crashes,
        "status": dict(status_c),
        "null_score": null_score,
        "insufficient_news": insuff,
        "offtopic_total": offtopic_total,
        "scores": scores,
        "sample_pool": sample_pool,
    }


def _hist(scores: list[float], bins: list[int] | None = None) -> dict[str, int]:
    bins = bins or [0, 20, 40, 50, 60, 80, 100]
    labels = []
    for i in range(len(bins) - 1):
        labels.append(f"[{bins[i]},{bins[i+1]})")
    labels.append(f"[{bins[-1]},]")
    c: Counter[str] = Counter()
    for s in scores:
        placed = False
        for i in range(len(bins) - 1):
            if bins[i] <= s < bins[i + 1]:
                c[labels[i]] += 1
                placed = True
                break
        if not placed:
            c[labels[-1]] += 1
    return dict(c)


def main() -> None:
    if not SNAP_DIR.is_dir():
        print("MISSING", SNAP_DIR)
        sys.exit(1)

    # Windows console (cp1252) không in được tiêu đề tiếng Việt.
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    except Exception:
        pass

    print("=== Smoke M5 defaults (lookback=60 half_life=14 min_rel=3 min_dir=2) ===")
    r = run_batch()
    vals = [s for _, s, _ in r["scores"]]
    print(
        f"n={r['n']} crashes={r['crashes']} status={r['status']} "
        f"null_score={r['null_score']} insufficient_news={r['insufficient_news']} "
        f"offtopic_excluded_sum={r['offtopic_total']}"
    )
    print("S histogram:", _hist(vals))
    ranked = sorted(r["scores"], key=lambda x: x[1], reverse=True)
    print("--- TOP 10 ---")
    for t, sc, out in ranked[:10]:
        print(f"  {t:5} S={sc:6.2f} | " + " || ".join(_headlines(out)))
    print("--- BOTTOM 10 ---")
    for t, sc, out in ranked[-10:]:
        print(f"  {t:5} S={sc:6.2f} | " + " || ".join(_headlines(out)))

    print("\n=== 36 random scored titles (user review) ===")
    pool = r["sample_pool"]
    random.seed(7)
    sample = pool if len(pool) <= 36 else random.sample(pool, 36)
    for i, (t, title, pol) in enumerate(sample, 1):
        direction = "tích cực" if pol > 0 else "tiêu cực"
        print(f"{i:2}. [{t}] {direction} ({pol:+.2f}) | {title[:120]}")


if __name__ == "__main__":
    main()
