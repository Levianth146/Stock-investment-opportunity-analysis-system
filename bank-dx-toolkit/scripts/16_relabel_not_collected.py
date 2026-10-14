"""Tách 'chưa thu thập' khỏi 'không công bố' trong ô TRỐNG của out/dti_inputs.csv.
  python 16_relabel_not_collected.py            # dry-run: đếm theo loại ghi chú
  python 16_relabel_not_collected.py --apply    # sao lưu out/dti_inputs.backup_<giờ>.csv rồi đổi ghi chú
Chỉ đụng ô TRỐNG (value rỗng) có ghi chú chung chung:
  not_disclosed_or_no_reliable_candidate[...]  -> 'not_collected: chưa tìm tay trong BCTN/BCTC'
  missing_candidate_needs_manual               -> 'not_collected [TODO]: cần đọc tay (script không có ứng viên)'
Ô đã tìm tay và ghi lý do cụ thể ('not_disclosed: ...', 'not_disclosed; ...', 'định nghĩa khác ...') GIỮ NGUYÊN.
Khi bạn tìm tay xong mà không thấy: sửa note thành 'not_disclosed: <đã tìm ở đâu, vì sao không có>'. Không điền 0."""
import argparse, datetime, os, shutil
import pandas as pd
from common import *

ap = argparse.ArgumentParser(); ap.add_argument("--apply", action="store_true"); ap.add_argument("--file", default=str(OUT / "dti_inputs.csv"))
a = ap.parse_args()
p = pathlib.Path(a.file)
d = pd.read_csv(p, encoding="utf-8-sig", dtype={"note": str, "confirmed_by": str, "unit": str, "source_file": str})
note = d.note.fillna(""); empty = d.value.isna()
m_gen = empty & note.str.startswith("not_disclosed_or_no_reliable_candidate")
m_todo = empty & note.str.startswith("missing_candidate_needs_manual")
m_done = empty & note.str.startswith(("not_disclosed:", "not_disclosed;")) | (empty & note.str.startswith(("not_disclosed")) & ~m_gen)
print(f"Ô trống: {int(empty.sum())} | chưa tìm (generic): {int(m_gen.sum())} | TODO (missing_candidate): {int(m_todo.sum())} | đã tìm tay/có lý do cụ thể: {int((empty & ~m_gen & ~m_todo).sum())}")
print("\nTheo năm (generic + TODO):"); print(d[m_gen | m_todo].groupby("year").size().to_string())
print("\nTheo biến:"); print(d[m_gen | m_todo].groupby("variable").size().sort_values(ascending=False).to_string())
if a.apply and (m_gen | m_todo).any():
    bk = OUT / f"dti_inputs.backup_{datetime.datetime.now():%Y%m%d_%H%M%S}.csv"; shutil.copy2(p, bk)
    d.loc[m_gen, "note"] = "not_collected: chưa tìm tay trong BCTN/BCTC"
    d.loc[m_todo, "note"] = "not_collected [TODO]: cần đọc tay (script không có ứng viên)"
    tmp = p.with_suffix(".tmp"); d.to_csv(tmp, index=False, encoding="utf-8-sig"); os.replace(tmp, p)
    print("\nĐã ghi", p, "| sao lưu:", bk.name)
elif not a.apply: print("\n(dry-run — thêm --apply để ghi)")
