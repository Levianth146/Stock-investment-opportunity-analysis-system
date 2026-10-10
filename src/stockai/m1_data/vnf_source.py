"""Nguồn BCTC năm thứ hai: gói `vnfinancialdata` (dataset Hugging Face thanhnp-uel/vietnam-listed-companies-financial-statements,
HSX+HNX, 2009-2025, VND, hợp nhất, KHÔNG có quý, KHÔNG có ngày công bố, KHÔNG có UpCom). Chỉ N2 sửa.

Dùng để: (1) đối chiếu khoản mục với vnstock (cờ vnf_mismatch / vnf_crosscheck_ok), (2) bổ sung khoản mục còn thiếu
(phải thu, phải trả người bán, EBITDA, cổ tức đã trả ...), (3) kéo dài lịch sử BCTC năm lên ~10 năm.
Gói là tùy chọn: thiếu gói/không tải được dataset -> chỉ gắn cờ vnf_unavailable, M1 chạy bình thường.
Ngày công bố vẫn ước lượng (năm + 90 ngày) và mọi năm có ngày ước lượng > as_of bị loại (chống look-ahead)."""
from __future__ import annotations

import math
import re
from datetime import datetime

from stockai.m1_data import normalize as nz

STATEMENTS = ("income_statement", "balance_sheet", "cash_flow")
SOURCE_ID = "src_vnf"
# khoản mục -> (danh sách slug item_code theo thứ tự ưu tiên, lấy trị tuyệt đối?)  (slug đã bỏ hậu tố băm _xxxxxxxx)
KEYS: dict[str, tuple[tuple[str, ...], bool]] = {
    "revenue": (("is_doanh_so_thuan", "is_doanh_thu_thuan_tu_hoat_dong_kinh_doanh_bao_hiem"), False),
    "gross_profit": (("is_lai_gop",), False),
    "ebitda": (("is_ebitda",), False),
    "pretax_profit": (("is_lai_lo_rong_truoc_thue",), False),
    "net_income": (("is_lai_lo_thuan_sau_thue", "is_loi_nhuan_sau_thue", "is_loi_nhuan_sau_thue_thu_nhap_doanh_nghiep"), False),
    "net_income_parent": (("is_loi_nhuan_cua_co_dong_cua_cong_ty_me", "is_loi_nhuan_sau_thue_cua_chu_so_huu_tap_doan"), False),
    "eps": (("is_lai_co_ban_tren_co_phieu",), False),
    "interest_expense": (("is_trong_do_chi_phi_lai_vay",), True),
    "selling_expense": (("is_chi_phi_ban_hang",), True),
    "admin_expense": (("is_chi_phi_quan_ly_doanh_nghiep",), True),
    "net_interest_income": (("is_thu_nhap_lai_thuan",), False),
    "total_assets": (("bs_tong_tai_san", "bs_tong_cong_tai_san"), False),
    "current_assets": (("bs_tai_san_ngan_han",), False),
    "current_liabilities": (("bs_no_ngan_han",), False),
    "total_liabilities": (("bs_no_phai_tra",), False),
    "total_equity": (("bs_von_chu_so_huu",), False),
    "inventory": (("bs_hang_ton_kho_rong", "bs_hang_ton_kho"), False),
    "receivables": (("bs_cac_khoan_phai_thu",), False),
    "trade_receivables": (("bs_phai_thu_khach_hang",), False),
    "trade_payables": (("bs_phai_tra_nguoi_ban",), False),
    "cash": (("bs_tien_va_tuong_duong_tien",), False),
    "short_term_debt": (("bs_vay_ngan_han",), False),
    "long_term_debt": (("bs_vay_dai_han",), False),
    "cfo": (("cf_luu_chuyen_tien_thuan_tu_cac_hoat_dong_san_xuat_kinh_doanh",), False),
    "cfi": (("cf_luu_chuyen_tien_te_rong_tu_hoat_dong_dau_tu",), False),
    "cff": (("cf_luu_chuyen_tien_te_tu_hoat_dong_tai_chinh",), False),
    "capex": (("cf_tien_mua_tai_san_co_dinh_va_cac_tai_san_dai_han_khac",), True),
    "depreciation": (("cf_khau_hao_tscd",), False),
    "dividends_paid": (("cf_co_tuc_da_tra",), True),
}
CRITICAL = {"revenue", "total_assets", "total_equity", "net_income", "current_assets", "current_liabilities", "total_liabilities"}  # 0 = thiếu
NO_CROSSCHECK = {"ebit"}          # định nghĩa khác nhau giữa nguồn
REL_TOL = 0.005
HASH_SUFFIX = re.compile(r"_[0-9a-f]{8}$")


class Vnf:
    """Bọc gói vnfinancialdata, nạp từng (sàn, báo cáo) một lần rồi lọc theo mã."""

    def __init__(self, loader=None):
        self._loader, self._cache, self.error = loader, {}, None

    def _load(self, ex: str, st: str):
        if (ex, st) not in self._cache:
            loader = self._loader
            if loader is None:
                import vnfinancialdata as vnf                     # noqa: PLC0415 - gói tùy chọn
                loader = vnf.load
            self._cache[(ex, st)] = loader(exchange=ex, statement=st)
        return self._cache[(ex, st)]

    def annual(self, ticker: str) -> dict[int, dict[str, float]]:
        """{năm: {khoản mục của ta: giá trị}} đã chuẩn hóa dấu. Mã không có -> {}. Lỗi tải -> raise."""
        slugs: dict[int, dict[str, float]] = {}
        for ex in ("HSX", "HNX"):
            found = False
            for st in STATEMENTS:
                df = self._load(ex, st)
                d = df[df["ticker"] == ticker]
                if d.empty:
                    continue
                found = True
                for r in d.itertuples(index=False):
                    v = r.value
                    if v is None or (isinstance(v, float) and math.isnan(v)):
                        continue
                    slugs.setdefault(int(r.year), {}).setdefault(HASH_SUFFIX.sub("", str(r.item_code)), float(v))
            if found:
                break
        out: dict[int, dict[str, float]] = {}
        for y, by in slugs.items():
            row = {}
            for key, (cands, ab) in KEYS.items():
                for c in cands:
                    if c in by and not (key in CRITICAL and by[c] == 0):
                        row[key] = abs(by[c]) if ab else by[c]
                        break
            if row:
                out[y] = row
        return out


def _close(a: float, b: float) -> bool:
    return abs(a - b) <= REL_TOL * max(abs(a), abs(b), 1.0)


def apply(snap: dict, cfg: dict, vnf: Vnf | None = None) -> dict:
    """Đối chiếu + bổ sung + kéo dài lịch sử cho snapshot. Trả thống kê {mismatch, filled, added_years}."""
    flags = snap["meta"]["flags"]
    stats = {"mismatch": 0, "filled": 0, "added_years": 0}
    if not cfg.get("vnf_enabled", False):       # mặc định tắt trong code; config/data_sources.yaml bật
        return stats
    vnf = vnf or Vnf()
    t, as_of = snap["meta"]["ticker"], snap["meta"]["as_of"]
    try:
        data = vnf.annual(t)
    except Exception as e:  # noqa: BLE001 - thiếu gói / không tải được dataset
        flags.append(f"vnf_unavailable: {type(e).__name__}: {str(e)[:100]}")
        return stats
    if not data:
        flags.append("vnf_ticker_not_found")
        return stats
    annual = snap["financials"]["annual"]
    have = {int(r["period"]): r for r in annual if str(r["period"]).isdigit()}
    mism, filled = [], set()
    latest = max(have) if have else None
    for y, row in have.items():
        v = data.get(y, {})
        for k, val in v.items():
            cur = row["items"].get(k)
            if cur is None:
                row["items"][k] = val
                filled.add(k)
            elif k not in NO_CROSSCHECK and not _close(cur, val) and not (k == "eps" and (val == 0 or y != latest)):
                mism.append(f"{k}:{y}")          # EPS các năm cũ lệch do mỗi nguồn điều chỉnh cổ phiếu thưởng/chia tách khác nhau -> không đối chiếu
    limit = int(cfg.get("vnf_history_years", 10))
    newest = max(have) if have else max(data)
    for y in sorted(data, reverse=True):
        if y in have or y <= newest - limit or nz.estimated_publish_date(y, 0) > as_of:
            continue
        annual.append({"period": str(y), "published_at": nz.estimated_publish_date(y, 0), "published_at_estimated": True,
                       "source_id": SOURCE_ID, "items": dict(data[y])})
        stats["added_years"] += 1
    annual.sort(key=lambda r: str(r["period"]), reverse=True)
    stats["mismatch"], stats["filled"] = len(mism), len(filled)
    for m in mism[:8]:
        flags.append(f"vnf_mismatch:{m}")
    if len(mism) > 8:
        flags.append(f"vnf_mismatch_more:{len(mism) - 8}")
    if not mism and have:
        flags.append(f"vnf_crosscheck_ok:{max(have)}")
    if filled:
        flags.append("vnf_filled:" + ",".join(sorted(filled)))
    if not any(s["id"] == SOURCE_ID for s in snap["sources"]):
        snap["sources"].append({"id": SOURCE_ID, "name": "vnfinancialdata (Hugging Face thanhnp-uel/vietnam-listed-companies-financial-statements)",
                                "url": "https://huggingface.co/datasets/thanhnp-uel/vietnam-listed-companies-financial-statements",
                                "fetched_at": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
                                "note": "BCTC năm hợp nhất, VND; không có ngày công bố (ước lượng năm+90 ngày); nguồn gốc: cổng sàn/website công ty"})
    snap["meta"]["flags"] = [x for x in dict.fromkeys(flags)]
    return stats
