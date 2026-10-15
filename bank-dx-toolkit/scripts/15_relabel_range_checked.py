"""Tách ô 'đã mở PDF đối chiếu' khỏi ô 'chỉ kiểm khoảng hợp lý' trong out/dti_inputs.csv.
  python 15_relabel_range_checked.py                        # dry-run: in số ô sẽ đổi
  python 15_relabel_range_checked.py --apply                # sao lưu out/dti_inputs.backup_<ngày giờ>.csv rồi đổi nhãn
  python 15_relabel_range_checked.py --sample 15 --seed 1   # danh sách ô range-checked cần MỞ PDF kiểm tay (phân tầng theo NH, ưu tiên VCB/Agribank OCR)
Quy tắc: confirmed_by='nam' mà note vẫn là chuỗi ứng viên tự động (fin-cand/page-patch/page-confirm/kpi-) => 'range-checked'
(chỉ qua kiểm ROA/ROE/CASA/xu hướng, CHƯA ai đọc PDF). Ô bạn đã đọc PDF (note mô tả trang/dòng) giữ 'nam'.
Sau khi mở PDF: python 14_triage_dti.py --apply --confirm bank:year:var,... --by nam   (range-checked -> nam)"""
import argparse, datetime, math, os, random, shutil
import pandas as pd
from common import *

ap = argparse.ArgumentParser()
ap.add_argument("--apply", action="store_true"); ap.add_argument("--sample", type=int, default=0); ap.add_argument("--seed", type=int, default=1)
ap.add_argument("--file", default=str(OUT / "dti_inputs.csv"))
a = ap.parse_args()
RAW = ("fin-cand", "page-patch", "page-confirm", "kpi-")
p = pathlib.Path(a.file)
d = pd.read_csv(p, encoding="utf-8-sig", dtype={"note": str, "confirmed_by": str, "unit": str, "source_file": str})
note = d.note.fillna("")
m_nam = (d.confirmed_by == "nam") & d.value.notna() & note.str.startswith(RAW)
m_rc = (d.confirmed_by == "range-checked") & d.value.notna()
print(f"nam + note là chuỗi OCR thô: {int(m_nam.sum())} ô (sẽ -> range-checked) | đã là range-checked: {int(m_rc.sum())} ô")
print(d[m_nam].groupby("bank").size().to_string())

if a.apply and m_nam.any():
    bk = OUT / f"dti_inputs.backup_{datetime.datetime.now():%Y%m%d_%H%M%S}.csv"; shutil.copy2(p, bk)
    d.loc[m_nam, "note"] = note[m_nam] + " | range-check (ROA/ROE/CASA/xu hướng), CHƯA đối chiếu PDF"
    d.loc[m_nam, "confirmed_by"] = "range-checked"
    tmp = p.with_suffix(".tmp"); d.to_csv(tmp, index=False, encoding="utf-8-sig"); os.replace(tmp, p)
    print("Đã ghi", p, "| sao lưu:", bk.name)
elif not a.apply:
    print("(dry-run — thêm --apply để ghi)")

if a.sample:
    pool = d[(m_nam | m_rc)].copy()
    W = {"vcb": 4, "agribank": 4, "bidv": 3, "mb": 2, "tcb": 2}; tot = sum(W.values()); rng = random.Random(a.seed); pick = []
    for b, w in W.items():
        g = pool[pool.bank == b]; k = min(len(g), max(1, math.ceil(a.sample * w / tot)))
        pick += rng.sample(list(g.index), k)
    s = pool.loc[pick].sort_values(["bank", "year", "variable"])
    print(f"\nMở PDF kiểm {len(s)} ô (cột: bank year variable value page file):")
    for _, r in s.iterrows(): print(f"  {r.bank:9} {int(r.year)} {r.variable:27} {r.value:>16,.0f}  p{r.page}  {str(r.source_file)[-40:]}")
    print("\nKhớp PDF -> nhập vào lệnh:  python 14_triage_dti.py --apply --confirm " + ",".join(f"{r.bank}:{int(r.year)}:{r.variable}" for _, r in s.iterrows()) + " --by nam")
    print("Chỗ nào KHÔNG khớp: sửa số + page + note trong dti_inputs.csv rồi mới confirm; nếu >1 ô sai trong mẫu, mở rộng mẫu cho NH đó.")
