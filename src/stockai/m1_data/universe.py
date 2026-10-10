"""Chạy M1 cho cả universe (VN30). Chỉ N2 sửa.

  python scripts/fetch_universe.py --as-of 2026-10-09                 # VN30, danh sách lấy từ vnstock rồi ghi config/universe.yaml
  python scripts/fetch_universe.py --tickers HPG,VCB,VNM              # danh sách tự chọn
Mỗi mã 1 file data/snapshots/<MÃ>_<as_of>.json, lưu ngay khi xong (ngắt giữa chừng vẫn giữ phần đã chạy).
Chạy lại sẽ bỏ qua mã đã đủ dữ liệu (dùng --force để làm lại). Peers = các mã CÙNG NGÀNH trong universe,
PE/PB/ROE tự tính từ snapshot tại as_of (point-in-time, không tốn thêm request).

Hạn chế (ghi vào báo cáo): danh sách thành viên là hiện hành tại thời điểm lấy, KHÔNG phải thành phần tại từng ngày lịch sử."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import yaml

from stockai.m1_data import fetch as f
from stockai.m1_data import normalize as nz

UNIVERSE_FILE = "config/universe.yaml"


def load_universe(cfg: dict, name: str = "VN30", refresh: bool = False) -> list[str]:
    """Đọc config/universe.yaml; chưa có (hoặc --refresh) thì lấy từ vnstock rồi lưu lại để cả nhóm dùng CHUNG một danh sách."""
    p = Path(UNIVERSE_FILE)
    if p.exists() and not refresh:
        data = yaml.safe_load(p.read_text(encoding="utf-8"))
        if data.get("name") == name and data.get("tickers"):
            return list(data["tickers"])
    tickers: list[str] = []
    try:
        from vnstock import Listing
        for src in cfg.get("vnstock_sources", ["VCI"]):
            try:
                res = Listing(source=src).symbols_by_group(name)
                tickers = sorted({str(x).strip().upper() for x in (res["symbol"] if hasattr(res, "columns") else res)})
                if tickers:
                    break
            except Exception:
                continue
    except Exception:
        pass
    if not tickers:
        if p.exists():
            data = yaml.safe_load(p.read_text(encoding="utf-8"))
            if data.get("name") == name and data.get("tickers"):
                print(f"[universe] vnstock không trả danh sách {name}, dùng {UNIVERSE_FILE} có sẵn")
                return list(data["tickers"])
        raise RuntimeError(f"Không lấy được danh sách {name}; điền tay vào {UNIVERSE_FILE} theo mẫu: name: VN30 / tickers: [..]")
    p.write_text(yaml.safe_dump({"name": name, "fetched_at": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
                                 "note": "thành viên hiện hành lúc lấy, không phải point-in-time", "tickers": tickers},
                                allow_unicode=True), encoding="utf-8")
    return tickers


def _metrics(snap: dict) -> dict | None:
    m = nz.multiples(snap["prices"]["rows"], snap["financials"]["annual"], snap["company"].get("shares_outstanding"))
    return m or None


def fill_peers(snaps: dict[str, dict]) -> None:
    """Gán peers = mã cùng sector trong universe. Sector đứng một mình thì giữ peers cũ (nếu có)."""
    met = {t: _metrics(s) for t, s in snaps.items()}
    by_sector: dict[str, list[str]] = {}
    for t, s in snaps.items():
        if s["company"].get("sector") and met[t]:
            by_sector.setdefault(s["company"]["sector"], []).append(t)
    for t, s in snaps.items():
        group = [x for x in by_sector.get(s["company"].get("sector", ""), []) if x != t]
        fallback = False
        if not group and not s["company"].get("is_bank"):   # ngành chỉ có 1 mã trong VN30: tạm dùng các mã phi ngân hàng còn lại (khác ngành)
            group = [x for x in snaps if x != t and met.get(x) and not snaps[x]["company"].get("is_bank")]
            fallback = bool(group)
        if not group:
            if "peers_none_in_universe_same_sector" not in s["meta"]["flags"]:
                s["meta"]["flags"].append("peers_none_in_universe_same_sector")
            continue
        s["peers"] = [{"ticker": x, **{k: (round(v, 4) if v is not None else None) for k, v in met[x].items()},
                       "source_id": "src_universe_calc"} for x in group]
        s["meta"]["data_status"]["peers"] = "partial" if (fallback or len(group) < 2) else "ok"
        if not any(x["id"] == "src_universe_calc" for x in s["sources"]):
            s["sources"].append({"id": "src_universe_calc", "name": "PE/PB/ROE tự tính từ snapshot các mã cùng ngành trong universe",
                                 "url": "internal://universe", "fetched_at": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
                                 "note": "PE=giá*CP/LNST công ty mẹ; PB=giá*CP/VCSH; ROE=LNST/VCSH cuối kỳ (xấp xỉ)"})
        s["meta"]["flags"] = [x for x in s["meta"]["flags"] if x not in ("peers_list_empty", "peers_multiples_not_point_in_time")]
        s["meta"]["flags"] = [x for x in s["meta"]["flags"] if x not in ("peers_none_in_universe_same_sector", "peers_cross_sector_vn30_nonbank_fallback")]
        if fallback:
            s["meta"]["flags"].append("peers_cross_sector_vn30_nonbank_fallback")
        if "universe_membership_current_not_point_in_time" not in s["meta"]["flags"]:
            s["meta"]["flags"].append("universe_membership_current_not_point_in_time")


def fetch_all(tickers: list[str], as_of: str, cfg: dict, out_dir: str = "data/snapshots", force: bool = False,
              log=print) -> dict:
    """Trả về bảng tóm tắt {ticker: {status, data_status, error}}. Mã lỗi không làm dừng cả lô."""
    cfg = {**cfg, "skip_peer_fetch": True}
    snaps: dict[str, dict] = {}
    summary: dict[str, dict] = {}
    for i, t in enumerate(tickers, 1):
        path = Path(out_dir) / f"{t}_{as_of}.json"
        try:
            if path.exists() and not force:
                snap = json.loads(path.read_text(encoding="utf-8"))
                if all(v == "ok" for k, v in snap["meta"]["data_status"].items() if k != "peers"):
                    snaps[t] = snap
                    summary[t] = {"status": "skipped (đã đủ)", "data_status": snap["meta"]["data_status"]}
                    log(f"[{i}/{len(tickers)}] {t}: bỏ qua, đã có snapshot đủ dữ liệu")
                    continue
            log(f"[{i}/{len(tickers)}] {t}: đang lấy dữ liệu...")
            snap = f.build_snapshot(t, as_of, cfg)
            snaps[t] = snap
            f.save_snapshot(snap, out_dir)
            summary[t] = {"status": "ok" if all(v == "ok" for k, v in snap["meta"]["data_status"].items() if k != "peers") else "partial",
                          "data_status": snap["meta"]["data_status"]}
        except Exception as e:  # noqa: BLE001
            summary[t] = {"status": "error", "error": str(e)[:200]}
            log(f"[{i}/{len(tickers)}] {t}: LỖI {str(e)[:120]}")
    fill_peers(snaps)
    for t, s in snaps.items():
        f.save_snapshot(s, out_dir)
        summary.setdefault(t, {}).update(data_status=s["meta"]["data_status"], flags=s["meta"]["flags"])   # status giữ nguyên, chỉ cập nhật peers/cờ sau fill_peers
    Path(out_dir, f"_summary_{as_of}.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
    return summary
