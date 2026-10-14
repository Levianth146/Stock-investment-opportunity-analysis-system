"""Kiểm tra chéo out/dti_inputs.csv: bắt số lấy nhầm cột/dòng TRƯỚC khi bàn giao. Không sửa dữ liệu, chỉ ghi out/dti_check.csv.
  python 13_check_dti.py [--bank vcb] [--year 2022]
Ba lớp kiểm tra:
  1) CHÉO NĂM: số năm t phải bằng cột so sánh (năm trước) của báo cáo năm t+1 trong financial_candidates.csv (lệch > 1% -> nghi nhầm cột hoặc BCTC trình bày lại).
  2) TỶ SỐ HỢP LÝ: vốn/tài sản, tiền gửi/tài sản, CASA, CIR, ROE, ROA nằm trong khoảng thường gặp của ngân hàng Việt Nam.
  3) BIẾN ĐỘNG NĂM: tài sản, vốn, tiền gửi đổi quá +-35%/năm (các biến dòng tiền: +-60%) thì nghi sai.
Một ô bị gắn cờ KHÔNG nhất thiết sai (có thể do trình bày lại hoặc định nghĩa) - chỉ là ô phải mở PDF xem lại. Ô sạch cũng chưa chắc đúng: vẫn phải đối chiếu mẫu ngẫu nhiên >= 10%."""
import sys, csv
import pandas as pd
from common import *

d = pd.read_csv(OUT / "dti_inputs.csv", encoding="utf-8-sig")
fc = pd.read_csv(OUT / "financial_candidates.csv", encoding="utf-8-sig") if (OUT / "financial_candidates.csv").exists() else pd.DataFrame()
V = d.pivot_table(index=["bank", "year"], columns="variable", values="value", aggfunc="first")
issues = []
def add(b, y, var, kind, msg): issues.append([b, y, var, kind, msg])

LEVEL = ["total_assets", "equity", "customer_deposits"]; FLOW = ["net_interest_income", "net_fee_income", "opex", "op_profit_before_provision", "net_profit", "casa_deposits"]
# 3) biến động năm
for (b, y), r in V.iterrows():
    if (b, y - 1) not in V.index: continue
    p = V.loc[(b, y - 1)]
    for var in LEVEL + FLOW:
        a, c = r.get(var), p.get(var)
        if pd.notna(a) and pd.notna(c) and c:
            g = a / c - 1; lim = 0.35 if var in LEVEL else 0.6
            if abs(g) > lim: add(b, y, var, "BIEN_DONG", f"{var} đổi {g:+.0%} so với {y-1} ({c:,.0f} -> {a:,.0f})")
# 2) tỷ số
def ratio(b, y, name, num, den, lo, hi, scale=1):
    n, m = V.loc[(b, y)].get(num), V.loc[(b, y)].get(den)
    if pd.notna(n) and pd.notna(m) and m:
        x = abs(n) / abs(m) * scale
        if not lo <= x <= hi: add(b, y, f"{num}/{den}", "TY_SO", f"{name} = {x:.1f} ngoài [{lo}, {hi}] ({num}={n:,.0f}, {den}={m:,.0f})")
for (b, y) in V.index:
    ratio(b, y, "vốn CSH / tài sản (%)", "equity", "total_assets", 3, 20, 100)
    ratio(b, y, "tiền gửi KH / tài sản (%)", "customer_deposits", "total_assets", 40, 90, 100)
    ratio(b, y, "CASA / tiền gửi KH (%)", "casa_deposits", "customer_deposits", 5, 60, 100)
    ratio(b, y, "LNST / tài sản = ROA (%)", "net_profit", "total_assets", 0.3, 3.5, 100)
    ratio(b, y, "LNST / vốn CSH ~ ROE (%)", "net_profit", "equity", 5, 35, 100)
    r = V.loc[(b, y)]; o, p = r.get("opex"), r.get("op_profit_before_provision")
    if pd.notna(o) and pd.notna(p) and (abs(o) + p):
        cir = abs(o) / (abs(o) + p) * 100
        if not 20 <= cir <= 70: add(b, y, "opex,op_profit", "TY_SO", f"CIR = {cir:.1f}% ngoài [20, 70]")
    n, p = r.get("net_profit"), r.get("op_profit_before_provision")
    if pd.notna(n) and pd.notna(p) and n >= p: add(b, y, "net_profit", "TY_SO", f"LNST ({n:,.0f}) >= LN trước dự phòng ({p:,.0f})")
    if pd.notna(r.get("net_fee_income")) and pd.notna(r.get("net_interest_income")) and r["net_fee_income"] > r["net_interest_income"]: add(b, y, "net_fee_income", "TY_SO", "lãi thuần dịch vụ > thu nhập lãi thuần")
# 1) chéo năm: so với cột so sánh trong báo cáo năm t+1
def second_col(b, y1, var, first):
    if fc.empty: return None
    g = fc[(fc.bank == b) & (fc.year == y1) & (fc.variable == var)]
    for s in g["parsed_numbers(first4)"].astype(str):
        v = [float(x.replace(",", "")) for x in s.split(" | ") if x.strip()]
        if len(v) >= 2 and first and abs(abs(v[0]) / abs(first) - 1) < 0.002: return abs(v[1])
    return None
for (b, y), r in V.iterrows():
    if (b, y + 1) not in V.index: continue
    for var in LEVEL + FLOW + ["opex"]:
        a, nxt = r.get(var), V.loc[(b, y + 1)].get(var)
        if pd.isna(a) or pd.isna(nxt): continue
        c = second_col(b, y + 1, var, abs(nxt))
        if c is not None and abs(abs(a) / c - 1) > 0.01:
            add(b, y, var, "CHEO_NAM", f"giá trị {y} = {abs(a):,.0f} nhưng cột so sánh trong BCTC {y+1} = {c:,.0f} (lệch {abs(a)/c-1:+.1%}): nghi nhầm cột/dòng hoặc trình bày lại")
# 4) lấy nhầm cột: giá trị khớp SỐ THỨ HAI (năm trước) của ứng viên cùng năm nhưng không khớp số thứ nhất
def nums_of(s): return [abs(float(x.replace(",", ""))) for x in str(s).split(" | ") if x.strip()]
for (b, y), r in V.iterrows():
    for var in LEVEL + FLOW:
        a = r.get(var)
        if pd.isna(a) or fc.empty: continue
        g = fc[(fc.bank == b) & (fc.year == y) & (fc.variable == var)]
        firsts = [nums_of(s)[0] for s in g["parsed_numbers(first4)"] if nums_of(s)]
        seconds = [nums_of(s)[1] for s in g["parsed_numbers(first4)"] if len(nums_of(s)) > 1]
        if firsts and not any(abs(abs(a) / f - 1) < 0.002 for f in firsts) and any(abs(abs(a) / sc - 1) < 0.002 for sc in seconds):
            add(b, y, var, "NHAM_COT", f"giá trị {abs(a):,.0f} trùng cột NĂM TRƯỚC của báo cáo {y}, không trùng cột năm {y}")
out = pd.DataFrame(issues, columns=["bank", "year", "variable", "kind", "message"]).drop_duplicates().sort_values(["bank", "year", "variable"])
if "--bank" in sys.argv or "--year" in sys.argv:
    out = out[[keep(r.bank, r.year) for r in out.itertuples()]]
out.to_csv(OUT / "dti_check.csv", index=False, encoding="utf-8-sig")
tot = d[d.value.notna()].shape[0]
print(f"{len(out)} cảnh báo trên {tot} ô có số  ->  {OUT / 'dti_check.csv'}")
print(out.groupby(["bank", "kind"]).size().unstack(fill_value=0).to_string())
bad = out[["bank", "year", "variable"]].drop_duplicates()
print(f"\nSố ô nghi sai (duy nhất): {len(bad)}")
