#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Bước 2–6: cập nhật out/dti_inputs.csv (definition, share, NCI/equity, KPI, training)."""
from __future__ import annotations

import csv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CSV_PATH = ROOT / "out" / "dti_inputs.csv"
FIELDS = [
    "bank",
    "year",
    "variable",
    "value",
    "unit",
    "source_file",
    "page",
    "confirmed_by",
    "note",
    "definition",
]


def key(r):
    return (r["bank"], str(r["year"]), r["variable"])


def set_row(rows_by_key, bank, year, variable, **kwargs):
    k = (bank, str(year), variable)
    if k not in rows_by_key:
        r = {f: "" for f in FIELDS}
        r["bank"] = bank
        r["year"] = str(year)
        r["variable"] = variable
        rows_by_key[k] = r
    r = rows_by_key[k]
    for f, v in kwargs.items():
        if f not in FIELDS:
            raise KeyError(f)
        r[f] = "" if v is None else str(v)
    return r


def main():
    with CSV_PATH.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    by = {key(r): r for r in rows}

    # --- Bước 2: definition ---
    # TCB 2022 digital_customers: p35 ~6.2M e-banking; p8 "registered on Techcombank Mobile"
    # → registered (khớp TCB 2020), không phải active
    set_row(
        by,
        "tcb",
        2022,
        "digital_customers",
        definition="registered",
        note=(
            "BCTN EN p35: Techcombank e-banking customers ~ 6.2 million (+21.2% YoY); "
            "p8: around six million retail customers registered on Techcombank Mobile. "
            "Phạm vi: registered e-banking/Mobile (đổi def active→registered cho khớp note + TCB2020)."
        ),
        confirmed_by="nam",
    )
    # bidv 2021–2023 training days_x6h: giữ nguyên (không đụng)

    # --- Bước 3: MB 2023 digital_customer_share + TCB 2024 ---
    set_row(
        by,
        "mb",
        2023,
        "digital_customer_share",
        value="86",
        unit="%",
        source_file="data/raw/mb/2023_bctn.pdf",
        page="9",
        confirmed_by="nam",
        note=(
            "khách hàng dùng app / digital platforms; BCTN EN p9: "
            "'86% of customers served on digital platforms' (All-in-one App MBBank/BIZ); "
            "p21 mô tả App MBBank — không công bố số tuyệt đối KH số."
        ),
        definition="digital_platforms",
    )
    set_row(
        by,
        "tcb",
        2024,
        "digital_customers",
        value="",
        unit="",
        source_file="data/raw/tcb/2024_bctn.pdf",
        page="",
        confirmed_by="nam",
        note=(
            "not_disclosed: không công bố riêng số khách hàng số; "
            "chỉ có total customers 15.4M và engagement (91% GD online)."
        ),
        definition="",
    )
    # cũng chuẩn hóa digital_customer_share tcb2024 nếu chỉ có total
    set_row(
        by,
        "tcb",
        2024,
        "digital_customer_share",
        value="",
        unit="%",
        confirmed_by="nam",
        note="not_disclosed: BCTN 2024 không công bố tỷ lệ KH số riêng (chỉ % GD online).",
        definition="",
    )

    # --- Bước 4: NCI + chuẩn hóa equity → parent ---
    # (bank, year, nci, total_or_None, equity_src, equity_page, nci_note)
    # Nếu equity đã parent: chỉ điền nci, không đổi equity.
    nci_updates = [
        # 13 ô total → parent
        (
            "agribank",
            2020,
            975182,
            73084295,
            "data/raw/agribank/2020_bctc.pdf",
            "8",
            "CĐKT hợp nhất p8: Lợi ích CĐ không KS 975.182; TỔNG VCSH 73.084.295 → parent=72.109.113",
        ),
        (
            "agribank",
            2023,
            1347748,
            100535854,
            "data/raw/agribank/2023_bctc.pdf",
            "8",
            "CĐKT hợp nhất p8: NCI 1.347.748; TỔNG VCSH 100.535.854 → parent=99.188.106",
        ),
        (
            "agribank",
            2025,
            1480515,
            131191251,  # chuyển từ BCTC riêng 128.208.531 sang hợp nhất
            "data/raw/agribank/2025_bctc.pdf",
            "21",
            "CĐKT hợp nhất p21: NCI 1.480.515; TỔNG VCSH 131.191.251 (trước đó lấy BCTC riêng 128.208.531 p8 không có NCI) → parent=129.710.736",
        ),
        (
            "bidv",
            2022,
            4722139,
            104189995,
            "data/raw/bidv/2022_bctc.pdf",
            "8",
            "CĐKT EN p8: Non-controlling interests 4,722,139; TOTAL OWNERS' EQUITY 104,189,995 → parent=99,467,856 (BCTC2023 restated opening NCI 4,723,238)",
        ),
        (
            "mb",
            2020,
            2152881,
            50055485,
            "data/raw/mb/2020_bctc.pdf",
            "11",
            "CĐKT p11 OCR: NCI ~2.152.881 (BCTC2021 comparative restated 2.192.991 / total 50.099.495); dùng số cùng năm OCR; parent=47.902.604",
        ),
        (
            "mb",
            2021,
            2911788,
            62486023,
            "data/raw/mb/2022_bctc.pdf",
            "11",
            "BCTC2022 CĐKT p11 cột 2021: NCI 2.911.788 (OCR BCTC2021 từng đọc 2.911.188); 62.486.023−2.911.788=59.574.235 (không dùng số cũ 59.574.835 lệch 600)",
        ),
        (
            "mb",
            2022,
            3664125,
            79613219,
            "data/raw/mb/2022_bctc.pdf",
            "11",
            "CĐKT p11: NCI 3.664.125; TỔNG VCSH 79.613.219 → parent=75.949.094",
        ),
        (
            "mb",
            2023,
            3973110,
            96711159,
            "data/raw/mb/2024_bctc.pdf",
            "11",
            "BCTC2024 CĐKT p11 cột 2023: NCI 3.973.110; TỔNG 96.711.159 → parent=92.738.049",
        ),
        (
            "mb",
            2024,
            4910880,
            117059581,
            "data/raw/mb/2024_bctc.pdf",
            "11",
            "CĐKT p11: NCI 4.910.880; TỔNG VCSH 117.059.581 → parent=112.148.701",
        ),
        (
            "mb",
            2025,
            5886495,
            142022525,
            "data/raw/mb/2025_bctc.pdf",
            "11",
            "CĐKT EN p11: Non-controlling interests 5,886,495; TOTAL OWNERS' EQUITY 142,022,525 → parent=136,136,030",
        ),
        (
            "vcb",
            2020,
            85024,
            94094979,
            "data/raw/vcb/2020_bctc.pdf",
            "9",
            "CĐKT p9: NCI 85.024; TỔNG VCSH 94.094.979 → parent=94.009.955",
        ),
        (
            "vcb",
            2021,
            87113,
            109117393,
            "data/raw/vcb/2021_bctc.pdf",
            "9",
            "CĐKT p9: NCI 87.113; TỔNG VCSH 109.117.393 → parent=109.030.280",
        ),
        (
            "vcb",
            2023,
            93990,
            165012666,
            "data/raw/vcb/2023_bctc.pdf",
            "10",
            "CĐKT p10: NCI 93.990; TỔNG VCSH 165.012.666 → parent=164.918.676",
        ),
    ]

    for bank, year, nci, total, src, page, note in nci_updates:
        parent = total - nci
        set_row(
            by,
            bank,
            year,
            "nci",
            value=str(float(nci)),
            unit="VND million",
            source_file=src,
            page=page,
            confirmed_by="nam",
            note=note,
            definition="nci",
        )
        # chỉ sửa equity nếu chưa tag parent
        eq = by.get((bank, str(year), "equity"))
        if eq is not None and (eq.get("definition") or "").strip() == "parent":
            continue
        set_row(
            by,
            bank,
            year,
            "equity",
            value=str(float(parent)),
            unit="VND million",
            source_file=src,
            page=page,
            confirmed_by="nam",
            note=f"parent = total {total:,} − NCI {nci:,}; {note}",
            definition="parent",
        )

    # NCI bổ sung cho ô equity đã parent (không đụng equity)
    extra_nci = [
        ("agribank", 2021, 1166940, "data/raw/agribank/2021_bctc.pdf", "90", "CĐKT p90: NCI 1.166.940 (equity đã parent)"),
        ("bidv", 2020, 3234595, "data/raw/bidv/2020_bctc.pdf", "15", "CĐKT EN p15: NCI 3,234,595 (equity đã parent)"),
        ("bidv", 2021, 3193928, "data/raw/bidv/2021_bctc.pdf", "8", "CĐKT EN p8: NCI 3,193,928 (equity đã parent)"),
        ("bidv", 2023, 4966154, "data/raw/bidv/2023_bctc.pdf", "8", "CĐKT EN p8: NCI 4,966,154 (equity đã parent)"),
        ("bidv", 2024, 5234039, "data/raw/bidv/2024_bctc.pdf", "10", "CĐKT EN p10: NCI 5,234,039 (equity đã parent)"),
        ("bidv", 2025, 5563943, "data/raw/bidv/2025_bctc.pdf", "10", "CĐKT EN p10: NCI 5,563,943 (equity đã parent)"),
        ("tcb", 2020, 483766, "data/raw/tcb/2020_bctc.pdf", "9", "CĐKT EN p9: NCI 483,766 (equity đã parent)"),
        ("tcb", 2021, 846898, "data/raw/tcb/2021_bctc.pdf", "9", "CĐKT EN p9: NCI 846,898 (equity đã parent)"),
        ("tcb", 2022, 1128915, "data/raw/tcb/2022_bctc.pdf", "9", "CĐKT EN p9: NCI 1,128,915 (equity đã parent)"),
        ("tcb", 2023, 1316833, "data/raw/tcb/2023_bctc.pdf", "9", "CĐKT EN p9: NCI 1,316,833 (equity đã parent)"),
        ("tcb", 2024, 2520466, "data/raw/tcb/2024_bctc.pdf", "9", "CĐKT EN p9: NCI 2,520,466 (equity đã parent)"),
        ("tcb", 2025, 9456938, "data/raw/tcb/2025_bctc.pdf", "9", "CĐKT EN p9: NCI 9,456,938 (equity đã parent)"),
        ("vcb", 2024, 96261, "data/raw/vcb/2024_bctc.pdf", "10", "CĐKT p10: NCI 96.261 (equity đã parent)"),
        ("vcb", 2025, 71521, "data/raw/vcb/2025_bctc.pdf", "9", "fin-cand/CĐKT: NCI 71.521 (equity đã parent)"),
    ]
    for bank, year, nci, src, page, note in extra_nci:
        set_row(
            by,
            bank,
            year,
            "nci",
            value=str(float(nci)),
            unit="VND million",
            source_file=src,
            page=page,
            confirmed_by="nam",
            note=note,
            definition="nci",
        )

    # --- Bước 5: ưu tiên headcount đã có; điền thêm BIDV 2020–22; software MB/BIDV 2020 ---
    set_row(
        by,
        "bidv",
        2020,
        "headcount",
        value="26752",
        unit="persons",
        source_file="data/raw/bidv/2021_bctn.pdf",
        page="79",
        confirmed_by="nam",
        note="BCTN 2021 p79 bảng HUMAN RESOURCE GROWTH 2019–2021: Total employees 2020 = 26,752",
        definition="unspecified",
    )
    set_row(
        by,
        "bidv",
        2021,
        "headcount",
        value="27223",
        unit="persons",
        source_file="data/raw/bidv/2021_bctn.pdf",
        page="79",
        confirmed_by="nam",
        note="BCTN 2021 p79: Total employees 2021 = 27,223",
        definition="unspecified",
    )
    set_row(
        by,
        "bidv",
        2022,
        "headcount",
        value="28435",
        unit="persons",
        source_file="data/raw/bidv/2022_bctn.pdf",
        page="39",
        confirmed_by="nam",
        note="BCTN 2022 p39: TOTAL EMPLOYEES as of 31/12/2022 = 28,435 (+~1,000 vs 2021)",
        definition="unspecified",
    )

    # Agribank headcount approximate / not_disclosed
    set_row(
        by,
        "agribank",
        2020,
        "headcount",
        value="40000",
        unit="persons",
        source_file="data/raw/agribank/2020_bctn.pdf",
        page="25",
        confirmed_by="nam",
        note="approx; BCTN p25: 'gần 4 vạn người lao động trong toàn hệ thống' — không có số exact; definition=group lower-bound làm tròn 40.000",
        definition="group_approx",
    )
    for year, where in [
        (2021, "BCTN 2021 (tìm 'người lao động' — không thấy tổng lao động exact)"),
        (2022, "BCTN 2022 (không thấy tổng lao động exact trong text)"),
        (2024, "BCTN 2024 (không thấy tổng lao động exact trong text)"),
    ]:
        set_row(
            by,
            "agribank",
            year,
            "headcount",
            value="",
            unit="",
            confirmed_by="nam",
            note=f"not_disclosed: {where}",
            definition="",
        )

    # VCB 2021/2022 headcount — mark searched
    for year, where in [
        (2021, "BCTN 2021 — không thấy Tổng số lao động exact trong text đã trích"),
        (2022, "BCTN 2022 — không thấy Tổng số lao động exact trong text đã trích"),
    ]:
        set_row(
            by,
            "vcb",
            year,
            "headcount",
            value="",
            unit="",
            confirmed_by="nam",
            note=f"not_disclosed: {where}",
            definition="",
        )

    # software MB 2020 / BIDV 2020
    set_row(
        by,
        "mb",
        2020,
        "software_gross_cost",
        value="1169487.0",
        unit="VND million",
        source_file="data/raw/mb/2021_bctc.pdf",
        page="57",
        confirmed_by="nam",
        note="BCTC2021 TM TSCĐ VH p57 bảng biến động năm 2020: Phần mềm máy vi tính — nguyên giá cuối năm 2020 = 1.169.487",
        definition="",
    )
    set_row(
        by,
        "bidv",
        2020,
        "software_gross_cost",
        value="1654829.0",
        unit="VND million",
        source_file="data/raw/bidv/2021_bctc.pdf",
        page="46",
        confirmed_by="nam",
        note="BCTC2021 TM EN p46: Computer software Cost opening balance (= cuối 2020) = 1,654,829",
        definition="",
    )

    # digital_txn_share / total_customers — BIDV rõ ràng
    set_row(
        by,
        "bidv",
        2022,
        "total_customers",
        value="15500000.0",
        unit="customers",
        source_file="data/raw/bidv/2022_bctn.pdf",
        page="11",
        confirmed_by="nam",
        note="BCTN p11: more than 15 million individual + 500,000 corporate ≈ 15.5M; definition=retail+corporate lower-bound",
        definition="retail+corporate",
    )
    set_row(
        by,
        "bidv",
        2022,
        "digital_txn_share",
        value="75.9",
        unit="%",
        source_file="data/raw/bidv/2022_bctn.pdf",
        page="51",
        confirmed_by="nam",
        note="BCTN p51/p57: proportion of transactions via digital channels = 75.9% (2021 comparative 66.9%)",
        definition="all_txn",
    )
    set_row(
        by,
        "bidv",
        2021,
        "digital_txn_share",
        value="66.9",
        unit="%",
        source_file="data/raw/bidv/2022_bctn.pdf",
        page="51",
        confirmed_by="nam",
        note="BCTN 2022 p51 comparative: digital channel share 2021 = 66.9%",
        definition="all_txn",
    )
    # Các năm digital_txn/total còn thiếu sau khi tìm — ghi not_disclosed nơi đã tìm
    for bank, year, var, where in [
        ("agribank", 2020, "digital_txn_share", "BCTN 2020 — không thấy % GD kênh số exact"),
        ("agribank", 2021, "digital_txn_share", "BCTN 2021 — không thấy % GD kênh số exact"),
        ("agribank", 2022, "digital_txn_share", "BCTN 2022 — không thấy % GD kênh số exact"),
        ("agribank", 2024, "digital_txn_share", "BCTN 2024 — không thấy % GD kênh số exact"),
        ("vcb", 2020, "digital_txn_share", "BCTN 2020 — không thấy % GD kênh số exact"),
        ("vcb", 2021, "digital_txn_share", "BCTN 2021 — không thấy % GD kênh số exact"),
        ("vcb", 2022, "digital_txn_share", "BCTN 2022 — không thấy % GD kênh số exact"),
        ("vcb", 2024, "digital_txn_share", "BCTN 2024 — không thấy % GD kênh số exact trong text đã tìm"),
        ("bidv", 2024, "digital_txn_share", "BCTN 2024 — không thấy % GD digital exact (có % quy trình nội bộ)"),
        ("agribank", 2024, "total_customers", "BCTN 2024 — không thấy tổng KH exact"),
        ("bidv", 2020, "total_customers", "BCTN 2020 — không thấy tổng KH exact"),
        ("bidv", 2021, "total_customers", "BCTN 2021 — không thấy tổng KH exact (có SmartBanking metrics)"),
        ("bidv", 2024, "total_customers", "BCTN 2024 — chưa chốt tổng KH exact trong text đã tìm"),
        ("vcb", 2020, "total_customers", "BCTN 2020 — không thấy tổng KH exact"),
        ("vcb", 2021, "total_customers", "BCTN 2021 — không thấy tổng KH exact"),
        ("vcb", 2022, "total_customers", "BCTN 2022 — không thấy tổng KH exact"),
        ("vcb", 2024, "total_customers", "BCTN 2024 — không thấy tổng KH exact trong text đã tìm"),
    ]:
        cur = by.get((bank, str(year), var))
        if cur and (cur.get("value") or "").strip():
            continue
        set_row(
            by,
            bank,
            year,
            var,
            value="",
            unit="%" if "share" in var else "",
            confirmed_by="nam",
            note=f"not_disclosed: {where}",
            definition="",
        )

    # --- Bước 6: training nghi ---
    set_row(
        by,
        "bidv",
        2024,
        "training_hours_per_head",
        value="59.0",
        unit="hours",
        source_file="data/raw/bidv/2024_bcptbv.pdf",
        page="66",
        confirmed_by="nam",
        definition="avg_hours",
        note=(
            "BCPTBV EN p66: prose 'average number of training hours per BIDV staff in 2024 will be 59 hours'. "
            "Cùng trang biểu đồ có 59 (2023) / 87 (2024) cạnh nhãn middle/senior/average managers — "
            "87 có thể là series quản lý hoặc metric khác; chốt 59 theo câu văn staff-wide; ghi cả 87 trong note."
        ),
    )
    set_row(
        by,
        "vcb",
        2023,
        "training_hours_per_head",
        value="41.0",
        unit="hours",
        source_file="data/raw/vcb/2023_bctn.pdf",
        page="68",
        confirmed_by="nam",
        definition="avg_hours",
        note=(
            "BCTN 2023 p68: Số giờ đào tạo trung bình/cán bộ = 41 giờ/năm (cách tính mới từ 2023). "
            "BCPTBV 2024 p41 nêu mức 2023 = 35 giờ/cán bộ theo phương pháp so sánh với 2024 — "
            "giữ 41 theo năm báo cáo 2023; ghi cả hai số (41 và 35)."
        ),
    )

    # Ghi lại — giữ thứ tự gốc + append nếu có dòng mới
    original_keys = [key(r) for r in rows]
    seen = set(original_keys)
    out_rows = []
    for k in original_keys:
        out_rows.append(by[k])
    for k, r in by.items():
        if k not in seen:
            out_rows.append(r)

    with CSV_PATH.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        for r in out_rows:
            w.writerow({f: r.get(f, "") for f in FIELDS})

    # thống kê nhanh
    filled = sum(1 for r in out_rows if (r.get("value") or "").strip())
    nc = sum(1 for r in out_rows if (r.get("note") or "").startswith("not_collected"))
    print(f"rows={len(out_rows)} filled={filled} still_not_collected={nc}")


if __name__ == "__main__":
    main()
