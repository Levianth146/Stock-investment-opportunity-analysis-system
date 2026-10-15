"""Đồng bộ company.shares_outstanding trong snapshot với issue_share của hồ sơ công ty.

Vì sao: snapshot suy số CP từ lợi nhuận/EPS báo cáo (cũ hơn các đợt phát hành thêm/CP thưởng),
trong khi giá đã theo số CP mới → EPS & BVPS bị tính cao, P/E, P/B trông rẻ giả.
Chỉ sửa khi lệch > --tol (mặc định 5%). Mặc định dry-run; --apply để ghi (có backup).

  python scripts/build_company_profiles.py      # nếu chưa có profiles.json
  python scripts/sync_shares_from_profile.py            # xem
  python scripts/sync_shares_from_profile.py --apply
  python scripts/build_m4_sector_stats.py       # sau khi apply
"""
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FLAG = "shares_synced_from_profile"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default="data/snapshots_ext")
    ap.add_argument("--asof", default=None)
    ap.add_argument("--tol", type=float, default=0.05)
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()
    prof = json.loads((ROOT / "data/company_profiles/profiles.json").read_text(encoding="utf-8"))
    d = ROOT / a.dir
    files = sorted(d.glob(f"*_{a.asof}.json" if a.asof else "*_*.json"))
    newest: dict[str, Path] = {}
    for f in files:
        sym = f.name.split("_")[0]
        if sym.startswith("_") or sym not in prof:
            continue
        newest[sym] = f  # sorted → ngày mới nhất cuối
    bak = d.parent / (d.name + "_bak_shares")
    n = 0
    for sym, f in sorted(newest.items()):
        ref = prof[sym].get("issue_share")
        snap = json.loads(f.read_text(encoding="utf-8"))
        cur = (snap.get("company") or {}).get("shares_outstanding")
        if not ref or not cur or abs(cur / float(ref) - 1) <= a.tol:
            continue
        n += 1
        print(f"{sym}: {cur/1e6:,.1f}M → {float(ref)/1e6:,.1f}M ({cur/float(ref):.2f}×)")
        if a.apply:
            bak.mkdir(exist_ok=True)
            shutil.copy2(f, bak / f.name)
            snap["company"]["shares_outstanding"] = float(ref)
            flags = snap.setdefault("meta", {}).setdefault("flags", [])
            if FLAG not in flags:
                flags.append(FLAG)
            f.write_text(json.dumps(snap, ensure_ascii=False), encoding="utf-8")
    print(f"{'Đã sửa' if a.apply else 'Sẽ sửa'} {n} mã." + (f" Backup: {bak}" if a.apply and n else ""))


if __name__ == "__main__":
    main()
