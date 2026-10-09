"""Chuẩn hóa DataFrame thô của vnstock -> khối snapshot đúng schema. Chỉ N2 sửa.

Tên cột của vnstock thay đổi theo nguồn/phiên bản, nên khớp bằng regex trên tên đã chuẩn hóa (bỏ dấu, chữ thường).
Cột nào không khớp -> giá trị null + cờ; chạy `python scripts/probe_data.py HPG` để xem tên cột thật rồi thêm regex vào ALIASES."""
from __future__ import annotations

import hashlib
import re
import unicodedata
from datetime import date, datetime, timedelta

import numpy as np
import pandas as pd

# ------------------------------------------------------------------ tiện ích
def norm(s) -> str:
    s = unicodedata.normalize("NFD", str(s)).replace("đ", "d").replace("Đ", "D")
    s = "".join(c for c in s if unicodedata.category(c) != "Mn").lower()
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", s)).strip()


def num(x):
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return None if (np.isnan(v) or np.isinf(v)) else v


def find_col(df: pd.DataFrame, patterns: list[str], exclude: str | None = None) -> str | None:
    """Cột đầu tiên khớp pattern ưu tiên cao nhất (pattern đứng trước thắng)."""
    names = {c: norm(c) for c in df.columns}
    for pat in patterns:
        for c, n in names.items():
            if re.search(pat, n) and not (exclude and re.search(exclude, n)):
                return c
    return None


def stamp(d: date | datetime | str) -> str:
    return pd.Timestamp(d).strftime("%Y-%m-%d")


# ------------------------------------------------------------------ giá
def _scale_factor(setting, median_value: float, threshold: float, factor: float) -> float:
    if str(setting) == "auto":
        return factor if median_value < threshold else 1.0
    return float(setting)


def normalize_prices(df: pd.DataFrame, start: str, as_of: str, setting="auto") -> tuple[list[dict], list[str]]:
    """Trả (rows, flags). Cắt cửa sổ [start, as_of], bỏ trùng ngày, đưa giá về VND."""
    flags: list[str] = []
    dcol = find_col(df, [r"^time$", r"^date$", r"trading ?date", r"^ngay"])
    cols = {k: find_col(df, [rf"^{k}$"]) for k in ("open", "high", "low", "close", "volume")}
    if dcol is None or any(v is None for v in cols.values()):
        raise ValueError(f"thiếu cột giá; có: {list(df.columns)}")
    x = pd.DataFrame({"date": pd.to_datetime(df[dcol]).dt.tz_localize(None).dt.normalize(),
                      **{k: pd.to_numeric(df[v], errors="coerce") for k, v in cols.items()}})
    x = x.dropna(subset=["date", "close"]).drop_duplicates("date", keep="last").sort_values("date")
    x = x[(x["date"] >= pd.Timestamp(start)) & (x["date"] <= pd.Timestamp(as_of))]
    f = _scale_factor(setting, float(x["close"].median()) if len(x) else 1e9, 500.0, 1000.0)
    if f != 1.0:
        for k in ("open", "high", "low", "close"):
            x[k] = x[k] * f
        flags.append(f"prices_scaled_x{int(f)}_to_VND")
    # cổ tức/chia tách chưa điều chỉnh sẽ để lại bước nhảy bất thường (biên độ sàn tối đa 15%)
    if len(x) > 2:
        jumps = x["close"].pct_change().abs()
        if (jumps > 0.2).any():
            flags.append(f"suspect_unadjusted_prices:{int((jumps > 0.2).sum())}_jumps_gt_20pct")
    rows = [{"date": r.date.strftime("%Y-%m-%d"), "open": round(r.open, 2), "high": round(r.high, 2),
             "low": round(r.low, 2), "close": round(r.close, 2), "volume": num(r.volume)}
            for r in x.itertuples()]
    return rows, flags


def normalize_index(df: pd.DataFrame, start: str, as_of: str) -> list[dict]:
    dcol = find_col(df, [r"^time$", r"^date$", r"^ngay"])
    ccol = find_col(df, [r"^close$"])
    if dcol is None or ccol is None:
        raise ValueError(f"thiếu cột chỉ số; có: {list(df.columns)}")
    x = pd.DataFrame({"date": pd.to_datetime(df[dcol]).dt.tz_localize(None).dt.normalize(),
                      "close": pd.to_numeric(df[ccol], errors="coerce")}).dropna()
    x = x.drop_duplicates("date", keep="last").sort_values("date")
    x = x[(x["date"] >= pd.Timestamp(start)) & (x["date"] <= pd.Timestamp(as_of))]
    return [{"date": r.date.strftime("%Y-%m-%d"), "close": round(float(r.close), 2)} for r in x.itertuples()]


# ------------------------------------------------------------------ báo cáo tài chính
_LEVEL_EXCL = r"growth|yoy|margin|%|tang truong|ty le|ty suat|per share|/ ?share|days|turnover|vong quay"
# canonical -> (danh sách regex theo thứ tự ưu tiên, regex loại trừ)
ALIASES: dict[str, tuple[list[str], str | None]] = {
    # kết quả kinh doanh (tên theo item_en của VCI; chạy scripts/probe_data.py để đối chiếu và thêm biến thể)
    "revenue": ([r"^net sales", r"^net revenues?", r"^sales$", r"^revenues?$", r"^doanh thu thuan", r"^total operating income"], _LEVEL_EXCL + r"|deduction"),
    "gross_profit": ([r"^gross profit", r"^loi nhuan gop", r"^gross insurance operating profit"], _LEVEL_EXCL),
    "ebit": ([r"^operating profit", r"^net operating profit", r"^profit from operating", r"^ebit$"], _LEVEL_EXCL),
    "net_income": ([r"^net profit loss after tax$", r"^net profit after tax$", r"^net profit loss after tax", r"^profit after tax", r"^net profit"],
                   _LEVEL_EXCL + r"|parent|mother|minority|before|attribut"),
    "net_income_parent": ([r"parent", r"mother", r"cong ty me", r"attributable to"], _LEVEL_EXCL + r"|minority"),
    "interest_expense": ([r"interest expenses?", r"interest and similar expenses"], _LEVEL_EXCL + r"|paid|payable|accrued|income"),
    "depreciation": ([r"^depreciation and amortization", r"^depreciation"], _LEVEL_EXCL),
    "eps": ([r"basic earnings per share", r"^eps", r"earnings per share"], None),
    # bảng cân đối
    "total_assets": ([r"^total assets?$", r"^total assets?"], _LEVEL_EXCL),
    "total_equity": ([r"^owner s equity$", r"^owners equity$", r"^total owner s equity", r"^total equity", r"^equity$", r"^owner s equity"],
                     _LEVEL_EXCL + r"|capital|contribut|liabilities"),
    "total_liabilities": ([r"^total liabilities$", r"^liabilities$"], _LEVEL_EXCL + r"|equity"),
    "current_assets": ([r"^current assets"], _LEVEL_EXCL),
    "current_liabilities": ([r"^current liabilities", r"^short term liabilities"], _LEVEL_EXCL),
    "inventory": ([r"^inventor(y|ies)", r"^hang ton kho"], _LEVEL_EXCL + r"|provision"),
    "cash": ([r"^cash and cash equivalents", r"^cash$"], _LEVEL_EXCL),
    "short_term_debt": ([r"short term borrowings", r"short term debt", r"^short term loans$"], _LEVEL_EXCL + r"|interest|expense|accrued"),
    "long_term_debt": ([r"long term borrowings", r"long term debt", r"^long term loans$"], _LEVEL_EXCL + r"|interest|expense|accrued|and liabilities"),
    # lưu chuyển tiền tệ
    "cfo": ([r"^net cash.*operating activities", r"operating activities"], _LEVEL_EXCL + r"|before|adjust"),
    "cfi": ([r"^net cash.*investing activities", r"investing activities"], _LEVEL_EXCL),
    "cff": ([r"^net cash.*financing activities", r"financing activities"], _LEVEL_EXCL),
    "capex": ([r"purchases? of fixed assets", r"capital expenditure", r"acquisition of fixed"], _LEVEL_EXCL),
    # ngân hàng
    "net_interest_income": ([r"^net interest income"], _LEVEL_EXCL),
    "total_operating_income": ([r"^total operating income"], _LEVEL_EXCL),
    "provision_expense": ([r"provision for credit losses", r"provision"], _LEVEL_EXCL + r"|reserve"),
    "opex": ([r"^general and admin"], _LEVEL_EXCL),
    "customer_loans": ([r"^customer loans", r"^loans and advances to customers"], _LEVEL_EXCL + r"|provision"),
    "customer_deposits": ([r"^deposits from customers", r"^customer deposits"], _LEVEL_EXCL),
    "npl_ratio": ([r"\bnpl\b"], None),
    "car": ([r"^car\b", r"capital adequacy"], None),
    "nim": ([r"^nim\b", r"net interest margin"], None),
    "cir": ([r"^cir\b", r"cost to income", r"cost income"], None),
}
MONETARY = {"revenue", "gross_profit", "ebit", "net_income", "net_income_parent", "interest_expense", "depreciation",
            "total_assets", "total_equity", "total_liabilities", "current_assets", "current_liabilities", "inventory",
            "cash", "short_term_debt", "long_term_debt", "cfo", "cfi", "cff", "capex", "net_interest_income",
            "total_operating_income", "provision_expense", "customer_loans", "customer_deposits", "opex"}
BANK_ONLY = {"opex", "net_interest_income", "total_operating_income", "provision_expense", "customer_loans",
             "customer_deposits", "npl_ratio", "car", "nim", "cir"}
# Ngân hàng không có các chỉ tiêu này trong BCTC (NPL, CAR chỉ có trong báo cáo thường niên; NIM, CIR được tính xấp xỉ)
BANK_NA = {"depreciation", "short_term_debt", "long_term_debt", "cff", "npl_ratio", "car", "nim", "cir"}
NONBANK_ONLY = {"gross_profit", "current_assets", "current_liabilities", "inventory"}


def to_wide(df: pd.DataFrame) -> pd.DataFrame:
    """vnstock (VCI) trả BCTC dạng DỌC: mỗi dòng là một chỉ tiêu (item, item_en, item_id), mỗi cột là một kỳ
    ('2025' hoặc '2026-Q2'). Chuyển thành dạng NGANG: index = kỳ, cột = tên chỉ tiêu (item_en)."""
    cols = list(df.columns)
    if "item_en" not in cols and "item_id" not in cols:
        return df
    name = "item_en" if "item_en" in cols else "item_id"
    meta = {"item", "item_en", "item_id"}
    per = [c for c in cols if c not in meta]
    w = df[[name] + per].copy()
    w[name] = w[name].astype(str)
    w = w.drop_duplicates(name, keep="first").set_index(name).T
    w.index = [str(i) for i in w.index]
    return w


def _period_keys(df: pd.DataFrame, annual: bool) -> pd.DataFrame:
    """Thêm cột _year, _q (0 = cả năm) từ cột năm/quý hoặc từ index."""
    ycol = find_col(df, [r"^yearreport$", r"^year report$", r"^year$", r"^nam$"])
    qcol = find_col(df, [r"^lengthreport$", r"^length report$", r"^quarter$", r"^quy$"])
    out = df.copy()
    if ycol is not None:
        out["_year"] = pd.to_numeric(out[ycol], errors="coerce")
        if annual or qcol is None:
            out["_q"] = 0
        else:
            q = pd.to_numeric(out[qcol], errors="coerce")
            out["_q"] = q.where(q.between(1, 4))
    else:  # index dạng "2024" hoặc "2024-Q1" / "Q1/2024"
        ys, qs = [], []
        for v in out.index.astype(str):
            m = re.search(r"(20\d{2})", v)
            q = re.search(r"[Qq]\s*([1-4])", v)
            ys.append(int(m.group(1)) if m else np.nan)
            qs.append(0 if annual else (int(q.group(1)) if q else np.nan))
        out["_year"], out["_q"] = ys, qs
    return out.dropna(subset=["_year", "_q"])


def estimated_publish_date(year: int, q: int) -> str:
    """Nguồn không cho ngày công bố -> ước lượng thận trọng: quý = cuối quý + 45 ngày, năm = cuối năm + 90 ngày."""
    end = date(year, 12, 31) if q == 0 else {1: date(year, 3, 31), 2: date(year, 6, 30), 3: date(year, 9, 30), 4: date(year, 12, 31)}[q]
    return (end + timedelta(days=90 if q == 0 else 45)).isoformat()


def normalize_financials(frames: list[pd.DataFrame], annual: bool, as_of: str, source_id: str, is_bank: bool,
                         setting="auto", keep: int = 6) -> tuple[list[dict], dict, list[str]]:
    """frames = [income, balance, cashflow, ratio] (cái nào lỗi thì bỏ). Trả (periods, column_map, flags)."""
    flags: list[str] = []
    wide: pd.DataFrame | None = None
    for f in frames:
        if f is None or len(f) == 0:
            continue
        k = _period_keys(to_wide(f), annual)
        k = k.loc[:, ~k.columns.duplicated()]
        k["_key"] = k["_year"].astype(int).astype(str) + "-" + k["_q"].astype(int).astype(str)
        k = k.drop_duplicates("_key", keep="last").set_index("_key")
        if wide is None:
            wide = k
        else:
            new = k[[c for c in k.columns if c not in wide.columns]]
            wide = wide.join(new, how="outer")
            for c in ("_year", "_q"):                       # dòng chỉ có ở bảng sau: lấy khóa kỳ từ bảng đó
                wide[c] = wide[c].fillna(k[c])
    if wide is None or wide.empty:
        return [], {}, ["financials_empty"]

    cmap: dict[str, str] = {}
    for canon, (pats, excl) in ALIASES.items():
        if (canon in BANK_ONLY and not is_bank) or (canon in NONBANK_ONLY and is_bank):
            continue
        col = find_col(wide, pats, excl)
        if col is not None:
            cmap[canon] = str(col)
    missing = [k for k in ALIASES if k not in cmap and not ((k in BANK_ONLY and not is_bank) or (k in NONBANK_ONLY and is_bank)
                                                           or (k in BANK_NA and is_bank))]
    if is_bank:
        flags += ["bank_npl_car_not_in_statements", "bank_nim_cir_derived_approx"]
    if missing:
        flags.append(f"fin_{'annual' if annual else 'quarterly'}_unmatched:{','.join(missing)}")

    mult = 1.0
    if "total_assets" in cmap:
        ta = pd.to_numeric(wide[cmap["total_assets"]], errors="coerce").median()
        mult = float(setting) if str(setting) != "auto" else (1e9 if ta < 1e8 else 1.0)
        if mult != 1.0:
            flags.append(f"financials_scaled_x{mult:g}_to_VND")

    periods = []
    for key, row in wide.sort_values(["_year", "_q"], ascending=False).iterrows():
        y, q = int(row["_year"]), int(row["_q"])
        pub = estimated_publish_date(y, q)
        if pub > as_of:                                      # chưa công bố tại as_of -> không dùng (chống look-ahead)
            continue
        items = {}
        for canon, col in cmap.items():
            v = num(row[col])
            if v is not None and canon in MONETARY:
                v *= mult
            if canon in ("capex", "interest_expense") and v is not None:
                v = abs(v)
            items[canon] = v
        if is_bank:                                          # CIR = chi phí hoạt động / tổng thu nhập hoạt động; NIM ≈ NII (quy năm) / tổng tài sản
            opx, toi, nii, tas = (items.get(k) for k in ("opex", "total_operating_income", "net_interest_income", "total_assets"))
            if opx is not None and toi:
                items["cir"] = round(abs(opx) / toi, 4)
            if nii is not None and tas:
                items["nim"] = round(nii * (4 if q else 1) / tas, 4)
        periods.append({"period": str(y) if q == 0 else f"{y}Q{q}", "published_at": pub, "published_at_estimated": True,
                        "source_id": source_id, "items": items})
        if len(periods) >= keep:
            break
    return periods, cmap, flags


# ------------------------------------------------------------------ công ty / peers
def _pick(d: dict, patterns: list[str]):
    nd = {norm(k): v for k, v in d.items()}
    for pat in patterns:
        for k, v in nd.items():
            if re.search(pat, k) and v not in (None, "") and not (isinstance(v, float) and np.isnan(v)):
                return v
    return None


def normalize_company(df: pd.DataFrame, ticker: str, banks: list[str], exchange_map: dict | None = None) -> tuple[dict, list[str]]:
    flags: list[str] = []
    d = df.iloc[0].to_dict() if len(df) else {}
    name = _pick(d, [r"company name", r"short name", r"organ name", r"ten cong ty"])
    exch = _pick(d, [r"^exchange", r"^san"]) or (exchange_map or {}).get(ticker)
    sector = _pick(d, [r"icb name 2", r"icb name2", r"sector", r"nganh cap 2"])
    industry = _pick(d, [r"icb name 4", r"icb name4", r"icb name 3", r"icb name3", r"industry", r"nganh"])
    shares = num(_pick(d, [r"^issue share", r"^outstanding share", r"shares outstanding", r"so co phieu luu hanh"]))
    for label, v in (("name", name), ("exchange", exch), ("sector", sector), ("shares_outstanding", shares)):
        if v is None:
            flags.append(f"company_{label}_missing")
    text = norm(f"{sector or ''} {industry or ''}")
    col_flag = d.get("is_bank")                       # overview của VCI có sẵn cột is_bank
    is_bank = ticker in banks or "ngan hang" in text or re.search(r"\bbanks?\b", text) is not None \
        or (isinstance(col_flag, (bool, np.bool_)) and bool(col_flag))
    if re.search(r"chung khoan|securities|brokerage", text):
        flags.append("securities_firm_needs_special_metrics")
    return {"name": str(name or ticker), "exchange": str(exch or ""), "sector": str(sector or industry or ""),
            "industry": str(industry) if industry else None, "is_bank": bool(is_bank), "shares_outstanding": shares}, flags


def multiples(price_rows: list[dict], annual: list[dict], shares: float | None) -> dict:
    """PE/PB/ROE/vốn hóa tự tính (VND) từ giá cuối + BCTC năm mới nhất đã công bố. Thiếu dữ liệu -> {}."""
    if not price_rows or not annual or not shares:
        return {}
    it = annual[0]["items"]
    ni = it.get("net_income_parent") or it.get("net_income")
    eq = it.get("total_equity")
    px = price_rows[-1]["close"]
    return {"pe": px * shares / ni if ni and ni > 0 else None, "pb": px * shares / eq if eq and eq > 0 else None,
            "roe": ni / eq if ni is not None and eq and eq > 0 else None, "market_cap": px * shares}


def latest_ratio_row(ratio_df: pd.DataFrame | None, as_of: str) -> dict:
    """Dòng tỷ số mới nhất đã công bố tại as_of -> {eps, pe, pb, roe}. Thiếu thì key vắng."""
    if ratio_df is None or len(ratio_df) == 0:
        return {}
    k = _period_keys(ratio_df, annual=True)
    k = k[k.apply(lambda r: estimated_publish_date(int(r["_year"]), 0) <= as_of, axis=1)] if len(k) else k
    if len(k) == 0:
        return {}
    row = k.sort_values("_year").iloc[-1]
    out = {}
    for key, pats in (("pe", [r"\bp e\b", r"price to earnings", r"\bpe\b"]), ("pb", [r"\bp b\b", r"price to book", r"\bpb\b"]),
                      ("roe", [r"\broe\b"]), ("eps", [r"^basic eps", r"\beps\b"])):
        col = find_col(k, pats, r"growth|yoy|tang truong")
        v = num(row[col]) if col is not None else None
        if key == "roe" and v is not None and abs(v) > 1.5:
            v /= 100.0                                   # luôn lưu ROE dạng phân số (0.13 = 13%)
        out[key] = v
    return out


# ------------------------------------------------------------------ tin tức
def _to_dt(v) -> pd.Timestamp | None:
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return None
    try:
        if isinstance(v, (int, float, np.integer, np.floating)):
            f = float(v)
            return pd.Timestamp(f, unit="ms" if f > 1e11 else "s")
        t = pd.to_datetime(v, errors="coerce")
        return None if pd.isna(t) else t.tz_localize(None) if t.tzinfo else t
    except Exception:  # noqa: BLE001
        return None


def normalize_news(df: pd.DataFrame, start: str, as_of: str, source_name: str, max_items: int) -> tuple[list[dict], list[str]]:
    flags: list[str] = []
    tcol = find_col(df, [r"^news title$", r"^title$", r"title"], r"friendly|sub")
    ucol = find_col(df, [r"^news source link$", r"source link", r"^link$", r"^url$", r"^news url$"], r"image|img|photo")
    dcol = find_col(df, [r"public date", r"publish", r"^date", r"time", r"^ngay"])
    scol = find_col(df, [r"^news short content$", r"short content", r"summary", r"description", r"full content", r"sapo"])
    icol = find_col(df, [r"^news id$"])
    if tcol is None or dcol is None:
        raise ValueError(f"thiếu cột tin; có: {list(df.columns)}")
    if ucol is None or df[ucol].isna().all():
        flags.append("news_url_missing")
    items, seen = [], set()
    end = pd.Timestamp(as_of) + pd.Timedelta(days=1)         # as_of tính hết ngày
    for r in df.to_dict("records"):
        dt = _to_dt(r[dcol])
        title = str(r[tcol]).strip()
        if dt is None or not title or dt < pd.Timestamp(start) or dt >= end:
            continue
        key = norm(title)
        if key in seen:
            continue
        seen.add(key)
        url = str(r[ucol]).strip() if ucol is not None and r.get(ucol) not in (None, "") and str(r.get(ucol)) != "nan" else "n/a"
        nid = f"n{r[icol]}" if icol is not None and r.get(icol) not in (None, "") else "n" + hashlib.sha1((url + title).encode("utf-8")).hexdigest()[:10]
        items.append({"id": nid, "title": title, "url": url,
                      "source": source_name, "published_at": dt.strftime("%Y-%m-%dT%H:%M:%S"),
                      "summary": (str(r[scol])[:500] if scol is not None and r.get(scol) else None)})
    items.sort(key=lambda x: x["published_at"], reverse=True)
    return items[:max_items], flags
