"""Chạy hàng loạt 01 -> 02 -> (OCR tự động cho file bị cờ) -> 03 -> 04 -> 12 cho nhiều ngân hàng một lần.
  python run_all.py                          # tất cả NH, tất cả năm
  python run_all.py --banks vcb,mb           # chỉ vài NH (mở nhiều terminal, mỗi terminal một NH; nhớ chạy --post-only ở cuối)
  python run_all.py --years 2020,2023,2025   # chỉ vài năm
  python run_all.py --skip-download          # đã có PDF, bỏ bước 01
  python run_all.py --ocr-types bctc,bctn    # loại tài liệu được OCR khi bị cờ (mặc định: bctc)
  python run_all.py --ocr-pages 1-60 --agri-pages 1-100 --psm 6
  python run_all.py --force-ocr              # OCR lại cả file đã OK
  python run_all.py --post-only              # chỉ chạy 03, 04, 12 (sau khi các terminal OCR xong)
  python run_all.py --dry-run                # chỉ in danh sách lệnh, không chạy
Quy tắc: không bao giờ ghi vào dti_inputs.csv / coding_sheet.xlsx / config. Lỗi một bước không làm dừng cả lượt; cuối lượt in bảng tổng kết.
Nhật ký: out/run_all.log"""
import argparse, csv, datetime, subprocess, sys, os, pathlib

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
OUT = ROOT / "out"; OUT.mkdir(exist_ok=True)
ap = argparse.ArgumentParser()
ap.add_argument("--banks", default=""); ap.add_argument("--years", default=""); ap.add_argument("--skip-download", action="store_true")
ap.add_argument("--ocr-types", default="bctc"); ap.add_argument("--ocr-pages", default="1-60"); ap.add_argument("--agri-pages", default="1-100")
ap.add_argument("--psm", default="6"); ap.add_argument("--force-ocr", action="store_true"); ap.add_argument("--post-only", action="store_true")
ap.add_argument("--no-ocr", action="store_true"); ap.add_argument("--dry-run", action="store_true")
a = ap.parse_args()

env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
LOG = open(OUT / "run_all.log", "a", encoding="utf-8")
results = []   # (bước, trạng thái)

def filt():
    f = []
    if a.banks: f += ["--bank", a.banks]
    if a.years: f += ["--year", a.years]
    return f

def run(label, script, *args):
    cmd = [sys.executable, script, *args]
    line = f"[{datetime.datetime.now():%H:%M:%S}] {label}: python {script} {' '.join(args)}"
    print(line, flush=True); LOG.write(line + "\n")
    if a.dry_run: results.append((label, "dry-run")); return 0
    r = subprocess.run(cmd, cwd=HERE, capture_output=True, env=env)
    out = (r.stdout + r.stderr).decode("utf-8", errors="replace")
    LOG.write(out + "\n"); LOG.flush()
    tail = "\n".join(out.strip().splitlines()[-6:])
    print("   " + tail.replace("\n", "\n   "), flush=True)
    results.append((label, "OK" if r.returncode == 0 else f"LỖI (mã {r.returncode})"))
    return r.returncode

def report_latest():
    """Dòng mới nhất của mỗi file trong extraction_report.csv (file được ghi nối tiếp nên lấy dòng cuối)."""
    p = OUT / "extraction_report.csv"; d = {}
    if not p.exists(): return d
    with open(p, newline="", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f): d[(r["bank"], str(r["year"]), r["doc_type"])] = r
    return d

if not a.post_only:
    if not a.skip_download: run("01 tải PDF", "01_download.py", *filt())
    run("02 trích text (không OCR, bỏ qua file đã có)", "02_extract_text.py", *filt())
    if not a.no_ocr:
        types = set(a.ocr_types.split(","))
        todo = [(b, y, t, r) for (b, y, t), r in report_latest().items()
                if t in types and (not a.banks or b in a.banks.split(",")) and (not a.years or y in a.years.split(","))
                and (a.force_ocr or not r["flag"].startswith("OK"))]
        print(f"\n{len(todo)} file cần OCR: " + ", ".join(f"{b}-{y}-{t}" for b, y, t, _ in todo) + "\n", flush=True)
        for b, y, t, _ in sorted(todo):
            pages = a.agri_pages if b == "agribank" else a.ocr_pages
            run(f"02 OCR {b} {y} {t}", "02_extract_text.py", "--bank", b, "--year", y, "--type", t, "--ocr", "--ocr-pages", pages, "--psm", a.psm, "--force")

run("03 tìm bằng chứng", "03_locate_evidence.py", *filt())
run("04 số BCTC + KPI", "04_extract_numbers.py", "--bctc", "--kpi", *filt())
run("09c chấm DBI bằng quy tắc", "09c_auto_score.py", *filt())
run("12 trang các báo cáo chính", "12_appendix.py", "--pages")
run("12 gợi ý dti_inputs", "12_appendix.py", "--prefill")
run("12 ma trận sẵn có dữ liệu", "12_appendix.py")

print("\n===== TỔNG KẾT =====")
for l, s in results: print(f"{s:14s} {l}")
rep = report_latest()
bad = [(k, r["flag"][:40]) for k, r in sorted(rep.items()) if not r["flag"].startswith("OK") and (not a.banks or k[0] in a.banks.split(","))]
print(f"\nFile còn bị cờ trong extraction_report.csv: {len(bad)}")
for k, f in bad: print("  ", "-".join(k), "|", f)
print("\nXem: out/availability_matrix.csv, out/financial_candidates.csv, out/kpi_candidates.csv, out/statement_pages.csv, out/dti_prefill.csv")
print("Nhật ký đầy đủ: out/run_all.log")
