# -*- coding: utf-8 -*-
"""Bước 3–5: sửa note/giá trị out/dti_inputs.csv (không điền 0)."""
import pandas as pd
from common import OUT

p = OUT / "dti_inputs.csv"
d = pd.read_csv(p, encoding="utf-8-sig", dtype={"note": str, "confirmed_by": str, "unit": str, "source_file": str, "definition": str})


def idx(bank, year, var):
    m = (d.bank == bank) & (d.year == year) & (d.variable == var)
    assert m.sum() == 1, (bank, year, var, m.sum())
    return d.index[m][0]


def set_row(i, **kw):
    for k, v in kw.items():
        d.at[i, k] = v


# ---------- Bước 3: refine notes (giá trị giữ đúng PDF) ----------
# 1) mb 2020 nci — chọn số BCTC 2020 (2.152.881); note cả hai
set_row(
    idx("mb", 2020, "nci"),
    value=2152881.0,
    unit="VND million",
    source_file="data/raw/mb/2020_bctc.pdf",
    page=11.0,
    note=(
        "BCTC2020 CĐKT p11: NCI 2.152.881 (OCR cùng năm). "
        "BCTC2021 p11 cột 2020 trình bày lại = 2.192.991 / TỔNG VCSH 50.099.495. "
        "Chọn số báo cáo năm 2020; parent=50.055.485−2.152.881=47.902.604"
    ),
    definition="nci",
)

# 2) mb 2021 nci — BCTC2022 p11 cột 2021 = 2.911.788 (không phải 2.911.188)
set_row(
    idx("mb", 2021, "nci"),
    value=2911788.0,
    unit="VND million",
    source_file="data/raw/mb/2022_bctc.pdf",
    page=11.0,
    note=(
        "BCTC2022 CĐKT p11 cột 2021: NCI 2.911.788 (đã đối PDF). "
        "BCTC2021 p11 OCR từng ghi 2.911.188 — sai/OCR; không dùng. "
        "parent=62.486.023−2.911.788=59.574.235"
    ),
    definition="nci",
)

# 3) agribank 2021 nci — p90 đúng là CĐKT (nợ/VSH), số 1.166.940
set_row(
    idx("agribank", 2021, "nci"),
    value=1166940.0,
    unit="VND million",
    source_file="data/raw/agribank/2021_bctc.pdf",
    page=90.0,
    note=(
        "BCTC2021 p90 = phần VỐN CHỦ SỞ HỮU của Bảng CĐKT hợp nhất (OCR; front p7–9 ảnh trống). "
        "NCI (Lợi ích CĐ thiếu số) 1.166.940; TỔNG VCSH 76.087.340 → parent=74.920.400. Đã xác nhận không phải bảng rủi ro."
    ),
    definition="nci",
)

# 4) agribank 2020 headcount — giữ approx 40.000
set_row(
    idx("agribank", 2020, "headcount"),
    value=40000.0,
    unit="persons",
    source_file="data/raw/agribank/2020_bctn.pdf",
    page=25.0,
    note=(
        "approx; BCTN p25: 'gần 4 vạn người lao động trong toàn hệ thống'; "
        "p23: 'gần 40.000 cán bộ Agribank' — không có số exact; giữ lower-bound làm tròn 40.000"
    ),
    definition="group_approx",
)

# 5) bidv headcount 2020/2021/2022
set_row(
    idx("bidv", 2020, "headcount"),
    value=26752.0,
    unit="persons",
    source_file="data/raw/bidv/2021_bctn.pdf",
    page=79.0,
    note="BCTN 2021 p79 bảng HUMAN RESOURCE GROWTH 2019–2021: Total employees 2020 = 26,752. Đã đối PDF bước 3.",
    definition="unspecified",
)
set_row(
    idx("bidv", 2021, "headcount"),
    value=27223.0,
    unit="persons",
    source_file="data/raw/bidv/2021_bctn.pdf",
    page=79.0,
    note="BCTN 2021 p79: Total employees 2021 = 27,223. Đã đối PDF bước 3.",
    definition="unspecified",
)
set_row(
    idx("bidv", 2022, "headcount"),
    value=28435.0,
    unit="persons",
    source_file="data/raw/bidv/2022_bctn.pdf",
    page=39.0,
    note="BCTN 2022 p39: TOTAL EMPLOYEES as of 31/12/2022 = 28,435 (+~1,000 vs 2021). Đã đối PDF bước 3.",
    definition="unspecified",
)

# 6) bidv 2022 total_customers — 15.5M lower bound
set_row(
    idx("bidv", 2022, "total_customers"),
    value=15500000.0,
    unit="customers",
    source_file="data/raw/bidv/2022_bctn.pdf",
    page=11.0,
    note=(
        "lower_bound; BCTN p11: 'more than 15 million individual customers and 500,000 corporate customers' "
        "→ ≈15.5M (cộng cận dưới hai phân khúc). Không phải số đếm chính xác."
    ),
    definition="retail+corporate",
)

# ---------- Bước 5: điền / gắn not_disclosed ----------
# headcount VCB
set_row(
    idx("vcb", 2021, "headcount"),
    value=21670.0,
    unit="persons",
    source_file="data/raw/vcb/2021_bctn.pdf",
    page=42.0,
    confirmed_by="nam",
    note="BCTN p42/p65/p78: Tổng số lao động Vietcombank tính đến 31/12/2021 = 21.670 người.",
    definition="unspecified",
)
set_row(
    idx("vcb", 2022, "headcount"),
    value=22599.0,
    unit="persons",
    source_file="data/raw/vcb/2022_bctn.pdf",
    page=47.0,
    confirmed_by="nam",
    note="BCTN p46/p47/p72: Tổng số lao động Vietcombank tính đến 31/12/2022 = 22.599 người.",
    definition="unspecified",
)

# headcount Agribank
set_row(
    idx("agribank", 2021, "headcount"),
    value=pd.NA,
    unit=pd.NA,
    source_file=pd.NA,
    page=pd.NA,
    confirmed_by="nam",
    note="not_disclosed: đã đọc BCTN 2021 trang 14,33–47 (mục nhân sự/lao động), không có tổng lao động exact",
    definition=pd.NA,
)
set_row(
    idx("agribank", 2022, "headcount"),
    value=40909.0,
    unit="persons",
    source_file="data/raw/agribank/2022_bctn.pdf",
    page=63.0,
    confirmed_by="nam",
    note="BCTN p63/p65: số lượng lao động tại Agribank = 40.909 người (nữ >22.000 ≈54%).",
    definition="group",
)
set_row(
    idx("agribank", 2024, "headcount"),
    value=42278.0,
    unit="persons",
    source_file="data/raw/agribank/2024_bctn.pdf",
    page=30.0,
    confirmed_by="nam",
    note="BCTN p30 TỔNG SỐ LAO ĐỘNG = 42.278; p45: đạt 42.278 (+195 vs 2023).",
    definition="group",
)

# digital_txn_share Agribank
set_row(
    idx("agribank", 2020, "digital_txn_share"),
    value=pd.NA,
    unit="%",
    source_file=pd.NA,
    page=pd.NA,
    confirmed_by="nam",
    note="not_disclosed: đã đọc BCTN 2020 (toàn văn text), không có % GD kênh số exact",
    definition=pd.NA,
)
set_row(
    idx("agribank", 2021, "digital_txn_share"),
    value=pd.NA,
    unit="%",
    source_file=pd.NA,
    page=pd.NA,
    confirmed_by="nam",
    note="not_disclosed: đã đọc BCTN 2021 trang 1–50 (tìm kênh số / tỷ lệ GD), không có % GD kênh số exact",
    definition=pd.NA,
)
set_row(
    idx("agribank", 2022, "digital_txn_share"),
    value=91.0,
    unit="%",
    source_file="data/raw/agribank/2024_bctn.pdf",
    page=30.0,
    confirmed_by="nam",
    note=(
        "BCTN 2024 p30 (cột so sánh): Tỷ lệ giao dịch qua kênh số năm 2022 = 91% "
        "(2024=96%). BCTN2022 p44 nêu GD tự động 91,97% — định nghĩa hơi khác; chọn 91% 'kênh số'."
    ),
    definition="all_txn",
)
set_row(
    idx("agribank", 2024, "digital_txn_share"),
    value=96.0,
    unit="%",
    source_file="data/raw/agribank/2024_bctn.pdf",
    page=30.0,
    confirmed_by="nam",
    note="BCTN p30: Tỷ lệ giao dịch qua kênh số = 96% (2024); so sánh 91% (2022).",
    definition="all_txn",
)

# total_customers Agribank 2024 — không thấy tổng
set_row(
    idx("agribank", 2024, "total_customers"),
    value=pd.NA,
    unit=pd.NA,
    source_file=pd.NA,
    page=pd.NA,
    confirmed_by="nam",
    note="not_disclosed: đã đọc BCTN 2024 trang 4–52; chỉ có Mobile Banking >16M / Agribank Plus >10M — không có tổng KH toàn hàng",
    definition=pd.NA,
)

# BIDV total_customers + digital_txn
set_row(
    idx("bidv", 2020, "total_customers"),
    value=11900000.0,
    unit="customers",
    source_file="data/raw/bidv/2020_bctn.pdf",
    page=26.0,
    confirmed_by="nam",
    note=(
        "lower_bound; BCTN EN p26: more than 11.6 million individual + more than 300,000 business "
        "≈ 11.9M (cộng cận dưới). Không phải số đếm chính xác."
    ),
    definition="retail+corporate",
)
set_row(
    idx("bidv", 2021, "total_customers"),
    value=pd.NA,
    unit=pd.NA,
    source_file=pd.NA,
    page=pd.NA,
    confirmed_by="nam",
    note="not_disclosed: đã đọc BCTN 2021 trang 1–30,40–60; không có tổng KH exact (chỉ metrics SmartBanking/iBank)",
    definition=pd.NA,
)
set_row(
    idx("bidv", 2024, "total_customers"),
    value=22500000.0,
    unit="customers",
    source_file="data/raw/bidv/2024_bctn.pdf",
    page=45.0,
    confirmed_by="nam",
    note=(
        "lower_bound; BCTN EN p5/p45: nearly 22 million individual + nearly 500,000 corporate "
        "≈ 22.5M (cộng cận dưới hai phân khúc)."
    ),
    definition="retail+corporate",
)
set_row(
    idx("bidv", 2024, "digital_txn_share"),
    value=pd.NA,
    unit="%",
    source_file=pd.NA,
    page=pd.NA,
    confirmed_by="nam",
    note="not_disclosed: đã đọc BCTN 2024 (digital/transaction); chỉ thấy % số hóa quy trình nội bộ (vd 90% cash processes) — không có % GD kênh số exact",
    definition=pd.NA,
)

# VCB total_customers + digital_txn (các năm còn not_collected ưu tiên)
for year, pages in [
    (2020, "1–41"),
    (2021, "1–20,42–78"),
    (2022, "1–43,69"),
    (2024, "1–53,92"),
]:
    set_row(
        idx("vcb", year, "total_customers"),
        value=pd.NA,
        unit=pd.NA,
        source_file=pd.NA,
        page=pd.NA,
        confirmed_by="nam",
        note=f"not_disclosed: đã đọc BCTN {year} trang {pages}; không có tổng KH exact (chỉ Digibank / KH mới / chuyển đổi)",
        definition=pd.NA,
    )
    set_row(
        idx("vcb", year, "digital_txn_share"),
        value=pd.NA,
        unit="%",
        source_file=pd.NA,
        page=pd.NA,
        confirmed_by="nam",
        note=f"not_disclosed: đã đọc BCTN {year} trang {pages}; không có % GD kênh số exact",
        definition=pd.NA,
    )

tmp = p.with_suffix(".csv.tmp")
d.to_csv(tmp, index=False, encoding="utf-8-sig")
tmp.replace(p)
print(f"Đã ghi {p}")
print("Ô có số:", int(d.value.notna().sum()), "/", len(d))
