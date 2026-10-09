"""Test offline cho M1: bảng giả có hình dạng giống vnstock. Không gọi mạng."""
import numpy as np
import pandas as pd

from stockai.m1_data import normalize as nz


def _px(n=400, scale=1.0, jump=False):
    d = pd.bdate_range(end="2026-10-09", periods=n)
    c = np.linspace(20, 30, n) * scale
    if jump:
        c[200:] = c[200:] * 0.5
    return pd.DataFrame({"time": d, "open": c, "high": c * 1.01, "low": c * 0.99, "close": c, "volume": 1e6})


def test_prices_scaled_to_vnd_and_cut_to_as_of():
    rows, flags = nz.normalize_prices(_px(), "2021-10-09", "2026-10-01")
    assert rows[-1]["date"] <= "2026-10-01"
    assert rows[-1]["close"] > 20000 and "prices_scaled_x1000_to_VND" in flags      # 30 (nghìn) -> 30000


def test_prices_already_vnd_not_rescaled():
    rows, flags = nz.normalize_prices(_px(scale=1000), "2021-10-09", "2026-10-09")
    assert not any("scaled" in f for f in flags)


def test_unadjusted_jump_flagged():
    _, flags = nz.normalize_prices(_px(jump=True), "2021-10-09", "2026-10-09")
    assert any(f.startswith("suspect_unadjusted_prices") for f in flags)


def _long(rows: dict, periods: list[str], k: float = 1.0) -> pd.DataFrame:
    """Dạng DỌC giống vnstock/VCI thật: cột item, item_en, item_id + một cột cho mỗi kỳ."""
    recs = []
    for i, (name, vals) in enumerate(rows.items()):
        rec = {"item": f"vn{i}", "item_en": name, "item_id": name.lower().replace(" ", "_")}
        rec.update({p: v * k for p, v in zip(periods, vals)})
        recs.append(rec)
    return pd.DataFrame(recs)


def _fin(annual=True, bn=False):
    """Trả [income, balance, cashflow] dạng dọc; kỳ mới nhất đứng đầu như nguồn thật."""
    per = ["2025", "2024", "2023", "2022", "2021", "2020"] if annual else ["2026-Q2", "2026-Q1", "2025-Q4", "2025-Q3", "2025-Q2", "2025-Q1"]
    k = 1e-9 if bn else 1.0
    G = 1e9
    inc = _long({"Sales": [160 * G] * 6, "Sales deductions": [-2 * G] * 6,
                 "Net sales": [150, 140, 130, 120, 110, 100], "Gross profit": [30, 28, 26, 24, 22, 20],
                 "Net profit/(loss) after tax": [14, 13, 12, 11, 10, 9],
                 "Attributable to the parent company": [13, 12, 11, 10, 9, 8],
                 "Basic earnings per share (VND)": [1700] * 6}, per, 1.0)
    for r in range(len(inc)):                       # chỉ nhân G cho các dòng tiền tệ (không phải EPS, dòng Sales đã có G)
        name = inc.loc[r, "item_en"]
        if name in ("Net sales", "Gross profit", "Net profit/(loss) after tax", "Attributable to the parent company"):
            for p_ in per:
                inc.loc[r, p_] = inc.loc[r, p_] * G * k
        elif "earnings per share" not in name:
            for p_ in per:
                inc.loc[r, p_] = inc.loc[r, p_] * k
    bal = _long({"CURRENT ASSETS": [70 * G] * 6, "Cash and cash equivalents": [8 * G] * 6, "TOTAL ASSETS": [160 * G] * 6,
                 "OWNER'S EQUITY": [80 * G] * 6, "Short-term borrowings": [20 * G] * 6}, per, k)
    cf = _long({"Net profit/(loss) before tax": [16 * G] * 6, "Depreciation and amortization": [8 * G] * 6,
                "Net cash inflows/outflows from operating activities": [10 * G] * 6,
                "Purchases of fixed assets and other long-term assets": [-7 * G] * 6}, per, k)
    return [inc, bal, cf]


def test_to_wide_transposes_vnstock_long_format():
    w = nz.to_wide(_fin()[0])
    assert list(w.index)[:2] == ["2025", "2024"] and "Net sales" in w.columns


def test_wide_input_still_supported():
    wide = pd.DataFrame({"yearReport": [2024, 2025], "lengthReport": 5, "Net sales": [1e11, 1.2e11], "TOTAL ASSETS": [2e11, 2.2e11]})
    per, _, _ = nz.normalize_financials([wide], True, "2026-10-09", "src", False)
    assert per[0]["period"] == "2025" and per[0]["items"]["revenue"] == 1.2e11


def test_financials_mapping_units_capex_and_lookahead():
    per, cmap, flags = nz.normalize_financials(_fin(), True, "2026-10-09", "src", False)
    assert [p["period"] for p in per][0] == "2025"            # 2025 công bố ước tính 2026-03-31 <= as_of
    it = per[0]["items"]
    assert it["revenue"] == 150e9                                   # "Net sales", không phải "Sales" (chưa trừ giảm trừ)
    assert it["net_income"] == 14e9 and it["net_income_parent"] == 13e9      # không nhầm "before tax" của dòng tiền
    assert it["total_assets"] == 160e9 and it["total_equity"] == 80e9 and it["cfo"] == 10e9 and it["capex"] == 7e9   # capex luôn dương
    assert it["short_term_debt"] == 20e9 and it["depreciation"] == 8e9 and it["eps"] == 1700
    assert cmap["revenue"] == "Net sales" and cmap["net_income"] == "Net profit/(loss) after tax"
    assert all(p["published_at_estimated"] for p in per)


def test_financials_not_yet_published_excluded():
    per, _, _ = nz.normalize_financials(_fin(), True, "2025-06-30", "src", False)
    assert per[0]["period"] == "2024"                          # 2025 chưa công bố tại 2025-06-30


def test_quarterly_long_format_periods():
    per, _, _ = nz.normalize_financials(_fin(annual=False), False, "2026-10-09", "src", False, keep=8)
    assert [p["period"] for p in per][:2] == ["2026Q2", "2026Q1"]      # Q2/2026 công bố ước tính 2026-08-14 <= as_of
    per2, _, _ = nz.normalize_financials(_fin(annual=False), False, "2026-07-01", "src", False, keep=8)
    assert per2[0]["period"] == "2026Q1"                                # Q2/2026 chưa công bố tại 2026-07-01


def test_financials_billion_vnd_rescaled():
    per, _, flags = nz.normalize_financials(_fin(bn=True), True, "2026-10-09", "src", False)
    assert per[0]["items"]["total_assets"] == 160e9 and any("scaled" in f for f in flags)


def test_company_real_vci_overview_shape():
    df = pd.DataFrame([{"symbol": "HPG", "organ_short_name": "Hòa Phát", "sector": "Basic Resources", "issue_share": 8442964520.0, "is_bank": False}])
    c, flags = nz.normalize_company(df, "HPG", ["VCB"], {"HPG": "HOSE"})
    assert c["name"] == "Hòa Phát" and c["sector"] == "Basic Resources" and not c["is_bank"] and c["exchange"] == "HOSE"
    assert c["shares_outstanding"] == 8442964520.0
    c2, _ = nz.normalize_company(pd.DataFrame([{"symbol": "XYZ", "sector": "Banks", "is_bank": True}]), "XYZ", [])
    assert c2["is_bank"]


def test_company_is_bank_by_ticker_and_by_text():
    df = pd.DataFrame([{"exchange": "HOSE", "icb_name2": "Ngân hàng", "icb_name4": "Ngân hàng", "issue_share": 8e9}])
    c, _ = nz.normalize_company(df, "XYZ", [])
    assert c["is_bank"] and c["shares_outstanding"] == 8e9 and c["exchange"] == "HOSE"
    c2, _ = nz.normalize_company(pd.DataFrame([{"exchange": "HOSE"}]), "VCB", ["VCB"])
    assert c2["is_bank"]


def test_news_filters_future_dedups_and_ids():
    df = pd.DataFrame({"title": ["A tăng", "A tăng", "B giảm", "C tương lai"],
                       "publish_date": [1790000000000, 1790000000000, "2026-09-01", "2026-12-01"],
                       "link": ["u1", "u1", "u2", "u3"]})
    items, _ = nz.normalize_news(df, "2025-10-09", "2026-10-09", "t", 50)
    titles = [i["title"] for i in items]
    assert titles.count("A tăng") == 1 and "C tương lai" not in titles
    assert all(i["id"].startswith("n") and i["published_at"][:10] <= "2026-10-09" for i in items)


def test_news_real_vci_shape_no_article_url_uses_news_id_and_ignores_image_url():
    df = pd.DataFrame({"id": ["6ac2"], "news_id": [12179514], "news_title": ["Hòa Phát hoàn tất góp vốn"], "friendly_title": [None],
                       "news_image_url": ["https://cdn.example/a.jpg"], "news_source_link": [None], "public_date": ["2026-10-03T07:50:00"]})
    items, flags = nz.normalize_news(df, "2025-10-09", "2026-10-09", "vnstock/VCI", 50)
    assert items[0]["id"] == "n12179514" and items[0]["url"] == "n/a"          # không lấy link ảnh làm URL bài
    assert "news_url_missing" in flags and items[0]["title"].startswith("Hòa Phát")


def test_multiples_math():
    rows = [{"date": "2026-10-09", "close": 20000.0}]
    ann = [{"items": {"net_income_parent": 12e9, "net_income": 14e9, "total_equity": 80e9}}]
    m = nz.multiples(rows, ann, 5e9)
    assert m["pe"] == 20000 * 5e9 / 12e9 and m["pb"] == 20000 * 5e9 / 80e9 and abs(m["roe"] - 0.15) < 1e-12
    assert nz.multiples(rows, ann, None) == {} and nz.multiples([], ann, 5e9) == {}


def test_ratio_row_roe_as_fraction():
    df = pd.DataFrame({"yearReport": [2024, 2025], "lengthReport": 5, "ROE (%)": [12.0, 14.0], "P/E": [10.0, 9.0], "P/B": [1.5, 1.4]})
    r = nz.latest_ratio_row(df, "2026-10-09")
    assert abs(r["roe"] - 0.14) < 1e-9 and r["pe"] == 9.0 and r["pb"] == 1.4


def test_aliases_match_real_vci_item_names():
    """Danh sách tên chỉ tiêu THẬT của VCI (HPG, lấy từ probe_data.py). Hỏng test này = nguồn đổi tên chỉ tiêu hoặc alias bị sửa sai."""
    from pathlib import Path
    sections, cur = {}, None
    for line in (Path(__file__).parent / "data" / "vci_hpg_items.txt").read_text(encoding="utf-8").splitlines():
        if line.startswith("---"):
            cur = line.strip("- ").strip(); sections[cur] = []
        else:
            iid, en = line.split(" | ", 1); sections[cur].append((iid, en))
    per = ["2025", "2024", "2023"]
    frames = [pd.DataFrame([{"item": en, "item_en": en, "item_id": iid, **{p: float(i + 1) * 1e9 for p in per}}
                            for i, (iid, en) in enumerate(sections[k])]) for k in ("income", "balance", "cashflow")]
    _, cmap, flags = nz.normalize_financials(frames, True, "2026-10-09", "s", False)
    expect = {"revenue": "Net sales", "gross_profit": "Gross Profit", "ebit": "Operating profit/(loss)",
              "net_income": "Net profit/(loss) after tax", "net_income_parent": "Attributable to parent company",
              "interest_expense": "Interest expenses", "depreciation": "Depreciation and amortization", "eps": "EPS basic (VND)",
              "total_assets": "Total Assets", "total_equity": "Owner's Equity", "total_liabilities": "Liabilities",
              "current_assets": "CURRENT ASSETS", "current_liabilities": "Current liabilities", "inventory": "Inventories, Net",
              "cash": "Cash and cash equivalents", "short_term_debt": "Short-term borrowings", "long_term_debt": "Long-term borrowings",
              "cfo": "Net cash inflows/(outflows) from operating activities", "cfi": "Net cash inflows/(outflows) from investing activities",
              "cff": "Net cash inflows/(outflows) from financing activities",
              "capex": "Purchases of fixed assets and other long term assets"}
    assert cmap == expect and not any("unmatched" in f for f in flags)
