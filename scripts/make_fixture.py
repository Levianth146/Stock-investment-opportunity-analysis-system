"""Sinh fixtures/snapshot_DEMO.json - dữ liệu GIẢ (meta.synthetic=true) để mọi người code song song ngay từ phút đầu.
Chạy: python scripts/make_fixture.py   (N1/N2 sở hữu; đổi schema thì sinh lại)."""
import json
import sys
from datetime import date, timedelta
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from stockai.contracts.helpers import check_no_lookahead  # noqa: E402
from stockai.contracts.schemas import assert_valid  # noqa: E402

AS_OF = date(2026, 10, 9)
rng = np.random.default_rng(42)


def bdays(start: date, end: date):
    d = start
    while d <= end:
        if d.weekday() < 5:
            yield d
        d += timedelta(days=1)


days = list(bdays(date(2021, 10, 11), AS_OF))
mkt = np.cumprod(1 + rng.normal(0.0003, 0.011, len(days))) * 1000
px = np.cumprod(1 + 0.8 * (np.diff(np.r_[mkt[0], mkt]) / np.r_[mkt[0], mkt[:-1]]) + rng.normal(0.0002, 0.012, len(days))) * 20000
rows = []
for d, c in zip(days, px):
    o = c * (1 + rng.normal(0, 0.004)); h = max(o, c) * 1.006; l = min(o, c) * 0.994
    rows.append({"date": d.isoformat(), "open": round(o, 2), "high": round(h, 2), "low": round(l, 2),
                 "close": round(float(c), 2), "volume": int(rng.integers(2_000_000, 9_000_000))})
idx = [{"date": d.isoformat(), "close": round(float(m), 2)} for d, m in zip(days, mkt)]

def fin(period, pub, base, g):
    rev = base * g
    return {"period": period, "published_at": pub, "source_id": "src_fin", "items": {
        "revenue": rev, "gross_profit": rev * 0.22, "ebit": rev * 0.12, "net_income": rev * 0.09,
        "total_assets": rev * 1.6, "total_equity": rev * 0.8, "total_liabilities": rev * 0.8,
        "current_assets": rev * 0.7, "current_liabilities": rev * 0.45, "cfo": rev * 0.1, "cfi": -rev * 0.08, "cff": -rev * 0.01,
        "capex": rev * 0.07, "eps": 1800 * g, "interest_expense": rev * 0.015}}

annual = [fin(str(y), f"{y + 1}-03-20", 100e9, 1.1 ** (y - 2021)) for y in range(2021, 2026)]
quarterly = [fin(f"2025Q{q}", f"2025-{m}-25", 28e9, 1.4) for q, m in ((1, "04"), (2, "07"))] + \
            [fin("2026Q1", "2026-04-25", 28e9, 1.45), fin("2026Q2", "2026-07-25", 28e9, 1.5)]
news = [{"id": f"n{i}", "title": t, "url": f"https://example.com/demo/{i}", "source": "example.com (GIẢ)",
         "published_at": p, "summary": s} for i, (t, p, s) in enumerate([
    ("DEMO công bố lợi nhuận quý 2 tăng 18%", "2026-07-26T08:00:00", "Dữ liệu giả để test."),
    ("DEMO mở rộng nhà máy mới", "2026-08-12T09:30:00", "Dữ liệu giả để test."),
    ("Ngành thép đối mặt áp lực giá đầu vào", "2026-09-03T10:00:00", "Dữ liệu giả để test."),
    ("DEMO bị điều tra chống bán phá giá", "2026-09-20T14:00:00", "Dữ liệu giả để test."),
    ("Khối ngoại bán ròng DEMO tuần qua", "2026-10-05T16:00:00", "Dữ liệu giả để test.")])]
snap = {
    "meta": {"schema_version": "1.0", "ticker": "DEMO", "as_of": AS_OF.isoformat(), "window_start": "2021-10-09",
             "fetched_at": "2026-10-09T09:00:00", "synthetic": True, "flags": ["synthetic_fixture"],
             "data_status": {k: "ok" for k in ("prices", "index", "financials", "company", "peers", "news")}},
    "company": {"name": "DEMO Steel JSC (GIẢ)", "exchange": "HOSE", "sector": "Tài nguyên cơ bản", "industry": "Thép",
                "is_bank": False, "shares_outstanding": 5_000_000_000, "source_id": "src_co"},
    "prices": {"adjusted": True, "source_id": "src_px", "rows": rows},
    "index": {"symbol": "VNINDEX", "source_id": "src_px", "rows": idx},
    "financials": {"unit": "VND", "annual": annual, "quarterly": quarterly},
    "peers": [{"ticker": t, "pe": pe, "pb": pb, "roe": roe, "market_cap": 1e13, "source_id": "src_co"}
              for t, pe, pb, roe in (("PEER1", 11.0, 1.4, 0.13), ("PEER2", 9.5, 1.1, 0.10), ("PEER3", 14.0, 2.0, 0.16))],
    "news": news,
    "sources": [{"id": i, "name": n, "url": "https://example.com/synthetic", "fetched_at": "2026-10-09T09:00:00", "note": "GIẢ"}
                for i, n in (("src_px", "synthetic prices"), ("src_fin", "synthetic financials"), ("src_co", "synthetic company"))],
}
assert_valid(snap, "snapshot")
assert not check_no_lookahead(snap)
out = Path(__file__).resolve().parents[1] / "fixtures" / "snapshot_DEMO.json"
out.write_text(json.dumps(snap, ensure_ascii=False, indent=1), encoding="utf-8")
print("wrote", out, f"({out.stat().st_size // 1024} KB)")
