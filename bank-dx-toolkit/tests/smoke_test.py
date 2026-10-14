"""Smoke test: chạy pipeline offline trên PDF mẫu trong examples/ (không cần mạng, không cần torch).
Chạy từ thư mục scripts/:  python ../tests/smoke_test.py
Test chạy trên BẢN SAO tạm của repo nên không làm bẩn data/ và out/ thật."""
import pathlib, shutil, subprocess, sys, tempfile, json, os
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = pathlib.Path(__file__).resolve().parents[1]
fails = []
def check(name, cond, detail=""):
    print(("OK   " if cond else "FAIL ") + name + (f"  {detail}" if detail and not cond else ""))
    if not cond: fails.append(name)

tmp = pathlib.Path(tempfile.mkdtemp(prefix="bankdx_")); work = tmp / "repo"
# Bỏ data/out/models: bản sao không mang PDF thật (tránh 02 --force trích lại cả kho).
shutil.copytree(ROOT, work, ignore=shutil.ignore_patterns(".git", "__pycache__", ".venv", "models", "data", "out"))
sc = work / "scripts"
(work / "data" / "raw" / "demo").mkdir(parents=True, exist_ok=True)
(work / "data" / "text").mkdir(parents=True, exist_ok=True)
(work / "out").mkdir(parents=True, exist_ok=True)
shutil.copy(work / "examples" / "mau_bctn.pdf", work / "data" / "raw" / "demo" / "2025_bctn.pdf")
shutil.copy(work / "examples" / "mau_bctc.pdf", work / "data" / "raw" / "demo" / "2025_bctc.pdf")

def run(*args):
    # Đọc bytes rồi decode UTF-8: trên Windows text=True hay dùng cp1252 và vỡ khi script in tiếng Việt
    r = subprocess.run([sys.executable, *args], cwd=sc, capture_output=True,
                       env=dict(os.environ, PYTHONUTF8="1", PYTHONIOENCODING="utf-8"))
    out = (r.stdout or b"").decode("utf-8", "replace") + (r.stderr or b"").decode("utf-8", "replace")
    return r.returncode, out

# 1) cú pháp mọi script
for f in sorted(sc.glob("*.py")):
    rc, out = run("-m", "py_compile", f.name); check(f"compile {f.name}", rc == 0, out[-200:])

# 2) hàm dùng chung
sys.path.insert(0, str(sc))
import common
check("parse_num kiểu Việt", common.parse_num("1.234.567") == 1234567.0)
check("parse_num số âm ngoặc", common.parse_num("(12.345)") == -12345.0)
rx = common.compile_kw("RPA")
check("acronym phân biệt hoa/thường: khớp 'RPA'", bool(rx.search("triển khai RPA")))
check("acronym phân biệt hoa/thường: không khớp 'rpa' trong từ khác", not rx.search("therapa rpa"), "")
check("compile_kw khớp mờ khoảng trắng", bool(common.compile_kw("chuyển đổi số").search("chuyển  đổi\nsố")))
check("squeeze bỏ khoảng trắng", common.squeeze("Lợi  nhuận\n sau thuế") == "lợinhuậnsauthuế")

# 3) pipeline offline
rc, out = run("02_extract_text.py", "--force"); check("02 trích text", rc == 0 and list((work / "data/text").glob("*.jsonl")), out[-300:])
rc, out = run("03_locate_evidence.py"); check("03 tìm bằng chứng", rc == 0 and (work / "out/evidence_candidates.csv").exists(), out[-300:])
rc, out = run("04_extract_numbers.py", "--bctc", "--kpi"); check("04 trích số", rc == 0 and (work / "out/financial_candidates.csv").exists(), out[-300:])
rc, out = run("07_text_mining.py", "--expand"); check("07 text mining", rc == 0 and (work / "out/tm_criterion.csv").exists(), out[-300:])
rc, out = run("09_phobert.py"); check("09 in hướng dẫn khi không có cờ", rc == 0, out[-200:])


# 4) tiếng Anh + bộ lọc dòng lệnh
import csv as _csv
common_keep = common.keep_lang
check("keep_lang mặc định vi: en bị loại", common_keep("en", "vi") is False and common_keep(None, "vi") is True)
EN_TXT = ("In 2024 we launched digital onboarding with e-KYC and facial recognition, and 8.5 million customers used our mobile app. "
          "Digital transactions accounted for 98.5% of all transactions in the year. "
          "We deployed robotic process automation (RPA) across 120 processes, saving 300,000 hours for the bank. "
          "Our data lake and data governance framework were established under the Chief Data Officer. "
          "Training hours reached 42 hours per employee. Technology staff represent 8.2% of total employees. "
          "The Board of Directors is committed to the strategy of the bank and to the interests of our customers and shareholders.")
check("detect_lang nhận ra tiếng Anh", common.detect_lang(EN_TXT * 2) == "en")
BCTC_EN = "\n".join(["Total assets 1,234,567,890 1,100,000,000", "Owners' equity 123,456,789 100,000,000", "Profit after tax 23,456,789 20,000,000",
                     "Operating expenses (12,345,678) (11,000,000)", "Net interest income 45,678,901 40,000,000", "Deposits from customers 900,000,000 850,000,000"])
tx = work / "data" / "text"
for y in ("2023", "2024"):
    with open(tx / f"enbank_{y}_bctn.jsonl", "w", encoding="utf8") as f:
        f.write(json.dumps({"bank": "enbank", "year": y, "doc_type": "bctn", "page": 1, "engine": "x", "junk": 0, "lang": "en", "text": EN_TXT}, ensure_ascii=False) + "\n")
with open(tx / "enbank_2024_bctc.jsonl", "w", encoding="utf8") as f:
    f.write(json.dumps({"bank": "enbank", "year": "2024", "doc_type": "bctc", "page": 1, "engine": "x", "junk": 0, "lang": "en", "text": BCTC_EN}, ensure_ascii=False) + "\n")
rc, out = run("04_extract_numbers.py", "--bctc", "--kpi", "--bank", "enbank")
fin = list(_csv.DictReader(open(work / "out/financial_candidates.csv", encoding="utf-8-sig")))
vars_found = {r["variable"] for r in fin if r["bank"] == "enbank"}
need = {"total_assets", "equity", "net_profit", "opex", "net_interest_income", "customer_deposits"}
check("04 --bctc nhãn tiếng Anh", rc == 0 and need <= vars_found, f"thiếu {need - vars_found}")
check("04 --bank lọc đúng (chỉ enbank)", all(r["bank"] == "enbank" for r in fin))
kp = list(_csv.DictReader(open(work / "out/kpi_candidates.csv", encoding="utf-8-sig")))
check("04 --kpi mẫu câu tiếng Anh", any(r["variable"] == "digital_txn_share" and "98.5" in r["numbers_found"] for r in kp), str([r["variable"] for r in kp]))
rc, out = run("03_locate_evidence.py", "--bank", "enbank")
ev = list(_csv.DictReader(open(work / "out/evidence_candidates.csv", encoding="utf-8-sig")))
crit_found = {r["criterion"] for r in ev}
check("03 từ khóa tiếng Anh + lọc --bank", rc == 0 and ev and all(r["bank"] == "enbank" for r in ev) and {"K2", "O1", "D1", "D2"} <= crit_found, str(sorted(crit_found)))
rc, out = run("03_locate_evidence.py", "--year", "1999")
check("03 --year không khớp thì không lỗi, kết quả rỗng", rc == 0 and len(list(_csv.DictReader(open(work / "out/evidence_candidates.csv", encoding="utf-8-sig")))) == 0)
rc, out = run("07_text_mining.py", "--bank", "enbank", "--only-lang", "en")
tm = list(_csv.DictReader(open(work / "out/tm_criterion.csv", encoding="utf-8-sig")))
check("07 có cột lang và chạy trên văn bản tiếng Anh", rc == 0 and tm and tm[0]["lang"] == "en" and any(float(r["bm25"]) > 0 for r in tm), out[-300:])

# 4) BCTC dạng ô-mỗi-dòng (nhãn, số thuyết minh, rồi số tiền ở dòng sau) - bố cục thật của Techcombank 2024 EN
cells = ["Deposits from customers","18","533,392,350","454,660,779","TOTAL SHAREHOLDERS\u2019 EQUITY","23","147,939,621","131,616,065",
         "Total operating income","46,990,397","40,061,092","Operating expenses","32","(15,369,735)","(13,251,796)",
         "Net profit contributed to the Bank\u2019s","shareholders","21,522,928","18,003,802","(VND million)"]
(work / "data" / "text" / "zz_2024_bctc.jsonl").write_text(json.dumps({"bank": "zz", "year": 2024, "doc_type": "bctc", "page": 1, "text": "\n".join(cells)}, ensure_ascii=False) + "\n", encoding="utf8")
rc, out = run("04_extract_numbers.py", "--bctc", "--bank", "zz", "--year", "2024")
import csv
fc = {r["variable"]: r["parsed_numbers(first4)"] for r in csv.DictReader(open(work / "out/financial_candidates.csv", encoding="utf-8-sig"))}
check("04 ô-mỗi-dòng: tiền gửi KH bỏ qua số thuyết minh 18", fc.get("customer_deposits", "").startswith("533,392,350"), str(fc))
check("04 ô-mỗi-dòng: vốn CSH (dấu ' cong)", fc.get("total_equity", "").startswith("147,939,621"), str(fc))
check("04 ô-mỗi-dòng: TOI", fc.get("total_operating_income", "").startswith("46,990,397"), str(fc))
check("04 ô-mỗi-dòng: opex bỏ qua note 32", fc.get("opex", "").startswith("-15,369,735"), str(fc))
check("04 ô-mỗi-dòng: lợi nhuận cổ đông mẹ (nhãn ngắt dòng)", fc.get("net_profit_parent", "").startswith("21,522,928"), str(fc))

shutil.rmtree(tmp, ignore_errors=True)
print("\n" + ("TẤT CẢ OK" if not fails else f"{len(fails)} LỖI: {fails}"))
sys.exit(1 if fails else 0)
