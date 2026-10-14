"""Rà S-Q1 trong BCTN đã tải: trích PDF trực tiếp, OCR các trang được chọn.

Không ghi điểm/đầu vào; kết quả OCR chỉ dùng định vị để đọc lại PDF.
Chạy từ scripts/: python 21_scan_sq1_reports.py --ocr.
"""
import argparse
import ctypes
import json
import os
from pathlib import Path
import re
import subprocess
import unicodedata
import pymupdf
from common import DATA, OUT


def fold(text):
    return "".join(c for c in unicodedata.normalize("NFD", text.lower())
                   if not unicodedata.combining(c))


def passages(text):
    compact = re.sub(r"\s+", " ", text)
    normalized = fold(compact)
    pattern = r"digital channels|digital transactions|online transactions|ty le giao dich|kenh so|giao dich truc tuyen|giao dich dien tu"
    return [compact[max(0, m.start() - 180):m.end() + 400]
            for m in re.finditer(pattern, normalized)]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ocr", action="store_true")
    args = parser.parse_args()
    output = OUT / "sq1_review"
    output.mkdir(exist_ok=True)
    rows = []
    for bank in ("bidv", "vcb"):
        for year in range(2021, 2026):
            source = DATA / "raw" / bank / f"{year}_bctn.pdf"
            with pymupdf.open(source) as document:
                for page_no, page in enumerate(document, 1):
                    text = page.get_text(sort=True)
                    for excerpt in passages(text):
                        rows.append(dict(bank=bank, year=year, source_file=source.relative_to(DATA.parent).as_posix(),
                                         page=page_no, engine="pymupdf_sorted", evidence_excerpt=excerpt))
    if args.ocr:
        executable = Path(os.environ["LOCALAPPDATA"]) / "Programs/Tesseract-OCR/tesseract.exe"
        if not executable.exists():
            raise FileNotFoundError("Không tìm thấy Tesseract để OCR")
        buffer = ctypes.create_unicode_buffer(32768)
        ctypes.windll.kernel32.GetShortPathNameW(str(executable), buffer, len(buffer))
        command = buffer.value or str(executable)
        selections = {("vcb", 2024): list(range(4, 27)) + list(range(36, 55)),
                      ("vcb", 2025): list(range(19, 26)),
                      ("bidv", 2025): [5, 6, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 50]}
        for (bank, year), pages in selections.items():
            source = DATA / "raw" / bank / f"{year}_bctn.pdf"
            with pymupdf.open(source) as document:
                for page_no in pages:
                    stem = output / f"{bank}_{year}_p{page_no}_ocr"
                    image = stem.with_suffix(".png")
                    document[page_no - 1].get_pixmap(matrix=pymupdf.Matrix(1.5, 1.5)).save(image)
                    result = subprocess.run([command, str(image), str(stem), "-l", "vie+eng", "--psm", "3"],
                                            capture_output=True, text=True, encoding="utf-8", errors="replace")
                    if result.returncode:
                        raise RuntimeError(result.stderr)
                    text = stem.with_suffix(".txt").read_text(encoding="utf-8-sig")
                    excerpts = passages(text)
                    rows.extend(dict(bank=bank, year=year, source_file=source.relative_to(DATA.parent).as_posix(),
                                     page=page_no, engine="tesseract", evidence_excerpt=excerpt) for excerpt in excerpts)
                    print(f"OCR {bank} {year} trang {page_no}: {len(excerpts)} đoạn", flush=True)
    target = output / "sq1_search_passages.jsonl"
    with target.open("w", encoding="utf-8-sig") as stream:
        for row in rows:
            stream.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"Đã lưu {len(rows)} đoạn định vị: {target}")


if __name__ == "__main__":
    main()
