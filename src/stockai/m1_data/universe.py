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


def _view(snap: dict) -> dict:
    return {"sector": snap["company"].get("sector") or "", "is_bank": bool(snap["company"].get("is_bank")), "met": _metrics(snap)}


def _closest(group: list[str], t: str, views: dict, max_peers: int | None) -> list[str]:
    """Giữ tối đa max_peers mã có vốn hóa gần mã t nhất (không có vốn hóa thì theo thứ tự mã)."""
    if not max_peers or len(group) <= max_peers:
        return group
    mc = (views.get(t, {}).get("met") or {}).get("market_cap")
    if not mc or mc <= 0:
        return sorted(group)[:max_peers]
    def dist(x):
        v = (views[x]["met"] or {}).get("market_cap")
        return abs(math.log(v / mc)) if v and v > 0 else 1e9
    return sorted(group, key=lambda x: (dist(x), x))[:max_peers]


def _assign_peers(s: dict, t: str, views: dict, by_sector: dict, max_peers: int | None) -> None:
    group = [x for x in by_sector.get(views[t]["sector"], []) if x != t]
    fallback = False
    if not group and not views[t]["is_bank"]:   # ngành chỉ có 1 mã trong universe: tạm dùng các mã phi ngân hàng còn lại (khác ngành)
        group = [x for x in views if x != t and views[x]["met"] and not views[x]["is_bank"]]
        fallback = bool(group)
    if not group:
        if "peers_none_in_universe_same_sector" not in s["meta"]["flags"]:
            s["meta"]["flags"].append("peers_none_in_universe_same_sector")
        return
    group = _closest(group, t, views, max_peers)
    s["peers"] = [{"ticker": x, **{k: (round(v, 4) if v is not None else None) for k, v in views[x]["met"].items()},
                   "source_id": "src_universe_calc"} for x in group]
    s["meta"]["data_status"]["peers"] = "partial" if (fallback or len(group) < 2) else "ok"
    if not any(x["id"] == "src_universe_calc" for x in s["sources"]):
        s["sources"].append({"id": "src_universe_calc", "name": "PE/PB/ROE tự tính từ snapshot các mã cùng ngành trong universe",
                             "url": "internal://universe", "fetched_at": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
                             "note": "PE=giá*CP/LNST công ty mẹ; PB=giá*CP/VCSH; ROE=LNST/VCSH cuối kỳ (xấp xỉ)"})
    s["meta"]["flags"] = [x for x in s["meta"]["flags"] if x not in (
        "peers_list_empty", "peers_multiples_not_point_in_time", "peers_none_in_universe_same_sector",
        "peers_cross_sector_vn30_nonbank_fallback")]
    if fallback:
        s["meta"]["flags"].append("peers_cross_sector_vn30_nonbank_fallback")
    if "universe_membership_current_not_point_in_time" not in s["meta"]["flags"]:
        s["meta"]["flags"].append("universe_membership_current_not_point_in_time")


def _by_sector(views: dict) -> dict:
    by: dict[str, list[str]] = {}
    for t, v in views.items():
        if v["sector"] and v["met"]:
            by.setdefault(v["sector"], []).append(t)
    return by


def fill_peers(snaps: dict[str, dict], max_peers: int | None = None) -> None:
    """Gán peers = mã cùng sector trong universe. Sector đứng một mình thì giữ peers cũ (nếu có)."""
    views = {t: _view(s) for t, s in snaps.items()}
    by = _by_sector(views)
    for t, s in snaps.items():
        _assign_peers(s, t, views, by, max_peers)


def fill_peers_dir(tickers: list[str], as_of: str, out_dir: str, cfg: dict, log=print) -> dict:
    """Như fill_peers nhưng đọc/ghi từng file (không giữ cả universe trong RAM) - dùng cho universe lớn hoặc sau khi
    nhiều người chạy từng lô (--shard) rồi gộp snapshot về một thư mục."""
    paths = {t: Path(out_dir) / f"{t}_{as_of}.json" for t in tickers}
    views = {}
    for t, p in paths.items():
        if p.exists():
            views[t] = _view(json.loads(p.read_text(encoding="utf-8")))
    by, cap = _by_sector(views), cfg.get("universe_max_peers")
    summary = {}
    for t in views:
        s = json.loads(paths[t].read_text(encoding="utf-8"))
        _assign_peers(s, t, views, by, cap)
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
            f.save_snapshot(snap, out_dir)
            summary[t] = {"status": "ok" if all(v == "ok" for k, v in snap["meta"]["data_status"].items() if k != "peers") else "partial",
                          "data_status": snap["meta"]["data_status"]}
        except Exception as e:  # noqa: BLE001
            summary[t] = {"status": "error", "error": str(e)[:200]}
            log(f"[{i}/{len(tickers)}] {t}: LỖI {str(e)[:120]}")
    if peers:
        fill_peers(snaps, cfg.get("universe_max_peers"))
    for t, s in snaps.items():
        res = quality.apply(s, cfg)
        f.save_snapshot(s, out_dir)
        summary.setdefault(t, {}).update(data_status=s["meta"]["data_status"], flags=s["meta"]["flags"], quality=res["tier"])   # status giữ nguyên, chỉ cập nhật peers/cờ
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    Path(out_dir, summary_name or f"_summary_{as_of}.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
    return summary
