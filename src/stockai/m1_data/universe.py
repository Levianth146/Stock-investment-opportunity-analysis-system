"""Chạy M1 cho cả universe (VN30, VN100, HOSE, HNX, UpCom, ALL). Chỉ N2 sửa.

  python scripts/fetch_universe.py --as-of 2026-10-08                          # VN30
  python scripts/fetch_universe.py --universe VN100 --as-of 2026-10-08         # đợt 1: VN30 dùng lại, chỉ cào phần còn lại
  python scripts/fetch_universe.py --tickers HPG,VCB,VNM                       # danh sách tự chọn
Mỗi mã 1 file data/snapshots[_ext]/<MÃ>_<as_of>.json, lưu ngay khi xong (ngắt giữa chừng vẫn giữ phần đã chạy).
Peers = các mã CÙNG NGÀNH trong universe (tối đa max_peers mã có vốn hóa gần nhất), PE/PB/ROE tự tính từ snapshot
tại as_of (point-in-time, không tốn thêm request). Mỗi snapshot được gắn bậc chất lượng (quality.py).

Hạn chế (ghi vào báo cáo): danh sách thành viên là hiện hành tại thời điểm lấy, KHÔNG phải thành phần tại từng ngày
lịch sử (survivorship bias: mã đã hủy niêm yết không có trong danh sách)."""
from __future__ import annotations

import json
import math
import re
import time
from datetime import datetime
from pathlib import Path

import yaml

from stockai.m1_data import fetch as f
from stockai.m1_data import icb_sector
from stockai.m1_data import normalize as nz
from stockai.m1_data import quality

UNIVERSE_FILE = "config/universe.yaml"          # VN30; universe khác: config/universe_<tên>.yaml
EXCHANGES = {"HOSE": {"HOSE", "HSX"}, "HNX": {"HNX"}, "UPCOM": {"UPCOM"}}
STOCK_RE = re.compile(r"^[A-Z][A-Z0-9]{2}$")     # cổ phiếu 3 ký tự; loại ETF/CW/trái phiếu (ký tự dài hơn)


def universe_path(name: str) -> Path:
    return Path(UNIVERSE_FILE) if name.upper() == "VN30" else Path(UNIVERSE_FILE).with_name(f"universe_{name.lower()}.yaml")


def _from_exchange(listing, wanted: set[str]) -> list[str]:
    df = listing.symbols_by_exchange()
    cols = {c.lower(): c for c in df.columns}
    sym, exch = cols.get("symbol"), cols.get("exchange") or cols.get("board")
    if not sym or not exch:
        return []
    typ = cols.get("type") or cols.get("product_grp_id")
    out = []
    for _, r in df.iterrows():
        t = str(r[sym]).strip().upper()
        if str(r[exch]).strip().upper() not in wanted or not STOCK_RE.match(t):
            continue
        if typ and str(r[typ]).strip().upper() not in ("STOCK", "STO", "S", "NAN", "NONE", ""):
            continue
        out.append(t)
    return sorted(set(out))


def _from_vnstock(cfg: dict, name: str) -> list[str]:
    """Lấy danh sách từ vnstock: nhóm chỉ số (VN30, VN100, HNX30 ...) hoặc sàn (HOSE, HNX, UPCOM, ALL). Lỗi -> []."""
    try:
        from vnstock import Listing
    except Exception:  # noqa: BLE001
        return []
    key = name.upper()
    for src in cfg.get("vnstock_sources", ["VCI"]):
        try:
            lst = Listing(source=src)
            if key in EXCHANGES or key == "ALL":
                wanted = set().union(*EXCHANGES.values()) if key == "ALL" else EXCHANGES[key]
                got = _from_exchange(lst, wanted)
            else:
                res = lst.symbols_by_group(name)
                got = sorted({str(x).strip().upper() for x in (res["symbol"] if hasattr(res, "columns") else res)})
            if got:
                return got
        except Exception:  # noqa: BLE001
            continue
    return []


def load_universe(cfg: dict, name: str = "VN30", refresh: bool = False) -> list[str]:
    """Đọc file universe của `name`; chưa có (hoặc --refresh-universe) thì lấy từ vnstock rồi lưu lại để cả nhóm dùng CHUNG một danh sách."""
    p = universe_path(name)
    if p.exists() and not refresh:
        data = yaml.safe_load(p.read_text(encoding="utf-8"))
        if data.get("name") == name and data.get("tickers"):
            return list(data["tickers"])
    tickers = _from_vnstock(cfg, name)
    if not tickers:
        if p.exists():
            data = yaml.safe_load(p.read_text(encoding="utf-8"))
            if data.get("name") == name and data.get("tickers"):
                print(f"[universe] vnstock không trả danh sách {name}, dùng {p} có sẵn")
                return list(data["tickers"])
        raise RuntimeError(f"Không lấy được danh sách {name}; điền tay vào {p} theo mẫu: name: {name} / tickers: [..] "
                           f"(hoặc dùng --tickers-file)")
    p.write_text(yaml.safe_dump({"name": name, "fetched_at": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
                                 "note": "thành viên hiện hành lúc lấy, không phải point-in-time", "tickers": tickers},
                                allow_unicode=True), encoding="utf-8")
    return tickers


def read_tickers_file(path: str) -> list[str]:
    """Mỗi dòng/ô phân tách bằng dấu phẩy hoặc khoảng trắng; bỏ dòng bắt đầu bằng #."""
    out: list[str] = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if line.strip().startswith("#"):
            continue
        out += [x.strip().upper() for x in re.split(r"[,\s;]+", line) if x.strip()]
    return list(dict.fromkeys(out))


def _metrics(snap: dict) -> dict | None:
    m = nz.multiples(snap["prices"]["rows"], snap["financials"]["annual"], snap["company"].get("shares_outstanding"))
    return m or None


def _view(snap: dict, listing: dict | None = None) -> dict:
    t = snap["meta"]["ticker"]
    parent = None
    if listing is not None:
        parent = (listing.get(t) or {}).get("parent_en")
    return {
        "sector": snap["company"].get("sector") or "",
        "parent": parent,
        "is_bank": bool(snap["company"].get("is_bank")),
        "met": _metrics(snap),
    }


def _closest(
    group: list[str],
    t: str,
    views: dict,
    max_peers: int | None,
    *,
    rank_by_market_cap: bool = False,
) -> list[str]:
    """Xếp peers.

    - rank_by_market_cap=True (cascade ICB): luôn sắp |Δ vốn hóa| rồi mã.
    - False (legacy VN30): giữ thứ tự group trừ khi cắt max_peers (khi đó sắp theo |Δcap|/mã).
    """
    mc = (views.get(t, {}).get("met") or {}).get("market_cap")

    def dist(x: str) -> float:
        if not mc or mc <= 0:
            return 1e9
        v = (views[x]["met"] or {}).get("market_cap")
        return abs(math.log(v / mc)) if v and v > 0 else 1e9

    if rank_by_market_cap:
        ordered = sorted(group, key=lambda x: (dist(x), x))
        if not max_peers or len(ordered) <= max_peers:
            return ordered
        return ordered[:max_peers]

    # Legacy: không đổi thứ tự nếu không cắt
    if not max_peers or len(group) <= max_peers:
        return group
    if not mc or mc <= 0:
        return sorted(group)[:max_peers]
    return sorted(group, key=lambda x: (dist(x), x))[:max_peers]


def _assign_peers(
    s: dict,
    t: str,
    views: dict,
    by_sector: dict,
    max_peers: int | None,
    *,
    listing: dict | None = None,
    min_peer_group_size: int | None = None,
    use_icb_peer_cascade: bool = False,
) -> None:
    group, small, finance_blocked = icb_sector.resolve_peer_group(
        t, views, listing=listing if use_icb_peer_cascade else None,
        min_size=min_peer_group_size,
        apply_finance_filter=use_icb_peer_cascade,
    )
    fallback = False
    # Legacy VN30: ngành chỉ có 1 mã phi ngân hàng → peers khác ngành
    if not use_icb_peer_cascade and not group and not views[t]["is_bank"]:
        group = [x for x in views if x != t and views[x]["met"] and not views[x]["is_bank"]
                 and (views[x].get("sector") or "").strip()]
        fallback = bool(group)
        small = small or fallback
    if not group:
        if finance_blocked:
            if "peers_finance_nonfinance_blocked" not in s["meta"]["flags"]:
                s["meta"]["flags"].append("peers_finance_nonfinance_blocked")
        elif "peers_none_in_universe_same_sector" not in s["meta"]["flags"]:
            s["meta"]["flags"].append("peers_none_in_universe_same_sector")
        s["peers"] = []
        return
    group = _closest(group, t, views, max_peers, rank_by_market_cap=use_icb_peer_cascade)
    s["peers"] = [{"ticker": x, **{k: (round(v, 4) if v is not None else None) for k, v in views[x]["met"].items()},
                   "source_id": "src_universe_calc"} for x in group]
    s["meta"]["data_status"]["peers"] = "partial" if (fallback or small or len(group) < 2) else "ok"
    if not any(x["id"] == "src_universe_calc" for x in s["sources"]):
        s["sources"].append({"id": "src_universe_calc", "name": "PE/PB/ROE tự tính từ snapshot các mã cùng ngành trong universe",
                             "url": "internal://universe", "fetched_at": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
                             "note": "PE=giá*CP/LNST công ty mẹ; PB=giá*CP/VCSH; ROE=LNST/VCSH cuối kỳ (xấp xỉ)"})
    s["meta"]["flags"] = [x for x in s["meta"]["flags"] if x not in (
        "peers_list_empty", "peers_multiples_not_point_in_time", "peers_none_in_universe_same_sector",
        "peers_cross_sector_vn30_nonbank_fallback", "sector_small_group", "peers_finance_nonfinance_blocked")]
    if fallback:
        s["meta"]["flags"].append("peers_cross_sector_vn30_nonbank_fallback")
    if small:
        s["meta"]["flags"].append("sector_small_group")
    if finance_blocked:
        s["meta"]["flags"].append("peers_finance_nonfinance_blocked")
    if "universe_membership_current_not_point_in_time" not in s["meta"]["flags"]:
        s["meta"]["flags"].append("universe_membership_current_not_point_in_time")


def _by_sector(views: dict) -> dict:
    by: dict[str, list[str]] = {}
    for t, v in views.items():
        if v["sector"] and v["met"]:
            by.setdefault(v["sector"], []).append(t)
    return by


def fill_peers(
    snaps: dict[str, dict],
    max_peers: int | None = None,
    cfg: dict | None = None,
    *,
    use_icb_peer_cascade: bool | None = None,
) -> None:
    """Gán peers trong universe.

    use_icb_peer_cascade mặc định False (cfg hoặc kwarg). True → cascade ICB + lọc tài chính.
    """
    cfg = cfg or {}
    if use_icb_peer_cascade is None:
        use_icb_peer_cascade = bool(cfg.get("use_icb_peer_cascade", False))
    listing = None
    if use_icb_peer_cascade and cfg.get("icb_sector_enabled", True):
        listing = icb_sector.load_listing(cfg.get("icb_sector_map"))
    elif cfg.get("icb_sector_enabled", True):
        # vẫn nạp listing để gắn parent trên view (không cascade)
        listing = icb_sector.load_listing(cfg.get("icb_sector_map"))
    views = {t: _view(s, listing) for t, s in snaps.items()}
    by = _by_sector(views)
    min_size = None
    if use_icb_peer_cascade:
        min_size = cfg.get("min_peer_group_size")
    for t, s in snaps.items():
        _assign_peers(
            s, t, views, by, max_peers, listing=listing,
            min_peer_group_size=min_size, use_icb_peer_cascade=use_icb_peer_cascade,
        )


def fill_peers_dir(
    tickers: list[str],
    as_of: str,
    out_dir: str,
    cfg: dict,
    log=print,
    *,
    use_icb_peer_cascade: bool | None = None,
) -> dict:
    """Như fill_peers nhưng đọc/ghi từng file (không giữ cả universe trong RAM)."""
    if use_icb_peer_cascade is None:
        use_icb_peer_cascade = bool(cfg.get("use_icb_peer_cascade", False))
    listing = None
    if cfg.get("icb_sector_enabled", True):
        listing = icb_sector.load_listing(cfg.get("icb_sector_map"))
    paths = {t: Path(out_dir) / f"{t}_{as_of}.json" for t in tickers}
    views = {}
    for t, p in paths.items():
        if p.exists():
            views[t] = _view(json.loads(p.read_text(encoding="utf-8")), listing)
    by, cap = _by_sector(views), cfg.get("universe_max_peers")
    min_size = cfg.get("min_peer_group_size") if use_icb_peer_cascade else None
    summary = {}
    for t in views:
        s = json.loads(paths[t].read_text(encoding="utf-8"))
        _assign_peers(
            s, t, views, by, cap, listing=listing,
            min_peer_group_size=min_size, use_icb_peer_cascade=use_icb_peer_cascade,
        )
        res = quality.apply(s, cfg)
        f.save_snapshot(s, out_dir)
        summary[t] = {"data_status": s["meta"]["data_status"], "flags": s["meta"]["flags"], "quality": res["tier"]}
    log(f"[peers] đã gán peers cho {len(summary)}/{len(tickers)} mã trong {out_dir}")
    return summary


def _usable(snap: dict) -> bool:
    """Snapshot có sẵn dùng lại được: không lỗi bước nào và giá/chỉ số/công ty/BCTC đều ok (tin, peers được phép thiếu)."""
    ds, flags = snap["meta"]["data_status"], snap["meta"]["flags"]
    return not any(x.startswith("m1_") and "error" in x for x in flags) and \
        all(ds.get(k) == "ok" for k in ("prices", "index", "company", "financials"))


def fetch_all(tickers: list[str], as_of: str, cfg: dict, out_dir: str = "data/snapshots", force: bool = False,
              log=print, reuse_dirs: tuple | list = (), resume: bool = False, peers: bool = True,
              summary_name: str | None = None) -> dict:
    """Trả về bảng tóm tắt {ticker: {status, data_status, quality, error}}. Mã lỗi không làm dừng cả lô.

    resume=True: snapshot đã có (không lỗi, giá/BCTC ok) coi như xong dù tin/peers còn thiếu - cần cho universe rộng,
    nếu không mã ít tin sẽ bị cào lại mãi. reuse_dirs: thư mục khác để tìm snapshot cùng as_of (vd data/snapshots của VN30).
    peers=False: bỏ bước gán peers (khi chạy theo lô; gán sau bằng fill_peers_dir)."""
    cfg = {**cfg, "skip_peer_fetch": True}
    snaps: dict[str, dict] = {}
    summary: dict[str, dict] = {}
    fetched, t0 = 0, time.time()
    for i, t in enumerate(tickers, 1):
        path = Path(out_dir) / f"{t}_{as_of}.json"
        try:
            if not force:
                for d, lenient in [(Path(out_dir), resume)] + [(Path(x), True) for x in reuse_dirs]:
                    p = d / f"{t}_{as_of}.json"
                    if not p.exists():
                        continue
                    snap = json.loads(p.read_text(encoding="utf-8"))
                    strict_ok = all(v == "ok" for k, v in snap["meta"]["data_status"].items() if k != "peers")
                    if strict_ok or (lenient and _usable(snap)):
                        snaps[t] = snap
                        summary[t] = {"status": "skipped (đã đủ)" if d == Path(out_dir) else f"reused ({d})",
                                      "data_status": snap["meta"]["data_status"]}
                        log(f"[{i}/{len(tickers)}] {t}: bỏ qua, đã có snapshot đủ dữ liệu ({d})")
                        break
                if t in snaps:
                    continue
            eta = ((time.time() - t0) / fetched) * (len(tickers) - i + 1) / 60 if fetched else None
            log(f"[{i}/{len(tickers)}] {t}: đang lấy dữ liệu..." + (f" (còn ~{eta:.0f} phút)" if eta else ""))
            snap = f.build_snapshot(t, as_of, cfg)
            fetched += 1
            snaps[t] = snap
            f.save_snapshot(snap, out_dir, peers_pending=True)  # lượt 1: peers gán sau fill_peers
            summary[t] = {"status": "ok" if all(v == "ok" for k, v in snap["meta"]["data_status"].items() if k != "peers") else "partial",
                          "data_status": snap["meta"]["data_status"]}
        except Exception as e:  # noqa: BLE001
            summary[t] = {"status": "error", "error": str(e)[:200]}
            log(f"[{i}/{len(tickers)}] {t}: LỖI {str(e)[:120]}")
    if peers:
        fill_peers(
            snaps, cfg.get("universe_max_peers"), cfg=cfg,
            use_icb_peer_cascade=bool(cfg.get("use_icb_peer_cascade", False)),
        )
    for t, s in snaps.items():
        res = quality.apply(s, cfg)
        f.save_snapshot(s, out_dir)
        summary.setdefault(t, {}).update(data_status=s["meta"]["data_status"], flags=s["meta"]["flags"], quality=res["tier"])   # status giữ nguyên, chỉ cập nhật peers/cờ
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    Path(out_dir, summary_name or f"_summary_{as_of}.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
    return summary
