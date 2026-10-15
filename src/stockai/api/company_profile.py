"""Company introductions from existing snapshots and local CSV caches (no network)."""
from __future__ import annotations

import csv
import re
from datetime import date
from pathlib import Path
from stockai.api.profiles import company_profile as cached_profile


def _text(value) -> str | None:
    if not isinstance(value, str) or value.strip().lower() in ("", "nan", "none", "null"):
        return None
    return value.strip()


def _year(value) -> int | None:
    try:
        year = int(str(value))
        return year if 1800 <= year <= date.today().year else None
    except (ValueError, TypeError):
        return None


def company_profile(snapshot: dict, ticker: str, root: Path) -> dict:
    company = snapshot.get("company") or {}
    cached = cached_profile(root, ticker).get("profile") or {}
    if not isinstance(cached, dict) or cached.get("symbol", ticker) != ticker:
        cached = {}
    row = {}
    source = "snapshot"
    # Only read CSVs for this exact symbol; never deserialize provider pickle caches.
    if re.fullmatch(r"[A-Z0-9]{1,6}", ticker):
        for directory in ("data/raw", "data/raw_ext"):
            path = root / directory / ticker / "overview.csv"
            try:
                with path.open(encoding="utf-8-sig", newline="") as handle:
                    match = next((r for r in csv.DictReader(handle)
                                  if (r.get("symbol") or r.get("ticker") or "").strip().upper() == ticker), None)
                if match:
                    row = match
                    source = "local_overview_cache"
                    break
            except (OSError, UnicodeError, csv.Error):
                continue
    description = _text(company.get("description")) or _text(company.get("company_profile")) or _text(cached.get("intro")) or _text(row.get("company_profile"))
    if cached:
        source = "company_profile_cache"
    founded = _year(company.get("founded_year")) or _year(row.get("founded_year"))
    if founded is None and description:
        match = re.search(r"thành lập\s+(?:vào\s+)?năm\s+(\d{4})\b", description, flags=re.IGNORECASE)
        founded = _year(match[1]) if match else None
    listing = _text(company.get("listing_date")) or _text(cached.get("listing_date")) or _text(row.get("listing_date"))
    try:
        listing = date.fromisoformat(listing[:10]).isoformat() if listing else None
    except ValueError:
        listing = None
    return {
        "ticker": ticker,
        "name": _text(cached.get("name")) or _text(row.get("organ_name")) or _text(company.get("name")) or ticker,
        "description": description,
        "founded_year": founded,
        "listing_date": listing,
        "sector": _text(company.get("sector")) or _text(row.get("sector")),
        "industry": _text(company.get("industry")) or _text(row.get("industry")),
        "exchange": _text(company.get("exchange")) or _text(row.get("exchange")),
        "website": _text(company.get("website")) or _text(row.get("website")),
        "address": _text(company.get("address")) or _text(row.get("address")),
        "source": source,
        "data_date": _text(cached.get("data_date")),
        "source_note": "Hồ sơ giới thiệu từ dữ liệu doanh nghiệp đã thu thập; không phải dữ liệu được chốt theo ngày giá.",
    }
