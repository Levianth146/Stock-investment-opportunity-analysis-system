"""Tải PDF công khai trong config/sources.csv, kiểm tra robots.txt và nghỉ >= 3 giây.
Cách dùng: python 01_download.py [--force] [--bank tcb,mb] [--year 2024] [--type bctn,bctc]
Biến môi trường CONTACT: email liên hệ ghi trong User-Agent."""
import csv
import hashlib
import os
import re
import sys
from urllib.parse import urlsplit

import requests
from common import CONF, DATA, ROOT, keep, today
from public_web import PublicFetcher

DELAY = 3.0
UA = f"Mozilla/5.0 (academic research; contact: {os.environ.get('CONTACT', 'n/a')})"
required_cols = ["bank", "year", "doc_type", "url"]


def iter_source_rows(path):
    """Bỏ dòng sai cấu trúc hoặc định danh; chuẩn hóa BOM và khoảng trắng ở header."""
    with open(path, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            raise ValueError(f"{path} trống hoặc thiếu header CSV")
        reader.fieldnames = [name.lstrip("\ufeff").strip() for name in reader.fieldnames]
        missing = set(required_cols) - set(reader.fieldnames)
        if missing or len(reader.fieldnames) != len(set(reader.fieldnames)):
            raise ValueError(f"{path}: header thiếu cột hoặc trùng cột: {sorted(missing)}")
        for line_no, row in enumerate(reader, start=2):
            if None in row or any(row.get(k) is None for k in required_cols):
                print(f"bỏ dòng {line_no}: số cột không khớp header")
                continue
            clean = {key: (value or "").strip() for key, value in row.items()}
            if not any(clean.values()):
                continue
            if (not re.fullmatch(r"[a-z0-9][a-z0-9_-]*", clean["bank"])
                    or not re.fullmatch(r"(?:19|20)\d{2}", clean["year"])
                    or clean["doc_type"] not in {"bctn", "bctc", "bcptbv", "other"}):
                print(f"bỏ dòng {line_no}: bank/year/doc_type không hợp lệ")
                continue
            try:
                parsed = urlsplit(clean["url"])
                valid_url = parsed.scheme in ("http", "https") and parsed.netloc and not parsed.username and not parsed.password
            except ValueError:
                valid_url = False
            if clean["url"] and not valid_url:
                print(f"bỏ dòng {line_no}: URL công khai không hợp lệ")
                continue
            yield clean


def download_pdf(fetcher, url, dest):
    """Retry độc lập; chỉ ghi đè PDF cũ khi đã nhận PDF mới hợp lệ."""
    for attempt in range(3):
        try:
            response = fetcher.get(url, timeout=60)
            response.raise_for_status()
            content = response.content
            if not content.startswith(b"%PDF"):
                return "not_pdf (kiểm tra link PDF trực tiếp)"
            temp = dest.with_suffix(".pdf.tmp")
            temp.write_bytes(content)
            temp.replace(dest)
            return "ok"
        except PermissionError as exc:
            return f"robots_blocked: {exc}"
        except (requests.RequestException, OSError) as exc:
            status = f"error: {exc}"
    return status


def main():
    if "--no-robots" in sys.argv:
        sys.exit("Không hỗ trợ --no-robots: dự án yêu cầu tôn trọng robots.txt.")
    force = "--force" in sys.argv
    rows = list(iter_source_rows(CONF / "sources.csv"))
    fetcher = PublicFetcher(UA, DELAY)
    man_path = DATA / "raw" / "manifest.csv"
    new = not man_path.exists() or man_path.stat().st_size == 0
    pending, pending_opt = [], []
    seen = {}
    with open(man_path, "a", newline="", encoding="utf-8-sig") as mf:
        writer = csv.writer(mf)
        if new:
            writer.writerow(["bank", "year", "doc_type", "url", "file", "sha256", "bytes", "accessed_at", "status"])
        for row in rows:
            bank, year, typ, url = (row[k] for k in required_cols)
            if not keep(bank, year, typ):
                continue
            if not url:
                if not row.get("notes"):
                    (pending_opt if typ == "bcptbv" else pending).append((bank, year, typ))
                continue
            key = (bank, year, url)
            if key in seen and seen[key] != typ:
                print("bỏ URL trùng giữa hai loại báo cáo:", bank, year, typ)
                continue
            seen[key] = typ
            dest = DATA / "raw" / bank / f"{year}_{typ}.pdf"
            dest.parent.mkdir(parents=True, exist_ok=True)
            if dest.exists() and not force:
                print("đã có", dest.name)
                continue
            status = download_pdf(fetcher, url, dest)
            success = status == "ok"
            sha = hashlib.sha256(dest.read_bytes()).hexdigest() if success else ""
            writer.writerow([bank, year, typ, url, str(dest.relative_to(ROOT)) if success else "",
                             sha, dest.stat().st_size if success else "", today(), status])
            print(bank, year, typ, "->", status)
    if pending:
        print(f"CHƯA ĐIỀN: {len(pending)} dòng bắt buộc thiếu cả URL lẫn ghi chú:", pending[:20])
    if pending_opt:
        print(f"Gợi ý: {len(pending_opt)} dòng BCPTBV chưa có URL/ghi chú; nếu tích hợp thì ghi 'tích hợp trong BCTN'.")


if __name__ == "__main__":
    main()
