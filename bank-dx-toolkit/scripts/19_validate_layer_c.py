"""Đối chiếu mô tả lớp C; chạy từ scripts/: python 19_validate_layer_c.py.

Không sửa điểm hoặc dữ liệu gốc. Chỉ số tài chính giữ nguyên dữ liệu thiếu;
ROE/ROA bắt buộc có số đầu kỳ. Tương quan tính riêng từng năm, không có p-value.
"""
import argparse
import hashlib
import json
import datetime
import shutil
from pathlib import Path

import numpy as np
import pandas as pd

from common import OUT, confirmed_mask

INDICATORS = {
    "roe": ("net_profit_parent", "equity"),
    "roa": ("net_profit_consolidated", "total_assets"),
    "casa": ("casa_deposits", "customer_deposits"),
    "non_interest_share": ("opex", "op_profit_before_provision", "net_interest_income"),
}
FORMULAS = {
    "roe": "100 * net_profit_parent / ((equity_previous + equity_current) / 2)",
    "roa": "100 * net_profit_consolidated / ((assets_previous + assets_current) / 2)",
    "casa": "100 * casa_deposits / customer_deposits",
    "non_interest_share": "100 * (TOI - net_interest_income) / TOI; TOI = abs(opex) + op_profit_before_provision",
}
REVIEW_COLUMNS = ("review_status", "reviewed_by", "review_date", "review_evidence")


def field(row, name):
    """Đọc trường tùy chọn, không biến ô trống thành chuỗi nan."""
    value = row.get(name)
    return "" if pd.isna(value) else str(value).strip()


def review_warnings(row):
    """resolved chỉ đóng cờ ghi chú khi có đủ người/ngày/bằng chứng."""
    status = field(row, "review_status").lower()
    flagged = any(s in field(row, "note").lower() for s in ("cần kiểm", "chưa đối chiếu", "giữ tạm"))
    if status == "resolved":
        try:
            datetime.date.fromisoformat(field(row, "review_date"))
            valid_date = True
        except ValueError:
            valid_date = False
        if all(field(row, c) for c in ("reviewed_by", "review_evidence")) and valid_date:
            return []
        return ["resolved thiếu người, ngày YYYY-MM-DD hoặc bằng chứng"]
    if status and status != "pending":
        return ["Trạng thái rà soát không hợp lệ"]
    return ["Cờ rà soát chưa giải quyết"] if flagged or status == "pending" else []


def prepare_inputs(path):
    """Bổ sung cấu trúc; không suy đoán số hoặc xác nhận từ ghi chú cũ."""
    df = read_table(path, ["bank", "year", "variable"])
    original_columns = list(df.columns)
    for col in REVIEW_COLUMNS:
        if col not in df:
            df[col] = ""
    rows = []
    keys = set(zip(df.bank, df.year, df.variable))
    for bank, year in df[["bank", "year"]].drop_duplicates().itertuples(index=False, name=None):
        for variable, scope in (("net_profit_parent", "parent"), ("net_profit_consolidated", "consolidated")):
            if (bank, year, variable) not in keys:
                r = {c: "" for c in df.columns}
                r.update(bank=bank, year=year, variable=variable, unit="VND million",
                         definition=scope, review_status="pending",
                         note="Chưa xác nhận LNST theo phạm vi; không sao chép net_profit cũ")
                rows.append(r)
    if rows or original_columns != list(df.columns):
        backup = path.with_name(f"{path.stem}.before_layer_c_{datetime.datetime.now():%Y%m%d_%H%M%S_%f}.csv")
        shutil.copy2(path, backup)
        df = pd.concat([df, pd.DataFrame(rows)], ignore_index=True) if rows else df
        df.to_csv(path, index=False, encoding="utf-8-sig")
        print(f"Đã bổ sung {len(rows)} dòng trống; bản lưu: {backup}")
    return df


def read_table(path, keys):
    """Không âm thầm chọn một dòng khi khóa bị trùng."""
    df = pd.read_csv(path, encoding="utf-8-sig")
    df["bank"] = df["bank"].astype(str).str.strip().str.lower()
    df["year"] = pd.to_numeric(df["year"], errors="raise").astype(int)
    if df.duplicated(keys).any():
        raise ValueError(f"Khóa trùng trong {path}: {keys}")
    return df


def calculate(inputs, targets):
    """Tính tỷ số và lưu toàn bộ đầu vào/nguồn dùng trong từng phép tính."""
    valid = inputs[confirmed_mask(inputs)].copy()
    lookup = {(r["bank"], int(r["year"]), r["variable"]): r
              for r in valid.to_dict("records")}
    rows = []
    for bank, year in targets:
        for indicator, variables in INDICATORS.items():
            required = [(year, v) for v in variables]
            if indicator in ("roe", "roa"):
                required.append((year - 1, variables[1]))
            evidence, missing, warnings, values = [], [], [], {}
            for source_year, variable in required:
                r = lookup.get((bank, source_year, variable))
                if r is None:
                    missing.append(f"{variable}:{source_year}")
                    continue
                values[(source_year, variable)] = float(r["value"])
                e = {k: (None if pd.isna(r.get(k)) else r.get(k)) for k in
                     ("variable", "value", "unit", "source_file", "page", "note", "definition", "confirmed_by", *REVIEW_COLUMNS)}
                e["year"] = source_year
                evidence.append(e)
                warnings.extend(f"{w}: {variable}:{source_year}" for w in review_warnings(r))
                if r.get("unit") != "VND million":
                    warnings.append(f"Đơn vị chưa đồng nhất: {variable}:{source_year}")
            scope_ok = True
            if indicator in ("roe", "roa"):
                expected = "parent" if indicator == "roe" else "consolidated"
                for source_year, variable in required:
                    r = lookup.get((bank, source_year, variable))
                    if r is not None and field(r, "definition") != expected:
                        scope_ok = False
                        warnings.append(f"Phạm vi phải là {expected}: {variable}:{source_year}")
            value = None
            if not missing and scope_ok:
                current = [values[(year, v)] for v in variables]
                if indicator in ("roe", "roa"):
                    numerator = current[0]
                    denominator = (current[1] + values[(year - 1, variables[1])]) / 2
                elif indicator == "casa":
                    numerator, denominator = current
                else:
                    denominator = abs(current[0]) + current[1]
                    numerator = denominator - current[2]
                if denominator > 0:
                    value = 100 * numerator / denominator
                    if indicator == "casa" and not 0 <= value <= 100:
                        warnings.append("CASA ngoài khoảng 0–100%")
                else:
                    warnings.append("Mẫu số không dương; không tính tỷ số")
            rows.append(dict(bank=bank, year=year, indicator=indicator, value=value,
                             unit="%", status="missing" if missing else
                             ("needs_review" if warnings else "available"),
                             missing_inputs="; ".join(missing), warnings="; ".join(warnings),
                             formula=FORMULAS[indicator],
                             evidence=json.dumps(evidence, ensure_ascii=False)))
    return pd.DataFrame(rows)


def spearman_pairs(pairs):
    """Pearson trên hạng trung bình, xử lý đồng hạng và cặp thiếu."""
    pairs = pairs.replace([np.inf, -np.inf], np.nan).dropna(subset=["x", "y"])
    if len(pairs) < 3:
        return None, "insufficient_pairs"
    if pairs.x.nunique() < 2 or pairs.y.nunique() < 2:
        return None, "constant_series"
    return float(pairs.x.rank(method="average").corr(pairs.y.rank(method="average"))), "descriptive_only"


def review_queue(inputs, targets):
    """Danh sách đầu vào cần rà soát, ưu tiên năm cuối và số đầu kỳ của nó."""
    lookup = {(r["bank"], int(r["year"]), r["variable"]): r for r in inputs.to_dict("records")}
    eligible = set(zip(inputs.loc[confirmed_mask(inputs), "bank"],
                       inputs.loc[confirmed_mask(inputs), "year"],
                       inputs.loc[confirmed_mask(inputs), "variable"]))
    requirements = {}
    latest = max(year for _, year in targets)
    for bank, year in targets:
        for indicator, variables in INDICATORS.items():
            required = [(year, v) for v in variables]
            if indicator in ("roe", "roa"):
                required.append((year - 1, variables[1]))
            for source_year, variable in required:
                key = (bank, source_year, variable)
                task = requirements.setdefault(key, dict(indicators=set(), target_years=set()))
                task["indicators"].add(indicator)
                task["target_years"].add(year)
    rows = []
    for key, task in requirements.items():
        bank, year, variable = key
        r = lookup.get(key, {})
        reasons = review_warnings(r)
        if key not in eligible:
            reasons.append("Thiếu số đã xác nhận hoặc nguồn/trang/người đối chiếu")
        if variable in ("net_profit_parent", "equity", "net_profit_consolidated", "total_assets"):
            expected = "parent" if variable in ("net_profit_parent", "equity") else "consolidated"
            if field(r, "definition") != expected:
                reasons.append(f"Cần xác nhận definition={expected}")
        if r and field(r, "unit") != "VND million":
            reasons.append("Cần xác nhận đơn vị VND million")
        if not reasons:
            continue
        row = {c: (None if pd.isna(r.get(c)) else r.get(c)) for c in
               ("value", "unit", "source_file", "page", "confirmed_by", "note", "definition", *REVIEW_COLUMNS)}
        row.update(bank=bank, year=year, variable=variable,
                   priority=1 if latest in task["target_years"] else 2,
                   used_for=";".join(sorted(task["indicators"])),
                   target_years=";".join(map(str, sorted(task["target_years"]))),
                   review_reason="; ".join(reasons))
        # Chỉ dẫn để mở lại tài liệu; không dùng số cũ thay LNST mới.
        legacy = lookup.get((bank, year, "net_profit"), {}) if variable.startswith("net_profit_") else {}
        for col in ("source_file", "page", "note"):
            row[f"legacy_{col}"] = legacy.get(col)
        rows.append(row)
    columns = ["priority", "bank", "year", "variable", "value", "unit", "source_file", "page",
               "confirmed_by", "note", "definition", *REVIEW_COLUMNS, "used_for", "target_years",
               "review_reason", "legacy_source_file", "legacy_page", "legacy_note"]
    return pd.DataFrame(rows, columns=columns).sort_values(["priority", "bank", "year", "variable"])


def correlations(indicators, scores):
    """Hai tập: đủ số đã xác nhận và tập loại các cờ cần rà soát."""
    merged = indicators.merge(scores, on=["bank", "year"], how="left", validate="many_to_one")
    rows = []
    for (year, indicator), group in merged.groupby(["year", "indicator"], sort=True):
        for score_name in ("score", "dbi_score"):
            for sample in ("available_confirmed", "without_review_flags"):
                selected = group if sample == "available_confirmed" else group[group.status == "available"]
                pairs = selected[["bank", score_name, "value"]].rename(columns={score_name: "x", "value": "y"})
                pairs = pairs.replace([np.inf, -np.inf], np.nan).dropna(subset=["x", "y"])
                rho, status = spearman_pairs(pairs)
                rows.append(dict(year=int(year), indicator=indicator, score_variable=score_name,
                                 sample=sample, n_banks=len(pairs), spearman=rho, status=status,
                                 banks=";".join(sorted(pairs.bank)),
                                 n_review_flags=int(selected.loc[selected.bank.isin(pairs.bank), "status"].eq("needs_review").sum())))
    return merged, pd.DataFrame(rows)


def report(indicators, corr):
    """Diễn giải với số quan sát thực tế, không suy diễn nhân quả."""
    lines = ["# Đối chiếu lớp C — kết quả mô tả sơ bộ", "",
             "Đầu vào là số liệu đã được đánh dấu đối chiếu PDF; bước này không đọc lại PDF để xác minh.",
             "Điểm DBI–DTI không thay đổi. ROE/ROA dùng bình quân đầu–cuối kỳ; thiếu đầu kỳ để trống.",
             "ROE dùng net_profit_parent và vốn thuộc cổ đông mẹ; ROA dùng net_profit_consolidated và tài sản hợp nhất. Không dùng net_profit cũ thay thế.",
             "Tỷ trọng thu nhập ngoài lãi dùng toàn bộ TOI trừ thu nhập lãi thuần, không chỉ phí dịch vụ.", "",
             "## Độ đầy đủ và cờ dữ liệu", "",
             "| Năm | Chỉ số | Có tỷ số | Cần rà soát | Thiếu/không tính được |",
             "|---|---|---:|---:|---:|"]
    for (year, ind), g in indicators.groupby(["year", "indicator"], sort=True):
        lines.append(f"| {year} | {ind} | {g.value.notna().sum()}/{len(g)} | {g.status.eq('needs_review').sum()} | {g.value.isna().sum()} |")
    lines += ["", "ROE yêu cầu definition=parent; ROA yêu cầu definition=consolidated cho cả tử số và mẫu số đầu–cuối kỳ. Phạm vi thiếu/sai thì tỷ số để trống.",
              "Ghi chú lịch sử được giữ nguyên. review_status=resolved chỉ đóng cờ ghi chú khi có reviewed_by, review_date dạng YYYY-MM-DD và review_evidence; không bỏ kiểm tra phạm vi/đơn vị/nguồn.",
              "review_status=pending giữ cờ đang mở. Ô trạng thái trống vẫn kiểm tra ghi chú cũ; không tự coi câu ‘đã đối chiếu’ trong note là bằng chứng giải quyết cờ.",
              "Danh sách việc cần xử lý: layer_c_review_queue.csv; priority=1 là đầu vào cho năm cuối, gồm số đầu kỳ. Các cột legacy_* chỉ dẫn đến số LNST cũ để đọc lại tài liệu.",
              "Năm 2020 cần dữ liệu cuối 2019 để tính ROE/ROA; không thay bằng số cuối 2020.", "",
              "## Tương quan với điểm tổng trên các cặp đủ số", "",
              "Bảng này bao gồm dữ liệu có cờ rà soát; đọc cùng bảng tương quan loại các cờ trong CSV.", "",
              "| Năm | Chỉ số | n | Spearman | Cặp có cờ |", "|---|---|---:|---:|---:|"]
    for r in corr[(corr.score_variable == "score") & (corr['sample'] == "available_confirmed")].itertuples():
        rho = "" if pd.isna(r.spearman) else f"{r.spearman:.3f}"
        lines.append(f"| {r.year} | {r.indicator} | {r.n_banks} | {rho} | {r.n_review_flags} |")
    lines += ["", "## Cách đọc và việc còn lại", "",
              "Spearman tính riêng từng năm trên cùng tập ngân hàng có đủ cặp, dùng hạng trung bình khi đồng hạng. Dưới 3 cặp hoặc dãy hằng thì để trống.",
              "Hệ số dương biểu thị đồng biến, âm biểu thị nghịch biến trong mẫu. Tối đa 5 ngân hàng/năm; không báo p-value, không suy diễn nhân quả hoặc gộp các năm thành quan sát độc lập.",
              "CSV có đối chiếu DBI thuần (trung bình đủ 6 trụ cột) vì điểm tổng chứa DTI liên quan hiệu quả hoạt động. Đây vẫn là đối chiếu mô tả, không xác nhận chất lượng thuật toán.",
              "Cần rà soát phạm vi hợp nhất/riêng lẻ và định nghĩa LNST/tài sản/tiền gửi từ PDF gốc trước khi dùng làm kết luận chính thức; các cờ tự động không bao quát mọi lỗi định nghĩa.",
              "Đối chiếu giải thưởng/xếp hạng bên thứ ba chưa thực hiện trong bước này. Cần nguồn công khai từ tổ chức trao, năm, tiêu chí, URL, ngày truy cập và đánh dấu bằng chứng đã dùng chấm DBI.", ""]
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--years", default="2020,2021,2022,2023,2024,2025")
    ap.add_argument("--inputs", type=Path, default=OUT / "dataset_clean/dti_inputs_confirmed.csv")
    ap.add_argument("--review-inputs", type=Path, default=OUT / "dti_inputs.csv",
                    help="Dữ liệu đầy đủ để lập danh sách rà soát, kể cả số chưa xác nhận")
    ap.add_argument("--prepare-inputs", action="store_true",
                    help="Thêm cột rà soát và dòng LNST trống vào --review-inputs; tạo bản lưu trước khi sửa")
    ap.add_argument("--summary", type=Path, default=OUT / "score_summary.csv")
    ap.add_argument("--pillars", type=Path, default=OUT / "scores.csv")
    ap.add_argument("--output-dir", type=Path, default=OUT)
    args = ap.parse_args()
    if args.prepare_inputs:
        prepare_inputs(args.review_inputs)
        awards = args.output_dir / "layer_c_awards.csv"
        args.output_dir.mkdir(parents=True, exist_ok=True)
        if not awards.exists():
            pd.DataFrame(columns=["bank", "year", "award_name", "issuer", "criteria", "url",
                                  "access_date", "used_in_dbi", "dbi_criterion", "note"]).to_csv(
                                      awards, index=False, encoding="utf-8-sig")
        print("Đã chuẩn bị cấu trúc; chạy 12_appendix.py --bundle rồi chạy lại bước 19.")
        return
    inputs = read_table(args.inputs, ["bank", "year", "variable"])
    review_inputs = read_table(args.review_inputs, ["bank", "year", "variable"])
    summary = read_table(args.summary, ["bank", "year"])
    pillars = read_table(args.pillars, ["bank", "year", "pillar"])
    summary = summary[summary.year.isin([int(y) for y in args.years.split(",")])].copy()
    if summary.empty:
        raise ValueError("Không có điểm cho các năm được chọn")
    # Chỉ nhận đủ sáu trụ cột; điểm chi tiết phải khớp bảng tổng.
    dbi_rows = []
    for r in summary.itertuples():
        g = pillars[(pillars.bank == r.bank) & (pillars.year == r.year)]
        if set(g.pillar) != set("KSTOCD") or len(g) != 6:
            raise ValueError(f"Thiếu sáu trụ cột: {r.bank}/{r.year}")
        if not np.allclose(g.score_total, r.score, equal_nan=True):
            raise ValueError(f"Điểm tổng không khớp điểm trụ cột: {r.bank}/{r.year}")
        for col in ("rules_version", "rules_hash", "scoring_method"):
            if col in summary and col in pillars and not g[col].eq(getattr(r, col)).all():
                raise ValueError(f"Phiên bản không khớp: {r.bank}/{r.year}/{col}")
        dbi = g.dbi.mean() if g.dbi.notna().all() else None
        dbi_rows.append(dict(bank=r.bank, year=r.year, dbi_score=dbi))
    scores = summary.merge(pd.DataFrame(dbi_rows), on=["bank", "year"], validate="one_to_one")
    indicators = calculate(inputs, list(zip(summary.bank, summary.year)))
    queue = review_queue(review_inputs, list(zip(summary.bank, summary.year)))
    merged, corr = correlations(indicators, scores)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    indicators.to_csv(args.output_dir / "layer_c_indicators.csv", index=False, encoding="utf-8-sig")
    merged.to_csv(args.output_dir / "layer_c_pairs.csv", index=False, encoding="utf-8-sig")
    corr.to_csv(args.output_dir / "layer_c_correlations.csv", index=False, encoding="utf-8-sig")
    queue.to_csv(args.output_dir / "layer_c_review_queue.csv", index=False, encoding="utf-8-sig")
    (args.output_dir / "layer_c_report.md").write_text(report(indicators, corr), encoding="utf-8-sig")
    paths = [args.inputs, args.review_inputs, args.summary, args.pillars, Path(__file__)]
    manifest = dict(method="layer-c-descriptive-v2", years=sorted(summary.year.unique().tolist()),
                    input_hashes={str(p.resolve()): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},
                    third_party_validation="not_performed", scope="descriptive_financial_comparison")
    (args.output_dir / "layer_c_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8-sig")
    print(f"Đã xuất {len(indicators)} dòng chỉ số và {len(corr)} dòng tương quan vào {args.output_dir}")
    print("Kết quả mô tả sơ bộ; xem layer_c_report.md và các cờ cần rà soát.")


if __name__ == "__main__":
    main()
