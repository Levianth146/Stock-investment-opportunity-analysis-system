#!/usr/bin/env python3
"""09c_auto_score.py — Chấm 24 tiêu chí DBI bằng quy tắc xác định, thay cho chấm tay/kappa.

Cách làm (quy tắc vận hành hóa rubric trong phiên bản thuật toán này):
  - Từ khóa (config/keywords.yaml) CHỈ để định vị đoạn văn. Điểm do các điều kiện của từng mức quyết định:
      Mức 0: có tài liệu của ngân hàng-năm đó nhưng không đoạn nào nhắc chủ đề
      Mức 1: có nhắc chủ đề (định hướng chung), chưa có hành động cụ thể
      Mức 2: có động từ triển khai thực tế (ra mắt, triển khai, vận hành...), không tính câu tương lai ("sẽ", "dự kiến")
      Mức 3: mức 2 và có con số kèm đơn vị trong cùng đoạn
      Mức 4: mức 3 và thỏa điều kiện bổ sung của tiêu chí (đa kỳ, kiểm chứng độc lập...; bảng L4 bên dưới theo Phụ lục A)
  - Mỗi điểm đi kèm bằng chứng tự động: file PDF, trang, trích đoạn, đặc trưng đã bắt được, độ tin cậy.

Đọc : data/text/*.jsonl, config/keywords.yaml và banks.yaml (lưới ngân hàng × năm × tiêu chí)
Ghi : out/auto_scores.csv     (điểm + bằng chứng + độ tin cậy)
      out/coding_auto.xlsx    (cùng cấu trúc coding_sheet, cột final = điểm tự động) -> đưa cho 10_score.py

Chạy: python 09c_auto_score.py [--context 300] [--bank tcb] [--year 2025]
Rồi : python 10_score.py [--draft nếu L/U chưa khóa]
Quy tắc là phép đo từ bằng chứng công khai; không mặc nhiên tương đương rubric do chuyên gia đánh giá.
"""
import argparse
import collections
import json
import re
import hashlib
from pathlib import Path

import pandas as pd

from common import CONF, DATA, OUT, ROOT, compile_kw, keep, keep_lang, load_yaml

RULES_VERSION = "rule-based-v1"

DOC_TYPES = ("bctn", "bcptbv", "web", "other")

# ---- đặc trưng văn bản --------------------------------------------------------------------------
ACTION = re.compile(r"triển khai|ra mắt|vận hành|ký kết|hoàn thành|đưa vào|áp dụng|thử nghiệm|xây dựng|nâng cấp|chứng nhận|đạt chuẩn"
                    r"|launched|deployed|implemented|went live|rolled out|introduced|completed|certified|piloted|upgraded|signed"
                    r"|partnered|established", re.I)
FUT_PRE = re.compile(r"(sẽ|dự kiến|dự định|phấn đấu|hướng tới|chưa|không|never|not|will|plans? to|aims? to|expected to|intends? to|going to)"
                     r"\s+(?:\S+\s+){0,2}$", re.I)      # động từ hành động đứng sau "sẽ/dự kiến/will" = kế hoạch, không tính
NUM = re.compile(r"\d[\d.,]*\s*(%|triệu|tỷ|nghìn|ngàn|lượt|khách hàng|giờ|người|quy trình|API|đối tác|million|billion|trillion|"
                 r"customers|users|hours|employees|staff|partners|transactions|processes|VND)", re.I)
MULTI_YEAR = re.compile(r"20\d\d.{0,40}20\d\d")
INDEP = re.compile(r"ISO\s?\d{4,5}|PCI[\s-]?DSS|SOC\s?2|kiểm toán độc lập|đánh giá độc lập|independent(ly)? (audit|assess|verif|review)"
                   r"|giải thưởng|\baward|xếp hạng|\branked|\branking|chứng nhận|certification|certified by"
                   r"|Deloitte|PwC|KPMG|Ernst|Global Finance|Asian Banker|Euromoney|The Banker|Forbes|Brand Finance|Kantar|Nielsen"
                   r"|Gartner|Great Place to Work|Vietnam Report|Fitch|Moody", re.I)
CERT = re.compile(r"ISO\s?\d{4,5}|PCI[\s-]?DSS|SOC\s?2", re.I)
GOV = re.compile(r"HĐQT|Hội đồng quản trị|ĐHĐCĐ|Đại hội đồng cổ đông|Board of Directors|General Meeting", re.I)
APPROVE = re.compile(r"phê duyệt|thông qua|nghị quyết|approv|endors|resolution", re.I)
PHASE = re.compile(r"giai đoạn|\bphase|lộ trình|roadmap|20\d\d\s*[-–]\s*20\d\d", re.I)
KPI = re.compile(r"\bKPI", re.I)
KPI_LINK = re.compile(r"đánh giá|thưởng|bonus|performance|lãnh đạo", re.I)
PLAN = re.compile(r"định hướng|chiến lược|kế hoạch|mục tiêu|tầm nhìn|strategy|strategic|plan|aim|vision|roadmap|priorit", re.I)

# Điều kiện bổ sung mức 4 của phiên bản quy tắc (mode, [atoms]). Atom: MULTI (số liệu đa kỳ), INDEP (dấu hiệu kiểm chứng),
# GOV (HĐQT/ĐHĐCĐ phê duyệt), PHASE (kế hoạch theo giai đoạn), KPI (KPI gắn đánh giá/thưởng), CERT2 (>= 2 chứng nhận)
L4 = {
    "K1": ("all", ["MULTI", "INDEP"]), "K2": ("all", ["MULTI", "INDEP"]), "K3": ("all", ["MULTI", "INDEP"]),
    "K4": ("all", ["MULTI", "INDEP"]), "S1": ("all", ["MULTI", "GOV"]), "S2": ("any", ["GOV", "KPI"]),
    "S3": ("all", ["MULTI", "PHASE"]), "S4": ("any", ["MULTI"]), "T1": ("any", ["INDEP", "MULTI"]),
    "T2": ("all", ["CERT2", "MULTI"]), "T3": ("all", ["MULTI"]), "T4": ("any", ["MULTI", "INDEP"]),
    "O1": ("any", ["MULTI", "INDEP"]), "O2": ("all", ["MULTI", "INDEP"]), "O3": ("all", ["MULTI", "INDEP"]),
    "O4": ("all", ["MULTI"]), "C1": ("any", ["MULTI", "INDEP"]), "C2": ("all", ["MULTI"]), "C3": ("all", ["MULTI"]),
    "C4": ("all", ["MULTI"]), "D1": ("any", ["INDEP"]), "D2": ("any", ["MULTI", "INDEP"]),
    "D3": ("any", ["MULTI", "INDEP"]), "D4": ("any", ["INDEP"]),
}


def has_action(w):
    return any(not FUT_PRE.search(w[max(0, m.start() - 40):m.start()]) for m in ACTION.finditer(w))


def features(w):
    """Đặc trưng của một đoạn (cửa sổ quanh từ khóa)."""
    act = has_action(w)
    return {
        "PLAN": bool(PLAN.search(w)), "ACT": act, "NUM": bool(NUM.search(w)), "L3": act and bool(NUM.search(w)),
        "INDEP": bool(INDEP.search(w)), "GOV": bool(GOV.search(w) and APPROVE.search(w)), "PHASE": bool(PHASE.search(w)),
        "KPI": bool(KPI.search(w) and KPI_LINK.search(w)), "MULTI_YEAR": bool(MULTI_YEAR.search(w)),
        "CERTS": {re.sub(r"[\s-]", "", c).upper() for c in (m.group(0) for m in CERT.finditer(w))},
    }


def level_of(f):
    return 3 if f["L3"] else 2 if f["ACT"] else 1


def search_key(text):
    """Khóa lọc sơ bộ; regex gốc vẫn quyết định khớp và ranh giới từ."""
    return re.sub(r"\s+", "", text).casefold().replace("ı", "i").replace("\u0307", "")


def workbook_evidence(row):
    """Excel giới hạn độ dài ô; bằng chứng đầy đủ luôn nằm trong auto_scores.csv."""
    evidence = row["supporting_evidence"]
    if len(evidence) <= 32767:
        return evidence
    return json.dumps(dict(source_file="out/auto_scores.csv", criterion=row["criterion"],
                           bank=row["bank"], year=int(row["year"])), ensure_ascii=False, sort_keys=True)


def excel_value(value):
    """Loại ký tự điều khiển XML không hợp lệ khi hiển thị Excel; CSV giữ nguyên đoạn gốc."""
    return re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", value) if isinstance(value, str) else value


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--context", type=int, default=300, help="số ký tự lấy mỗi bên từ khóa")
    ap.add_argument("--missing-as-zero", action="store_true",
                    help="tùy chọn cũ đã ngừng hỗ trợ: thiếu tài liệu luôn để trống")
    ap.add_argument("--coding", help="lưới tiêu chí tùy chọn; mặc định tạo từ banks.yaml và keywords.yaml")
    ap.add_argument("--bank", default="")
    ap.add_argument("--year", default="")
    ap.add_argument("--type", default="")
    ap.add_argument("--only-lang", default="")
    a, _ = ap.parse_known_args()          # --bank/--year/--only-lang do common.py xử lý
    if a.context < 1: ap.error("--context phải là số nguyên dương")
    if a.missing_as_zero: ap.error("Thiếu tài liệu phải để trống; không hỗ trợ --missing-as-zero.")

    KW = load_yaml("keywords.yaml")
    PAT = {c: [(search_key(k), compile_kw(k)) for k in v["keywords"]] for c, v in KW.items()}
    if a.coding:
        base = pd.read_excel(a.coding)
    else:
        banks = load_yaml("banks.yaml")
        base = pd.DataFrame([dict(criterion=c, criterion_name=v["name"], bank=b, year=y)
                             for c, v in KW.items() for b in banks["banks"]
                             for y in banks.get("coding_years", banks["years"])])
    base["bank"] = base["bank"].astype(str).str.strip().str.lower()
    base["criterion"] = base["criterion"].astype(str).str.strip().str.upper()
    base["year"] = base["year"].astype(int)
    base = base.loc[[keep(r.bank, r.year) for r in base.itertuples()]].copy()
    if base.empty: ap.error("Không có ngân hàng/năm nào khớp bộ lọc.")
    if base.duplicated(["criterion", "bank", "year"]).any(): ap.error("Lưới tiêu chí có dòng trùng.")
    if not base["criterion"].isin(KW).all(): ap.error("Lưới tiêu chí có mã ngoài keywords.yaml.")
    selected_banks = set(base["bank"])
    selected_types = set(a.type.split(",")) if a.type else set(DOC_TYPES)
    input_hashes = {}
    rules_hash = hashlib.sha256(Path(__file__).read_bytes() + (ROOT / "scripts/common.py").read_bytes()
                                + (CONF / "keywords.yaml").read_bytes()).hexdigest()
    input_hashes["config/banks.yaml"] = hashlib.sha256((CONF / "banks.yaml").read_bytes()).hexdigest()
    if a.coding: input_hashes[str(Path(a.coding))] = hashlib.sha256(Path(a.coding).read_bytes()).hexdigest()

    # ---- 1) đọc văn bản, gom các đoạn quanh từ khóa ----
    wins = collections.defaultdict(list)      # (bank, year, crit) -> [dict(file, page, text, feat)]
    docs = collections.defaultdict(list)      # (bank, year) -> [file]
    for jf in sorted((DATA / "text").glob("*.jsonl")):
        input_hashes[str(jf.relative_to(ROOT))] = hashlib.sha256(jf.read_bytes()).hexdigest()
        for line in open(jf, encoding="utf8"):
            d = json.loads(line)
            # Giữ lịch sử ba năm để điều kiện MULTI không đổi khi lọc riêng năm đầu ra.
            if (d["doc_type"] not in DOC_TYPES or d["doc_type"] not in selected_types
                    or str(d["bank"]).lower() not in selected_banks or not keep_lang(d.get("lang"))):
                continue
            if not d["text"].strip() or d.get("junk", 0) > (0.06 if d.get("engine") == "ocr" else 0.03):
                continue
            bank, year = str(d["bank"]).lower(), int(d["year"])
            pdf = d.get("source_file") or (str(jf.relative_to(ROOT)) if d["doc_type"] == "web"
                                           else f"data/raw/{bank}/{year}_{d['doc_type']}.pdf")
            if pdf not in docs[(bank, year)]:
                docs[(bank, year)].append(pdf)
            flat = re.sub(r"\s+", " ", d["text"])
            folded = search_key(flat)
            for c, pats in PAT.items():
                spans = sorted((m.start(), m.end()) for key, rx in pats if key in folded for m in rx.finditer(flat))
                last = -10 ** 9
                for s, e in spans:
                    if s < last + a.context:
                        continue                     # gộp các hit gần nhau thành một đoạn
                    last = e
                    w = flat[max(0, s - a.context): e + a.context]
                    wins[(bank, year, c)].append(dict(file=pdf, page=d["page"], text=w, f=features(w)))

    # ---- 2) lượt 1: năm nào có số liệu (mức 3) -> dùng cho điều kiện đa kỳ ----
    f3 = collections.defaultdict(bool)
    for k, ws in wins.items():
        f3[k] = any(w["f"]["L3"] for w in ws)

    # ---- 3) lượt 2: chấm điểm từng ô ----
    rows = []
    for r in base.itertuples():
        key = (r.bank, int(r.year), r.criterion)
        ws = wins.get(key, [])
        out = dict(criterion=r.criterion, bank=r.bank, year=int(r.year), auto_score=None, status="", confidence="",
                   evidence_file="", evidence_page="", evidence_quote="", features="", not_disclosed="", note="",
                   scoring_method="rule_based", rules_version=RULES_VERSION, rules_hash=rules_hash, supporting_evidence="[]")
        if not docs.get((r.bank, int(r.year))):
            out.update(status="no_document", note="chưa có văn bản đọc được sau lọc; thiếu dữ liệu, không chấm 0")
            rows.append(out); continue
        if not ws:
            out.update(auto_score=0, status="no_mention", confidence="low",
                       evidence_file="; ".join(docs[(r.bank, int(r.year))]),
                       note="thuật toán không tìm thấy từ khóa trong tài liệu đọc được; không kết luận ngân hàng không công bố")
            rows.append(out); continue

        fl = [w["f"] for w in ws]
        any_act, any_l3 = any(f["ACT"] for f in fl), any(f["L3"] for f in fl)
        score = 3 if any_l3 else 2 if any_act else 1
        atoms = {
            "INDEP": any(f["INDEP"] for f in fl), "GOV": any(f["GOV"] for f in fl),
            "PHASE": any(f["PHASE"] for f in fl), "KPI": any(f["KPI"] for f in fl),
            "CERT2": len(set().union(*[f["CERTS"] for f in fl])) >= 2,
            "MULTI": any_l3 and (any(f["MULTI_YEAR"] for f in fl)
                                 or any(f3.get((r.bank, y, r.criterion), False) for y in range(int(r.year) - 3, int(r.year)))),
        }
        mode, need = L4[r.criterion]
        ok = all(atoms[x] for x in need) if mode == "all" else any(atoms[x] for x in need)
        if score == 3 and ok:
            score = 4
        reach = [w for w in ws if level_of(w["f"]) >= min(score, 3)]
        best = max(reach or ws, key=lambda w: (sum(bool(v) for k, v in w["f"].items() if k != "CERTS"), len(w["text"])))
        caught = [k for k in ("PLAN", "ACT", "NUM", "L3", "INDEP", "GOV", "PHASE", "KPI") if any(f[k] for f in fl)]
        caught += [k for k in ("MULTI", "CERT2") if atoms[k]]
        out.update(auto_score=score, status="scored", evidence_file=best["file"], evidence_page=best["page"],
                   evidence_quote=best["text"][:400], features=",".join(caught),
                   confidence="high" if len(reach) >= 2 else "low",
                   note=f"{len(ws)} đoạn khớp từ khóa; mức 4 chỉ kiểm tra điều kiện {need} ({mode})" if score == 4 else
                        f"{len(ws)} đoạn khớp từ khóa")
        support = [dict(file=w["file"], page=w["page"], year=int(r.year), quote=w["text"],
                        features={k: sorted(v) if isinstance(v, set) else v for k, v in w["f"].items()}) for w in ws]
        if atoms["MULTI"]:
            for y in range(int(r.year) - 3, int(r.year)):
                support.extend(dict(file=w["file"], page=w["page"], year=y, quote=w["text"],
                                    features={k: sorted(v) if isinstance(v, set) else v for k, v in w["f"].items()})
                               for w in wins.get((r.bank, y, r.criterion), []) if w["f"]["L3"])
        out["supporting_evidence"] = json.dumps(support, ensure_ascii=False, sort_keys=True)
        rows.append(out)

    res = pd.DataFrame(rows)
    res.to_csv(OUT / "auto_scores.csv", index=False, encoding="utf-8-sig")

    # ---- 4) xuất cùng cấu trúc coding_sheet để 10_score.py dùng ----
    generated = set(res.columns) - {"criterion", "bank", "year"}
    m = base.drop(columns=[c for c in generated if c in base], errors="ignore").merge(res, on=["criterion", "bank", "year"], how="left", validate="one_to_one")
    m["final"] = m["auto_score"].astype("Int64")
    m["not_disclosed"] = pd.to_numeric(m["not_disclosed"], errors="coerce").astype("Int64")
    m["notes"] = "AUTO | conf=" + m["confidence"].fillna("") + " | " + m["features"].fillna("") + " | " + m["note"].fillna("")
    m["supporting_evidence"] = m.apply(workbook_evidence, axis=1)
    m = m.apply(lambda column: column.map(excel_value))
    workbook_path = OUT / "coding_auto.xlsx"
    temp_workbook = workbook_path.with_suffix(".tmp.xlsx")
    m.to_excel(temp_workbook, index=False)
    temp_workbook.replace(workbook_path)
    manifest = dict(scoring_method="rule_based", rules_version=RULES_VERSION, rules_hash=rules_hash,
                    context=a.context, bank=a.bank, year=a.year, doc_type=a.type, only_lang=a.only_lang,
                    input_hashes=input_hashes, missing_policy="blank", rows=len(res))
    (OUT / "auto_scoring_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8-sig")

    # ---- 5) tóm tắt ----
    print(f"Đã chấm {res.auto_score.notna().sum()}/{len(res)} ô -> out/auto_scores.csv, out/coding_auto.xlsx")
    print("\nTheo trạng thái:\n", res.status.value_counts().to_string())
    print("\nPhân bố điểm:\n", res.auto_score.value_counts(dropna=False).sort_index().to_string())
    miss = res[res.status == "no_document"][["bank", "year"]].drop_duplicates()
    if len(miss):
        print("\n[!] Ngân hàng-năm chưa có văn bản (kiểm tra 01_download/02_extract_text), các ô để trống:")
        print(miss.sort_values(["bank", "year"]).to_string(index=False))
    print("\nTiếp theo: python 10_score.py (hoặc --draft khi L/U chưa khóa)")


if __name__ == "__main__":
    main()
