# -*- coding: utf-8 -*-
"""Điền out/dti_inputs.csv từ financial/kpi candidates + đối chiếu statement_pages.
Giữ mọi dòng đã xác nhận thủ công hoặc kiểm khoảng hợp lý. Không ghi 0 cho thiếu số."""
import csv
import json
import re
import unicodedata
from collections import defaultdict
from pathlib import Path
from common import is_manual_confirmation

ROOT = Path(__file__).resolve().parents[1]
TEXT = ROOT / "data" / "text"
OUT = ROOT / "out"

BANKS = ["agribank", "mb", "tcb", "bidv", "vcb"]
YEARS = [2020, 2021, 2022, 2023, 2024, 2025]
PRIORITY = [2020, 2023, 2025, 2021, 2022, 2024]

FIN_VARS = {
    "total_assets",
    "equity",
    "opex",
    "op_profit_before_provision",
    "net_profit",
    "casa_deposits",
    "customer_deposits",
    "net_interest_income",
    "net_fee_income",
    "software_gross_cost",
}
KPI_VARS = {
    "digital_txn_share",
    "digital_customers",
    "total_customers",
    "headcount",
    "tech_staff",
    "training_hours_per_head",
}

RANGES = {
    "total_assets": (1e11, 5e13),  # ~100 nghìn tỷ – 50 triệu tỷ (VND million scale: 1e8–5e12)
    "equity": (1e7, 5e12),
    "customer_deposits": (1e7, 5e13),
    "casa_deposits": (1e6, 2e12),
    "opex": (1e6, 2e11),
    "op_profit_before_provision": (1e6, 2e11),
    "net_profit": (1e5, 2e11),
    "net_interest_income": (1e6, 2e11),
    "net_fee_income": (1e5, 5e10),
    "software_gross_cost": (1e4, 5e10),
    "total_operating_income": (1e6, 5e11),
}


def nfc(s):
    return unicodedata.normalize("NFC", s or "")


def squeeze(s):
    return re.sub(r"\s+", "", s or "")


def _norm(s):
    t = unicodedata.normalize(
        "NFD",
        squeeze(s).replace("’", "'").replace("‘", "'").replace("đ", "d").replace("Đ", "D"),
    )
    return "".join(c for c in t if unicodedata.category(c) != "Mn").lower()


def parse_page_list(s):
    return {int(p) for p in re.split(r"[,\s]+", (s or "").strip()) if p.isdigit()}


def parse_nums_field(s):
    out = []
    for part in re.split(r"\s*\|\s*", s or ""):
        part = part.strip().replace(",", "")
        if not part:
            continue
        try:
            out.append(float(part))
        except ValueError:
            pass
    return out


def in_range(var, v):
    # BCTC đơn vị triệu VND: total assets thường 3e8–4e12
    lo_hi = {
        "total_assets": (1e8, 5e12),
        "equity": (1e7, 5e11),
        "customer_deposits": (1e8, 5e12),
        "casa_deposits": (1e7, 2e12),
        "opex": (1e6, 1e11),
        "op_profit_before_provision": (1e6, 1e11),
        "net_profit": (1e5, 1e11),
        "net_interest_income": (1e6, 1e11),
        "net_fee_income": (1e5, 5e10),
        "software_gross_cost": (1e4, 5e10),
        "total_operating_income": (1e6, 2e11),
        "net_profit_parent": (1e5, 1e11),
        "non_controlling_interests": (1e3, 5e10),
        "total_equity": (1e7, 5e11),
    }.get(var)
    if not lo_hi:
        return True
    lo, hi = lo_hi
    return lo <= abs(v) <= hi


def load_statement_pages():
    sp = defaultdict(lambda: defaultdict(set))
    for r in csv.DictReader(open(OUT / "statement_pages.csv", encoding="utf-8-sig")):
        sp[(r["bank"], r["year"])][r["statement"]] |= parse_page_list(r["page"])
    return sp


def stmt_pages_for(sp, bank, year, kinds):
    out = set()
    for k in kinds:
        out |= sp[(bank, str(year))].get(k, set())
    return out


def load_pages(bank, year, doc):
    jf = TEXT / f"{bank}_{year}_{doc}.jsonl"
    pages = {}
    if not jf.exists():
        return pages
    for line in open(jf, encoding="utf8"):
        d = json.loads(line)
        pages[int(d["page"])] = nfc(d.get("text", ""))
    return pages


def pick_from_financial(fc_rows, bank, year, var, prefer_pages, aliases=None):
    """Chọn ứng viên tốt nhất: trang trong prefer_pages, số trong range, raw_line khớp."""
    aliases = aliases or [var]
    cands = []
    for r in fc_rows:
        if r["bank"] != bank or int(r["year"]) != year:
            continue
        if r["variable"] not in aliases:
            continue
        p = int(r["page"])
        nums = parse_nums_field(r["parsed_numbers(first4)"])
        raw = r.get("raw_line (+dòng kế)") or ""
        rn = _norm(raw)
        # lọc nhiễu
        if var == "opex" and (
            "dichvu" in rn
            or "services" in rn
            and "totaloperating" not in rn
            and "chiphihoatdong" in rn
            and "dichvu" in rn
        ):
            if "chiphihoatdongdichvu" in rn or "expensesonservices" in rn:
                continue
        if var == "opex" and "khac" in rn and "total" not in rn and "viii" not in rn and "vill" not in rn:
            # chi phí hoạt động khác (một dòng con) — bỏ nếu số quá nhỏ
            pass
        if var == "casa_deposits" and ("tctd" in rn or "creditinstitution" in rn):
            continue
        if var == "equity" and "tongnophaitra" in rn and "tongvon" not in rn:
            # OCR dán nhầm tổng tài sản vào dòng vốn
            continue
        for v in nums:
            if not in_range(var if var != "net_profit_parent" else "net_profit", v):
                continue
            score = 0
            if prefer_pages and p in prefer_pages:
                score += 10
            elif prefer_pages and any(abs(p - x) <= 1 for x in prefer_pages):
                score += 5
            # ưu tiên số đầu (cột năm nay)
            idx = nums.index(v)
            score += max(0, 3 - idx)
            # ưu tiên dòng có TOTAL / TỔNG / mục La Mã rõ
            if any(k in rn for k in ["tong", "total", "viii", "vill", "ix.", "xii", "xiii"]):
                score += 2
            if var == "casa_deposits" and (
                rn.startswith("tienguikhongkyhan")
                or rn.startswith("demanddeposits")
                or rn.startswith("currentaccounts")
            ):
                score += 4
            if var in ("equity", "total_assets") and rn.startswith("tong"):
                score += 4
            # phạt số âm trừ opex
            if v < 0 and var != "opex":
                score -= 5
            val = abs(v) if var == "opex" else v
            cands.append((score, p, val, raw[:140]))
    if not cands:
        return None
    cands.sort(key=lambda x: (-x[0], x[1], -abs(x[2])))
    return cands[0]  # score, page, value, raw


def extract_page_confirm(bctc, page_set, var, labels, mode="start"):
    """Đọc trực tiếp text trang khi financial_candidates thiếu."""
    hits = []
    for p in sorted(page_set):
        text = bctc.get(p, "")
        if not text:
            continue
        lines = [x for x in text.splitlines() if x.strip()]
        # ghép số xuống dòng
        joined, buf = [], ""
        for ln in lines:
            if re.fullmatch(r"[\s\d.,()\-–—]+", ln) and buf:
                buf = buf + " " + ln.strip()
            else:
                if buf:
                    joined.append(buf)
                buf = ln
        if buf:
            joined.append(buf)
        for ln in lines + joined:
            n = _norm(ln)
            ok = False
            for lab in labels:
                if mode == "start":
                    stripped = re.sub(r"^[ivxlcuh1|!]{0,5}h?[.,)]?", "", n)
                    if stripped.startswith(lab) or n.startswith(lab):
                        ok = True
                elif lab in n:
                    ok = True
            if not ok:
                continue
            from_common = __import__("re")
            # nums inline
            NUMTOK = re.compile(r"\(?-?\d[\d.,]*\)?")
            THOUSANDS = re.compile(r"\d{1,3}(?:[.,]\d{3})+")
            ns = []
            for m in NUMTOK.finditer(ln):
                core = m.group(0).strip("()-")
                if THOUSANDS.fullmatch(core):
                    v = float(re.sub(r"[.,]", "", core))
                    if m.group(0).startswith("(") or m.group(0).startswith("-"):
                        v = -v
                    ns.append(v)
            for v in ns:
                if not in_range(var, abs(v) if var == "opex" else v):
                    continue
                val = abs(v) if var == "opex" else v
                hits.append((p, val, ln[:140]))
                break
    if not hits:
        return None
    return sorted(hits, key=lambda x: x[0])[0]


PAGE_LABELS = {
    "total_assets": (["tongtaisan", "totalassets"], "start"),
    "equity": (["tongvonchusohuu", "totalowners'equity", "totalshareholders'equity", "owners'equity"], "start"),
    "customer_deposits": (["tienguicuakhachhang", "depositsfromcustomers"], "start"),
    "net_interest_income": (["thunhaplaithuan", "netinterestincome", "netinterestandsimilarincome"], "start"),
    "net_fee_income": (
        ["laithuantuhoatdongdichvu", "netfeeandcommissionincome", "netfeesandcommissionincome", "netgainfromservices"],
        "start",
    ),
    "opex": (["totaloperatingexpenses", "chiphihoatdong", "operatingexpenses"], "start"),
    "op_profit_before_provision": (
        [
            "loinhuanthuantuhoatdongkinhdoanhtruocchiphiduphong",
            "netoperatingprofitbeforeprovision",
            "profitbeforeprovisionforcreditlosses",
            "profitbeforeprovisionexpenses",
        ],
        "has",
    ),
    "net_profit": (["loinhuansauthue", "profitaftertax", "netprofitaftertax"], "start"),
    "net_profit_parent": (
        [
            "netprofitattributable",
            "profitattributableto",
            "loinhuanthuanucuacodong",
            "netprofitcontributed",
        ],
        "has",
    ),
    "casa_deposits": (["tienguikhongkyhan", "demanddeposits", "currentaccounts"], "has"),
}


def score_kpi(var, v, sent, doc):
    sl = (sent or "").lower()
    score = 0
    if doc != "bctn":
        return -1
    score += 5
    # từ chối nhiễu TOC / glossary / % tăng
    bad = [
        "table of content",
        "glossary",
        "contents",
        "message management",
        "increase in",
        "tăng",
        "decreased",
        "page ",
    ]
    if any(b in sl for b in bad) and var in ("tech_staff", "training_hours_per_head", "digital_customers"):
        score -= 8
    if var == "digital_txn_share":
        if not (0 < v <= 100):
            return -1
        if "%" in sent or "percent" in sl or "per cent" in sl or "tỷ lệ" in sl:
            score += 4
        else:
            return -1
    elif var == "headcount":
        if not (3000 <= v <= 60000):
            return -1
        if any(w in sl for w in ["employee", "nhân viên", "cán bộ", "workforce", "người lao động", "staff total", "total employees"]):
            score += 4
        else:
            return -1
    elif var == "total_customers":
        if not (5e5 <= v <= 5e7):  # 0.5–50 triệu KH
            # cho phép số viết dạng million: 15.4 -> đã parse khác
            if not (1e6 <= v <= 5e7):
                return -1
        if any(w in sl for w in ["million customer", "khách hàng", "total customer", "customers at"]):
            score += 4
        elif "customer" in sl:
            score += 2
        else:
            return -1
        # phạt phân khúc sản phẩm
        if any(w in sl for w in ["inspire", "grew to", "open ai", "university"]):
            score -= 6
    elif var == "digital_customers":
        if not (1e5 <= v <= 5e7):
            return -1
        if any(w in sl for w in ["digital customer", "khách hàng số", "active customer", "users", "e-banking"]):
            score += 4
        else:
            return -1
    elif var == "tech_staff":
        if not (100 <= v <= 15000):
            return -1
        if any(w in sl for w in ["it staff", "công nghệ thông tin", "technology staff", "digital talent", "nhân sự it", "nhân sự công nghệ"]):
            score += 5
        else:
            return -1  # rất dễ nhiễu — chỉ nhận khi có cụm rõ
    elif var == "training_hours_per_head":
        if not (5 <= v <= 150):
            return -1
        if any(w in sl for w in ["hours of training", "giờ đào tạo", "training hours", "averaged", "per employee"]):
            score += 4
        else:
            return -1
        if "%" in sent or "increase" in sl or "tăng" in sl:
            return -1
    return score


def main():
    sp = load_statement_pages()
    fc = list(csv.DictReader(open(OUT / "financial_candidates.csv", encoding="utf-8-sig")))
    kpi = list(csv.DictReader(open(OUT / "kpi_candidates.csv", encoding="utf-8-sig")))

    results = {}

    # --- Financial ---
    for year in YEARS:
        for bank in BANKS:
            cdkt = stmt_pages_for(sp, bank, year, ["can_doi_ke_toan"])
            kqkd = stmt_pages_for(sp, bank, year, ["ket_qua_kinh_doanh"])
            tm_dep = stmt_pages_for(sp, bank, year, ["thuyet_minh_tien_gui_KH"])
            tm_soft = stmt_pages_for(sp, bank, year, ["thuyet_minh_TSCD_vo_hinh"])
            if not kqkd:
                kqkd = {10, 11, 12, 13, 19, 24, 25}
            bctc = load_pages(bank, year, "bctc")
            src = f"data/raw/{bank}/{year}_bctc.pdf"
            unit = "VND million"

            plan = [
                ("total_assets", cdkt, ["total_assets"]),
                ("customer_deposits", cdkt, ["customer_deposits"]),
                ("equity", cdkt, ["equity", "total_equity"]),
                ("net_interest_income", kqkd, ["net_interest_income"]),
                ("net_fee_income", kqkd, ["net_fee_income"]),
                ("opex", kqkd, ["opex"]),
                ("op_profit_before_provision", kqkd, ["op_profit_before_provision"]),
                ("net_profit", kqkd, ["net_profit_parent", "net_profit"]),
                ("casa_deposits", tm_dep or cdkt, ["casa_deposits"]),
            ]

            for dti_var, prefer, aliases in plan:
                hit = pick_from_financial(fc, bank, year, dti_var if dti_var != "net_profit" else aliases[0], prefer, aliases)
                # nếu alias đầu là net_profit_parent thất bại, thử net_profit
                if hit is None and dti_var == "net_profit":
                    hit = pick_from_financial(fc, bank, year, "net_profit", prefer, ["net_profit"])
                if hit is None and dti_var in PAGE_LABELS and bctc:
                    labs, mode = PAGE_LABELS[dti_var]
                    pc = extract_page_confirm(bctc, prefer | set(range(7, 16)), dti_var, labs, mode)
                    if pc:
                        p, val, raw = pc
                        results[(bank, year, dti_var)] = {
                            "bank": bank,
                            "year": str(year),
                            "variable": dti_var,
                            "value": f"{val:.0f}",
                            "unit": unit,
                            "source_file": src,
                            "page": str(p),
                            "confirmed_by": "page-confirm",
                            "note": f"page-confirm; {raw}".replace("\n", " ")[:200],
                        }
                    continue
                if hit is None:
                    continue
                score, p, val, raw = hit
                if score < 5 and dti_var not in ("casa_deposits",):
                    # yêu cầu khớp trang statement (trừ khi không có lựa chọn)
                    alt = pick_from_financial(fc, bank, year, dti_var, set(), aliases)
                    if alt and alt[0] >= score:
                        # vẫn yếu — bỏ nếu score quá thấp
                        if score < 3:
                            continue
                note = f"fin-cand score={score}; {raw}".replace("\n", " ")[:200]
                # equity: trừ NCI nếu có trên CĐKT
                if dti_var == "equity":
                    nci = pick_from_financial(fc, bank, year, "non_controlling_interests", prefer | cdkt, ["non_controlling_interests"])
                    if nci and abs(nci[2]) < abs(val) * 0.15 and abs(nci[1] - p) <= 3:
                        parent = val - abs(nci[2])
                        note = f"fin-cand equity {val:,.0f}−NCI {abs(nci[2]):,.0f}={parent:,.0f}; {raw}"[:200]
                        val = parent
                results[(bank, year, dti_var)] = {
                    "bank": bank,
                    "year": str(year),
                    "variable": dti_var,
                    "value": f"{val:.0f}",
                    "unit": unit,
                    "source_file": src,
                    "page": str(p),
                    "confirmed_by": "fin-cand",
                    "note": note,
                }

            # software: chỉ khi dòng có cost/nguyên giá gần software
            soft = pick_from_financial(fc, bank, year, "software_gross_cost", tm_soft, ["software_gross_cost"])
            if soft and soft[0] >= 5:
                score, p, val, raw = soft
                results[(bank, year, "software_gross_cost")] = {
                    "bank": bank,
                    "year": str(year),
                    "variable": "software_gross_cost",
                    "value": f"{val:.0f}",
                    "unit": unit,
                    "source_file": src,
                    "page": str(p),
                    "confirmed_by": "fin-cand",
                    "note": f"fin-cand software; {raw}"[:200],
                }
            elif bctc and tm_soft:
                for p in sorted(tm_soft):
                    t = bctc.get(p, "")
                    if not t:
                        continue
                    if "software" not in t.lower() and "phanmem" not in _norm(t):
                        continue
                    for ln in t.splitlines():
                        n = _norm(ln)
                        if "software" not in n and "phanmem" not in n:
                            continue
                        if "cost" not in n and "nguyengia" not in n and "closing" not in n:
                            # vẫn lấy nếu có số lớn trên dòng software
                            pass
                        NUMTOK = re.compile(r"\d{1,3}(?:[.,]\d{3})+")
                        for m in NUMTOK.finditer(ln):
                            v = float(re.sub(r"[.,]", "", m.group(0)))
                            if in_range("software_gross_cost", v):
                                results[(bank, year, "software_gross_cost")] = {
                                    "bank": bank,
                                    "year": str(year),
                                    "variable": "software_gross_cost",
                                    "value": f"{v:.0f}",
                                    "unit": unit,
                                    "source_file": src,
                                    "page": str(p),
                                    "confirmed_by": "page-confirm",
                                    "note": f"page-confirm software; {ln[:120]}".replace("\n", " "),
                                }
                                break
                        if (bank, year, "software_gross_cost") in results:
                            break
                    if (bank, year, "software_gross_cost") in results:
                        break

    # --- KPI ---
    kpi_best = {}
    for r in kpi:
        bank, year, var = r["bank"], int(r["year"]), r["variable"]
        if var not in KPI_VARS:
            continue
        doc = r.get("doc_type", "bctn")
        sent = r.get("sentence", "") or ""
        page = r.get("page", "")
        for part in re.split(r"[|;]", r.get("numbers_found") or ""):
            part = part.strip().replace(",", "")
            if not part:
                continue
            try:
                v = float(part)
            except ValueError:
                continue
            sc = score_kpi(var, v, sent, doc)
            if sc < 5:
                continue
            key = (bank, year, var)
            prev = kpi_best.get(key)
            if prev is None or sc > prev[0]:
                kpi_best[key] = (sc, v, page, doc, sent[:140])

    units = {
        "digital_txn_share": "%",
        "digital_customers": "customers",
        "total_customers": "customers",
        "headcount": "employees",
        "tech_staff": "employees",
        "training_hours_per_head": "hours",
    }
    for (bank, year, var), (sc, v, page, doc, sent) in kpi_best.items():
        val_s = f"{v:g}" if var in ("digital_txn_share", "training_hours_per_head") else f"{v:.0f}"
        results[(bank, year, var)] = {
            "bank": bank,
            "year": str(year),
            "variable": var,
            "value": val_s,
            "unit": units[var],
            "source_file": f"data/raw/{bank}/{year}_{doc}.pdf",
            "page": str(page),
            "confirmed_by": "kpi-heuristic",
            "note": f"kpi-cand score={sc}; {sent}".replace("\n", " "),
        }

    # --- Merge vào template ---
    existing = list(csv.DictReader(open(OUT / "dti_inputs.csv", encoding="utf-8-sig")))
    fieldnames = list(existing[0].keys())
    kept = filled_new = 0
    out_rows = []
    for r in existing:
        bank, year, var = r["bank"], int(r["year"]), r["variable"]
        if is_manual_confirmation(r.get("confirmed_by")) or r.get("confirmed_by") == "range-checked":
            out_rows.append(r)
            kept += 1
            continue
        # giữ tcb2024 đã điền tay (kể cả ô trống có note)
        if bank == "tcb" and year == 2024 and r.get("confirmed_by") == "manual-t023":
            out_rows.append(r)
            kept += 1
            continue
        if bank == "tcb" and year == 2024 and (r.get("note") or "") and "không công bố" in (r.get("note") or ""):
            out_rows.append(r)
            kept += 1
            continue
        if bank == "tcb" and year == 2024 and (r.get("value") or "").strip() and "manual" in (r.get("confirmed_by") or ""):
            out_rows.append(r)
            kept += 1
            continue

        hit = results.get((bank, year, var))
        if hit:
            out_rows.append({**r, **hit})
            filled_new += 1
        else:
            nr = {
                "bank": bank,
                "year": str(year),
                "variable": var,
                "value": "",
                "unit": "",
                "source_file": "",
                "page": "",
                "confirmed_by": "",
                "note": (
                    "not_disclosed_or_no_reliable_candidate"
                    if var in KPI_VARS
                    else "missing_candidate_needs_manual"
                ),
            }
            out_rows.append({**r, **nr})

    with open(OUT / "dti_inputs.csv", "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(out_rows)

    filled_by = defaultdict(int)
    for r in out_rows:
        if (r.get("value") or "").strip():
            filled_by[(r["bank"], r["year"])] += 1
    print(f"filled_new={filled_new}; kept={kept}")
    print("Coverage filled/16:")
    for year in PRIORITY:
        for bank in BANKS:
            print(f"  {bank} {year}: {filled_by[(bank, str(year))]}/16")


if __name__ == "__main__":
    main()
