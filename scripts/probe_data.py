"""Dò nguồn dữ liệu THẬT trên máy bạn: in tên cột, vài dòng đầu, và cột nào khớp/không khớp ALIASES.
Chạy:  python scripts/probe_data.py HPG        (cần: pip install vnstock, có internet)
Dán toàn bộ output cho Cursor/Claude để chỉnh ALIASES trong src/stockai/m1_data/normalize.py."""
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import pandas as pd  # noqa: E402
import yaml  # noqa: E402

from stockai.m1_data import normalize as nz  # noqa: E402
from stockai.m1_data import sources as src  # noqa: E402

pd.set_option("display.width", 200, "display.max_columns", 12)
ticker = sys.argv[1] if len(sys.argv) > 1 else "HPG"
cfg = yaml.safe_load(Path("config/data_sources.yaml").read_text(encoding="utf-8"))
as_of = date.today().isoformat()
start = (date.today() - timedelta(days=365 * 5)).isoformat()


def show(title, fn):
    print(f"\n===== {title} =====")
    try:
        df, provider = fn()
        print(f"nguồn={provider} shape={df.shape}")
        print("cột:", list(df.columns))
        print(df.head(2).to_string()[:1500])
        return df
    except Exception as e:  # noqa: BLE001
        print("LỖI:", e)


h = show(f"giá {ticker}", lambda: src.get_history(ticker, start, as_of, cfg))
if h is not None:
    rows, flags = nz.normalize_prices(h, start, as_of, cfg.get("price_multiplier", "auto"))
    print(f"-> chuẩn hóa: {len(rows)} dòng, close cuối={rows[-1]['close'] if rows else None}, cờ={flags}")
i = show("VNINDEX", lambda: src.get_history("VNINDEX", start, as_of, cfg))
if i is not None:
    print(f"-> chuẩn hóa: {len(nz.normalize_index(i, start, as_of))} dòng")
o = show("overview", lambda: src.get_overview(ticker, cfg))
if o is not None:
    print("->", nz.normalize_company(o, ticker, cfg.get("banks", [])))
is_bank = ticker in cfg.get("banks", [])
for period in ("year", "quarter"):
    frames = [show(f"{k}/{period}", lambda k=k: src.get_finance(ticker, k, period, cfg)) for k in ("income", "balance", "cashflow")]
    frames = [f for f in frames if f is not None]
    if period == "year":      # in TOÀN BỘ tên chỉ tiêu để chỉnh ALIASES
        out = Path("data/raw") / f"probe_items_{ticker}.txt"
        out.parent.mkdir(parents=True, exist_ok=True)
        lines = []
        for name, fr in zip(("income", "balance", "cashflow"), frames):
            if "item_en" in fr.columns:
                lines += [f"--- {name} ---"] + [f"{r.item_id} | {r.item_en}" for r in fr.itertuples()]
        out.write_text("\n".join(lines), encoding="utf-8")
        print(f"\n>>> danh sách chỉ tiêu đầy đủ đã lưu: {out} ({len(lines)} dòng) - gửi file này nếu còn chỉ tiêu không khớp")
    per, cmap, flags = nz.normalize_financials(frames, period == "year", as_of, "src_x", is_bank, cfg.get("financial_multiplier", "auto"))
    print(f"\n-> {period}: {len(per)} kỳ; khớp cột:")
    for k, v in cmap.items():
        print(f"   {k:<22} <- {v}")
    print("   cờ:", flags)
    if per:
        print("   kỳ mới nhất:", per[0]["period"], per[0]["published_at"], {k: v for k, v in list(per[0]["items"].items())[:8]})
n = show("news", lambda: src.get_news(ticker, cfg))
if n is not None:
    items, fl = nz.normalize_news(n, start, as_of, "probe", 5)
    print(f"-> chuẩn hóa: {len(items)} tin; cờ={fl}")
    for it in items[:3]:
        print("  ", it["published_at"], it["title"][:80], it["url"][:60])
