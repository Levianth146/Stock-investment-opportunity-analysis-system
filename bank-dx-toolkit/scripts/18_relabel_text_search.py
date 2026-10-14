"""Ô TRỐNG ghi 'not_disclosed: ... không thấy ... trong text' thực ra chỉ là tìm bằng từ khóa trong text trích (chưa ai đọc PDF).
  python 18_relabel_text_search.py            # dry-run: liệt kê
  python 18_relabel_text_search.py --apply    # sao lưu rồi đổi note thành 'not_collected: ...' (giữ nguyên lý do cũ ở cuối)
Chỉ đụng ô TRỐNG có note bắt đầu 'not_disclosed' và chứa 'không thấy' / 'chưa chốt' / 'text đã'.
Khi bạn đọc tay xong mà vẫn không có: đặt lại 'not_disclosed: đã đọc BCTN trang X-Y, không có'."""
import argparse, datetime, os, re, shutil
import pandas as pd
from common import *
ap = argparse.ArgumentParser(); ap.add_argument("--apply", action="store_true"); ap.add_argument("--file", default=str(OUT / "dti_inputs.csv"))
a = ap.parse_args(); p = pathlib.Path(a.file)
d = pd.read_csv(p, encoding="utf-8-sig", dtype={"note": str, "confirmed_by": str, "unit": str, "source_file": str})
note = d.note.fillna("")
m = d.value.isna() & note.str.startswith("not_disclosed") & note.str.contains(r"không thấy|chưa chốt|text đã", regex=True)
print(f"{int(m.sum())} ô trống bị gắn not_disclosed nhưng chỉ là tìm text:")
print(d[m].groupby(["bank", "variable"]).year.apply(lambda s: ",".join(s.astype(str))).to_string())
if a.apply and m.any():
    bk = OUT / f"dti_inputs.backup_{datetime.datetime.now():%Y%m%d_%H%M%S}.csv"; shutil.copy2(p, bk)
    d.loc[m, "note"] = "not_collected: tìm bằng từ khóa trong text, chưa đọc tay PDF | " + note[m].str.replace(r"^not_disclosed:?\s*", "", regex=True)
    tmp = p.with_suffix(".tmp"); d.to_csv(tmp, index=False, encoding="utf-8-sig"); os.replace(tmp, p)
    print("\nĐã ghi", p, "| sao lưu:", bk.name)
elif not a.apply: print("\n(dry-run — thêm --apply để ghi)")
