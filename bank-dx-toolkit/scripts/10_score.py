#!/usr/bin/env python3
"""10_score.py — Tính 11 chỉ số DTI, 24 tiêu chí DBI, P_k, Score_Bank, xếp hạng và 5 mức trưởng thành.

Chỉ dùng công thức/chỉ tiêu trong file "Mô hình DBI-DTI điều chỉnh" (docx):
  z      = 100 * min{1; max[0; (x - L)/(U - L)]}            (chỉ số nghịch: (U - x)/(U - L))   [mục II.2]
  DBI_k  = trung bình 4 tiêu chí rubric 0-4, quy về % (0/25/50/75/100)                        [mục II.1]
  DTI_k  = trung bình z của các chỉ số DTI CÓ dữ liệu thuộc trụ cột k                          [mục II]
  P_k    = 0,8 * DBI_k + 0,2 * DTI_k ; nếu trụ cột không có DTI nào thì P_k = DBI_k           [mục II]
  Score  = (1/6) * sum(P_k)                                                                    [mục II]
  Mức    = <25 Khởi động | 25-<50 Bắt đầu | 50-<75 Hình thành | 75-<100 Nâng cao | =100 Dẫn dắt [mục IV]
  Tin cậy dữ liệu = số chỉ số DTI có dữ liệu thực / 11                                         [mục II]

Chạy (trong thư mục scripts/):
  python 10_score.py                      # chạy chính thức: toàn bộ năm cấu hình, yêu cầu locked=true
  python 10_score.py --years 2021,2023,2025
  python 10_score.py --draft              # chạy thử: bounds chưa khóa / DBI chưa đủ; file ra có hậu tố _draft
  python 10_score.py --w-dbi 0.7          # đổi tỷ lệ DBI/DTI (kịch bản độ nhạy)
  python 10_score.py --weight-scenarios   # chạy luôn 100/0, 80/20, 70/30, 60/40
"""
import argparse
import sys

import numpy as np
import pandas as pd

from common import CONF, OUT, ROOT, load_yaml, confirmed_mask

# ----------------------------------------------------------------------------------------------
# Hằng số theo docx
# ----------------------------------------------------------------------------------------------
PILLARS = {"K": "Khách hàng", "S": "Chiến lược", "T": "Công nghệ",
           "O": "Vận hành", "C": "Văn hóa", "D": "Dữ liệu"}
DTI_BY_PILLAR = {"K": ["K-Q1", "K-Q2", "K-Q3"], "S": ["S-Q1", "S-Q2"], "T": ["T-Q1", "T-Q2"],
                 "O": ["O-Q1", "O-Q2"], "C": ["C-Q1", "C-Q2"], "D": []}
ALL_DTI = [i for p in PILLARS for i in DTI_BY_PILLAR[p]]            # 11 chỉ số
STEP0_MISSING_THRESHOLD = 2
CRITERIA = [f"{p}{n}" for p in PILLARS for n in range(1, 5)]        # 24 tiêu chí
RUBRIC_PCT = {0: 0.0, 1: 25.0, 2: 50.0, 3: 75.0, 4: 100.0}
LEVELS = [(25, "Mức 1 - Khởi động"), (50, "Mức 2 - Bắt đầu"),
          (75, "Mức 3 - Hình thành"), (100, "Mức 4 - Nâng cao")]
# Chỉ số có cận do docx quy định cố định (không cần khóa L,U trong yaml):
DOCX_FIXED = {"K-Q3": (1.0, 5.0, "higher_better"),     # z = (r - 1)/4 * 100
              "T-Q2": (0.0, 100.0, "higher_better")}   # z = x * 100 (x = số nền tảng đạt / 8)


def maturity(score):
    """Quy đổi Score_Bank (%) -> mức 1..5. Đúng 100% mới là Mức 5."""
    if score is None or np.isnan(score):
        return None
    if score >= 100:
        return "Mức 5 - Dẫn dắt"
    for upper, name in LEVELS:
        if score < upper:
            return name


def normalize(x, L, U, direction):
    """Chuẩn hóa tuyến tính theo cận cố định, kẹp trong [0, 100]."""
    if any(v is None or not np.isfinite(v) for v in (x, L, U)) or U <= L:
        return None
    if direction not in ("higher_better", "lower_better"):
        raise ValueError("Chiều chuẩn hóa không hợp lệ")
    t = (U - x) / (U - L) if direction == "lower_better" else (x - L) / (U - L)
    return 100.0 * min(1.0, max(0.0, t))


# ----------------------------------------------------------------------------------------------
# Đọc dữ liệu
# ----------------------------------------------------------------------------------------------
def read_csv(path):
    return pd.read_csv(path, encoding="utf-8-sig")


def load_bounds(draft):
    cfg = load_yaml("dti_bounds.yaml")
    if not cfg.get("locked", False) and not draft:
        sys.exit("DỪNG: config/dti_bounds.yaml chưa khóa (locked: false). Chốt L, U có nguồn rồi đặt "
                 "locked: true, hoặc chạy thử bằng --draft.")
    bounds = {}
    for k, b in cfg["bounds"].items():
        bounds[k] = (b.get("L"), b.get("U"), b.get("direction", "higher_better"))
    bounds.update(DOCX_FIXED)
    missing = [k for k in ALL_DTI if k not in bounds or bounds[k][0] is None or bounds[k][1] is None]
    invalid = [k for k, (L, U, direction) in bounds.items()
               if direction not in ("higher_better", "lower_better")
               or (L is not None and U is not None and
                   (not np.isfinite(L) or not np.isfinite(U) or U <= L))]
    if invalid:
        sys.exit(f"DỪNG: cận hoặc chiều chuẩn hóa không hợp lệ: {invalid}")
    if missing and not draft:
        sys.exit(f"DỪNG: còn chỉ số chưa có L/U: {missing}. Điền theo mục II.2 docx (phân vị 10%/90% hoặc benchmark có nguồn).")
    return bounds, missing


def load_coding(path, draft):
    df = pd.read_excel(path)
    df["criterion"] = df["criterion"].astype(str).str.strip().str.upper()
    df["bank"] = df["bank"].astype(str).str.strip().str.lower()
    df["year"] = df["year"].astype(int)
    df["final"] = pd.to_numeric(df["final"], errors="coerce")
    df["score"] = df["final"]
    if df.duplicated(["bank", "year", "criterion"]).any():
        sys.exit("DỪNG: lưới điểm có dòng ngân hàng/năm/tiêu chí trùng.")
    bad = df[df["score"].notna() & ~df["score"].isin([0, 1, 2, 3, 4])]
    if len(bad):
        sys.exit(f"DỪNG: điểm rubric phải là số nguyên 0-4. Ô sai:\n{bad[['criterion','bank','year','score']].head(10)}")
    return df


def load_inputs(path, draft=False):
    df = read_csv(path)
    df["bank"] = df["bank"].astype(str).str.strip().str.lower()
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    df = df.dropna(subset=["value"])                      # ô trống = thiếu, KHÔNG điền 0
    if not np.isfinite(df["value"]).all():
        sys.exit("DỪNG: dữ liệu đầu vào có số không hữu hạn.")
    if not draft and not confirmed_mask(df).all():
        sys.exit("DỪNG: số liệu chính thức phải được người chấm đối chiếu PDF, có source_file và page; loại range-checked/tự động.")
    if df.duplicated(["bank", "year", "variable"]).any():
        sys.exit("DỪNG: trùng dòng ngân hàng/năm/biến trong dữ liệu đầu vào.")
    if "definition" not in df:
        df["definition"] = ""
    V = {(r.bank, int(r.year), r.variable): float(r.value) for r in df.itertuples()}
    D = {(r.bank, int(r.year), r.variable): (r.definition if isinstance(r.definition, str) else "")
         for r in df.itertuples()}
    return V, D


def load_app_rating(path):
    """K-Q3: r = (r_AS*n_AS + r_GP*n_GP)/(n_AS + n_GP)."""
    try:
        df = read_csv(path)
    except FileNotFoundError:
        return {}
    df["bank"] = df["bank"].astype(str).str.lower()
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    for col in ("rating", "rating_count"):
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.dropna(subset=["date"])
    out = {}
    for b, g in df.groupby("bank"):
        # Một ảnh chụp cùng ngày; lượt thu thập cuối cùng của mỗi cửa hàng thắng.
        g = g[g["date"] == g["date"].max()].drop_duplicates("store", keep="last")
        g = g[g["rating"].between(1, 5) & np.isfinite(g["rating_count"]) & g["rating_count"].gt(0)]
        n = g["rating_count"].sum()
        if n > 0:
            out[b] = (float((g["rating"] * g["rating_count"]).sum() / n), g["date"].max().date().isoformat())
    return out


def load_platform(path):
    """T-Q2: số nền tảng đạt / 8 (checklist manual_audit.xlsx). Chưa kiểm kê đủ 8 dòng -> thiếu."""
    try:
        df = pd.read_excel(path)
    except FileNotFoundError:
        return {}
    col = "achieved(0/1)"
    df["bank"] = df["bank"].astype(str).str.lower()
    out = {}
    for b, g in df.groupby("bank"):
        v = pd.to_numeric(g[col], errors="coerce")
        platform = pd.to_numeric(g["platform_no"], errors="coerce")
        if len(g) == 8 and v.isin([0, 1]).all() and set(platform) == set(range(1, 9)):
            out[b] = float(v.sum() / 8 * 100)           # x tính theo %, z = x
    return out


# ----------------------------------------------------------------------------------------------
# Tính 11 chỉ số DTI (giá trị thô x) cho một ngân hàng-năm
# ----------------------------------------------------------------------------------------------
class Calc:
    def __init__(self, V, D, app, plat, start_year, app_year):
        self.V, self.D, self.app, self.plat = V, D, app, plat
        self.start, self.app_year = start_year, app_year

    def g(self, b, y, v):
        return self.V.get((b, y, v))

    def avg(self, b, y, v):
        """Bình quân đầu-cuối năm (docx dùng 'bình quân'); thiếu năm trước thì dùng cuối kỳ và ghi chú."""
        a, p = self.g(b, y, v), self.g(b, y - 1, v)
        if a is None:
            return None, ""
        return ((a + p) / 2, "") if p is not None else (a, "dùng số cuối kỳ (thiếu năm trước)")

    def cir(self, b, y):
        o, p = self.g(b, y, "opex"), self.g(b, y, "op_profit_before_provision")
        return None if o is None or p is None or (abs(o) + p) <= 0 else abs(o) / (abs(o) + p) * 100

    def toi_per_head(self, b, y):
        o, p = self.g(b, y, "opex"), self.g(b, y, "op_profit_before_provision")
        hc, _ = self.avg(b, y, "headcount")
        return None if o is None or p is None or not hc or hc <= 0 else (abs(o) + p) / hc

    def start_for(self, b, y, var, min_span, same_def=True):
        """Năm đầu kỳ: sớm nhất >= start_year, cách năm cuối >= min_span, cùng nhãn definition."""
        d_end = self.D.get((b, y, var), "")
        for s in range(self.start, y - min_span + 1):
            if (b, s, var) in self.V and (not same_def or self.D.get((b, s, var), "") == d_end):
                return s
        return None

    # --- từng chỉ số: trả (x, ghi_chú) ; x = None nghĩa là thiếu ---
    def kq1(self, b, y):
        x = self.g(b, y, "digital_txn_share")
        return x, f"định nghĩa: {self.D.get((b, y, 'digital_txn_share'), '')}" if x is not None else "thiếu digital_txn_share"

    def kq2(self, b, y):
        s = self.g(b, y, "digital_customer_share")
        if s is not None:
            return s, "KH số/tổng KH do NH công bố"
        n, t = self.g(b, y, "digital_customers"), self.g(b, y, "total_customers")
        if n is not None and t:
            return n / t * 100, (f"digital_customers/total_customers "
                                 f"({self.D.get((b, y, 'digital_customers'), '')}/{self.D.get((b, y, 'total_customers'), '')})")
        return None, "thiếu số KH số hoặc tổng KH"

    def kq3(self, b, y):
        if y != self.app_year or b not in self.app:
            return None, f"chỉ có ảnh chụp tại ngày thu thập (áp cho năm {self.app_year})"
        r, d = self.app[b]
        return r, f"điểm app gộp theo lượt đánh giá, ngày {d}"

    def sq1(self, b, y):
        v = "digital_txn_share"
        if (b, y, v) not in self.V:
            return None, "thiếu digital_txn_share năm cuối"
        s = self.start_for(b, y, v, 1)
        if s is None:
            return None, "không có năm đầu kỳ cùng định nghĩa"
        return (self.V[(b, y, v)] - self.V[(b, s, v)]) / (y - s), f"{s}->{y}, quy về điểm %/năm"

    def sq2(self, b, y):
        v = "digital_customers"
        if (b, y, v) not in self.V:
            return None, "thiếu digital_customers năm cuối"
        s = self.start_for(b, y, v, 2)
        if s is None:
            return None, "không có mốc đầu kỳ cùng định nghĩa cách >= 2 năm"
        if self.V[(b, s, v)] <= 0 or self.V[(b, y, v)] < 0:
            return None, "không tính CAGR khi số đầu kỳ <= 0 hoặc cuối kỳ âm"
        return ((self.V[(b, y, v)] / self.V[(b, s, v)]) ** (1 / (y - s)) - 1) * 100, f"CAGR {s}->{y}"

    def tq1(self, b, y):
        sw, ta = self.g(b, y, "software_gross_cost"), self.avg(b, y, "total_assets")
        if sw is None or not ta[0]:
            return None, "thiếu nguyên giá phần mềm hoặc tổng tài sản"
        return sw / ta[0] * 100, ta[1]

    def tq2(self, b, y):
        if y != self.app_year or b not in self.plat:
            return None, "chưa kiểm kê đủ 8 nền tảng (manual_audit.xlsx)"
        return self.plat[b], "số nền tảng đạt / 8 x 100"

    def oq1(self, b, y):
        e = self.cir(b, y)
        if e is None:
            return None, "thiếu opex hoặc LN trước dự phòng"
        for s in range(self.start, y):
            c = self.cir(b, s)
            if c is not None:
                return (e - c) / (y - s), f"ΔCIR {s}->{y} (điểm %/năm; âm = cải thiện)"
        return None, "không có năm đầu kỳ"

    def oq2(self, b, y):
        e = self.toi_per_head(b, y)
        if e is None or e < 0:
            return None, "thiếu TOI hoặc CBNV"
        for s in range(self.start, y - 1):
            c = self.toi_per_head(b, s)
            if c is not None and c > 0:
                return ((e / c) ** (1 / (y - s)) - 1) * 100, f"CAGR TOI/CBNV bình quân {s}->{y}"
        return None, "không có mốc đầu kỳ cách >= 2 năm"

    def cq1(self, b, y):
        t, h = self.g(b, y, "tech_staff"), self.g(b, y, "headcount")
        if t is None or not h:
            return None, "không công bố nhân sự công nghệ"
        return t / h * 100, ""

    def cq2(self, b, y):
        x = self.g(b, y, "training_hours_per_head")
        return x, f"định nghĩa: {self.D.get((b, y, 'training_hours_per_head'), '')}" if x is not None else "thiếu giờ đào tạo"

    def all(self, b, y):
        fn = {"K-Q1": self.kq1, "K-Q2": self.kq2, "K-Q3": self.kq3, "S-Q1": self.sq1, "S-Q2": self.sq2,
              "T-Q1": self.tq1, "T-Q2": self.tq2, "O-Q1": self.oq1, "O-Q2": self.oq2,
              "C-Q1": self.cq1, "C-Q2": self.cq2}
        return {k: f(b, y) for k, f in fn.items()}


# ----------------------------------------------------------------------------------------------
# Ghép điểm
# ----------------------------------------------------------------------------------------------
def pillar_scores(dbi_by_crit, z_by_ind, w_dbi, missing="drop"):
    """Trả dict {pillar: (dbi, dti, p, n_dti)}; dữ liệu thiếu luôn để trống."""
    if missing != "drop":
        raise ValueError("Không được điền 0 cho chỉ số DTI thiếu dữ liệu")
    if not np.isfinite(w_dbi) or not 0 <= w_dbi <= 1:
        raise ValueError("Trọng số DBI phải thuộc [0, 1]")
    out = {}
    for p in PILLARS:
        vals = [dbi_by_crit[c] for c in CRITERIA if c[0] == p and dbi_by_crit.get(c) is not None]
        dbi = float(np.mean(vals)) if vals else None
        zs = [z_by_ind.get(i) for i in DTI_BY_PILLAR[p]]
        have = [z for z in zs if z is not None]
        if not DTI_BY_PILLAR[p]:
            dti = None
        else:
            dti = float(np.mean(have)) if have else None
        if dbi is None:
            pk = None
        elif dti is None:
            pk = dbi                               # quy tắc thiếu dữ liệu: P_k = DBI_k
        else:
            pk = w_dbi * dbi + (1 - w_dbi) * dti
        out[p] = (dbi, dti, pk, len(have))
    return out


def score_total(pk_dict, weights=None):
    w = weights or {p: 1 / 6 for p in PILLARS}
    if any(v[2] is None for v in pk_dict.values()):
        return None
    return float(sum(w[p] * pk_dict[p][2] for p in PILLARS))


def rank_desc(series):
    return series.rank(ascending=False, method="min").astype("Int64")


def build_indicators(calc, banks, years, bounds):
    """Bước 0: loại chỉ số thiếu ở >=2 ngân hàng, riêng từng năm; giữ số gốc để truy vết."""
    rows = []
    for year in years:
        for bank in banks:
            for indicator, (x, note) in calc.all(bank, year).items():
                L, U, direction = bounds.get(indicator, (None, None, "higher_better"))
                raw_z = normalize(x, L, U, direction)
                rows.append(dict(bank=bank, year=year, indicator=indicator, x=x, L=L, U=U,
                                 direction=direction, z_before_step0=raw_z, note=note))
    frame = pd.DataFrame(rows)
    gates = []
    for (year, indicator), group in frame.groupby(["year", "indicator"], sort=False):
        # Cổng kiểm tra khả năng tính x; thiếu cận không phải thiếu dữ liệu ngân hàng.
        missing = group.loc[group.x.isna(), "bank"].tolist()
        excluded = len(missing) >= STEP0_MISSING_THRESHOLD
        reason = f"thiếu ở {len(missing)}/{len(banks)} ngân hàng; ngưỡng loại >={STEP0_MISSING_THRESHOLD}"
        gates.append(dict(year=year, indicator=indicator, n_banks=len(banks), n_missing=len(missing),
                          missing_banks=";".join(missing), retained=not excluded,
                          step0_reason=reason, step0_method="indicator_per_year_v1"))
    gate = pd.DataFrame(gates)
    frame = frame.merge(gate, on=["year", "indicator"], validate="many_to_one")
    frame["z"] = frame.z_before_step0.where(frame.retained)
    frame["included_in_score"] = frame.z.notna()
    frame["status"] = ["loại bởi bước 0" if not r.retained else
                       ("có dữ liệu" if pd.notna(r.z) else
                        ("thiếu dữ liệu" if pd.isna(r.x) else "chưa có L/U"))
                       for r in frame.itertuples()]
    return frame, gate


def write_results_excel(tables, path):
    """Giữ kiểu số thật để Excel không diễn giải dấu thập phân theo vùng của CSV."""
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        for sheet, table in tables.items():
            table.to_excel(writer, sheet_name=sheet, index=False)
            ws = writer.sheets[sheet]
            ws.freeze_panes = "C2"
            ws.auto_filter.ref = ws.dimensions
            for column in ws.columns:
                name = str(column[0].value)
                ws.column_dimensions[column[0].column_letter].width = min(35, max(15, len(name) + 2))
                for cell in column[1:]:
                    if isinstance(cell.value, float):
                        cell.number_format = "0.00"


def main():
    ap = argparse.ArgumentParser()
    project = load_yaml("banks.yaml")
    ap.add_argument("--years", default=",".join(map(str, project["coding_years"])), help="mặc định toàn bộ năm chấm trong banks.yaml")
    ap.add_argument("--start-year", type=int, default=2021, help="đầu kỳ cho Δ/CAGR (docx: 2021-2025)")
    ap.add_argument("--w-dbi", type=float, default=0.8, help="trọng số DBI trong P_k (cơ sở 0,8)")
    ap.add_argument("--coding", default=str(OUT / "coding_auto.xlsx"))
    ap.add_argument("--inputs", default=str(OUT / "dataset_clean" / "dti_inputs_confirmed.csv"))
    ap.add_argument("--app", default=str(OUT / "app_ratings.csv"))
    ap.add_argument("--audit", default=str(OUT / "manual_audit.xlsx"))
    ap.add_argument("--draft", action="store_true", help="chạy thử: cho phép bounds chưa khóa/DBI chưa đủ; điểm thiếu vẫn để trống")
    ap.add_argument("--weight-scenarios", action="store_true", help="chạy thêm 100/0, 80/20, 70/30, 60/40")
    a = ap.parse_args()
    years = [int(y) for y in a.years.split(",")]
    suffix = "_draft" if a.draft else ""

    bounds, missing_bounds = load_bounds(a.draft)
    coding = load_coding(a.coding, a.draft)
    metadata = {}
    for name in ("scoring_method", "rules_version", "rules_hash"):
        if name in coding:
            values = coding[name].dropna().unique()
            if len(values) != 1: sys.exit(f"DỪNG: lưới điểm có nhiều hoặc thiếu phiên bản {name}.")
            metadata[name] = values[0]
    V, D = load_inputs(a.inputs, a.draft)
    calc = Calc(V, D, load_app_rating(a.app), load_platform(a.audit), a.start_year, max(project["coding_years"]))
    banks = sorted(coding["bank"].unique())
    if set(banks) != set(project["banks"]):
        sys.exit("DỪNG: Bước 0 phải kiểm tra đủ tập ngân hàng trong config/banks.yaml.")

    # ---- 1) 11 chỉ số DTI ----
    ind, gate = build_indicators(calc, banks, years, bounds)
    z_map = {(r.bank, r.year, r.indicator): (float(r.z) if pd.notna(r.z) else None)
             for r in ind.itertuples()}
    raw_counts = ind.groupby(["bank", "year"]).z_before_step0.count().to_dict()
    retained_counts = gate.groupby("year").retained.sum().to_dict()
    ind.to_csv(OUT / f"dti_indicators{suffix}.csv", index=False, encoding="utf-8-sig")
    gate.to_csv(OUT / f"step0_gate{suffix}.csv", index=False, encoding="utf-8-sig")

    # ---- 2) DBI (24 tiêu chí) ----
    c = coding[coding["year"].isin(years)].copy()
    c["pct"] = c["score"].map(lambda s: None if pd.isna(s) else s / 4 * 100)
    dbi_map = {(r.bank, r.year, r.criterion): r.pct for r in c.itertuples()}
    incomplete = [(b, y, k) for b in banks for y in years for k in CRITERIA
                  if dbi_map.get((b, y, k)) is None or pd.isna(dbi_map.get((b, y, k)))]
    if incomplete and not a.draft:
        sys.exit(f"DỪNG: còn {len(incomplete)} ô chưa có điểm final, ví dụ {incomplete[:5]}. "
                 "Kiểm tra tài liệu và chạy 09c_auto_score.py, hoặc chạy thử bằng --draft.")

    # ---- 3) P_k, Score_Bank, hạng, mức ----
    def run(w_dbi, missing="drop", weights=None):
        rows = []
        for y in years:
            for b in banks:
                dbi_c = {k: dbi_map.get((b, y, k)) for k in CRITERIA}
                dbi_c = {k: (None if v is None or pd.isna(v) else v) for k, v in dbi_c.items()}
                z_i = {i: z_map.get((b, y, i)) for i in ALL_DTI}
                ps = pillar_scores(dbi_c, z_i, w_dbi, missing)
                n_have = sum(z is not None for z in z_i.values())
                rows.append(dict(bank=b, year=y, ps=ps, score=score_total(ps, weights),
                                 conf=raw_counts[(b, y)] / 11, scoring_coverage=n_have / 11,
                                 n_dti_available=raw_counts[(b, y)], n_dti_used=n_have,
                                 n_dti_retained=int(retained_counts[y]), step0_method="indicator_per_year_v1", **metadata))
        df = pd.DataFrame(rows)
        df["rank"] = df.groupby("year")["score"].transform(rank_desc)
        df["level"] = df["score"].map(maturity)
        return df

    base = run(a.w_dbi)
    long_rows = []
    for r in base.itertuples():
        for p, (dbi, dti, pk, n) in r.ps.items():
            long_rows.append(dict(bank=r.bank, year=r.year, pillar=p, pillar_name=PILLARS[p], dbi=dbi, dti=dti,
                                  n_dti=n, p=pk, data_confidence=round(r.conf, 3), score_total=r.score,
                                  scoring_coverage=r.scoring_coverage, n_dti_retained=r.n_dti_retained,
                                  step0_method=r.step0_method, maturity_level=r.level, rank=r.rank, **metadata))
    pillar_table = pd.DataFrame(long_rows)
    pillar_table.to_csv(OUT / f"scores{suffix}.csv", index=False, encoding="utf-8-sig")
    summ = base.drop(columns="ps").rename(columns={"conf": "data_confidence", "level": "maturity_level"})
    summ["note"] = "DRAFT - không dùng làm kết quả chính thức" if a.draft else ""
    summ.sort_values(["year", "rank"]).to_csv(OUT / f"score_summary{suffix}.csv", index=False, encoding="utf-8-sig")
    report = ["# Bước 0 — cổng sẵn có dữ liệu", "",
              "Quy tắc indicator_per_year_v1: chỉ số DTI thiếu giá trị tính được ở từ 2 ngân hàng trở lên bị loại khỏi điểm của cả tập ngân hàng, riêng từng năm. Không tự thay proxy.", "",
              "Dữ liệu nguồn và x/z_before_step0 được giữ nguyên; z là điểm thực sự dùng sau cổng. Thiếu dữ liệu không điền 0. Trụ cột không còn DTI dùng DBI thuần.", "",
              "data_confidence = số chỉ số có dữ liệu chuẩn hóa được trước cổng / 11; scoring_coverage = số dùng sau cổng / 11. Hai tỷ lệ đo hai việc khác nhau.", "",
              "24 tiêu chí DBI và công thức 80/20, trung bình 6 trụ cột, cận L/U cố định không đổi. Rating/checklist chỉ áp cho năm cuối dự án. Bộ chỉ số giữ lại khác nhau giữa các năm; điểm xuyên năm không dựa trên một bộ DTI cố định.", "",
              "Ma trận ngân hàng × biến × năm: variable_availability_matrix.csv (bước 12). Quyết định loại áp ở cấp chỉ số sau khi kiểm tra đủ đầu vào/định nghĩa, không xóa biến thô khỏi dataset.", "",
              "Agribank không niêm yết: đọc riêng nguồn và note trong ma trận; không miễn cổng hoặc coi thiếu dữ liệu là 0.", "",
              "| Năm | Chỉ số DTI giữ lại | Số giữ |", "|---|---|---:|"]
    for year, group in gate.groupby("year"):
        kept = group.loc[group.retained, "indicator"].tolist()
        report.append(f"| {year} | {', '.join(kept) or 'Không có'} | {len(kept)} |")
    report.extend(["", "| Năm | Ngân hàng | Điểm | Hạng | Có dữ liệu / 11 | Dùng chấm / 11 |",
                   "|---|---|---:|---:|---:|---:|"])
    for r in summ.sort_values(["year", "rank"]).itertuples():
        report.append(f"| {r.year} | {r.bank} | {r.score:.2f} | {r.rank} | {r.n_dti_available}/11 | {r.n_dti_used}/11 |")
    if a.draft:
        report.insert(2, "DRAFT — không dùng làm kết quả chính thức.")
    (OUT / f"step0_report{suffix}.md").write_text("\n".join(report) + "\n", encoding="utf-8-sig")

    print(f"\n=== KẾT QUẢ (w_DBI={a.w_dbi}, {'DRAFT' if a.draft else 'CHÍNH THỨC'}) ===")
    for y in years:
        print(f"\nNăm {y}")
        print(summ[summ.year == y].sort_values("rank")[["rank", "bank", "score", "maturity_level", "data_confidence"]]
              .to_string(index=False, float_format=lambda v: f"{v:.2f}"))
    if a.draft and missing_bounds:
        print(f"\n[!] Chỉ số chưa có L/U (bị loại khỏi DTI, làm giảm data_confidence): {missing_bounds}")

    # ---- 4) kịch bản trọng số DBI/DTI (mục V.2) ----
    excel_tables = {"Tổng điểm": summ.sort_values(["year", "rank"]),
                    "Sáu trụ cột": pillar_table, "Chỉ số DTI": ind, "Cổng bước 0": gate}
    wide = pillar_table.pivot(index=["bank", "year"], columns="pillar_name", values="p").reset_index()
    excel_tables["Trụ cột bảng ngang"] = wide
    if a.weight_scenarios:
        parts = []
        for w in (1.0, 0.8, 0.7, 0.6):
            s = run(w)[["bank", "year", "score", "rank"]]
            s.insert(0, "scenario", f"{int(w*100)}/{int(round((1-w)*100))}")
            parts.append(s)
        sens = pd.concat(parts)
        sens.to_csv(OUT / f"sensitivity_weights{suffix}.csv", index=False, encoding="utf-8-sig")
        excel_tables["Độ nhạy trọng số"] = sens
        pv = sens[sens.year == max(years)].pivot(index="bank", columns="scenario", values="rank")
        print("\nThứ hạng theo kịch bản (năm cuối):\n", pv.to_string())

    # XLSX giữ kiểu số thật, tránh Excel theo vùng Việt Nam hiểu dấu chấm CSV là hàng nghìn.
    write_results_excel(excel_tables, OUT / f"score_results{suffix}.xlsx")
    print(f"\nBảng Excel giữ đúng kiểu số: {OUT / f'score_results{suffix}.xlsx'}")


if __name__ == "__main__":
    main()
