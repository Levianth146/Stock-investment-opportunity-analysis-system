"""Xuất CSV từ snapshot M1 để đưa vào mô hình Python (offline, không mạng).

  python scripts/export_snapshots_csv.py --as-of 2026-10-08
  python scripts/export_snapshots_csv.py --as-of 2026-10-08 --in-dir data/snapshots_ext --out-dir data/export_csv
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8", newline="\n")
    os.replace(tmp, path)


def _atomic_write_csv(path: Path, header: list[str], rows: list[list]) -> int:
    """Ghi CSV UTF-8 không BOM, lineterminator \\n. Trả số dòng dữ liệu (không kể header)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(header)
        for row in rows:
            w.writerow(row)
    os.replace(tmp, path)
    return len(rows)


def list_snapshot_files(in_dir: Path, as_of: str) -> list[Path]:
    """Chỉ file trực tiếp trong in_dir: TICKER_as_of.json, bỏ _* và thư mục con."""
    suffix = f"_{as_of}.json"
    out: list[Path] = []
    if not in_dir.is_dir():
        return out
    for p in sorted(in_dir.iterdir(), key=lambda x: x.name):
        if not p.is_file():
            continue
        name = p.name
        if name.startswith("_"):
            continue
        if not name.endswith(suffix):
            continue
        out.append(p)
    return out


def _quality_tier(flags: list) -> str:
    for fl in flags or []:
        if isinstance(fl, str) and fl.startswith("quality_tier_"):
            return fl[len("quality_tier_"):]
    return ""


def _cell(v) -> str:
    if v is None:
        return ""
    if isinstance(v, bool):
        return "true" if v else "false"
    return str(v)


def _load(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001
        print(f"cảnh báo: bỏ qua {path.name}: {e}", flush=True)
        return None


def export_all(in_dir: str | Path, out_dir: str | Path, as_of: str) -> dict:
    """Hai lượt quét: (1) hợp khóa BCTC (2) ghi CSV. Trả dict tóm tắt."""
    in_path = Path(in_dir)
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)
    files = list_snapshot_files(in_path, as_of)

    annual_keys: set[str] = set()
    quarterly_keys: set[str] = set()
    for fp in files:
        snap = _load(fp)
        if not snap:
            continue
        fin = snap.get("financials") or {}
        for per in fin.get("annual") or []:
            items = (per or {}).get("items") or {}
            annual_keys.update(k for k in items if isinstance(k, str))
        for per in fin.get("quarterly") or []:
            items = (per or {}).get("items") or {}
            quarterly_keys.update(k for k in items if isinstance(k, str))

    annual_cols = sorted(annual_keys)
    quarterly_cols = sorted(quarterly_keys)

    uni_rows: list[list] = []
    price_rows: list[list] = []
    index_rows_out: list[list] | None = None
    index_source: str | None = None
    ann_rows: list[list] = []
    qtr_rows: list[list] = []
    n_no_prices = 0
    n_no_fin = 0

    for fp in files:
        snap = _load(fp)
        if not snap:
            continue
        meta = snap.get("meta") or {}
        company = snap.get("company") or {}
        ticker = meta.get("ticker") or fp.name.split("_")[0]
        flags = list(meta.get("flags") or [])
        prices = ((snap.get("prices") or {}).get("rows")) or []
        fin = snap.get("financials") or {}
        annual = list(fin.get("annual") or [])
        quarterly = list(fin.get("quarterly") or [])

        if not prices:
            n_no_prices += 1
        if not annual and not quarterly:
            n_no_fin += 1

        last_date = ""
        if prices:
            # rows may already be chronological; take max date for safety
            dates = [r.get("date") for r in prices if isinstance(r, dict) and r.get("date")]
            last_date = max(dates) if dates else ""

        uni_rows.append([
            ticker,
            as_of,
            _cell(company.get("name")),
            _cell(company.get("exchange")),
            _cell(company.get("sector")),
            _cell(bool(company.get("is_bank"))),
            _cell(company.get("shares_outstanding")),
            _quality_tier(flags),
            "true" if "fetch_skipped_early" in flags else "false",
            str(len(prices)),
            last_date,
            str(len(annual)),
            str(len(quarterly)),
            ";".join(str(f) for f in flags),
        ])

        for r in sorted(
            (x for x in prices if isinstance(x, dict)),
            key=lambda x: x.get("date") or "",
        ):
            price_rows.append([
                ticker,
                _cell(r.get("date")),
                _cell(r.get("open")),
                _cell(r.get("high")),
                _cell(r.get("low")),
                _cell(r.get("close")),
                _cell(r.get("volume")),
            ])

        idx = snap.get("index") or {}
        irows = list(idx.get("rows") or [])
        if irows:
            normalized = [
                [_cell(r.get("date")), _cell(r.get("close"))]
                for r in sorted(
                    (x for x in irows if isinstance(x, dict)),
                    key=lambda x: x.get("date") or "",
                )
            ]
            if index_rows_out is None:
                index_rows_out = normalized
                index_source = ticker
            elif normalized != index_rows_out:
                print(
                    f"cảnh báo: chuỗi index của {ticker} khác {index_source}; "
                    f"giữ index từ snapshot đầu tiên ({index_source})",
                    flush=True,
                )

        for per in sorted(annual, key=lambda p: (p or {}).get("period") or ""):
            if not isinstance(per, dict):
                continue
            items = per.get("items") or {}
            row = [
                ticker,
                _cell(per.get("period")),
                _cell(per.get("published_at")),
                _cell(per.get("published_at_estimated")),
            ]
            for k in annual_cols:
                v = items.get(k)
                row.append("" if v is None else str(v))
            ann_rows.append(row)

        for per in sorted(quarterly, key=lambda p: (p or {}).get("period") or ""):
            if not isinstance(per, dict):
                continue
            items = per.get("items") or {}
            row = [
                ticker,
                _cell(per.get("period")),
                _cell(per.get("published_at")),
                _cell(per.get("published_at_estimated")),
            ]
            for k in quarterly_cols:
                v = items.get(k)
                row.append("" if v is None else str(v))
            qtr_rows.append(row)

    # sắp xếp tất định
    uni_rows.sort(key=lambda r: r[0])
    price_rows.sort(key=lambda r: (r[0], r[1]))
    ann_rows.sort(key=lambda r: (r[0], r[1]))
    qtr_rows.sort(key=lambda r: (r[0], r[1]))
    if index_rows_out is None:
        index_rows_out = []

    n_uni = _atomic_write_csv(
        out_path / "universe_summary.csv",
        [
            "ticker", "as_of", "name", "exchange", "sector", "is_bank", "shares_outstanding",
            "quality_tier", "fetch_skipped_early", "n_price_rows", "last_price_date",
            "n_annual", "n_quarterly", "flags",
        ],
        uni_rows,
    )
    n_px = _atomic_write_csv(
        out_path / "prices.csv",
        ["ticker", "date", "open", "high", "low", "close", "volume"],
        price_rows,
    )
    n_idx = _atomic_write_csv(
        out_path / "index.csv",
        ["date", "close"],
        index_rows_out,
    )
    n_ann = _atomic_write_csv(
        out_path / "financials_annual.csv",
        ["ticker", "period", "published_at", "published_at_estimated", *annual_cols],
        ann_rows,
    )
    n_qtr = _atomic_write_csv(
        out_path / "financials_quarterly.csv",
        ["ticker", "period", "published_at", "published_at_estimated", *quarterly_cols],
        qtr_rows,
    )

    readme = (
        f"as_of={as_of}\n"
        f"n_tickers={n_uni}\n"
        f"universe_summary.csv rows={n_uni}\n"
        f"prices.csv rows={n_px}\n"
        f"index.csv rows={n_idx}\n"
        f"financials_annual.csv rows={n_ann}\n"
        f"financials_quarterly.csv rows={n_qtr}\n"
        f"unit=VND (giữ nguyên như snapshot; không chia, không làm tròn)\n"
        f"note: published_at là ước lượng (quý +45 ngày, năm +90 ngày)\n"
        f"note: mã insufficient không có dòng BCTC\n"
    )
    _atomic_write_text(out_path / "README_export.txt", readme)

    summary = {
        "n_tickers": n_uni,
        "n_prices": n_px,
        "n_index": n_idx,
        "n_annual": n_ann,
        "n_quarterly": n_qtr,
        "n_no_prices": n_no_prices,
        "n_no_fin": n_no_fin,
    }
    return summary


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description="Xuất CSV từ snapshot M1")
    ap.add_argument("--as-of", required=True, help="Ngày as_of (YYYY-MM-DD), lọc file *_as_of.json")
    ap.add_argument("--in-dir", default="data/snapshots_ext")
    ap.add_argument("--out-dir", default="data/export_csv")
    a = ap.parse_args(argv)
    s = export_all(a.in_dir, a.out_dir, a.as_of)
    print("\n=== TÓM TẮT EXPORT CSV ===", flush=True)
    print(f"as_of={a.as_of}  out={a.out_dir}", flush=True)
    print(f"số mã: {s['n_tickers']}", flush=True)
    print(f"universe_summary: {s['n_tickers']} dòng", flush=True)
    print(f"prices: {s['n_prices']} dòng", flush=True)
    print(f"index: {s['n_index']} dòng", flush=True)
    print(f"financials_annual: {s['n_annual']} dòng", flush=True)
    print(f"financials_quarterly: {s['n_quarterly']} dòng", flush=True)
    print(f"mã không có prices: {s['n_no_prices']}", flush=True)
    print(f"mã không có BCTC: {s['n_no_fin']}", flush=True)


if __name__ == "__main__":
    main()
