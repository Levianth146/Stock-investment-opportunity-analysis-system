"""Trích hồ sơ công ty (giới thiệu, niêm yết, sở hữu) từ cache overview M1 -> data/company_profiles/profiles.json.

Chạy offline, không gọi mạng: đọc data/raw_ext/overview_<MÃ>_x_<ngày>.pkl (và data/raw/) mới nhất.
Dùng: python scripts/build_company_profiles.py
"""
from __future__ import annotations

import glob
import json
import math
import pickle
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "company_profiles" / "profiles.json"
PAT = re.compile(r"overview_([A-Z0-9]+)_x_(.*)\.pkl$")


def _clean(v):
    if v is None:
        return None
    if hasattr(v, "iloc"):  # cột trùng tên -> Series: lấy giá trị đầu
        v = v.iloc[0] if len(v) else None
        if v is None:
            return None
    if isinstance(v, float) and math.isnan(v):
        return None
    if hasattr(v, "item"):
        v = v.item()
    return v


def _num(v):
    v = _clean(v)
    try:
        return float(v) if v is not None else None
    except (TypeError, ValueError):
        return None


def main() -> int:
    best: dict[str, str] = {}
    for f in glob.glob(str(ROOT / "data" / "raw_ext" / "overview_*_x_*.pkl")) + glob.glob(
        str(ROOT / "data" / "raw" / "overview_*_x_*.pkl")
    ):
        m = PAT.search(f.replace("\\", "/"))
        if not m:
            continue
        sym, day = m.group(1), m.group(2)
        if sym not in best or day > PAT.search(best[sym].replace("\\", "/")).group(2):
            best[sym] = f
    out: dict[str, dict] = {}
    for sym, f in sorted(best.items()):
        try:
            with open(f, "rb") as fh:
                o = pickle.load(fh)
            df = o[0] if isinstance(o, tuple) else o
            r = df.iloc[0]
        except Exception as exc:  # noqa: BLE001
            print(f"bỏ {sym}: {type(exc).__name__}")
            continue
        text = str(_clean(r.get("company_profile")) or "").strip()
        listing = str(_clean(r.get("listing_date")) or "")[:10] or None
        first_price = _num(r.get("first_price"))
        out[sym] = {
            "symbol": sym,
            "name": _clean(r.get("organ_name")),
            "short_name": _clean(r.get("organ_short_name")),
            "intro": text or None,
            "listing_date": listing,
            "first_price": first_price if first_price and first_price > 0 else None,
            "state_pct": _num(r.get("state_percentage")),
            "foreign_pct": _num(r.get("foreigner_percentage")),
            "foreign_max_pct": _num(r.get("maximum_foreign_percentage")),
            "free_float_pct": _num(r.get("free_float_percentage")),
            "issue_share": _num(r.get("issue_share")),
            "icb_lv2": _clean(r.get("icb_code_lv2")),
            "icb_lv4": _clean(r.get("icb_code_lv4")),
            "source": "vnstock/VCI overview (cache M1)",
            "data_date": Path(f).stem.rsplit("_", 1)[-1],
        }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"ghi {len(out)} mã -> {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
