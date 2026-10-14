"""Trích số liệu ứng viên cho các chỉ số DTI và biến Lớp C.
  --bctc : đọc BCTC (doc_type=bctc) -> out/financial_candidates.csv (tổng tài sản, vốn CSH, LNST, chi phí HĐ, LN thuần trước dự phòng,
           thu nhập lãi thuần, lãi thuần dịch vụ, phần mềm máy tính, tiền gửi KKH, tiền gửi KH)
  --kpi  : đọc BCTN/BCPTBV -> out/kpi_candidates.csv (tỷ lệ GD số, KH số, CBNV, nhân sự công nghệ, giờ đào tạo)
Kết quả là ỨNG VIÊN kèm trang để đối chiếu mắt; người dùng xác nhận rồi ghi vào out/dti_inputs.csv.
Đơn vị BCTC ngân hàng thường là 'triệu đồng' - kiểm tra đầu bảng (bản tiếng Anh: 'VND million').
Lọc: --bank tcb,mb  --year 2024  (xem common.keep). Hỗ trợ cả nhãn/câu tiếng Anh (chưa kiểm thử trên báo cáo thật)."""
import csv, json, re, sys
from common import *

NUMTOK = re.compile(r"\(?-?\d[\d.,]*\)?")
THOUSANDS = re.compile(r"\d{1,3}(?:[.,]\d{3})+")
def nums(line):
    out = []
    for m in NUMTOK.finditer(line):
        core = m.group(0).strip("()-")
        if THOUSANDS.fullmatch(core):      # số tiền nguyên (triệu đồng): bỏ mọi dấu ngăn nghìn, kể cả OCR lẫn . và , (1.414,986.259)
            v = float(re.sub(r"[.,]", "", core)); v = -v if m.group(0).startswith("(") or m.group(0).startswith("-") else v
            out.append(v); continue
        v = parse_num(m.group(0))
        if v is not None: out.append(v)
    return out

# (biến, nhãn, kiểu so khớp: start = dòng bắt đầu bằng nhãn | has = chứa nhãn, ghi chú). So khớp đã bỏ khoảng trắng + chữ thường.
BCTC_LABELS = [
 ("total_assets", "tổng tài sản", "start", "Bảng CĐKT, cột số cuối năm"),
 ("equity", "vốn chủ sở hữu", "start", "Bảng CĐKT; trùng ở thuyết minh, chọn dòng trong CĐKT"),
 ("equity", "tổng vốn chủ sở hữu", "start", "Bảng CĐKT: TỔNG VỐN CHỦ SỞ HỮU"),
 ("total_assets", "tổng cộng tài sản", "start", "Bảng CĐKT"),
 ("net_profit", "lợi nhuận sau thuế", "start", "Báo cáo KQKD (dùng LNST của cổ đông ngân hàng mẹ nếu có tách)"),
 ("opex", "chi phí hoạt động", "start", "KQKD: Chi phí hoạt động (mục VIII)"),
 ("op_profit_before_provision", "lợi nhuận thuần từ hoạt động kinh doanh trước chi phí dự phòng", "has", "KQKD (mục IX). Tổng thu nhập HĐ = mục IX + mục VIII. Nhãn dài có thể bị ngắt dòng: xem raw_line"),
 ("net_interest_income", "thu nhập lãi thuần", "start", "KQKD (mục I)"),
 ("net_fee_income", "lãi thuần từ hoạt động", "start", "KQKD: dòng bắt đầu 'Lãi thuần từ hoạt động...' có thể là dịch vụ / kinh doanh ngoại hối / khác; nhãn bị ngắt dòng, xem raw_line"),
 ("software_gross_cost", "phần mềm", "start", "Thuyết minh TSCĐ vô hình: lấy NGUYÊN GIÁ cuối kỳ, không lấy hao mòn"),
 ("casa_deposits", "tiền gửi không kỳ hạn", "has", "Thuyết minh Tiền gửi của khách hàng"),
 ("customer_deposits", "tiền gửi của khách hàng", "start", "Bảng CĐKT/ thuyết minh"),
 # ---- Nhãn tiếng Anh (BCTC bản dịch). CHƯA kiểm thử trên BCTC thật; mỗi ngân hàng dịch nhãn hơi khác nhau -> bổ sung khi gặp.
 ("total_assets", "total assets", "start", "[EN] Balance sheet"),
 ("equity", "owners' equity", "start", "[EN] Balance sheet (cũng thử: owners’ equity, shareholders' equity)"),
 ("equity", "owners’ equity", "start", "[EN] Balance sheet"),
 ("equity", "shareholders' equity", "start", "[EN] Balance sheet"),
 ("equity", "total equity", "start", "[EN] Balance sheet"),
 ("net_profit", "profit after tax", "start", "[EN] Income statement (dùng phần thuộc cổ đông ngân hàng mẹ nếu có tách)"),
 ("net_profit", "net profit after tax", "start", "[EN] Income statement"),
 ("net_profit", "net profit for the year", "start", "[EN] Income statement"),
 ("opex", "operating expenses", "start", "[EN] Income statement: Operating expenses"),
 ("opex", "total operating expenses", "start", "[EN] Income statement"),
 ("op_profit_before_provision", "net operating profit before provision for credit losses", "has", "[EN] Income statement; nhãn dài có thể ngắt dòng, xem raw_line"),
 ("op_profit_before_provision", "operating profit before provision", "has", "[EN] Income statement"),
 ("net_interest_income", "net interest income", "start", "[EN] Income statement"),
 ("net_interest_income", "net interest and similar income", "start", "[EN] Income statement"),
 ("net_fee_income", "net fee and commission income", "start", "[EN] Income statement"),
 ("net_fee_income", "net gain from services", "start", "[EN] Income statement: Net gain from services activities"),
 ("software_gross_cost", "software", "start", "[EN] Thuyết minh intangible fixed assets: lấy cost (nguyên giá) cuối kỳ, không lấy accumulated amortisation"),
 ("casa_deposits", "demand deposits", "has", "[EN] Thuyết minh Deposits from customers"),
 ("casa_deposits", "current accounts", "has", "[EN] Thuyết minh Deposits from customers"),
 ("customer_deposits", "deposits from customers", "start", "[EN] Balance sheet / thuyết minh"),
 ("customer_deposits", "customer deposits", "start", "[EN] Balance sheet / thuyết minh"),
 # ---- Bổ sung sau khi chạy BCTC thật (Techcombank 2024, bản EN)
 ("total_operating_income", "total operating income", "start", "[EN] Income statement: Total operating income = TOI (dùng trực tiếp; nếu báo cáo không có dòng này thì TOI = mục IX + mục VIII)"),
 ("total_operating_income", "tổng thu nhập hoạt động", "start", "Nếu báo cáo có dòng này thì dùng trực tiếp làm TOI"),
 ("op_profit_before_provision", "profit before provision for credit losses", "has", "[EN] Income statement: Profit before provision for credit losses"),
 ("net_profit_parent", "net profit contributed to the bank's shareholders", "start", "[EN] Income statement: lợi nhuận thuộc cổ đông ngân hàng mẹ (ưu tiên cho ROE)"),
 ("net_profit_parent", "profit attributable to shareholders of the bank", "start", "[EN] Income statement"),
 ("net_profit_parent", "profit attributable to equity holders of the bank", "start", "[EN] Income statement"),
 ("net_profit_parent", "lợi nhuận sau thuế của cổ đông của ngân hàng mẹ", "has", "Income statement"),
 ("non_controlling_interests", "non-controlling interests", "start", "[EN] Balance sheet (trong vốn chủ sở hữu) hoặc Income statement: lấy dòng trong CĐKT để trừ khi tính vốn CSH của cổ đông ngân hàng mẹ"),
 ("non_controlling_interests", "lợi ích của cổ đông thiểu số", "start", "CĐKT / KQKD"),
 ("net_fee_income", "net fees and commission income", "start", "[EN] Income statement"),
 ("net_profit_parent", "profit attributable to the shareholders of the bank", "start", "[EN] Income statement (ưu tiên cho ROE)"),
 ("net_profit_parent", "profit attributable to the bank's shareholders", "start", "[EN] Income statement"),
 ("net_profit_parent", "lợi nhuận thuần của cổ đông ngân hàng", "start", "KQKD (VCB): LN thuộc cổ đông ngân hàng mẹ (ưu tiên cho ROE)"),
 ("net_profit_parent", "lợi nhuận của cổ đông ngân hàng mẹ", "start", "KQKD"),
 ("non_controlling_interests", "lợi ích của cổ đông không kiểm soát", "start", "CĐKT (vốn CSH) hoặc KQKD (VCB)"),
 ("non_controlling_interests", "lợi ích cổ đông thiểu số", "start", "CĐKT / KQKD"),
 ("non_controlling_interests", "profit attributable to non-controlling interest", "start", "[EN] Income statement: LN thuộc cổ đông thiểu số (trừ khỏi LNST để ra LN cổ đông mẹ)"),
 ("op_profit_before_provision", "profit before provision expenses for credit losses", "has", "[EN] Income statement (BIDV: Net profit before provision expenses for credit losses)"),
 ("total_equity", "total shareholders' equity", "start", "[EN] Balance sheet: TOTAL SHAREHOLDERS' EQUITY (gồm cả lợi ích cổ đông thiểu số)"),
 ("total_equity", "total owners' equity", "start", "[EN] Balance sheet"),
 # software_gross_cost: KHÔNG tự động. Trong thuyết minh TSCĐ vô hình, "Software" là CỘT của bảng; đọc tay hàng Cost/Closing balance.
]
# số La Mã đầu dòng, kể cả khi OCR đọc sai (Ih. / lll, / XUI. - / ill,): chỉ cắt khi cả token toàn ký tự giống số La Mã và theo sau là khoảng trắng
ROMAN = re.compile(r"^\s*[IVXLUHivxluh1|!]{1,5}h?\s*[.,)]?\s+[-–]?\s*")
UNIT = re.compile(r"(VND\s*(?:million|billion|thousand)|million\s*VND|triệu\s*đồng|tỷ\s*đồng|nghìn\s*đồng)", re.I)
import unicodedata
def _norm(s):
    """Bỏ khoảng trắng, hạ chữ thường, chuẩn hóa nháy cong và BỎ DẤU tiếng Việt (OCR hay làm rụng dấu: 'TONG VON CHU SO HUU')."""
    t = unicodedata.normalize("NFD", squeeze(s).replace("’", "'").replace("‘", "'").replace("đ", "d"))
    return "".join(c for c in t if unicodedata.category(c) != "Mn")
def _numeric_only(s):
    return bool(re.fullmatch(r"[\s\d.,()\-–—]*", s))
def run_bctc():
    rows = []
    for jf in sorted((DATA / "text").glob("*_bctc.jsonl")):
        for line in open(jf, encoding="utf8"):
            d = json.loads(line)
            if not keep(d["bank"], d["year"], "bctc") or not keep_lang(d.get("lang")): continue
            lines = [nfc(x) for x in d["text"].splitlines() if x.strip()]
            um = UNIT.search(d["text"]); unit = um.group(1) if um else ""
            for idx, ln in enumerate(lines):
                body = ROMAN.sub("", ln)
                sq = _norm(body)
                txt = _norm(NUMTOK.sub("", body))                                         # phần chữ của dòng (không có số)
                sq3 = _norm(NUMTOK.sub("", " ".join([body] + lines[idx + 1: idx + 3])))  # nhãn có thể ngắt qua 2-3 dòng
                for var, label, mode, note in BCTC_LABELS:
                    lab = _norm(label)
                    wrapped = len(txt) >= 8 and ((lab.startswith(txt) and sq3.startswith(lab)) or (mode == "has" and lab not in sq and 0 <= sq3.find(lab) <= 6))
                    if (mode == "start" and sq.startswith(lab)) or (mode == "has" and lab in sq) or wrapped:
                        v = nums(body)
                        if any(abs(x) >= 1000 for x in v): v = [x for x in v if abs(x) >= 1000]   # bỏ số tham chiếu thuyết minh (V.5...)
                        else:
                            # PDF dạng ô-mỗi-dòng: nhãn, rồi số thuyết minh, rồi các số tiền nằm ở các dòng kế tiếp
                            v = []; cont = lab not in sq          # nhãn chưa kết thúc ở dòng này -> cho phép bỏ qua dòng chữ nối tiếp
                            skipped = 0
                            for nxt in lines[idx + 1: idx + 9]:
                                if not _numeric_only(nxt):
                                    if cont and not v and skipped == 0 and len([x for x in nums(nxt) if abs(x) >= 1000]) >= 2:
                                        v = nums(nxt); break          # dòng nối tiếp của nhãn ngắt dòng mang luôn số tiền
                                    if v or not cont or skipped >= 2: break
                                    skipped += 1; continue
                                v.extend(nums(nxt))
                            if any(abs(x) >= 1000 for x in v): v = [x for x in v if abs(x) >= 1000]
                        if v and any(abs(x) >= 1000 for x in v):     # mọi biến BCTC tính bằng triệu đồng: bỏ ứng viên chỉ toàn số nhỏ (số thuyết minh / số thứ tự)
                            nxt3 = " ⏎ ".join(x.strip() for x in lines[idx + 1: idx + 5])
                            rows.append([d["bank"], d["year"], d["page"], var, (ln.strip() + " ⏎ " + nxt3)[:260], " | ".join(f"{x:,.2f}" for x in v[:4]), len(v), note, unit,
                                         str((DATA / "raw" / d["bank"] / f"{d['year']}_bctc.pdf").relative_to(ROOT))])
    with open(OUT / "financial_candidates.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f); w.writerow(["bank", "year", "page", "variable", "raw_line (+dòng kế)", "parsed_numbers(first4)", "n_numbers", "where_to_check", "unit_hint", "source_file"]); w.writerows(rows)
    print(len(rows), "dòng ứng viên ->", OUT / "financial_candidates.csv")

SENT = re.compile(r"(?<=[.;!?])\s+|\n{2,}")
PCT = r"\d{1,3}(?:[.,]\d+)?\s*%"
BIG = r"\d[\d.,]*\s*(?:triệu|nghìn|ngàn|tỷ|million|billion|thousand)?"
KPI_PATTERNS = [
 ("digital_txn_share", re.compile(r"giao dịch.{0,60}(kênh số|trực tuyến|digital|điện tử|phi tiền mặt)|(kênh số|trực tuyến|digital).{0,60}giao dịch|(digital|online|electronic|non-cash|mobile|via digital channels?).{0,60}transactions?|transactions?.{0,60}(digital|online|electronic|non-cash|via digital|through digital)", re.I), re.compile(PCT)),
 ("digital_customers", re.compile(r"khách hàng.{0,50}(số|digital|ngân hàng số|mobile banking|hoạt động trên)|(mobile banking|ngân hàng số|kênh số).{0,50}khách hàng|(digital|mobile banking|internet banking|active|app).{0,50}(customers|users|clients)|(customers|users|clients).{0,50}(digital|mobile banking|app\b)", re.I), re.compile(BIG + r"\s*(?:khách hàng|KH|customers|users|clients)?|" + PCT)),
 ("total_customers", re.compile(r"(tổng số|quy mô|có hơn|đạt)\s*.{0,25}khách hàng|(total|over|more than|reached|serving)\s*.{0,25}customers", re.I), re.compile(BIG)),
 ("headcount", re.compile(r"(tổng số|số lượng|quy mô).{0,30}(cán bộ nhân viên|CBNV|nhân sự|lao động|nhân viên)|(total|number of).{0,30}(employees|staff|headcount|workforce)", re.I), re.compile(r"\d[\d.,]{2,}")),
 ("tech_staff", re.compile(r"(nhân sự|cán bộ|nhân viên|CBNV|kỹ sư).{0,40}(công nghệ|CNTT|IT\b|kỹ thuật số|dữ liệu)|(IT|technology|tech|digital|data|engineers?).{0,40}(staff|employees|talents?|professionals?|personnel)|(staff|employees|engineers).{0,40}(IT\b|technology|digital|data)", re.I), re.compile(PCT + r"|\d[\d.,]{2,}")),
 ("training_hours_per_head", re.compile(r"(giờ đào tạo|giờ/người|số giờ|giờ học)|(training hours|hours of training|learning hours|hours per (employee|person|staff))", re.I), re.compile(r"\d[\d.,]*")),
]
def run_kpi():
    rows = []
    for jf in sorted((DATA / "text").glob("*.jsonl")):
        for line in open(jf, encoding="utf8"):
            d = json.loads(line)
            if d["doc_type"] not in ("bctn", "bcptbv", "other"): continue
            if not keep(d["bank"], d["year"], d["doc_type"]) or not keep_lang(d.get("lang")): continue
            flat = re.sub(r"[ \t]+", " ", d["text"])
            for s in SENT.split(flat):
                s1 = re.sub(r"\s+", " ", s).strip()
                if len(s1) < 25: continue
                for var, trig, numrx in KPI_PATTERNS:
                    if trig.search(s1):
                        found = [m.group(0) for m in numrx.finditer(s1)]
                        found = [x for x in found if not re.fullmatch(r"\s*(19|20)\d\d[.,]?\s*", x)]   # bỏ số năm
                        if found: rows.append([d["bank"], d["year"], d["doc_type"], d["page"], var, "; ".join(x.strip() for x in found[:5]), s1[:300], str((DATA / "raw" / d["bank"] / f"{d['year']}_{d['doc_type']}.pdf").relative_to(ROOT))])
    with open(OUT / "kpi_candidates.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f); w.writerow(["bank", "year", "doc_type", "page", "variable", "numbers_found", "sentence", "source_file"]); w.writerows(rows)
    print(len(rows), "câu ứng viên ->", OUT / "kpi_candidates.csv")

if __name__ == "__main__":
    if "--bctc" in sys.argv: run_bctc()
    if "--kpi" in sys.argv: run_kpi()
    if not ({"--bctc", "--kpi"} & set(sys.argv)): print(__doc__)
