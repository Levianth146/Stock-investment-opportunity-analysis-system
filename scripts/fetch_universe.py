"""Cào cả universe. Xem docstring src/stockai/m1_data/universe.py.

  python scripts/fetch_universe.py --as-of 2026-10-08                            # VN30 -> data/snapshots
  python scripts/fetch_universe.py --universe VN100 --as-of 2026-10-08           # đợt 1 -> data/snapshots_ext (dùng lại VN30)
  python scripts/fetch_universe.py --universe HOSE --shard 1/4 --no-news         # chạy lô 1/4 (4 máy chạy 4 lô)
  python scripts/fetch_universe.py --universe HOSE --peers-only                  # sau khi gộp snapshot các lô: gán peers + chất lượng
  python scripts/fetch_universe.py --tickers-file config/my_list.txt             # danh sách tự điền
Universe khác VN30 ghi vào data/snapshots_ext và cache data/raw_ext (đều bị .gitignore, KHÔNG commit).
Ước tính: ~11 request/mã x 3.5 giây ≈ 40 giây/mã (thêm tin Google News nếu bật). Chạy nền, ngắt được, chạy lại sẽ tiếp tục."""
import argparse
import sys
from collections import Counter
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import yaml  # noqa: E402

from stockai.m1_data.universe import fetch_all, fill_peers_dir, load_universe, read_tickers_file  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--as-of", default=date.today().isoformat())
ap.add_argument("--tickers", help="HPG,VCB,... (bỏ trống = cả universe)")
ap.add_argument("--tickers-file", help="file danh sách mã, mỗi dòng một hoặc nhiều mã")
ap.add_argument("--universe", default="VN30", help="VN30 | VN100 | HNX30 | HOSE | HNX | UPCOM | ALL")
ap.add_argument("--refresh-universe", action="store_true")
ap.add_argument("--force", action="store_true")
ap.add_argument("--resume", action="store_true", help="coi snapshot đã có (giá/BCTC ok) là xong dù tin/peers thiếu (mặc định bật với universe ngoài VN30)")
ap.add_argument("--shard", help="i/n: chỉ chạy lô thứ i trong n lô (vd 2/4), peers gán sau bằng --peers-only")
ap.add_argument("--no-news", action="store_true", help="bỏ qua tin tức (nhanh hơn nhiều; M5 sẽ thiếu dữ liệu)")
ap.add_argument("--limit", type=int, help="chỉ chạy N mã đầu (thử nghiệm)")
ap.add_argument("--out-dir")
ap.add_argument("--peers-only", action="store_true", help="không cào, chỉ gán peers và bậc chất lượng cho snapshot đã có trong out-dir")
a = ap.parse_args()

cfg = yaml.safe_load(Path("config/data_sources.yaml").read_text(encoding="utf-8"))
wide = a.universe.upper() != "VN30" or bool(a.tickers_file)
out_dir = a.out_dir or ("data/snapshots_ext" if wide else "data/snapshots")
# Cascade ICB peers chỉ khi universe ≠ VN30 (mặc định fill_peers = False)
cfg["use_icb_peer_cascade"] = wide  # True khi universe ≠ VN30 hoặc --tickers-file
if wide:
    cfg["cache_dir"] = "data/raw_ext"
    cfg.setdefault("universe_max_peers", 15)     # VN30 giữ nguyên hành vi cũ (không trần)
if a.no_news:
    cfg["news_enabled"] = False
# FR-004: portal chỉ VN30/VN100; --tickers / --tickers-file → custom (không bật portal)
if a.tickers or a.tickers_file:
    cfg["universe_name"] = "custom"
else:
    cfg["universe_name"] = a.universe.upper()
if a.tickers:
    tickers = [t.strip().upper() for t in a.tickers.split(",") if t.strip()]
elif a.tickers_file:
    tickers = read_tickers_file(a.tickers_file)
else:
    tickers = load_universe(cfg, a.universe, a.refresh_universe)
if a.limit:
    tickers = tickers[: a.limit]
tag = (a.universe if not (a.tickers or a.tickers_file) else "custom").lower()

if a.peers_only:
    res = fill_peers_dir(tickers, a.as_of, out_dir, cfg)
else:
    suffix = ""
    if a.shard:
        i, n = (int(x) for x in a.shard.split("/"))
        assert 1 <= i <= n, "--shard phải dạng i/n với 1 <= i <= n"
        tickers = tickers[i - 1::n]
        suffix = f"_shard{i}of{n}"
    print(f"{len(tickers)} mã ({a.universe}) -> {out_dir}")
    reuse = ["data/snapshots"] if wide else []
    res = fetch_all(tickers, a.as_of, cfg, out_dir=out_dir, force=a.force, reuse_dirs=reuse, resume=a.resume or wide,
                    peers=not a.shard, summary_name=f"_summary_{tag}_{a.as_of}{suffix}.json" if wide else None)

print("\n=== TÓM TẮT ===")
tiers = Counter(r.get("quality", "?") for r in res.values() if r.get("status") != "error")
errs = [t for t, r in res.items() if r.get("status") == "error"]
print("bậc chất lượng:", dict(tiers), "| lỗi:", len(errs), (" ".join(errs[:30]) + (" ..." if len(errs) > 30 else "")) if errs else "")
show_all = len(res) <= 60
for t, r in res.items():
    ds = r.get("data_status")
    miss = [k for k, v in (ds or {}).items() if v != "ok"]
    if show_all or r.get("status") == "error" or r.get("quality") == "insufficient":
        print(f"{t:<5} {r.get('status', ''):<18} {r.get('quality', ''):<13} {('thiếu/ít: ' + ','.join(miss)) if miss else ''} {r.get('error', '')}")
