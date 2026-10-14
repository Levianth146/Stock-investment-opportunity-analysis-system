# -*- coding: utf-8 -*-
"""Vá tay các ô DTI đã đối chiếu từ text trang (peek) — ưu tiên 2020/2023/2025.
Không ghi 0; KPI không chắc → để trống + not_disclosed."""
import csv
from pathlib import Path
from common import is_manual_confirmation

OUT = Path(__file__).resolve().parents[1] / "out" / "dti_inputs.csv"

# (bank, year, variable, value, unit, source_file, page, confirmed_by, note)
PATCHES = [
    # ---- VCB 2020 (BCTC VI, peek p8/9/11) ----
    ("vcb", "2020", "total_assets", "1326230092", "VND million", "data/raw/vcb/2020_bctc.pdf", "8", "page-patch",
     "CĐKT p8: TONG TÀI SẲN CO — số cuối trang 1.326.230.092 (khớp TỔNG NỢ+VCSH p9)"),
    ("vcb", "2020", "customer_deposits", "1032113567", "VND million", "data/raw/vcb/2020_bctc.pdf", "9", "page-patch",
     "CĐKT p9: Ill Tiền gửi cia khách hang 1.032.113.567"),
    ("vcb", "2020", "net_fee_income", "6607317", "VND million", "data/raw/vcb/2020_bctc.pdf", "11", "page-patch",
     "KQKD p11: Lai thuần HĐ dịch vụ 6.607.317 (OCR 'Lai thud')"),
    # equity/opex/NII/op_profit/casa/net_profit đã có fin-cand ổn

    # ---- VCB 2023 ----
    ("vcb", "2023", "total_assets", "1839613198", "VND million", "data/raw/vcb/2023_bctc.pdf", "9", "page-patch",
     "CĐKT p9: TONG TAI SAN CO — số cuối 1.839.613.198 (khớp p10 TỔNG NỢ+VCSH)"),
    ("vcb", "2023", "equity", "165012666", "VND million", "data/raw/vcb/2023_bctc.pdf", "10", "page-patch",
     "CĐKT p10: TONG VON CHU SO HUU 165.012.666"),
    ("vcb", "2023", "customer_deposits", "1395697611", "VND million", "data/raw/vcb/2023_bctc.pdf", "10", "page-patch",
     "CĐKT p10: IH Tiền gửi của khách hang 1.395.697.611"),
    ("vcb", "2023", "net_profit", "33033203", "VND million", "data/raw/vcb/2023_bctc.pdf", "13", "page-patch",
     "KQKD p13: XV Lợi nhuận thuần của cổ đông Ngân hàng 33.033.203 (ưu tiên ROE)"),
    # KQKD 2023 thiếu phần đầu trên p13 — thử p12 nếu có trong candidates; để trống NII/opex nếu chưa thấy
    # casa: tổng KKH cần dòng "Tiền gửi không kỳ hạn" tổng — không lấy chỉ ngoại tệ

    # ---- VCB 2023 KQKD p12 (nhãn/số tách dòng) ----
    ("vcb", "2023", "net_interest_income", "53620869", "VND million", "data/raw/vcb/2023_bctc.pdf", "12", "page-patch",
     "KQKD p12: NII 53.620.869 (khối số)"),
    ("vcb", "2023", "net_fee_income", "5779723", "VND million", "data/raw/vcb/2023_bctc.pdf", "12", "page-patch",
     "KQKD p12: Lãi thuần HĐ DV 5.779.723"),
    ("vcb", "2023", "opex", "21914899", "VND million", "data/raw/vcb/2023_bctc.pdf", "12", "page-patch",
     "KQKD p12: VII CHI PHI HOAT DONG 21.914.899 trị tuyệt đối"),
    ("vcb", "2023", "op_profit_before_provision", "45808563", "VND million", "data/raw/vcb/2023_bctc.pdf", "12", "page-patch",
     "KQKD p12: LN trước dự phòng 45.808.563; TOI 67.723.462"),
    # ---- VCB 2025 ----
    ("vcb", "2025", "total_assets", "2442279166", "VND million", "data/raw/vcb/2025_bctc.pdf", "8", "page-patch",
     "CĐKT p8: TONG TÀI SẲN CO — số cuối 2.442.279.166"),
    ("vcb", "2025", "net_interest_income", "58771410", "VND million", "data/raw/vcb/2025_bctc.pdf", "11", "page-patch",
     "KQKD p11: NII 58.771.410"),
    ("vcb", "2025", "net_fee_income", "3469867", "VND million", "data/raw/vcb/2025_bctc.pdf", "11", "page-patch",
     "KQKD p11: Lãi thuần HĐ DV 3.469.867"),
    ("vcb", "2025", "opex", "25242799", "VND million", "data/raw/vcb/2025_bctc.pdf", "11", "page-patch",
     "KQKD p11: Chi phí HĐ 25.242.799 trị tuyệt đối"),
    ("vcb", "2025", "op_profit_before_provision", "47211823", "VND million", "data/raw/vcb/2025_bctc.pdf", "11", "page-patch",
     "KQKD p11: LN trước dự phòng 47.211.823 (OCR 47211.823); TOI 72.454.622"),
]

# More patches from peeks / financial candidates cross-check
PATCHES += [
    # Agribank 2020
    ("agribank", "2020", "total_assets", "1568126913", "VND million", "data/raw/agribank/2020_bctc.pdf", "8", "page-patch",
     "CĐKT p8: TONG NO PHAI TRA VA VON CHU SỞ HỮU 1.568.126.913 (= tổng tài sản cuối kỳ; thay số năm trước 1.452.213.413)"),
    ("agribank", "2020", "equity", "73084295", "VND million", "data/raw/agribank/2020_bctc.pdf", "8", "page-patch",
     "CĐKT p8: TONG VON CHU SO HOU 73.084.295"),
    ("agribank", "2020", "net_interest_income", "43660623", "VND million", "data/raw/agribank/2020_bctc.pdf", "10", "page-patch",
     "KQKD p10: Thu nhập lãi thuần 43.660.623 (bảng số tách dòng)"),
    ("agribank", "2020", "net_fee_income", "5177499", "VND million", "data/raw/agribank/2020_bctc.pdf", "10", "page-patch",
     "KQKD p10: Lãi thuần HĐ dịch vụ 5.177.499"),
    ("agribank", "2020", "opex", "26117208", "VND million", "data/raw/agribank/2020_bctc.pdf", "10", "page-patch",
     "KQKD p10: Chi phí hoạt động (mục VIII) 26.117.208 trị tuyệt đối"),
    ("agribank", "2020", "op_profit_before_provision", "31935227", "VND million", "data/raw/agribank/2020_bctc.pdf", "10", "page-patch",
     "KQKD p10: LN thuần trước dự phòng 31.935.227; TOI≈58.052.435 ≈ IX+VIII"),
    ("agribank", "2020", "net_profit", "10516804", "VND million", "data/raw/agribank/2020_bctc.pdf", "10", "page-patch",
     "KQKD p10: LNST 10.516.804"),

    # Agribank 2023
    ("agribank", "2023", "equity", "100535854", "VND million", "data/raw/agribank/2023_bctc.pdf", "22", "page-patch",
     "CĐKT p22: TONG VON CHU sO HOt 100.535.854"),
    ("agribank", "2023", "net_interest_income", "55964737", "VND million", "data/raw/agribank/2023_bctc.pdf", "24", "page-patch",
     "KQKD p24: Thu nhập lãi thuần 55.964.737"),
    ("agribank", "2023", "net_fee_income", "4565788", "VND million", "data/raw/agribank/2023_bctc.pdf", "24", "page-patch",
     "KQKD p24: Lãi thuần HĐ dịch vụ 4.565.788"),
    ("agribank", "2023", "opex", "30932407", "VND million", "data/raw/agribank/2023_bctc.pdf", "24", "page-patch",
     "KQKD p24: Chi phí hoạt động 30.932.407 trị tuyệt đối"),
    ("agribank", "2023", "op_profit_before_provision", "45206255", "VND million", "data/raw/agribank/2023_bctc.pdf", "24", "page-patch",
     "KQKD p24: LN trước dự phòng 45.206.255"),
    ("agribank", "2023", "net_profit", "20695801", "VND million", "data/raw/agribank/2023_bctc.pdf", "24", "page-patch",
     "KQKD p24: LNST 20.695.801"),

    # BIDV 2020 op_profit + fee from earlier peek
    ("bidv", "2020", "op_profit_before_provision", "32344184", "VND million", "data/raw/bidv/2020_bctc.pdf", "19", "page-patch",
     "KQKD p19: Net operating profit before provision 32,344,184"),
    ("bidv", "2020", "net_fee_income", "5266381", "VND million", "data/raw/bidv/2020_bctc.pdf", "19", "page-patch",
     "KQKD p19: Net gain from services 5,266,381"),

    # TCB 2020
    ("tcb", "2020", "op_profit_before_provision", "18411331", "VND million", "data/raw/tcb/2020_bctc.pdf", "11", "page-patch",
     "KQKD p11: Net operating profit before allowance 18,411,331; TOI=IX+VIII=18,411,331+8,631,195=27,042,526"),
    ("tcb", "2020", "net_profit", "12324991", "VND million", "data/raw/tcb/2020_bctc.pdf", "12", "page-patch",
     "KQKD p12: XVI Net profit attributable to Bank’s shareholders 12,324,991 (ưu tiên ROE; PAT tổng 12,582,467)"),
    # MB 2020
    ("mb", "2020", "total_assets", "494982162", "VND million", "data/raw/mb/2020_bctc.pdf", "11", "page-patch",
     "CĐKT p11: TONG NO PHAI TRA VA VON CHU SỞ HỮU 494.982.162 (= tổng TS)"),
    ("mb", "2020", "equity", "50055485", "VND million", "data/raw/mb/2020_bctc.pdf", "11", "page-patch",
     "CĐKT p11: TONG VON CHU SỞ HỮU 50.055.485"),
    ("mb", "2020", "customer_deposits", "310960354", "VND million", "data/raw/mb/2020_bctc.pdf", "11", "page-patch",
     "CĐKT p11: Tiền gửi của khách hàng 310.960.354"),
    ("mb", "2020", "net_interest_income", "20277795", "VND million", "data/raw/mb/2020_bctc.pdf", "13", "page-patch",
     "KQKD p13: NII 20.277.795 (khối số)"),
    ("mb", "2020", "net_fee_income", "3675553", "VND million", "data/raw/mb/2020_bctc.pdf", "13", "page-patch",
     "KQKD p13: Lãi thuần HĐ DV 3.675.553"),
    ("mb", "2020", "opex", "10555457", "VND million", "data/raw/mb/2020_bctc.pdf", "13", "page-patch",
     "KQKD p13: TONG CHI PHI HOAT DONG 10.555.457 trị tuyệt đối"),
    ("mb", "2020", "op_profit_before_provision", "16806746", "VND million", "data/raw/mb/2020_bctc.pdf", "13", "page-patch",
     "KQKD p13: LN trước dự phòng 16.806.746; TOI≈27.362.173"),
    ("mb", "2020", "net_profit", "8606039", "VND million", "data/raw/mb/2020_bctc.pdf", "13", "page-patch",
     "KQKD p13: LNST ≈8.606.039"),
    # BIDV 2023
    ("bidv", "2023", "total_assets", "2300868728", "VND million", "data/raw/bidv/2023_bctc.pdf", "7", "page-patch",
     "CĐKT p7: TOTAL ASSETS 2,300,868,728"),
    ("bidv", "2023", "customer_deposits", "1704690185", "VND million", "data/raw/bidv/2023_bctc.pdf", "8", "page-patch",
     "CĐKT p8: Deposits from customers 1,704,690,185"),
    ("bidv", "2023", "net_fee_income", "6569870", "VND million", "data/raw/bidv/2023_bctc.pdf", "10", "page-patch",
     "KQKD p10: Net gain from services 6,569,870"),
    ("bidv", "2023", "net_profit", "21504918", "VND million", "data/raw/bidv/2023_bctc.pdf", "10", "page-patch",
     "KQKD p10: Net profit attributable to equity holders 21,504,918"),
    # Agribank 2025
    ("agribank", "2025", "total_assets", "2682737813", "VND million", "data/raw/agribank/2025_bctc.pdf", "7", "page-patch",
     "CĐKT p7/p8: TONG TAI SAN / TỔNG NỢ+VCSH 2.682.737.813"),
    ("agribank", "2025", "customer_deposits", "2160302986", "VND million", "data/raw/agribank/2025_bctc.pdf", "8", "page-patch",
     "CĐKT p8: Tiền gửi của khách hàng 2.160.302.986"),
    ("agribank", "2025", "equity", "128208531", "VND million", "data/raw/agribank/2025_bctc.pdf", "8", "page-patch",
     "CĐKT p8: TONG VON CHU SỞ HỮU 128.208.531"),
    ("agribank", "2025", "net_interest_income", "70243509", "VND million", "data/raw/agribank/2025_bctc.pdf", "10", "page-patch",
     "KQKD p10: Thu nhập lãi thuần 70.243.509"),
    ("agribank", "2025", "net_fee_income", "4804178", "VND million", "data/raw/agribank/2025_bctc.pdf", "10", "page-patch",
     "KQKD p10: Lãi thuần HĐ DV 4.804.178 (riêng); hợp nhất p23=5.746.225 — giữ riêng nếu BCTC riêng"),
    ("agribank", "2025", "opex", "33684480", "VND million", "data/raw/agribank/2025_bctc.pdf", "10", "page-patch",
     "KQKD p10: Chi phí hoạt động 33.684.480"),
    ("agribank", "2025", "op_profit_before_provision", "62477239", "VND million", "data/raw/agribank/2025_bctc.pdf", "10", "page-patch",
     "KQKD p10: LN trước dự phòng 62.477.239"),
    ("agribank", "2025", "net_profit", "24534691", "VND million", "data/raw/agribank/2025_bctc.pdf", "11", "page-patch",
     "KQKD: LNST 24.534.691 (đã có fin-cand p11) — xác nhận lại"),
]


def main():
    rows = list(csv.DictReader(open(OUT, encoding="utf-8-sig")))
    fields = list(rows[0].keys())
    idx = {(r["bank"], r["year"], r["variable"]): i for i, r in enumerate(rows)}

    # Clear remaining bad KPI / wrong agribank total_assets will be overwritten
    clears = [
        ("tcb", "2023", "headcount", "not_disclosed_or_no_reliable_candidate — câu EMPLOYEE BENEFITS không phải headcount rõ"),
    ]
    for bank, year, var, note in clears:
        i = idx.get((bank, year, var))
        if i is not None and not (is_manual_confirmation(rows[i].get("confirmed_by")) or rows[i].get("confirmed_by") == "range-checked"):
            rows[i].update({"value": "", "unit": "", "source_file": "", "page": "", "confirmed_by": "", "note": note})

    n = 0
    for bank, year, var, value, unit, src, page, by, note in PATCHES:
        i = idx.get((bank, year, var))
        if i is None:
            continue
        if is_manual_confirmation(rows[i].get("confirmed_by")) or rows[i].get("confirmed_by") == "range-checked":
            continue
        rows[i].update(
            {
                "value": value,
                "unit": unit,
                "source_file": src,
                "page": page,
                "confirmed_by": by,
                "note": note,
            }
        )
        n += 1

    with open(OUT, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)

    from collections import defaultdict
    filled = defaultdict(int)
    for r in rows:
        if (r.get("value") or "").strip():
            filled[(r["bank"], r["year"])] += 1
    print(f"patched={n}")
    for year in ["2020", "2023", "2025", "2021", "2022", "2024"]:
        for bank in ["agribank", "mb", "tcb", "bidv", "vcb"]:
            print(f"  {bank} {year}: {filled[(bank, year)]}/16")


if __name__ == "__main__":
    main()
