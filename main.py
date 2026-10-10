"""CLI. CHỈ N1 SỬA.
  python main.py DEMO --profile long_term --snapshot fixtures/snapshot_DEMO.json   # chạy từ snapshot có sẵn
  python main.py HPG  --profile swing --as-of 2026-10-09                           # M1 tự lấy dữ liệu rồi chạy
"""
import argparse
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

from stockai.m1_data.fetch import build_snapshot, load_snapshot, save_snapshot  # noqa: E402
from stockai.pipeline import analyze, load_cfg, status_table  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("ticker")
    ap.add_argument("--profile", choices=["long_term", "swing"], default="long_term")
    ap.add_argument("--as-of", default=date.today().isoformat())
    ap.add_argument("--snapshot", help="đường dẫn snapshot JSON có sẵn (bỏ qua bước cào dữ liệu)")
    ap.add_argument("--out", default="reports")
    a = ap.parse_args()
    snap = load_snapshot(a.snapshot) if a.snapshot else build_snapshot(a.ticker, a.as_of, load_cfg(a.profile))
    if not a.snapshot:
        print("snapshot saved:", save_snapshot(snap))
    up = analyze(snap, a.profile, a.out)
    print(f"{snap['meta']['ticker']} as_of={snap['meta']['as_of']} profile={a.profile}")
    print(status_table(up))
    r = up["m7"]
    sc = r.get("score")
    score_s = "n/a" if sc is None else f"{sc:.1f}"
    rating_s = str(r.get("rating") or "").encode("ascii", "replace").decode()
    print(f"Score={score_s}  Rating={rating_s}")
    qg = r.get("quality_gate") or {}
    if qg:
        print(f"quality_gate={qg.get('tier')} scored={qg.get('scored')} reasons={qg.get('reasons')}")
    print("PDF:", up["m9"].get("pdf_path"))


if __name__ == "__main__":
    main()
