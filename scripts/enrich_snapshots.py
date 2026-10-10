"""Bổ sung BCTC từ vnfinancialdata vào snapshot ĐÃ CÓ (không cào lại vnstock). Chỉ N2 sửa.
  pip install vnfinancialdata
  python scripts/enrich_snapshots.py --as-of 2026-10-08                  # VN30 trong data/snapshots
  python scripts/enrich_snapshots.py --dir data/snapshots_ext --as-of 2026-10-08
Đối chiếu khoản mục (cờ vnf_mismatch/vnf_crosscheck_ok), điền khoản mục thiếu, kéo dài lịch sử năm tới 10 năm.
Chạy lại an toàn: chỉ thêm năm/khoản mục còn thiếu, cờ vnf_* được ghi mới."""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import yaml  # noqa: E402

from stockai.contracts.schemas import validate  # noqa: E402
from stockai.m1_data import vnf_source  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--dir", default="data/snapshots")
ap.add_argument("--as-of", required=True)
ap.add_argument("--tickers", help="HPG,VCB,... (bỏ trống = tất cả snapshot trong thư mục)")
a = ap.parse_args()
cfg = yaml.safe_load(Path("config/data_sources.yaml").read_text(encoding="utf-8"))
only = {t.strip().upper() for t in a.tickers.split(",")} if a.tickers else None
vnf = vnf_source.Vnf()
bad = 0
for p in sorted(Path(a.dir).glob(f"*_{a.as_of}.json")):
    if p.name.startswith("_"):
        continue
    snap = json.loads(p.read_text(encoding="utf-8"))
    t = snap["meta"]["ticker"]
    if only and t not in only:
        continue
    snap["meta"]["flags"] = [x for x in snap["meta"]["flags"] if not x.startswith("vnf_")]
    st = vnf_source.apply(snap, cfg, vnf)
    errs = validate(snap, "snapshot")
    if errs:
        bad += 1
        print(f"{t:<5} KHÔNG GHI (schema lỗi): {errs[:2]}")
        continue
    p.write_text(json.dumps(snap, ensure_ascii=False, indent=1), encoding="utf-8")
    vf = [x for x in snap["meta"]["flags"] if x.startswith("vnf_")]
    print(f"{t:<5} +{st['added_years']} năm | điền {st['filled']} khoản mục | lệch {st['mismatch']} | {'; '.join(vf)[:110]}")
print("xong" + (f", {bad} snapshot lỗi schema" if bad else ""))
