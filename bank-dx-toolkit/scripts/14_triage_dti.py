"""Phân loại lại out/dti_inputs.csv: tách số ĐÃ kiểm tay khỏi số tự động, bỏ KPI đoán, đánh dấu ô nghi sai.
  python 14_triage_dti.py                       # chạy thử (dry-run), chỉ in những gì SẼ đổi
  python 14_triage_dti.py --apply               # ghi thật (tự sao lưu out/dti_inputs.backup_<ngày giờ>.csv)
  python 14_triage_dti.py --apply --confirm tcb:2023:equity,vcb:2020:opex --by nam   # đánh dấu các ô BẠN ĐÃ MỞ PDF xác nhận
  python 14_triage_dti.py --file out/dti_inputs.csv --check out/dti_check.csv       # đường dẫn khác (dùng khi thử)
Việc làm khi --apply:
  1) confirmed_by thuộc {fin-cand, page-patch, page-confirm} -> 'auto-unverified' (số do script điền, CHƯA ai mở PDF xác nhận).
  2) confirmed_by = 'kpi-heuristic' -> XÓA giá trị/đơn vị/nguồn/trang, note = not_disclosed_or_no_reliable_candidate (không đoán). Giá trị cũ nằm trong file sao lưu.
  3) Ô có trong out/dti_check.csv (chạy 13_check_dti.py trước) -> thêm 'CẦN KIỂM: <loại>' vào note; không đổi giá trị.
  4) --confirm bank:year:variable[,...] --by TÊN -> confirmed_by = TÊN (chỉ khi ô đang có giá trị). Ô manual-* giữ nguyên.
Không bao giờ điền 0. Không đụng các ô manual-*."""
import argparse, datetime, os, shutil, sys
import pandas as pd
from common import *

ap = argparse.ArgumentParser()
ap.add_argument("--apply", action="store_true"); ap.add_argument("--confirm", default=""); ap.add_argument("--by", default="")
ap.add_argument("--file", default=str(OUT / "dti_inputs.csv")); ap.add_argument("--check", default=str(OUT / "dti_check.csv"))
a = ap.parse_args()
if a.confirm and not a.by: sys.exit("--confirm cần --by TÊN (người đã mở PDF đối chiếu).")

p = pathlib.Path(a.file)
d = pd.read_csv(p, encoding="utf-8-sig", dtype={"note": str, "confirmed_by": str, "unit": str, "source_file": str})
AUTO = {"fin-cand", "page-patch", "page-confirm"}
log = []

m = d.confirmed_by.isin(AUTO) & d.value.notna()
log.append(f"1) {int(m.sum())} ô số tự động -> confirmed_by='auto-unverified'")
d.loc[m, "confirmed_by"] = "auto-unverified"

m = (d.confirmed_by == "kpi-heuristic")
log.append(f"2) {int(m.sum())} ô KPI heuristic -> xóa giá trị (có {int(d.loc[m, 'value'].notna().sum())} ô đang có số)")
for c in ("value", "unit", "source_file", "page"): d.loc[m, c] = pd.NA
d.loc[m, "confirmed_by"] = pd.NA
d.loc[m, "note"] = "not_disclosed_or_no_reliable_candidate (heuristic cũ đã xóa, đọc tay từ BCTN)"

cp = pathlib.Path(a.check)
if cp.exists():
    ck = pd.read_csv(cp, encoding="utf-8-sig")
    n = 0
    for (b, y, v), g in ck.groupby(["bank", "year", "variable"]):
        for var in str(v).split("/")[0].split(","):
            idx = d.index[(d.bank == b) & (d.year == y) & (d.variable == var.strip()) & d.value.notna()]
            for i in idx:
                tag = "CẦN KIỂM: " + ",".join(sorted(set(g.kind)))
                old = d.at[i, "note"] if isinstance(d.at[i, "note"], str) else ""
                if tag not in old: d.at[i, "note"] = (old + " | " if old else "") + tag; n += 1
    log.append(f"3) {n} ô bị gắn 'CẦN KIỂM' theo {cp.name}")
else:
    log.append(f"3) bỏ qua: chưa có {cp.name} (chạy 13_check_dti.py trước)")

if a.confirm:
    n = 0
    for item in a.confirm.split(","):
        b, y, v = item.strip().split(":")
        idx = d.index[(d.bank == b) & (d.year == int(y)) & (d.variable == v) & d.value.notna() & ~d.confirmed_by.fillna("").str.startswith("manual")]
        for i in idx:
            d.at[i, "confirmed_by"] = a.by
            note = d.at[i, "note"] if isinstance(d.at[i, "note"], str) else ""
            d.at[i, "note"] = note.replace("CẦN KIỂM", "đã kiểm").strip(" |")
            n += 1
        if len(idx) == 0: log.append(f"   (không tìm thấy ô có số cho {item})")
    log.append(f"4) {n} ô được {a.by} xác nhận")

print("\n".join(log))
print("\nPhân bố confirmed_by sau khi đổi:", d.confirmed_by.fillna("(trống)").value_counts().to_dict())
print(f"Ô có số: {int(d.value.notna().sum())}/{len(d)}")
if not a.apply:
    print("\n[DRY-RUN] chưa ghi gì. Thêm --apply để ghi thật."); sys.exit(0)
bk = p.with_name(f"dti_inputs.backup_{datetime.datetime.now():%Y%m%d_%H%M%S}.csv"); shutil.copy(p, bk)
tmp = p.with_suffix(".csv.tmp"); d.to_csv(tmp, index=False, encoding="utf-8-sig"); os.replace(tmp, p)
print(f"\nĐã ghi {p}. Bản sao lưu: {bk}")
