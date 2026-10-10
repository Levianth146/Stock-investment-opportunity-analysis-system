"""vnfinancialdata: đối chiếu / bổ sung / kéo dài lịch sử / chống look-ahead / tùy chọn."""
import json
from pathlib import Path

import pandas as pd

from stockai.contracts.schemas import validate
from stockai.m1_data import vnf_source as v

ON = {"vnf_enabled": True}
FIX = Path(__file__).resolve().parents[1] / "fixtures" / "snapshot_DEMO.json"
# giá trị thật của HPG năm 2025 (từ vnfinancialdata) ở dạng (item_code, giá trị)
HPG25 = [("is_doanh_so_thuan", 156116094618482.0), ("is_lai_gop", 24497788183182.0), ("is_lai_lo_thuan_sau_thue", 15514931571606.0),
         ("is_trong_do_chi_phi_lai_vay", -3114855868974.0), ("bs_tong_tai_san", 257899200817547.0),
         ("bs_von_chu_so_huu_4d280b22", 131220010876575.0), ("bs_cac_khoan_phai_thu", 15042323117690.0),
         ("bs_phai_tra_nguoi_ban", 21183376049432.0), ("cf_tien_mua_tai_san_co_dinh_va_cac_tai_san_dai_han_khac", -25748320476719.0),
         ("cf_co_tuc_da_tra", -36538787548.0), ("is_ebitda", 28898303373941.0), ("is_lai_co_ban_tren_co_phieu", 1973.0)]
STMT = {"is": "income_statement", "bs": "balance_sheet", "cf": "cash_flow"}


def _df(exchange, statement, years=(2025,), ticker="HPG", scale=1.0):
    rows = [dict(ticker=ticker, year=y, exchange=exchange, statement=STMT[c[:2]], item_code=c, item_name=c, value=val * scale,
                 source_file="f", source_sheet="s")
            for y in years for c, val in HPG25 if STMT[c[:2]] == statement]
    return pd.DataFrame(rows, columns=["ticker", "year", "exchange", "statement", "item_code", "item_name", "value", "source_file", "source_sheet"])


def _loader(years=(2025,), scale=1.0, ticker="HPG"):
    return lambda exchange, statement: _df(exchange, statement, years, ticker, scale) if exchange == "HSX" else _df(exchange, statement, (), ticker)


def _snap(as_of="2026-10-08"):
    s = json.loads(FIX.read_text(encoding="utf-8"))
    s["meta"].update(ticker="HPG", as_of=as_of, synthetic=False)
    s["financials"]["annual"] = [{"period": "2025", "published_at": "2026-03-31", "published_at_estimated": True, "source_id": "src_fin_year",
                                  "items": {"revenue": 156116094618482.0, "net_income": 15514931571606.0, "total_assets": 257899200817547.0,
                                            "total_equity": 131220010876575.0, "interest_expense": 3114855868974.0, "capex": 25748320476719.0}}]
    s["financials"]["quarterly"] = []
    return s


def test_crosscheck_ok_fill_and_sign_normalisation():
    s = _snap()
    st = v.apply(s, ON, v.Vnf(_loader()))
    it = s["financials"]["annual"][0]["items"]
    assert any(x == "vnf_crosscheck_ok:2025" for x in s["meta"]["flags"]) and st["mismatch"] == 0
    assert it["receivables"] == 15042323117690.0 and it["trade_payables"] == 21183376049432.0 and it["ebitda"] == 28898303373941.0
    assert it["dividends_paid"] == 36538787548.0 and it["capex"] == 25748320476719.0     # chi phí/dòng chi lấy trị tuyệt đối
    assert any(x.startswith("vnf_filled:") and "receivables" in x for x in s["meta"]["flags"])
    assert any(x["id"] == "src_vnf" for x in s["sources"]) and validate(s, "snapshot") == []


def test_mismatch_is_flagged_and_existing_value_kept():
    s = _snap()
    st = v.apply(s, ON, v.Vnf(_loader(scale=1.10)))                                       # vnf lệch 10%
    assert st["mismatch"] >= 3 and any(x.startswith("vnf_mismatch:revenue:2025") for x in s["meta"]["flags"])
    assert s["financials"]["annual"][0]["items"]["revenue"] == 156116094618482.0           # không ghi đè số vnstock
    assert not any(x.startswith("vnf_crosscheck_ok") for x in s["meta"]["flags"])


def test_history_extension_respects_as_of_and_limit():
    s = _snap("2026-10-08")
    years = tuple(range(2009, 2027))                                                       # có cả 2026 (chưa công bố ở as_of)
    st = v.apply(s, {**ON, "vnf_history_years": 10}, v.Vnf(_loader(years=years)))
    got = [r["period"] for r in s["financials"]["annual"]]
    assert got[0] == "2025" and got == sorted(got, reverse=True)
    assert "2026" not in got                                                               # publish ước lượng 2027-03 > as_of
    assert min(got) == "2016" and st["added_years"] == 9                                   # 2025 + 9 năm cũ = 10 năm
    assert all(r["published_at_estimated"] for r in s["financials"]["annual"])
    s2 = _snap("2026-02-01")                                                               # as_of sớm: năm 2025 chưa công bố
    v.apply(s2, ON, v.Vnf(_loader(years=(2024, 2025))))
    assert "2025" in [r["period"] for r in s2["financials"]["annual"]]                    # đã có sẵn trong snapshot (vnstock) thì giữ nguyên
    assert [r for r in s2["financials"]["annual"] if r["source_id"] == "src_vnf"][0]["period"] == "2024"


def test_unavailable_and_not_found_and_disabled():
    s = _snap()
    def boom(**k): raise ImportError("no module vnfinancialdata")
    v.apply(s, ON, v.Vnf(boom))
    assert any(x.startswith("vnf_unavailable") for x in s["meta"]["flags"]) and len(s["financials"]["annual"]) == 1
    s = _snap(); v.apply(s, ON, v.Vnf(_loader(ticker="ZZZ")))
    assert "vnf_ticker_not_found" in s["meta"]["flags"]
    s = _snap(); assert v.apply(s, {}, v.Vnf(boom)) == {"mismatch": 0, "filled": 0, "added_years": 0}
    assert not any(x.startswith("vnf_") for x in s["meta"]["flags"])


def test_eps_only_crosschecked_for_latest_year():
    s = _snap()
    s["financials"]["annual"].append({"period": "2024", "published_at": "2025-03-31", "published_at_estimated": True, "source_id": "src_fin_year",
                                      "items": {"eps": 1505.0, "revenue": 1.0}})
    v.apply(s, ON, v.Vnf(_loader(years=(2024, 2025))))                  # vnf EPS 2024 = 1973 (khác) nhưng là năm cũ
    assert not any(x.startswith("vnf_mismatch:eps") for x in s["meta"]["flags"])
    s = _snap(); s["financials"]["annual"][0]["items"]["eps"] = 1500.0      # năm mới nhất lệch EPS thì vẫn báo
    v.apply(s, ON, v.Vnf(_loader()))
    assert "vnf_mismatch:eps:2025" in s["meta"]["flags"]
