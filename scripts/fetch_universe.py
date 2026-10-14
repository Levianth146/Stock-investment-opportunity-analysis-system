"""Cào cả universe. Xem docstring src/stockai/m1_data/universe.py.

  python scripts/fetch_universe.py --as-of 2026-10-08                            # VN30 -> data/snapshots
  python scripts/fetch_universe.py --universe VN100 --as-of 2026-10-08           # đợt 1 -> data/snapshots_ext (dùng lại VN30)
  python scripts/fetch_universe.py --universe HOSE --shard 1/4 --no-news         # chạy lô 1/4 (4 máy chạy 4 lô)
  python scripts/fetch_universe.py --universe HOSE --peers-only                  # sau khi gộp snapshot các lô: gán peers + chất lượng
  python scripts/fetch_universe.py --tickers-file config/my_list.txt             # danh sách tự điền
Universe khác VN30 ghi vào data/snapshots_ext và cache data/raw_ext (đều bị .gitignore, KHÔNG commit).
Ước tính: ~11 request/mã x 3.5 giây ≈ 40 giây/mã (thêm tin Google News nếu bật). Chạy nền, ngắt được, chạy lại sẽ tiếp tục."""
from __future__ import annotations

import argparse
import sys
from collections import Counter
from datetime import date
from pathlib import Path

# Windows redirect cp1252: tránh UnicodeEncodeError (A7 / FR-014)
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import yaml  # noqa: E402

from stockai.m1_data.fetch import (  # noqa: E402
    backfill_quarterly,
    fast_mode_enabled,
    refresh_financials_from_raw,
    refresh_news_prices,
    run_deep_fetch,
)
from stockai.m1_data.universe import fetch_all, fill_peers_dir, load_universe, read_tickers_file  # noqa: E402


def compute_wide(*, universe: str, tickers_file: str | None) -> bool:
    """Wide khi universe ≠ VN30 hoặc có --tickers-file. --tickers đơn không làm wide."""
    return universe.upper() != "VN30" or bool(tickers_file)


def validate_deep_backfill_args(
    *,
    deep: bool,
    backfill: bool,
    has_tickers: bool,
    wide: bool,
) -> str | None:
    """Trả thông báo lỗi tiếng Việt nếu FR-001 vi phạm; None nếu OK. Caller `sys.exit(2)`."""
    if deep and backfill:
        return (
            "Lỗi: không dùng --deep cùng --backfill-quarterly. "
            "Chạy riêng: --deep (lấy đủ mã chọn) hoặc --backfill-quarterly (chỉ bổ sung quý)."
        )
    if deep and not has_tickers:
        return (
            "Lỗi: --deep cần --tickers hoặc --tickers-file (không deep cả universe). "
            "Ví dụ: --deep --tickers HPG --universe VN100 --as-of YYYY-MM-DD"
        )
    if deep and not wide:
        return (
            "Lỗi: --deep chỉ hợp lệ ở chế độ rộng (wide): dùng --tickers-file, "
            "hoặc --tickers kèm --universe khác VN30. "
            "VN30 thuần không hỗ trợ --deep."
        )
    return None


def apply_cli_cfg(
    cfg: dict,
    *,
    universe: str,
    tickers: list[str] | None,
    tickers_file: str | None,
    no_news: bool = False,
    no_google: bool = False,
) -> tuple[bool, str]:
    """Gắn cascade / universe_name / news flags. Trả (wide, out_tag)."""
    wide = compute_wide(universe=universe, tickers_file=tickers_file)
    cfg["use_icb_peer_cascade"] = wide
    if wide:
        cfg["cache_dir"] = "data/raw_ext"
        cfg.setdefault("universe_max_peers", 15)
    if no_news:
        cfg["news_enabled"] = False
    if no_google:
        cfg["_no_google"] = True
        cfg["news_google"] = False
    if tickers or tickers_file:
        cfg["universe_name"] = "custom"
        tag = "custom"
    else:
        cfg["universe_name"] = universe.upper()
        tag = universe.lower()
    return wide, tag


def build_parser() -> argparse.ArgumentParser:
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
    ap.add_argument("--no-google", action="store_true", help="tắt Google News lần chạy này (không sửa yaml)")
    ap.add_argument("--limit", type=int, help="chỉ chạy N mã đầu (thử nghiệm)")
    ap.add_argument("--out-dir")
    ap.add_argument("--peers-only", action="store_true", help="không cào, chỉ gán peers và bậc chất lượng cho snapshot đã có trong out-dir")
    ap.add_argument("--refresh-news-prices", action="store_true", help="chỉ làm mới giá/chỉ số/tin trên snapshot đã có")
    ap.add_argument("--in-place", action="store_true", help="cho phép ghi đè thư mục nguồn khi refresh / backfill")
    ap.add_argument("--deep", action="store_true", help="lấy đủ dữ liệu cho mã chọn (wide + tickers/file); tắt early-exit/bỏ quý")
    ap.add_argument(
        "--backfill-quarterly", action="store_true",
        help="chỉ bổ sung BCTC quý (3 lệnh/mã) vào snapshot thiếu quý; mutual exclusive với --deep",
    )
    ap.add_argument(
        "--from-raw",
        action="store_true",
        help="chỉ dựng snapshot từ data/raw* (.pkl) đã có — không gọi mạng; thiếu cache → lỗi mã đó",
    )
    return ap


def main(argv: list[str] | None = None) -> None:
    a = build_parser().parse_args(argv)
    cfg = yaml.safe_load(Path("config/data_sources.yaml").read_text(encoding="utf-8"))
    tickers_arg = [t.strip().upper() for t in a.tickers.split(",") if t.strip()] if a.tickers else None
    wide, tag = apply_cli_cfg(
        cfg,
        universe=a.universe,
        tickers=tickers_arg,
        tickers_file=a.tickers_file,
        no_news=a.no_news,
        no_google=a.no_google,
    )
    out_dir = a.out_dir or ("data/snapshots_ext" if wide else "data/snapshots")
    if tickers_arg:
        tickers = tickers_arg
    elif a.tickers_file:
        tickers = read_tickers_file(a.tickers_file)
    else:
        tickers = load_universe(cfg, a.universe, a.refresh_universe)
    if a.limit:
        tickers = tickers[: a.limit]

    err = validate_deep_backfill_args(
        deep=bool(a.deep),
        backfill=bool(a.backfill_quarterly),
        has_tickers=bool(tickers_arg or a.tickers_file),
        wide=wide,
    )
    if err:
        print(err, file=sys.stderr)
        sys.exit(2)

    if a.from_raw:
        cfg["from_raw"] = True
        cfg["vnf_enabled"] = False  # offline: không tải Hugging Face
        cfg.setdefault("news_enabled", False)
        # Làm mới BCTC từ raw trên snapshot đã có (giữ prices/news/peers)
        in_dir = out_dir
        print(
            f"from-raw: refresh financials {len(tickers)} mã | in={in_dir} -> {out_dir} "
            f"(cache={cfg.get('cache_dir')})",
            flush=True,
        )
        res = refresh_financials_from_raw(
            tickers, a.as_of, cfg, in_dir=in_dir, out_dir=out_dir,
        )
        print("\n=== TÓM TẮT FROM-RAW ===")
        ok = sum(1 for r in res.values() if r.get("status") == "ok")
        div_n = sum(1 for r in res.values() if r.get("dividends_paid"))
        skip = sum(1 for r in res.values() if r.get("status") == "skipped_no_raw")
        err = sum(1 for r in res.values() if r.get("status") == "error")
        print(f"ok={ok} (có dividends_paid={div_n}) skipped_no_raw={skip} error={err}", flush=True)
        return

    if a.deep:
        cfg["_deep"] = True
        print(
            f"deep: {len(tickers)} mã -> {out_dir} (không gán peers; sau đó chạy --peers-only)",
            flush=True,
        )
        res = run_deep_fetch(tickers, a.as_of, cfg, out_dir=out_dir)
        print("\n=== TÓM TẮT DEEP ===")
        for t, r in res.items():
            print(f"{t:<5} {r.get('status', '')} {r.get('quality', '')} {r.get('error', '')}")
        print("Nhắc: gán peers bằng --peers-only sau khi deep xong.", flush=True)
        return

    if a.backfill_quarterly:
        in_dir = out_dir
        dest = out_dir
        if a.shard:
            i, n = (int(x) for x in a.shard.split("/"))
            assert 1 <= i <= n, "--shard phải dạng i/n với 1 <= i <= n"
            tickers = tickers[i - 1::n]
        res = backfill_quarterly(
            tickers, a.as_of, cfg, in_dir=in_dir, out_dir=dest, in_place=a.in_place,
        )
        print("\n=== TÓM TẮT BACKFILL QUARTERLY ===")
        for t, r in res.items():
            print(f"{t:<5} {r.get('status', '')} {r.get('error', '')}")
        return

    if a.refresh_news_prices:
        in_dir = out_dir
        dest = out_dir
        res = refresh_news_prices(
            tickers, a.as_of, cfg, in_dir=in_dir, out_dir=dest, in_place=a.in_place,
        )
        print("\n=== TÓM TẮT REFRESH ===")
        for t, r in res.items():
            print(f"{t:<5} {r.get('status', '')} {r.get('error', '')}")
        return

    if a.peers_only:
        res = fill_peers_dir(tickers, a.as_of, out_dir, cfg)
    else:
        suffix = ""
        if a.shard:
            i, n = (int(x) for x in a.shard.split("/"))
            assert 1 <= i <= n, "--shard phải dạng i/n với 1 <= i <= n"
            tickers = tickers[i - 1::n]
            suffix = f"_shard{i}of{n}"
        print(f"{len(tickers)} mã ({a.universe}) -> {out_dir} | fast_mode_enabled={fast_mode_enabled(cfg)}")
        reuse = ["data/snapshots"] if wide else []
        res = fetch_all(
            tickers, a.as_of, cfg, out_dir=out_dir, force=a.force, reuse_dirs=reuse,
            resume=a.resume or wide, peers=not a.shard,
            summary_name=f"_summary_{tag}_{a.as_of}{suffix}.json" if wide else None,
        )

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


if __name__ == "__main__":
    main()
