#!/usr/bin/env python3
"""Làm mới dữ liệu hàng ngày (feature 017 + hook prefetch debate 014j).

Các bước dự kiến:
1. fetch universe / snapshots (M1)
2. build API cache + scoring
3. (tuỳ chọn) prefetch debate AI cho top N

Hiện tại: stub mỏng — gọi prefetch debate nếu ``--prefetch-debate N``.
Khi feature 017 có pipeline đầy đủ, gắn bước này sau scoring.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _parse() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Daily refresh stub (+ optional debate prefetch)")
    p.add_argument("--as-of", required=True, help="YYYY-MM-DD")
    p.add_argument("--profile", default="long_term")
    p.add_argument(
        "--prefetch-debate",
        type=int,
        default=0,
        metavar="N",
        help="Sau scoring: chạy run_debate_batch --top N (0 = bỏ qua)",
    )
    p.add_argument("--pause-sec", type=float, default=2.0)
    p.add_argument(
        "--max-live-calls",
        type=int,
        default=12,
        help="Trần HTTP LLM trong prefetch",
    )
    return p.parse_args()


def main() -> int:
    args = _parse()
    print(
        f"refresh_daily stub as_of={args.as_of} profile={args.profile} "
        f"(feature 017: thêm fetch+score khi sẵn sàng)"
    )
    if int(args.prefetch_debate or 0) <= 0:
        print("skip prefetch-debate")
        return 0
    cmd = [
        sys.executable,
        str(ROOT / "scripts" / "run_debate_batch.py"),
        "--as-of",
        args.as_of,
        "--profile",
        args.profile,
        "--top",
        str(int(args.prefetch_debate)),
        "--pause-sec",
        str(args.pause_sec),
        "--max-live-calls",
        str(args.max_live_calls),
    ]
    print("run:", " ".join(cmd))
    return int(subprocess.call(cmd, cwd=str(ROOT)))


if __name__ == "__main__":
    raise SystemExit(main())
