"""Hàm dùng chung."""
import pathlib, re, unicodedata, yaml, datetime

ROOT = pathlib.Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
OUT = ROOT / "out"
CONF = ROOT / "config"
for p in (DATA / "raw", DATA / "text", DATA / "web", OUT):
    p.mkdir(parents=True, exist_ok=True)

def load_yaml(name):
    with open(CONF / name, encoding="utf8") as f:
        return yaml.safe_load(f)

def nfc(s: str) -> str:
    return unicodedata.normalize("NFC", s)

def today() -> str:
    return datetime.date.today().isoformat()

def stem_parts(path: pathlib.Path):
    """data/raw/<bank>/<year>_<type>.pdf -> (bank, year, type)"""
    bank = path.parent.name
    year, _, typ = path.stem.partition("_")
    return bank, year, typ

# Từ thông dụng để kiểm tra PDF có trích ra tiếng Việt đúng không (lỗi font cũ TCVN3/VNI cho kết quả rác)
VI_STOP = {"của","và","các","trong","là","có","được","cho","với","ngân","hàng","năm","một","những","này","đã","không","để"}
def vi_score(text: str) -> float:
    toks = re.findall(r"\w+", nfc(text).lower())
    if len(toks) < 50:
        return 1.0  # quá ngắn để kết luận
    return sum(t in VI_STOP for t in toks) / len(toks)

EN_STOP = {"the","of","and","to","in","for","with","our","we","is","are","by","on","that","as","from","an","at","has","have","this"}
def en_score(text: str) -> float:
    toks = re.findall(r"[a-z]+", text.lower())
    if len(toks) < 50:
        return 1.0
    return sum(t in EN_STOP for t in toks) / len(toks)
def detect_lang(text: str) -> str:
    """'vi' nếu có nhiều từ chức năng tiếng Việt; 'en' nếu có nhiều từ chức năng tiếng Anh; ngược lại 'unknown'."""
    if vi_score(text) >= 0.05 and vi_score(text) < 1.0: return "vi"
    return "en" if en_score(text) >= 0.08 and en_score(text) < 1.0 else "unknown"

# ---- Bộ lọc dòng lệnh dùng chung cho 01-04, 07-09:  --bank tcb,mb  --year 2024,2025  --type bctn,bctc  --only-lang vi|en
import sys as _sys
for _stream in (_sys.stdout, _sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")
def _argv_set(name):
    if name in _sys.argv:
        i = _sys.argv.index(name)
        return {x.strip().lower() for x in _sys.argv[i + 1].split(",") if x.strip()}
    return None
_FB, _FY, _FT, ONLY_LANG = _argv_set("--bank"), _argv_set("--year"), _argv_set("--type"), _argv_set("--only-lang")
def keep(bank, year, doc_type=None) -> bool:
    """True nếu (ngân hàng, năm, loại tài liệu) thỏa các cờ --bank/--year/--type. Không có cờ nào thì giữ tất cả."""
    if _FB is not None and str(bank).lower() not in _FB: return False
    if _FY is not None and str(year) not in _FY: return False
    if _FT is not None and doc_type is not None and str(doc_type).lower() not in _FT: return False
    return True
def keep_lang(lang, default=None) -> bool:
    """Lọc ngôn ngữ; default='vi' giới hạn LDA/PhoBERT dù có --only-lang."""
    lang = lang or "vi"
    if default is not None and lang != default: return False
    if ONLY_LANG is not None: return lang in ONLY_LANG
    return default is None or lang == default

AUTO_LABELS = {"auto-unverified", "range-checked", "fin-cand", "page-patch", "page-confirm", "kpi-heuristic"}

def is_manual_confirmation(label):
    """Nhãn người xác nhận; loại mọi nhãn kiểm tra hoặc điền tự động đã biết."""
    return isinstance(label, str) and bool(label.strip()) and label.strip() not in AUTO_LABELS

def confirmed_mask(df):
    """Chỉ nhận số hữu hạn đã đối chiếu, có tệp nguồn và trang PDF hợp lệ."""
    import pandas as pd
    import numpy as np
    required = {"value", "confirmed_by", "source_file", "page"}
    if not required <= set(df.columns):
        return pd.Series(False, index=df.index)
    value = pd.to_numeric(df["value"], errors="coerce")
    page = pd.to_numeric(df["page"], errors="coerce")
    return (np.isfinite(value) & df["confirmed_by"].map(is_manual_confirmation)
            & df["source_file"].fillna("").astype(str).str.strip().ne("")
            & page.ge(1) & page.mod(1).eq(0))

def parse_num(tok: str):
    """Đọc số kiểu Việt/Anh: '1.234.567', '1,234,567.89', '(12.345)', '12,5'. Trả float hoặc None."""
    t = tok.strip()
    neg = t.startswith("(") and t.endswith(")") or t.startswith("-")
    t = t.strip("()-").strip()
    if not re.fullmatch(r"\d[\d.,]*", t):
        return None
    if "." in t and "," in t:
        dec = "." if t.rfind(".") > t.rfind(",") else ","
        t = t.replace("," if dec == "." else ".", "").replace(dec, ".")
    elif t.count(".") > 1 or t.count(",") > 1:
        t = t.replace(".", "").replace(",", "")
    elif "." in t or "," in t:
        sep = "." if "." in t else ","
        tail = t.split(sep)[1]
        t = t.replace(sep, "") if len(tail) == 3 else t.replace(sep, ".")
    try:
        v = float(t)
    except ValueError:
        return None
    return -v if neg else v

def clean_text(t: str) -> str:
    t = re.sub(r"\(cid:\d+\)", "", t)
    t = t.replace("\ufffd", "").replace("\u00ad", "")
    return nfc(t)

def junk_score(text: str) -> float:
    """Điểm 'rác' của văn bản trích từ PDF (càng thấp càng tốt): tỷ lệ token 1 ký tự (mảnh vỡ do lỗi font/dấu)
    + (cid:..) + ký tự thay thế. Văn bản tiếng Việt bình thường gần như không có token 1 chữ cái."""
    raw = text
    n_bad = len(re.findall(r"\(cid:\d+\)", raw)) + raw.count("\ufffd")
    body = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", " ", nfc(clean_text(raw)))      # ký tự điều khiển của dấu đầu dòng (♦, \x07...)
    is_en = en_score(body) >= 0.08 and vi_score(body) < 0.05
    if is_en:   # những cấu trúc hợp lệ của tiếng Anh bị tách thành mảnh 1 chữ cái: sở hữu cách, E&S, y.o., nhãn danh sách a./b./i.
        body = re.sub(r"[’']s\b", "", body)
        body = re.sub(r"\b([A-Za-z])&([A-Za-z])\b", r"\1\2", body)
        body = re.sub(r"\by\.o\.", " ", body, flags=re.I)
        body = re.sub(r"(?m)^[ \t]*[A-Za-z]{1,3}[.)][ \t]", " ", body)
    toks = re.findall(r"[^\W\d_]+", body)
    if len(toks) < 20:
        return 0.0
    ok1 = {"a", "à", "ơ", "ô"} | ({"i"} if is_en else set())
    one = sum(1 for t in toks if len(t) == 1 and t.lower() not in ok1)
    return (one + n_bad) / len(toks)

def squeeze(s: str) -> str:
    """Bỏ mọi khoảng trắng + hạ chữ thường: so khớp nhãn bất chấp khoảng trắng thừa do lỗi trích PDF."""
    return re.sub(r"\s+", "", nfc(s)).lower()

def compile_kw(k: str, exact: bool = False):
    """Regex cho một từ khóa. Viết tắt IN HOA (<=6 ký tự): khớp chính xác, phân biệt hoa/thường.
    Còn lại: không phân biệt hoa/thường; chế độ chịu lỗi cho phép 0-1 khoảng trắng giữa các chữ cái
    (PDF lỗi font hay tạo 'Tiề n', 'ch uyển'). exact=True tắt chế độ chịu lỗi."""
    cs = k.replace(" ", "").isupper() and len(k) <= 6
    fuzzy = (not exact) and (not cs) and len(k.replace(" ", "")) >= 6
    word = (lambda w: r"\s?".join(map(re.escape, w))) if fuzzy else re.escape
    pat = r"(?<!\w)" + r"\s+".join(word(w) for w in k.split()) + r"(?!\w)"
    return re.compile(pat, 0 if cs else re.I)
