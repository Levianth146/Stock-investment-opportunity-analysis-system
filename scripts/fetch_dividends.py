"""Lấy lịch sử cổ tức (tiền mặt / cổ phiếu) từ vnstock -> data/dividends/dividends.json.

Chạy trên máy có mạng:  python scripts/fetch_dividends.py [--only ACB,HPG] [--limit 20] [--pause-sec 1.2]
Có thể chạy lại: mã đã có dữ liệu (có events hoặc đã thử cả 2 nguồn hôm nay) được bỏ qua.
In ra 3 dòng mẫu cột gốc để đối chiếu cách quy đổi (cash_dividend_percentage = % mệnh giá 10.000đ).
"""
from __future__ import annotations

import argparse
import contextlib
import glob
import io
import json
import re
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "dividends" / "dividends.json"
SOURCES = ("KBS", "VCI")  # vnstock mới chỉ hỗ trợ KBS, VCI, MSN, FMP (TCBS đã bỏ)
PAR_VND = 10_000.0


def _symbols() -> list[str]:
    syms = sorted({Path(p).name.split("_")[0] for p in glob.glob(str(ROOT / "data" / "snapshots_ext" / "*_2*.json"))})
    return [s for s in syms if re.fullmatch(r"[A-Z0-9]{2,5}", s)]


def _fetch(sym: str, source: str):
    """Thử API mới (vnstock.api.company.Company) rồi API cũ (Vnstock().stock().company)."""
    last: Exception | None = None
    for how in ("new", "old"):
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                if how == "new":
                    from vnstock.api.company import Company

                    comp = Company(symbol=sym, source=source)
                else:
                    from vnstock import Vnstock

                    comp = Vnstock().stock(symbol=sym, source=source).company
                if hasattr(comp, "dividends"):
                    try:
                        return comp.dividends()
                    except AttributeError:
                        pass  # nguồn không cài hàm này -> thử events()
                return comp.events()
        except ImportError as exc:
            last = exc
        except AttributeError as exc:
            last = exc
    raise last or RuntimeError("không lấy được")


def _d(v) -> str | None:
    t = str(v)[:10]
    return t if re.fullmatch(r"\d{4}-\d{2}-\d{2}", t) else None


def _norm(df) -> list[dict]:
    """Chuẩn hoá company.events() của vnstock/VCI: chỉ giữ sự kiện cổ tức (category=DIVIDEND).

    DIV  = cổ tức tiền mặt: value_per_share = đồng/cổ phiếu, exercise_ratio = % mệnh giá (0.03 = 3%).
    ISS  = phát hành cổ phiếu (cổ tức bằng cổ phiếu / thưởng): exercise_ratio = tỷ lệ (0.18 = 18%).
    """
    cols = set(df.columns)
    ev: list[dict] = []
    for _, r in df.iterrows():
        cat = str(r.get("category") or "")
        code = str(r.get("event_code") or "").upper()
        title = str(r.get("event_title_vi") or "")
        is_div = cat == "DIVIDEND" or (code in ("DIV", "ISS") and re.search(r"cổ tức", title, re.I))
        if not is_div:
            continue
        ex = _d(r.get("exright_date")) or _d(r.get("record_date")) or _d(r.get("public_date"))
        if not ex:
            continue
        try:
            vps = float(r.get("value_per_share"))
        except (TypeError, ValueError):
            vps = None
        try:
            ratio = float(r.get("exercise_ratio"))
        except (TypeError, ValueError):
            ratio = None
        is_stock = code == "ISS" or "cổ phiếu" in title.lower() and vps is None
        if vps is not None and vps != vps:
            vps = None
        if ratio is not None and ratio != ratio:
            ratio = None
        m = re.search(r"(20\d{2})", title)
        ev.append(
            {
                "ex_date": ex,
                "record_date": _d(r.get("record_date")),
                "pay_date": _d(r.get("payout_date")),
                "year": int(m.group(1)) if m else None,
                "kind": "stock" if is_stock else "cash",
                "percent_of_par": round(ratio * 100.0, 2) if ratio is not None else None,
                "dps_vnd": None if is_stock else (vps if vps is not None else (round(ratio * PAR_VND) if ratio is not None else None)),
                "title": title or None,
            }
        )
    ev.sort(key=lambda e: e["ex_date"], reverse=True)
    return ev


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--pause-sec", type=float, default=1.2)
    args = ap.parse_args()
    syms = [s.strip().upper() for s in args.only.split(",") if s.strip()] or _symbols()
    if args.limit:
        syms = syms[: args.limit]
    data: dict = {}
    if OUT.exists():
        data = json.loads(OUT.read_text(encoding="utf-8"))
    today = datetime.now().strftime("%Y-%m-%d")
    done = tried = shown = 0
    for i, sym in enumerate(syms, 1):
        old = data.get(sym)
        if old and old.get("events") and old.get("schema") == 2:
            continue
        tried += 1
        events: list[dict] = []
        used = None
        errs: list[str] = []
        for src in SOURCES:
            try:
                df = _fetch(sym, src)
                time.sleep(args.pause_sec)
                if df is not None and len(df):
                    if shown < 3:
                        print(f"[mẫu {src}] {sym} cột={list(df.columns)}\n{df.head(2).to_dict('records')}")
                        shown += 1
                    events = _norm(df)
                    used = src
                    break
                errs.append(f"{src}: rỗng")
            except Exception as exc:  # noqa: BLE001
                errs.append(f"{src}: {type(exc).__name__}: {str(exc)[:120]}")
                if tried <= 2:
                    print(f"  lỗi {sym}/{src}: {type(exc).__name__}: {str(exc)[:300]}")
                    try:
                        from vnstock import Vnstock

                        comp = Vnstock().stock(symbol=sym, source=src).company
                        print("  company có:", [m for m in dir(comp) if not m.startswith("_")])
                    except Exception as e2:  # noqa: BLE001
                        print("  (không liệt kê được company:", type(e2).__name__, ")")
                time.sleep(args.pause_sec * 2)
        data[sym] = {
            "symbol": sym,
            "schema": 2,
            "source": f"vnstock/{used}" if used else None,
            "events": events,
            "tried_on": today,
            "fetched_at": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
            "errors": errs if not events else [],
        }
        if events:
            done += 1
        print(f"[{i}/{len(syms)}] {sym}: {len(events)} sự kiện ({used or '; '.join(errs)})")
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Xong: thử {tried} mã, có dữ liệu {done}. File: {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
