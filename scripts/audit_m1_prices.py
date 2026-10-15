"""Kiểm tra chất lượng dữ liệu M1 cho toàn bộ snapshot (giá, tài chính, số CP).

Phần 1 (offline, mặc định): giá/khối lượng/ngày, thang giá, nhảy giá, tài chính, P/E-P/B cực đoan.
Phần 2 (--cross-source): đối chiếu giá đóng cửa 5 phiên gần nhất với nguồn khác qua vnstock
(mặc định KBS; snapshot lấy từ VCI) — cần mạng và vnstock.

  python scripts/audit_m1_prices.py --asof 2026-10-14
  python scripts/audit_m1_prices.py --asof 2026-10-14 --cross-source --source KBS --limit 40
Kết quả: in tóm tắt + ghi data/audit/m1_audit_<asof>.json
"""
from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LIMIT_PCT = {"HSX": 7.0, "HOSE": 7.0, "HNX": 10.0, "UPCOM": 15.0}


def _f(x):
    try:
        v = float(x)
        return v if v == v else None
    except (TypeError, ValueError):
        return None


def audit_one(sym: str, snap: dict, asof: str) -> list[dict]:
    out: list[dict] = []

    def add(sev, code, msg):
        out.append({"symbol": sym, "severity": sev, "code": code, "msg": msg})

    rows = ((snap.get("prices") or {}).get("rows")) or []
    if len(rows) < 200:
        add("warn", "few_rows", f"chỉ {len(rows)} phiên giá")
    if rows:
        last = str(rows[-1].get("date"))[:10]
        if last != asof:
            add("warn", "stale_last_date", f"phiên cuối {last} ≠ as_of {asof}")
        closes = [_f(r.get("close")) for r in rows]
        if any(c is None or c <= 0 for c in closes):
            add("error", "bad_close", "có close ≤ 0 hoặc thiếu")
        med = statistics.median([c for c in closes if c]) if any(closes) else 0
        if med and (med < 500 or med > 2_000_000):
            add("error", "price_scale", f"median close {med:,.0f} nghi sai thang giá")
        bad_ohlc = 0
        zero_vol = 0
        flat_run = best_run = 0
        exch = str((snap.get("company") or {}).get("exchange") or "HSX").upper()
        lim = LIMIT_PCT.get(exch, 7.0)
        jumps = []
        for i, r in enumerate(rows):
            c, h, l_, v = _f(r.get("close")), _f(r.get("high")), _f(r.get("low")), _f(r.get("volume"))
            if None not in (c, h, l_) and not (l_ - 1e-6 <= c <= h + 1e-6 and h >= l_):
                bad_ohlc += 1
            if v == 0 or v is None:
                zero_vol += 1
            if i:
                p = closes[i - 1]
                if p and c:
                    ch = (c / p - 1) * 100
                    flat_run = flat_run + 1 if abs(ch) < 1e-9 else 0
                    best_run = max(best_run, flat_run)
                    if abs(ch) > lim * 2 + 1:  # xa hơn 2× biên độ → nghi chưa điều chỉnh/lỗi
                        jumps.append((str(r.get("date"))[:10], round(ch, 1)))
        if bad_ohlc:
            add("warn", "bad_ohlc", f"{bad_ohlc} phiên close ngoài [low, high]")
        if rows and zero_vol / len(rows) > 0.2:
            add("info", "zero_volume", f"{zero_vol}/{len(rows)} phiên KL = 0 (thanh khoản thấp)")
        if best_run >= 10:
            add("info", "flat_close", f"{best_run} phiên liên tiếp giá không đổi")
        if jumps:
            add("warn", "price_jump", f"nhảy giá vượt biên độ: {jumps[:3]}")

    fin = snap.get("financials") or {}
    q = fin.get("quarterly") or []
    if len(q) < 4:
        add("warn", "few_quarters", f"chỉ {len(q)} quý báo cáo")
    sh = _f((snap.get("company") or {}).get("shares_outstanding"))
    if not sh or sh <= 0:
        add("error", "no_shares", "thiếu số cổ phiếu")
    if q and sh and rows:
        ni = [_f((p.get("items") or {}).get("net_income_parent")) or _f((p.get("items") or {}).get("net_income")) for p in q[:4]]
        eq = _f((q[0].get("items") or {}).get("total_equity"))
        px = _f(rows[-1].get("close"))
        if eq and eq <= 0:
            add("warn", "neg_equity", "vốn chủ sở hữu ≤ 0")
        if all(x is not None for x in ni) and px:
            pe = px * sh / sum(ni) if sum(ni) > 0 else None
            pb = px * sh / eq if eq and eq > 0 else None
            if pe is not None and (pe < 3 or pe > 100):
                add("review", "extreme_pe", f"P/E TTM {pe:.1f} — kiểm tra lợi nhuận bất thường/số CP")
            if pb is not None and (pb < 0.3 or pb > 10):
                add("review", "extreme_pb", f"P/B {pb:.2f} — kiểm tra vốn CSH/số CP/giá")
    return out


def cross_source(symbols: list[str], source: str, n: int = 5) -> list[dict]:
    from vnstock import Vnstock  # type: ignore

    res = []
    for s in symbols:
        try:
            df = Vnstock().stock(symbol=s, source=source).quote.history(
                start="2026-09-20", end="2026-12-31", interval="1D"
            )
        except Exception as e:  # noqa: BLE001
            res.append({"symbol": s, "severity": "info", "code": "xsrc_fail", "msg": type(e).__name__})
            continue
        snap = json.loads(next((ROOT / "data/snapshots_ext").glob(f"{s}_*.json")).read_text(encoding="utf-8"))
        mine = {str(r["date"])[:10]: _f(r["close"]) for r in snap["prices"]["rows"][-n:]}
        diffs = []
        for _, r in df.tail(15).iterrows():
            d = str(r.get("time") or r.get("date"))[:10]
            c = _f(r.get("close"))
            if d in mine and c and mine[d]:
                # nguồn khác có thể theo nghìn đồng
                for k in (1, 1000):
                    if abs(c * k / mine[d] - 1) < 0.002:
                        break
                else:
                    diffs.append((d, mine[d], c))
        if diffs:
            res.append({"symbol": s, "severity": "warn", "code": "xsrc_diff", "msg": f"lệch giá vs {source}: {diffs[:3]}"})
    return res


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--asof", required=True)
    ap.add_argument("--dir", default="data/snapshots_ext")
    ap.add_argument("--cross-source", action="store_true")
    ap.add_argument("--source", default="KBS")
    ap.add_argument("--limit", type=int, default=0, help="giới hạn số mã đối chiếu (0 = tất cả)")
    a = ap.parse_args()
    d = ROOT / a.dir
    findings: list[dict] = []
    syms = []
    for f in sorted(d.glob(f"*_{a.asof}.json")):
        s = f.name.split("_")[0]
        if s.startswith("_") or not s.isalnum():
            continue
        syms.append(s)
        findings += audit_one(s, json.loads(f.read_text(encoding="utf-8")), a.asof)
    if a.cross_source:
        findings += cross_source(syms[: a.limit or None], a.source)
    out = ROOT / "data" / "audit"
    out.mkdir(parents=True, exist_ok=True)
    (out / f"m1_audit_{a.asof}.json").write_text(json.dumps(findings, ensure_ascii=False, indent=1), encoding="utf-8")
    by: dict[str, list[dict]] = {}
    for x in findings:
        by.setdefault(x["code"], []).append(x)
    print(f"Đã kiểm {len(syms)} mã, {len(findings)} phát hiện")
    for code, xs in sorted(by.items(), key=lambda kv: -len(kv[1])):
        print(f"- {code} [{xs[0]['severity']}]: {len(xs)} mã — " + ", ".join(x['symbol'] for x in xs[:12]) + (" …" if len(xs) > 12 else ""))
    print(f"Chi tiết: {out / f'm1_audit_{a.asof}.json'}")


if __name__ == "__main__":
    main()
