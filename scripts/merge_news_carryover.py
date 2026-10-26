#!/usr/bin/env python3
"""Khôi phục tin đã mất sau một lần refresh ghi đè tin: gộp tin từ snapshot ngày cũ vào snapshot ngày mới.

  python scripts/merge_news_carryover.py --from-asof 2026-10-08 --to-asof 2026-10-15
Mặc định thư mục: snapshots_dir trong config/api.yaml. Chạy lại nhiều lần vẫn an toàn (khử trùng theo tiêu đề)."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from stockai.m1_data.fetch import merge_news  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--from-asof", required=True)
    ap.add_argument("--to-asof", required=True)
    ap.add_argument("--dir", default="data/snapshots")
    a = ap.parse_args()
    d = Path(a.dir) if Path(a.dir).is_absolute() else ROOT / a.dir
    changed = total_before = total_after = 0
    for new_path in sorted(d.glob(f"*_{a.to_asof}.json")):
        t = new_path.name[: -len(a.to_asof) - 6]
        old_path = d / f"{t}_{a.from_asof}.json"
        if not old_path.is_file():
            continue
        try:
            new = json.loads(new_path.read_text(encoding="utf-8"))
            old = json.loads(old_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        start = str((new.get("meta") or {}).get("window_start") or "0000-00-00")
        before = len(new.get("news") or [])
        merged = merge_news(old.get("news") or [], new.get("news") or [], start, a.to_asof)
        total_before += before
        total_after += len(merged)
        if len(merged) == before:
            continue
        new["news"] = merged
        flags = list((new.get("meta") or {}).get("flags") or [])
        if any(str(i.get("url") or "").startswith("http") for i in merged):
            flags = [f for f in flags if f not in ("news_url_missing", "news_has_no_article_url")]
        if any("google" in str(i.get("source") or "").lower() for i in merged) and "news_urls_partly_google_redirect" not in flags:
            flags.append("news_urls_partly_google_redirect")
        new["meta"]["flags"] = flags
        ds = (new["meta"].get("data_status") or {})
        ds["news"] = "ok" if len(merged) >= 10 else ("partial" if merged else "missing")
        new_path.write_text(json.dumps(new, ensure_ascii=False, indent=1), encoding="utf-8")
        changed += 1
    print(f"đã gộp tin cho {changed} mã; tổng tin {total_before} -> {total_after}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
