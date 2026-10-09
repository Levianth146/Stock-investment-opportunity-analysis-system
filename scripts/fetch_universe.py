"""Cào cả universe (mặc định VN30). Xem docstring src/stockai/m1_data/universe.py.
  python scripts/fetch_universe.py --as-of 2026-10-09
  python scripts/fetch_universe.py --tickers HPG,VCB --force
Ước tính: ~11 request/mã x 3.5 giây ≈ 40 giây/mã -> VN30 khoảng 20 phút. Chạy nền, ngắt được, chạy lại sẽ tiếp tục."""
import argparse
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import yaml  # noqa: E402

from stockai.m1_data.universe import fetch_all, load_universe  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--as-of", default=date.today().isoformat())
ap.add_argument("--tickers", help="HPG,VCB,... (bỏ trống = cả VN30)")
ap.add_argument("--universe", default="VN30")
ap.add_argument("--refresh-universe", action="store_true")
ap.add_argument("--force", action="store_true")
a = ap.parse_args()
cfg = yaml.safe_load(Path("config/data_sources.yaml").read_text(encoding="utf-8"))
tickers = [t.strip().upper() for t in a.tickers.split(",")] if a.tickers else load_universe(cfg, a.universe, a.refresh_universe)
print(f"{len(tickers)} mã: {' '.join(tickers)}")
res = fetch_all(tickers, a.as_of, cfg, force=a.force)
print("\n=== TÓM TẮT ===")
for t, r in res.items():
    ds = r.get("data_status")
    miss = [k for k, v in (ds or {}).items() if v != "ok"]
    print(f"{t:<5} {r['status']:<18} {('thiếu/ít: ' + ','.join(miss)) if miss else ''} {r.get('error', '')}")
