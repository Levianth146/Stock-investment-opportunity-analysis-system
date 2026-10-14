"""Ma trận sẵn có dữ liệu + gợi ý điền dti_inputs + gói bàn giao dataset sạch.
  python 12_appendix.py                 # out/availability_matrix.csv  (NH x năm: tài liệu, trích text, số liệu DTI, chấm điểm, app)
  python 12_appendix.py --prefill       # out/dti_prefill.csv: số GỢI Ý từ financial_candidates.csv (CHƯA xác nhận, không ghi đè dti_inputs.csv)
  python 12_appendix.py --pages         # out/statement_pages.csv: trang CĐKT/KQKD/thuyết minh trong từng BCTC để mở PDF đọc tay
  python 12_appendix.py --bundle        # out/dataset_clean/: chỉ số liệu ĐÃ xác nhận + điểm chấm 'final' + app + ma trận + từ điển dữ liệu
Quy tắc: ô trống = không có dữ liệu (KHÔNG điền 0). data_conf = số chỉ số DTI TÍNH ĐƯỢC / 11."""
import csv, shutil, sys, importlib.util
import pandas as pd
from common import *

_score_spec = importlib.util.spec_from_file_location("bank_score", ROOT / "scripts" / "10_score.py")
score_tools = importlib.util.module_from_spec(_score_spec)
_score_spec.loader.exec_module(score_tools)

def rd(p):
    """Đọc CSV; nếu lệch số cột (append cũ) thử engine python / bỏ dòng lỗi."""
    if not p.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(p, encoding="utf-8-sig")
    except pd.errors.ParserError:
        return pd.read_csv(p, encoding="utf-8-sig", engine="python", on_bad_lines="warn")

def rd_extraction_report(p):
    """Chuẩn hóa extraction_report (header cũ 11 cột ↔ mới có bad_pages)."""
    if not p.exists():
        return pd.DataFrame()
    cols = ["file", "bank", "year", "doc_type", "pages", "pages_ocr", "avg_chars", "avg_junk",
            "engines_used", "flag", "lang", "bad_pages"]
    rows = []
    with open(p, newline="", encoding="utf-8-sig") as f:
        r = csv.reader(f)
        header = next(r, None) or []
        for row in r:
            d = dict(zip(header, row))
            if len(row) > len(header) and "bad_pages" not in header:
                d["lang"] = row[10] if len(row) > 10 else d.get("lang", "")
                d["bad_pages"] = row[11] if len(row) > 11 else ""
            rows.append({c: d.get(c, "") for c in cols})
    return pd.DataFrame(rows, columns=cols) if rows else pd.DataFrame(columns=cols)

banks = load_yaml("banks.yaml"); BK = list(banks["banks"]); YEARS = banks["years"]; CY = banks.get("coding_years", [])
src = rd(CONF / "sources.csv"); man = rd(DATA / "raw" / "manifest.csv")
rep = rd_extraction_report(OUT / "extraction_report.csv")
dti = rd(OUT / "dti_inputs.csv"); app = rd(OUT / "app_ratings.csv")
for df in (src, man, rep, dti):
    if len(df): df["year"] = df["year"].astype(int)
if len(rep): rep["doc_type"] = rep["doc_type"].astype(str)
APP_RATINGS = score_tools.load_app_rating(OUT / "app_ratings.csv")
PLATFORM = score_tools.load_platform(OUT / "manual_audit.xlsx")

def doc_state(b, y, t):
    s = src[(src.bank == b) & (src.year == y) & (src.doc_type == t)] if len(src) else []
    url = isinstance(s.iloc[0]["url"], str) and s.iloc[0]["url"].strip() if len(s) else ""
    note = s.iloc[0]["notes"] if len(s) and isinstance(s.iloc[0]["notes"], str) else ""
    if not url: return note or ("CHƯA ĐIỀN" if t != "bcptbv" else "chưa tìm thấy")
    r = rep[(rep.bank == b) & (rep.year == y) & (rep.doc_type == t)] if len(rep) else []
    if len(r): return "OK" if str(r.iloc[-1]["flag"]).startswith("OK") else "CẦN KIỂM"
    m = man[(man.bank == b) & (man.year == y) & (man.doc_type == t)] if len(man) and "doc_type" in man else []
    return "đã tải, chưa trích" if len(m) and m.iloc[-1]["status"] == "ok" else "có link, chưa tải"

DEF = {}; DEFT = {}; HASDEF = False   # (bank, year) -> definition của digital_customers (nạp trong matrix())
AUX = {"digital_customer_share", "nci", "net_profit_parent", "net_profit_consolidated"}   # biến phụ, không tính vào inputs_coverage
IND = ["K-Q1", "K-Q2", "K-Q3", "S-Q1", "S-Q2", "T-Q1", "T-Q2", "O-Q1", "O-Q2", "C-Q1", "C-Q2"]

def computable(V, b, y, has_app):
    """Dùng cùng công thức với bước 10; đếm chỉ số có đầu vào đã xác nhận."""
    definitions = {(bank, year, "digital_customers"): label for (bank, year), label in DEF.items()}
    definitions.update({(bank, year, "digital_txn_share"): label for (bank, year), label in DEFT.items()})
    calc = score_tools.Calc(V, definitions, APP_RATINGS, PLATFORM, 2021, max(YEARS))
    return {ind: value is not None for ind, (value, note) in calc.all(b, y).items()}

def matrix():
    rows = []
    V = {}
    global DEF, DEFT, HASDEF
    HASDEF = bool(len(dti)) and "definition" in dti.columns
    DEF = {(r["bank"], int(r["year"])): r["definition"] for _, r in dti[dti["variable"] == "digital_customers"].iterrows() if isinstance(r.get("definition"), str)} if HASDEF else {}
    DEFT = {(r["bank"], int(r["year"])): r["definition"] for _, r in dti[(dti["variable"] == "digital_txn_share") & dti["value"].notna()].iterrows() if isinstance(r.get("definition"), str)} if HASDEF else {}
    if len(dti):
        for _, r in dti[confirmed_mask(dti)].iterrows(): V[(r["bank"], int(r["year"]), r["variable"])] = float(r["value"])
    definitions = {(r.bank, int(r.year), r.variable): r.definition if isinstance(r.definition, str) else ""
                   for r in dti.itertuples()}
    calc = score_tools.Calc(V, definitions, APP_RATINGS, PLATFORM, 2021, max(CY or YEARS))
    indicators, gate = score_tools.build_indicators(calc, BK, YEARS, score_tools.load_bounds(False)[0])
    gate.to_csv(OUT / "step0_gate.csv", index=False, encoding="utf-8-sig")
    indicators.to_csv(OUT / "indicator_availability_matrix.csv", index=False, encoding="utf-8-sig")
    # Phụ lục B.3: lưới biến đầu vào đầy đủ; giữ bằng chứng dù chỉ số bị loại khỏi điểm.
    grid = pd.MultiIndex.from_product([BK, YEARS, sorted(dti.variable.unique())],
                                     names=["bank", "year", "variable"])
    variables = dti.set_index(["bank", "year", "variable"]).reindex(grid).reset_index()
    variables["available"] = confirmed_mask(variables)
    variables["n_missing_banks"] = variables.groupby(["year", "variable"]).available.transform(lambda s: (~s).sum())
    variables["disclosure_review"] = variables.bank.map(lambda b: "Agribank không niêm yết; đọc cùng note và nguồn" if b == "agribank" else "")
    variables.to_csv(OUT / "variable_availability_matrix.csv", index=False, encoding="utf-8-sig")
    for b in BK:
        has_app = b in APP_RATINGS
        for y in YEARS:
            d = dti[(dti.bank == b) & (dti.year == y) & ~dti.variable.isin(AUX)] if len(dti) else pd.DataFrame()
            nv = int(d["value"].notna().sum()) if len(d) else 0; nt = len(d)
            nc = int(confirmed_mask(d).sum()) if len(d) else 0
            npdf = nc
            ar = int(((app.bank == b) & (app.get("year", y) == y)).sum()) if len(app) and "bank" in app else 0
            group = indicators[(indicators.bank == b) & (indicators.year == y)]
            n = int(group.z_before_step0.notna().sum())
            used = int(group.included_in_score.sum())
            f = {r.indicator: r.included_in_score for r in group.itertuples()}
            rows.append({"bank": b, "year": y, "bctn": doc_state(b, y, "bctn"), "bctc": doc_state(b, y, "bctc"), "bcptbv": doc_state(b, y, "bcptbv"),
                         "dti_vars_total": nt, "dti_vars_filled": nv, "dti_vars_confirmed": nc, "dti_vars_pdf_read": npdf,
                         "dti_vars_not_collected": int((d["value"].isna() & d["note"].fillna("").str.startswith("not_collected")).sum()) if len(d) else 0,
                         "inputs_coverage": round(nv / nt, 3) if nt else "",
                         "dti_ind_computable": n,
                         "dti_ind_list": ";".join(group.loc[group.z_before_step0.notna(), "indicator"]),
                         "dti_ind_used_list": ";".join(k for k, v in f.items() if v),
                         "dti_ind_used": used, "dti_ind_retained": int(group.retained.sum()),
                         "scoring_coverage": round(used / len(IND), 3), "step0_method": "indicator_per_year_v1",
                         "data_conf": round(n / len(IND), 3), "in_coding_years": y in CY, "app_rows": ar})
    m = pd.DataFrame(rows); m.to_csv(OUT / "availability_matrix.csv", index=False, encoding="utf-8-sig")
    print(m.drop(columns=["dti_ind_list", "dti_ind_used_list"]).to_string(index=False)); print("->", OUT / "availability_matrix.csv")
    print(f"data_conf = chỉ số DTI có đầu vào đã xác nhận / {len(IND)}; cửa sổ và công thức theo bước 10. inputs_coverage = biến đầu vào đã điền / tổng biến.")

MAP = {"equity": "equity", "total_equity": "equity", "customer_deposits": "customer_deposits", "casa_deposits": "casa_deposits", "total_assets": "total_assets",
       "net_profit": "net_profit", "net_interest_income": "net_interest_income", "net_fee_income": "net_fee_income", "opex": "opex",
       "op_profit_before_provision": "op_profit_before_provision", "software_gross_cost": "software_gross_cost"}

def prefill():
    fc = rd(OUT / "financial_candidates.csv")
    if not len(fc): sys.exit("Chưa có out/financial_candidates.csv (chạy 04 --bctc trước).")
    out = []
    for (b, y, v), g in fc.groupby(["bank", "year", "variable"]):
        if v not in MAP: continue
        g = g.sort_values("page"); first = g.iloc[0]
        nums = str(first["parsed_numbers(first4)"]).split(" | ")
        out.append([b, y, MAP[v], nums[0].replace(",", ""), first.get("unit_hint", ""), first.get("source_file", f"data/raw/{b}/{y}_bctc.pdf"), first["page"], len(g), "GỢI Ý - phải đối chiếu PDF; dòng: " + str(first["raw_line (+dòng kế)"])[:90]])
    pd.DataFrame(out, columns=["bank", "year", "variable", "value_suggested", "unit", "source_file", "page", "n_candidates", "note"]).to_csv(OUT / "dti_prefill.csv", index=False, encoding="utf-8-sig")
    print(len(out), "gợi ý ->", OUT / "dti_prefill.csv", "(số liệu cột năm HIỆN TẠI = số đầu tiên; kiểm tay rồi chép sang dti_inputs.csv kèm confirmed_by)")

def bundle():
    d = OUT / "dataset_clean"; d.mkdir(exist_ok=True)
    matrix()
    matrix_df = rd(OUT / "availability_matrix.csv")
    conf = dti[confirmed_mask(dti)].copy() if len(dti) else dti
    if len(conf): conf["verification"] = "đã đối chiếu PDF"
    conf.to_csv(d / "dti_inputs_confirmed.csv", index=False, encoding="utf-8-sig")
    cs = OUT / "coding_auto.xlsx"
    if cs.exists():
        c = pd.read_excel(cs); c = c[c["final"].notna() | (c.get("not_disclosed") == 1)] if "final" in c else c
        if len(c): c.to_csv(d / "coding_final.csv", index=False, encoding="utf-8-sig")
    if len(app): app.to_csv(d / "app_ratings.csv", index=False, encoding="utf-8-sig")
    matrix_df.to_csv(d / "availability_matrix.csv", index=False, encoding="utf-8-sig")
    for filename in ("step0_gate.csv", "indicator_availability_matrix.csv", "variable_availability_matrix.csv"):
        shutil.copy2(OUT / filename, d / filename)
    dti.to_csv(d / "dti_inputs_full.csv", index=False, encoding="utf-8-sig")
    source_path = CONF / "sources.csv"
    if source_path.exists(): shutil.copy2(source_path, d / "sources.csv")
    check_path = OUT / "dti_check.csv"
    if check_path.exists(): shutil.copy2(check_path, d / "dti_check.csv")
    variable_rows = []
    if len(dti):
        for variable, group in dti.groupby("variable"):
            filled = int(pd.to_numeric(group["value"], errors="coerce").notna().sum())
            verified = int(confirmed_mask(group).sum())
            units = ", ".join(sorted(set(group["unit"].dropna().astype(str))))
            variable_rows.append(f"| {variable} | {units} | {filled}/{len(group)} | {verified} |")
    dictionary = [
        "# Từ điển dữ liệu bàn giao",
        "",
        f"Ngày tạo gói: {today()}. Có {len(conf)} dòng số liệu đã xác nhận trên {len(dti)} dòng đầu vào.",
        "Gói được tạo từ dữ liệu hiện tại; thông tin phạm vi, định nghĩa và ngoại lệ nằm trong note/definition của từng dòng.",
        "",
        "- dti_inputs_confirmed.csv: số hữu hạn, có nguồn/trang, được người chấm đối chiếu PDF; loại range-checked và mọi nhãn tự động.",
        "- dti_inputs_full.csv: toàn bộ đầu vào, gồm ô trống và lý do thiếu. Không thay đổi dữ liệu gốc.",
        "- availability_matrix.csv: dti_ind_computable/data_conf là số tính được trước cổng; dti_ind_used/scoring_coverage là số dùng sau Bước 0 / 11.",
        "- variable_availability_matrix.csv: Phụ lục B.3, ngân hàng × biến × năm, xác nhận/nguồn/trang và số ngân hàng thiếu biến.",
        "- indicator_availability_matrix.csv và step0_gate.csv: khả năng tính chỉ số và quyết định giữ/loại chung từng năm; thiếu >=2 ngân hàng thì loại.",
        "- coding_final.csv: các điểm thuật toán đã có từ coding_auto.xlsx, kèm phiên bản quy tắc và bằng chứng.",
        "- app_ratings.csv: lịch sử thu thập; bước 10 chọn ngày mới nhất từng ngân hàng và dòng cuối cùng mỗi cửa hàng trong ngày đó.",
        "- sources.csv: URL và ghi chú tài liệu; BCPTBV tùy chọn, có thể tích hợp trong BCTN.",
        "",
        "Các cột đầu vào: bank, year, variable, value, unit, source_file, page, confirmed_by, note, definition.",
        "Bước 19 bổ sung review_status (pending/resolved), reviewed_by, review_date (YYYY-MM-DD), review_evidence; gói giữ nguyên các cột này.",
        "resolved chỉ giải quyết cờ ghi chú ở lớp C khi đủ người/ngày/bằng chứng; không thay thế xác nhận PDF hoặc kiểm tra phạm vi.",
        "net_profit_parent dùng cho ROE với equity definition=parent; net_profit_consolidated dùng cho ROA với total_assets definition=consolidated. Không sao chép net_profit khi chưa xác nhận phạm vi.",
        "page là số trang PDF từ 1. verification trong bản confirmed là đã đối chiếu PDF.",
        "range-checked chỉ kiểm khoảng hợp lý, chưa đọc PDF; nằm trong bản full, chưa dùng tính điểm chính thức.",
        "not_collected là chưa thu thập; not_disclosed là đã đọc và không có. Ô thiếu để trống, không điền 0.",
        "",
        "| Biến | Đơn vị ghi trong đầu vào | Có số/tổng dòng | Đã đối chiếu đủ nguồn |",
        "|---|---|---|---|",
        *variable_rows,
        "",
        "Công thức theo scripts/10_score.py; mốc đầu kỳ mặc định 2021, S-Q2/O-Q2 cần cách ít nhất 2 năm.",
        "S-Q1 và S-Q2 cần cùng definition. CIR = abs(opex)/(abs(opex)+LN trước dự phòng); TOI = abs(opex)+LN trước dự phòng.",
        "T-Q1 dùng tổng tài sản bình quân; O-Q2 dùng CBNV bình quân. Nếu thiếu năm trước, bước 10 ghi rõ trường hợp dùng cuối kỳ.",
        "T-Q2 cần đủ 8 mã nền tảng duy nhất, giá trị 0/1. Rating/checklist chỉ áp dụng cho năm cuối được chọn.",
        "z = 100·min{1; max[0; (x−L)/(U−L)]}; L/U cố định trong config/dti_bounds.yaml, phải khóa trước tính chính thức.",
        "Nếu trụ cột thiếu DTI, P_k = DBI_k; trọng số cơ sở 80/20 và trung bình 6 trụ cột.",
        "Bước 0 bắt buộc ở cấp chỉ số DTI theo từng năm; không xóa số gốc, không tự thay proxy. Cận L/U và mẫu số độ tin cậy 11 không đổi.",
        "Rating/checklist chỉ áp cho năm cuối của dự án, không áp lùi khi chạy riêng một năm lịch sử. Bộ DTI giữ lại khác nhau giữa các năm.",
        "",
        "Mọi số và điểm phải được truy vết tới nguồn gốc. Xem README.md, config và ghi chú từng dòng trước khi dùng kết quả.",
    ]
    (d / "DATA_DICTIONARY.md").write_text("\n".join(dictionary) + "\n", encoding="utf-8-sig")
    print("Đã tạo", d, [p.name for p in d.iterdir()])

def pages():
    """Tìm trang của từng báo cáo chính trong BCTC (đã OCR) để bạn mở PDF đọc tay số còn thiếu: out/statement_pages.csv."""
    import json, re, unicodedata
    def fold(s):
        s = unicodedata.normalize("NFD", s.replace("đ", "d").replace("Đ", "D")); return "".join(c for c in s if unicodedata.category(c) != "Mn").lower()
    KEYS = {"can_doi_ke_toan": r"bao cao tinh hinh tai chinh|balance sheet|statement of financial position|can doi ke toan",
            "ket_qua_kinh_doanh": r"bao cao ket qua hoat dong|income statement|statement of income|ket qua kinh doanh",
            "thuyet_minh_tien_gui_KH": r"tien gui cua khach hang|deposits from customers",
            "thuyet_minh_TSCD_vo_hinh": r"tai san co dinh vo hinh|intangible"}
    rows = []
    for jf in sorted((DATA / "text").glob("*_bctc.jsonl")):
        for line in open(jf, encoding="utf8"):
            d = json.loads(line); t = fold(d["text"])
            if len(re.findall(r"\d{1,3}[.,]\d{3}[.,]\d{3}", t)) < 4: continue          # trang có bảng số lớn mới tính
            for k, pat in KEYS.items():
                if re.search(pat, t[:600] if k in ("can_doi_ke_toan", "ket_qua_kinh_doanh") else t): rows.append([d["bank"], d["year"], k, d["page"]])
    df = pd.DataFrame(rows, columns=["bank", "year", "statement", "page"]).groupby(["bank", "year", "statement"]).page.apply(lambda s: ",".join(map(str, sorted(s)[:6]))).reset_index()
    df.to_csv(OUT / "statement_pages.csv", index=False, encoding="utf-8-sig"); print(df.to_string(index=False)); print("->", OUT / "statement_pages.csv")

if "--pages" in sys.argv: pages()
elif "--prefill" in sys.argv: prefill()
elif "--bundle" in sys.argv: bundle()
else: matrix()
