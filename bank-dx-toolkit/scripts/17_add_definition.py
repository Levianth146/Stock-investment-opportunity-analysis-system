"""Thêm cột `definition` + 2 biến phụ vào out/dti_inputs.csv (không đổi số liệu hiện có).
  python 17_add_definition.py            # dry-run: in nhãn định nghĩa sẽ gắn tự động để BẠN RÀ LẠI
  python 17_add_definition.py --apply    # sao lưu out/dti_inputs.backup_<giờ>.csv rồi ghi
Việc làm:
  1) thêm cột `definition` (ô đã có nhãn thì giữ nguyên, chạy lại không ghi đè nhãn bạn sửa tay).
  2) gắn nhãn tự động từ `note` cho: digital_customers, total_customers, digital_txn_share, training_hours_per_head, headcount, equity.
  3) thêm biến `digital_customer_share` (%; K-Q2 cách 2: tỷ lệ KH số do ngân hàng công bố) và `nci` (VND million; để chuẩn hóa
     equity về vốn cổ đông mẹ = tổng vốn CSH − NCI) cho mọi NH x năm, ô trống ghi 'not_collected'.
Nhãn là GỢI Ý từ ghi chú — sai thì sửa thẳng cột `definition` trong dti_inputs.csv. KHÔNG điền 0."""
import argparse, datetime, os, re, shutil
import pandas as pd
from common import *
banks = load_yaml("banks.yaml"); BK = list(banks["banks"]); YEARS = banks["years"]

ap = argparse.ArgumentParser(); ap.add_argument("--apply", action="store_true"); ap.add_argument("--file", default=str(OUT / "dti_inputs.csv"))
a = ap.parse_args()
p = pathlib.Path(a.file)
d = pd.read_csv(p, encoding="utf-8-sig", dtype=str)
if "definition" not in d.columns: d["definition"] = pd.NA
has = lambda s, *pats: any(re.search(x, s, re.I) for x in pats)

def tag(var, n):
    n = n or ""
    if var == "digital_customers":
        if has(n, r"đăng ký|đăng kí|registered|accounts|held"): return "registered"
        if has(n, r"hoạt động|active"): return "active"
        if has(n, r"transact|giao dịch"): return "transacting"
        if has(n, r"sử dụng|users?\b|người dùng"): return "users"
    elif var == "total_customers":
        if has(n, r"gửi tiền|depositor"): return "depositors"
        if has(n, r"ước lượng|lower.?bound|tài khoản"): return "lower_bound_or_accounts"
        if has(n, r"không phải toàn bộ|subset|sử dụng dịch vụ"): return "subset"
        if has(n, r"cộng hai|retail and corporate|retail \+"): return "retail+corporate"
        if has(n, r"cumulative"): return "cumulative"
        return "total"
    elif var == "digital_txn_share":
        if has(n, r"full-line"): return "full_line"
        if has(n, r"retail") and not has(n, r"bán lẻ"): return "retail"
        if has(n, r"sản phẩm|product"): return "product_digitized"
        return "all_txn"
    elif var == "training_hours_per_head":
        if has(n, r"day/") and has(n, r"6h|6 hour|= ?6"): return "days_x6h"
        if has(n, r"including|incl\.") and not has(n, r"không nêu rõ"): return "incl_new_hire"
        return "avg_hours"
    elif var == "headcount":
        return "group" if has(n, r"subsidiar|công ty con|group|hợp nhất|consolidated|bank \+") else "unspecified"
    elif var == "equity":
        if has(n, r"gồm NCI|including NCI"): return "total"
        if has(n, r"[−\-–]\s*NCI|parent|thuộc cổ đông|cổ đông (ngân hàng|NH)"): return "parent"
        return "total"
    return None

VARS = {"digital_customers", "total_customers", "digital_txn_share", "training_hours_per_head", "headcount", "equity"}
m = d.value.notna() & d.variable.isin(VARS) & d.definition.isna()
new = {i: tag(r.variable, r.note if isinstance(r.note, str) else "") for i, r in d[m].iterrows()}
new = {i: t for i, t in new.items() if t}
print(f"Gắn nhãn tự động: {len(new)} ô (ô đã có nhãn giữ nguyên)")
for var in ["digital_customers", "total_customers", "digital_txn_share", "training_hours_per_head", "equity"]:
    print(f"\n== {var}")
    for i, t in sorted(new.items(), key=lambda kv: (d.loc[kv[0], "bank"], d.loc[kv[0], "year"])):
        if d.loc[i, "variable"] == var: print(f"  {d.loc[i,'bank']:9} {d.loc[i,'year']} {t}")

ADD = [("digital_customer_share", "%", "not_collected: tỷ lệ KH số do NH công bố (K-Q2 cách 2)"), ("nci", "VND million", "not_collected: NCI trên CĐKT (chuẩn hóa equity về vốn cổ đông mẹ)")]
have = set(zip(d.bank, d.year, d.variable)); rows = []
for b in BK:
    for y in YEARS:
        for v, u, nt in ADD:
            if (b, str(y), v) not in have: rows.append({"bank": b, "year": str(y), "variable": v, "unit": u, "note": nt})
print(f"\nThêm {len(rows)} dòng biến phụ (digital_customer_share, nci) — trống, chờ bạn nhập")
sug = d[(d.variable == "digital_customers") & d.value.isna() & d.note.fillna("").str.contains(r"\d{2}(?:[.,]\d+)?\s*%")]
for _, r in sug.iterrows(): print(f"Gợi ý nhập digital_customer_share: {r.bank} {r.year} <- note: {str(r.note)[:130]}")

if a.apply:
    bk = p.with_name(f"{p.stem}.backup_{datetime.datetime.now():%Y%m%d_%H%M%S}.csv"); shutil.copy2(p, bk)
    for i, t in new.items(): d.loc[i, "definition"] = t
    if rows: d = pd.concat([d, pd.DataFrame(rows)], ignore_index=True)
    tmp = p.with_suffix(".tmp"); d.to_csv(tmp, index=False, encoding="utf-8-sig"); os.replace(tmp, p)
    print("\nĐã ghi", p, "| sao lưu:", bk.name)
else: print("\n(dry-run — thêm --apply để ghi)")
