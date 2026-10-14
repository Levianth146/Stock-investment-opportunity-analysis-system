"""Kiểm thử các quy tắc tính điểm theo docx. Chạy từ thư mục scripts/:  python ../tests/test_score.py"""
import importlib.util, pathlib, sys

SC = pathlib.Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(SC))
spec = importlib.util.spec_from_file_location("score", SC / "10_score.py")
S = importlib.util.module_from_spec(spec); spec.loader.exec_module(S)

fails = []
def check(name, cond):
    print(("OK   " if cond else "FAIL ") + name)
    if not cond: fails.append(name)

# 1. Chuẩn hóa z = 100*min{1;max[0;(x-L)/(U-L)]}
check("z giữa thang", abs(S.normalize(45, 0, 90, "higher_better") - 50) < 1e-9)
check("z kẹp trên 100", S.normalize(120, 0, 90, "higher_better") == 100)
check("z kẹp dưới 0", S.normalize(-5, 0, 90, "higher_better") == 0)
check("chỉ số nghịch (U-x)/(U-L)", abs(S.normalize(2, -7, 7, "lower_better") - 100 * 5 / 14) < 1e-9)
check("thiếu L/U -> None", S.normalize(10, None, 5, "higher_better") is None)
check("K-Q3: r=5 -> 100, r=1 -> 0",
      S.normalize(5, 1, 5, "higher_better") == 100 and S.normalize(1, 1, 5, "higher_better") == 0)

# 2. Năm mức (mục IV)
lv = S.maturity
check("24.99 -> Mức 1", lv(24.99).startswith("Mức 1"))
check("25 -> Mức 2", lv(25).startswith("Mức 2"))
check("50 -> Mức 3", lv(50).startswith("Mức 3"))
check("75 -> Mức 4", lv(75).startswith("Mức 4"))
check("99.99 -> Mức 4", lv(99.99).startswith("Mức 4"))
check("100 -> Mức 5", lv(100).startswith("Mức 5"))

# 3. P_k và Score_Bank
dbi = {c: 50.0 for c in S.CRITERIA}                 # mọi tiêu chí = 2/4 -> 50%
z = {i: None for i in S.ALL_DTI}
ps = S.pillar_scores(dbi, z, 0.8)
check("không có DTI -> P_k = DBI_k", all(abs(v[2] - 50) < 1e-9 for v in ps.values()))
z["K-Q1"], z["K-Q2"] = 100.0, 50.0                  # DTI_K = 75
ps = S.pillar_scores(dbi, z, 0.8)
check("P_K = 0,8*50 + 0,2*75 = 55", abs(ps["K"][2] - 55) < 1e-9)
check("trụ cột D luôn = DBI_D", abs(ps["D"][2] - 50) < 1e-9)
check("Score = TB 6 trụ cột = 50.8333", abs(S.score_total(ps) - (55 + 5 * 50) / 6) < 1e-9)
try:
    S.pillar_scores(dbi, z, 0.8, missing="zero")
    check("từ chối điền 0 cho DTI thiếu", False)
except ValueError:
    check("từ chối điền 0 cho DTI thiếu", True)

# 4. Danh mục
check("11 chỉ số DTI", len(S.ALL_DTI) == 11)
check("24 tiêu chí DBI", len(S.CRITERIA) == 24)

print("\nTất cả đạt" if not fails else f"\nCÓ {len(fails)} LỖI: {fails}")
sys.exit(1 if fails else 0)
