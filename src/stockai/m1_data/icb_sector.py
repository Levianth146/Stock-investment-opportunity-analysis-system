"""Nạp ngành ICB cấp 2 từ config/listing_icb.csv → company.sector (tiếng Anh). Chỉ N2 sửa.

- Khóa ngành: Supersector (cấp 2), không dùng cấp 1 CSV làm parent peers.
- Ánh xạ VI→EN qua config/icb_sector_map.yaml; không ghi chữ Việt vào snapshot.
- Sàn: HOSE→HSX, UPCOM→UpCoM.
- vnstock đã có sector: giữ nguyên; lệch / thiếu CSV thì gắn cờ.
- Mã không có trong CSV / L2 chưa map: sector "" (không đoán) + cờ — không dùng JSON null.
"""
from __future__ import annotations

import csv
from functools import lru_cache
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_MAP = ROOT / "config" / "icb_sector_map.yaml"

COL_TICKER = "Mã CK"
COL_EXCHANGE = "Sàn giao dịch"
COL_L1 = "Ngành ICB Cấp 1 (Industry)"
COL_L2 = "Ngành ICB Cấp 2 (Supersector)"


def _load_map(path: str | Path | None = None) -> dict:
    p = Path(path) if path else _DEFAULT_MAP
    if not p.is_absolute():
        p = ROOT / p
    return yaml.safe_load(p.read_text(encoding="utf-8")) or {}


def financial_sectors(map_path: str | None = None) -> set[str]:
    cfg = _load_map(map_path)
    raw = cfg.get("financial_sectors") or ["Banks", "Insurance", "Financial Services"]
    return {str(x).strip() for x in raw}


@lru_cache(maxsize=4)
def load_listing(map_path: str | None = None) -> dict[str, dict]:
    """{TICKER: {sector_en, parent_en, exchange, l2_vi, l1_vi}} — sector_en/parent_en có thể None nếu chưa map.

    parent_en lấy từ supersector_parent_en theo L2 VI — không đọc industry_to_en / cột L1 CSV.
    """
    cfg = _load_map(map_path)
    csv_rel = cfg.get("listing_csv", "config/listing_icb.csv")
    csv_path = ROOT / csv_rel if not Path(csv_rel).is_absolute() else Path(csv_rel)
    ss_map = cfg.get("supersector_to_en") or {}
    parent_map = cfg.get("supersector_parent_en") or {}
    ex_map = {str(k).strip().upper(): v for k, v in (cfg.get("exchange_aliases") or {}).items()}
    out: dict[str, dict] = {}
    with csv_path.open(encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            t = (row.get(COL_TICKER) or "").strip().upper()
            if not t:
                continue
            l2 = (row.get(COL_L2) or "").strip()
            l1 = (row.get(COL_L1) or "").strip()
            raw_ex = (row.get(COL_EXCHANGE) or "").strip()
            sector_en = ss_map.get(l2)
            parent_en = parent_map.get(l2)
            if parent_en is None and sector_en:
                parent_en = parent_map.get(sector_en)
            out[t] = {
                "l2_vi": l2,
                "l1_vi": l1,
                "sector_en": sector_en,
                "parent_en": parent_en,
                "exchange": ex_map.get(raw_ex.upper(), raw_ex or None),
            }
    return out


def clear_listing_cache() -> None:
    load_listing.cache_clear()


def normalize_exchange(raw: str | None, map_path: str | None = None) -> str:
    if not raw:
        return ""
    cfg = _load_map(map_path)
    aliases = {str(k).strip().upper(): v for k, v in (cfg.get("exchange_aliases") or {}).items()}
    return aliases.get(str(raw).strip().upper(), str(raw).strip())


def apply_to_company(
    company: dict,
    ticker: str,
    *,
    listing: dict[str, dict] | None = None,
    map_path: str | None = None,
    flags: list[str] | None = None,
) -> list[str]:
    """Điền/đối chiếu sector + exchange. Trả về danh sách cờ mới (cũng append vào `flags` nếu truyền vào)."""
    new_flags: list[str] = []
    listing = listing if listing is not None else load_listing(map_path)
    row = listing.get(ticker.strip().upper())
    if row is None:
        if not (company.get("sector") or "").strip():
            company["sector"] = ""
        new_flags.append("icb_ticker_not_found")
        if flags is not None:
            flags.extend(new_flags)
        return new_flags

    # exchange
    icb_ex = row.get("exchange") or ""
    cur_ex = (company.get("exchange") or "").strip()
    if icb_ex:
        if not cur_ex:
            company["exchange"] = icb_ex
            new_flags.append("icb_exchange_filled")
        else:
            norm_cur = normalize_exchange(cur_ex, map_path)
            if norm_cur != icb_ex:
                new_flags.append("icb_exchange_mismatch")
            elif norm_cur != cur_ex:
                company["exchange"] = norm_cur

    mapped = row.get("sector_en")
    if not mapped:
        if not (company.get("sector") or "").strip():
            company["sector"] = ""
        new_flags.append("icb_sector_unmapped")
        if flags is not None:
            flags.extend(new_flags)
        return new_flags

    existing = (company.get("sector") or "").strip()
    if not existing:
        company["sector"] = mapped
        new_flags.append("icb_sector_filled")
    elif existing != mapped:
        new_flags.append("icb_sector_mismatch")

    if flags is not None:
        flags.extend(new_flags)
    return new_flags


def parent_of(ticker: str, listing: dict[str, dict] | None = None, map_path: str | None = None) -> str | None:
    listing = listing if listing is not None else load_listing(map_path)
    row = listing.get(ticker.strip().upper())
    return (row or {}).get("parent_en")


def is_financial_view(view: dict, fin: set[str]) -> bool:
    """Sector thuộc financial_sectors, hoặc sector "" và is_bank True."""
    sector = (view.get("sector") or "").strip()
    if sector in fin:
        return True
    if not sector and bool(view.get("is_bank")):
        return True
    return False


def _has_sector(view: dict) -> bool:
    return bool((view.get("sector") or "").strip())


def resolve_peer_group(
    ticker: str,
    views: dict[str, dict],
    *,
    listing: dict[str, dict] | None = None,
    map_path: str | None = None,
    min_size: int | None = None,
    apply_finance_filter: bool = False,
) -> tuple[list[str], bool, bool]:
    """Peers cùng sector; cascade parent/market khi nhỏ.

    Trả (peer_tickers, used_small_group, finance_blocked).
    `views[t]`: sector, met (truthy nếu dùng được), parent, is_bank.
    Mã sector "" không bao giờ nằm trong peer_tickers.
    Khi apply_finance_filter: không gộp tài chính với phi tài chính.
    """
    def usable(x: str) -> bool:
        return bool(views.get(x, {}).get("met"))

    def peer_ok(x: str) -> bool:
        return usable(x) and _has_sector(views.get(x, {}))

    sector = (views.get(ticker, {}).get("sector") or "").strip()
    same = [x for x in views if x != ticker and peer_ok(x) and (views[x].get("sector") or "") == sector] if sector else []

    # listing is None → chỉ cùng sector string (legacy), không cascade / không finance filter
    if listing is None:
        return same, False, False

    cfg = _load_map(map_path)
    if min_size is None:
        min_size = int(cfg.get("min_peer_group_size", 10))
    fin = financial_sectors(map_path)

    def finance_filter(cands: list[str]) -> tuple[list[str], bool]:
        if not apply_finance_filter:
            return cands, False
        want = is_financial_view(views.get(ticker, {}), fin)
        out = [x for x in cands if is_financial_view(views[x], fin) == want]
        blocked = bool(cands) and not out
        return out, blocked

    # sector rỗng → thẳng market (+ small)
    if not sector:
        market = [x for x in views if x != ticker and peer_ok(x)]
        filtered, blocked = finance_filter(market)
        return filtered, True, blocked

    group_size = len(same) + (1 if usable(ticker) else 0)
    if group_size >= min_size:
        return same, False, False

    parent = views.get(ticker, {}).get("parent") or parent_of(ticker, listing, map_path)
    if parent and parent != sector:
        same_p = [
            x for x in views
            if x != ticker and peer_ok(x)
            and (views[x].get("parent") or parent_of(x, listing, map_path)) == parent
        ]
        parent_size = len(same_p) + (1 if usable(ticker) else 0)
        if parent_size >= min_size:
            filtered, blocked = finance_filter(same_p)
            return filtered, True, blocked

    market = [x for x in views if x != ticker and peer_ok(x)]
    filtered, blocked = finance_filter(market)
    return filtered, True, blocked
