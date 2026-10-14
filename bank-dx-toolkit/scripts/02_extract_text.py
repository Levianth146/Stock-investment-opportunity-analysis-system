"""PDF -> text theo trang (JSONL). Tự chọn engine tốt nhất cho từng trang (ít 'rác' nhất): pdftotext (poppler) / PyMuPDF / pdfplumber.
OCR dự phòng (--ocr) khi trang không có chữ hoặc vẫn nhiều lỗi font tiếng Việt.
  --ocr-pages 1-60,80-90 : chỉ OCR các trang này (BCTC: CĐKT/KQKD + thuyết minh cần dùng) -> nhanh hơn nhiều; trang còn lại giữ text gốc.
Cách dùng: python 02_extract_text.py [--bank tcb] [--year 2024] [--type bctn] [--ocr [--ocr-pages 1-60,80-90] [--psm 6]] [--force] [--lang vie+eng] [--engines pdftotext,pymupdf,pdfplumber]"""
import csv, json, os, shutil, subprocess, sys, pdfplumber
from common import *

# Windows cp1252 không in được tiếng Việt trong flag — tránh UnicodeEncodeError khi print
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

force = "--force" in sys.argv; use_ocr = "--ocr" in sys.argv
lang = sys.argv[sys.argv.index("--lang") + 1] if "--lang" in sys.argv else "vie+eng"
order = (sys.argv[sys.argv.index("--engines") + 1] if "--engines" in sys.argv else "pdftotext,pymupdf,pdfplumber").split(",")
JUNK_MAX = 0.03   # trên ngưỡng này coi là nghi lỗi font/dấu
def parse_pages(spec):
    """'1-40,60-80' -> {1..40, 60..80}; None nếu không đặt --ocr-pages (OCR mọi trang cần)."""
    if not spec: return None
    s = set()
    for part in spec.split(","):
        a, _, b = part.strip().partition("-"); s.update(range(int(a), int(b or a) + 1))
    return s
OCR_PAGES = parse_pages(sys.argv[sys.argv.index("--ocr-pages") + 1] if "--ocr-pages" in sys.argv else "")
ocr = None
if use_ocr:
    import pytesseract
    # Tìm cả bản cài riêng cho người dùng, kể cả terminal chưa cập nhật PATH.
    _candidates = [os.environ.get("TESSERACT_CMD"), shutil.which("tesseract"),
                   r"C:\Program Files\Tesseract-OCR\tesseract.exe",
                   r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe"]
    if os.environ.get("LOCALAPPDATA"):
        _candidates.append(os.path.join(os.environ["LOCALAPPDATA"], "Programs", "Tesseract-OCR", "tesseract.exe"))
    _exe = next((p for p in _candidates if p and os.path.isfile(p)), None)
    if _exe and os.name == "nt":
        # Tesseract Windows cần đường dẫn 8.3 khi tên tài khoản chứa dấu tiếng Việt.
        import ctypes
        _short_path = ctypes.create_unicode_buffer(32768)
        _length = ctypes.windll.kernel32.GetShortPathNameW(ctypes.c_wchar_p(_exe), _short_path, len(_short_path))
        if 0 < _length < len(_short_path): _exe = _short_path.value
    if _exe:
        pytesseract.pytesseract.tesseract_cmd = _exe
    _data_dir = os.path.join(os.path.dirname(_exe), "tessdata") if _exe else None
    # Truyền thư mục qua môi trường của tiến trình để tránh lỗi dấu ngoặc kép trên Windows.
    if _data_dir and os.path.isdir(_data_dir) and not os.environ.get("TESSDATA_PREFIX"):
        os.environ["TESSDATA_PREFIX"] = _data_dir
    _data_cfg = ""
    try:
        _have = set(pytesseract.get_languages(config=_data_cfg))
        _need = set(lang.split("+"))
        if not _need <= _have:
            sys.exit(f"Tesseract thiếu gói ngôn ngữ {sorted(_need - _have)} (đang có: {sorted(_have)}). Cài lại Tesseract và tick 'Vietnamese', hoặc chép vie.traineddata vào thư mục tessdata.")
    except pytesseract.TesseractNotFoundError:
        sys.exit("Không tìm thấy Tesseract. Cài bản Windows (UB Mannheim) rồi thêm thư mục cài (C:\\Program Files\\Tesseract-OCR) vào PATH, mở terminal MỚI; hoặc kiểm tra: tesseract --version")
    PSM = sys.argv[sys.argv.index("--psm") + 1] if "--psm" in sys.argv else ""
    _cfg = _data_cfg + (f" --psm {PSM}" if PSM else "")   # --psm 6 giữ nhãn và số trên cùng một dòng của bảng
    ocr = lambda img: pytesseract.image_to_string(img, lang=lang, config=_cfg)
try:
    import pymupdf
except Exception:
    try: import fitz as pymupdf
    except Exception: pymupdf = None

def by_pdftotext(path):
    if not shutil.which("pdftotext"): return None
    r = subprocess.run(["pdftotext", "-layout", str(path), "-"], capture_output=True)
    if r.returncode: return None
    return r.stdout.decode("utf8", "replace").split("\f")[:-1] or None
def by_pymupdf(path):
    if pymupdf is None: return None
    with pymupdf.open(path) as d: return [p.get_text() for p in d]
def by_plumber(path):
    with pdfplumber.open(path) as d: return [p.extract_text() or "" for p in d.pages]
ENG = {"pdftotext": by_pdftotext, "pymupdf": by_pymupdf, "pdfplumber": by_plumber}

report = []
for pdf in sorted((DATA / "raw").glob("*/*.pdf")):
    bank, year, typ = stem_parts(pdf)
    if not keep(bank, year, typ): continue
    out = DATA / "text" / f"{bank}_{year}_{typ}.jsonl"
    if out.exists() and not force:
        print("bỏ qua (đã có)", out.name); continue
    results = {}
    for e in order:
        try:
            pages = ENG[e](pdf)
            if pages: results[e] = pages
        except Exception as ex:
            print("  engine", e, "lỗi:", ex)
    if not results:
        print("KHÔNG đọc được", pdf.name); continue
    npages = max(len(v) for v in results.values())
    n_ocr = 0; chars = 0; used = {}; jsum = 0.0; recs = []
    doc_for_ocr = pdfplumber.open(pdf) if ocr else None
    mdoc = pymupdf.open(str(pdf)) if (ocr and pymupdf) else None
    def render(i):
        """Ảnh trang để OCR: ưu tiên pymupdf (nhanh, chịu được PDF mà pdfplumber không dựng được trang); dự phòng pdfplumber."""
        if mdoc is not None:
            from PIL import Image
            pix = mdoc[i].get_pixmap(dpi=200, alpha=False)
            return Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
        return doc_for_ocr.pages[i].to_image(resolution=200).original
    for i in range(npages):
        best = None
        for e, pages in results.items():
            if i < len(pages):
                t = clean_text(pages[i]); j = junk_score(pages[i])
                if best is None or j < best[1] - 1e-9: best = (e, j, t)
        e, j, t = best
        if (len(t.strip()) < 40 or j > JUNK_MAX) and ocr is not None and (OCR_PAGES is None or (i + 1) in OCR_PAGES):
            try:
                img = render(i)
                t2 = clean_text(ocr(img)); j2 = junk_score(t2)
                if len(t2.strip()) >= 40 and (len(t.strip()) < 40 or j2 < j): t, e, j = t2, "ocr", j2; n_ocr += 1
            except Exception as ex:
                if not globals().get("_ocr_err_shown"):
                    print(f"  OCR lỗi ở trang {i + 1}: {type(ex).__name__}: {str(ex)[:300]}"); _ocr_err_shown = True
                e = f"{e}+ocr_failed"
        used[e] = used.get(e, 0) + 1; chars += len(t); jsum += j
        recs.append({"bank": bank, "year": year, "doc_type": typ, "page": i + 1, "engine": e, "junk": round(j, 4), "text": t})
    if doc_for_ocr: doc_for_ocr.close()
    doc_lang = detect_lang(" ".join(r["text"] for r in recs))
    for r in recs: r["lang"] = doc_lang
    with open(out, "w", encoding="utf8") as f:
        for r in recs: f.write(json.dumps(r, ensure_ascii=False) + "\n")
    avg_j = jsum / max(npages, 1)
    full = " ".join(r["text"] for r in recs)
    sqf = squeeze(full)
    if typ == "bctc": ok_content = any(x in sqf for x in ("tàisản", "lợinhuận", "totalassets", "profitaftertax", "netprofit", "totalliabilities"))
    else: ok_content = doc_lang in ("vi", "en")
    long_pages = [r for r in recs if len(r["text"]) >= 200 and (OCR_PAGES is None or r["page"] in OCR_PAGES)]     # trang bìa/trang thưa chữ giãn cách không đại diện
    bad_pages = sum(1 for r in long_pages if r["junk"] > (0.06 if r["engine"] == "ocr" else JUNK_MAX))   # OCR nhiễu ở đầu/chân trang -> ngưỡng nới
    bad_share = bad_pages / max(len(long_pages), 1)
    flag = ("OK (có OCR: kiểm tay số)" if n_ocr else "OK") if (bad_share <= 0.15 and ok_content) else "NGHI LỖI FONT/ẢNH -> chạy lại với --ocr (cần Tesseract + gói 'vie') và kiểm tra tay vài trang"
    report.append([pdf.name, bank, year, typ, npages, n_ocr, round(chars / max(npages, 1)), round(avg_j, 4), json.dumps(used), flag, doc_lang, bad_pages])
    print(pdf.name, npages, "trang | engine:", used, "| OCR:", n_ocr, "| junk:", round(avg_j, 4), "|", flag)
# Cột cố định — đừng đổi thứ tự khi append (file cũ thiếu bad_pages sẽ được chuẩn hóa).
REPORT_COLS = ["file", "bank", "year", "doc_type", "pages", "pages_ocr", "avg_chars", "avg_junk", "engines_used", "flag", "lang", "bad_pages"]
if report:
    p = OUT / "extraction_report.csv"
    existing = []
    if p.exists():
        with open(p, newline="", encoding="utf-8-sig") as f:
            r = csv.reader(f)
            old_h = next(r, None) or []
            for row in r:
                d = dict(zip(old_h, row))
                if len(row) > len(old_h) and "bad_pages" not in old_h:
                    d["lang"] = row[10] if len(row) > 10 else d.get("lang", "")
                    d["bad_pages"] = row[11] if len(row) > 11 else ""
                existing.append([d.get(c, "") for c in REPORT_COLS])
    with open(p, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f, quoting=csv.QUOTE_MINIMAL)
        w.writerow(REPORT_COLS)
        w.writerows(existing)
        w.writerows(report)
