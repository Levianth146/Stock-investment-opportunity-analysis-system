import json
from copy import deepcopy
from pathlib import Path

from stockai.contracts.schemas import validate
from stockai.m1_data import fetch as f
from stockai.m1_data import universe as u

FIX = Path(__file__).resolve().parents[1] / "fixtures" / "snapshot_DEMO.json"


def _snap(ticker, sector, ni=9e9, eq=80e9, shares=5e9, px=20000.0):
    s = json.loads(FIX.read_text(encoding="utf-8"))
    s["meta"]["ticker"], s["meta"]["synthetic"] = ticker, False
    s["company"].update(sector=sector, shares_outstanding=shares)
    s["prices"]["rows"][-1]["close"] = px
    s["financials"]["annual"][0]["items"].update(net_income=ni, total_equity=eq)
    s["financials"]["annual"][0]["items"].pop("net_income_parent", None)
    s["peers"] = []
    return s


def test_fill_peers_same_sector_point_in_time_math():
    snaps = {"AAA": _snap("AAA", "Ngân hàng"), "BBB": _snap("BBB", "Ngân hàng", ni=10e9, eq=50e9, shares=1e9, px=30000.0),
             "CCC": _snap("CCC", "Thép")}
    u.fill_peers(snaps)
    p = {x["ticker"]: x for x in snaps["AAA"]["peers"]}
    assert set(p) == {"BBB"}                                           # chỉ cùng ngành, không có chính nó
    assert abs(p["BBB"]["pe"] - 30000 * 1e9 / 10e9) < 1e-6             # 3000
    assert abs(p["BBB"]["pb"] - 30000 * 1e9 / 50e9) < 1e-6             # 600
    assert abs(p["BBB"]["roe"] - 0.2) < 1e-9
    # ngành đứng một mình (phi ngân hàng) -> peers khác ngành, gắn cờ và trạng thái partial
    assert {x["ticker"] for x in snaps["CCC"]["peers"]} == {"AAA", "BBB"}
    assert "peers_cross_sector_vn30_nonbank_fallback" in snaps["CCC"]["meta"]["flags"]
    assert snaps["CCC"]["meta"]["data_status"]["peers"] == "partial"
    assert all(validate(s, "snapshot") == [] for s in snaps.values())


def test_fetch_all_survives_errors_and_resumes(tmp_path, monkeypatch):
    calls = []

    def fake_build(t, as_of, cfg):
        calls.append(t)
        assert cfg["skip_peer_fetch"] is True
        if t == "BAD":
            raise RuntimeError("nguồn lỗi")
        return _snap(t, "Thép")
    monkeypatch.setattr(f, "build_snapshot", fake_build)
    res = u.fetch_all(["AAA", "BAD", "CCC"], "2026-10-09", {}, out_dir=str(tmp_path), log=lambda *_: None)
    assert res["BAD"]["status"] == "error" and res["AAA"]["status"] == "ok"
    assert (tmp_path / "AAA_2026-10-09.json").exists() and not (tmp_path / "BAD_2026-10-09.json").exists()
    calls.clear()
    res2 = u.fetch_all(["AAA", "BAD", "CCC"], "2026-10-09", {}, out_dir=str(tmp_path), log=lambda *_: None)
    assert calls == ["BAD"]                                           # chạy lại chỉ làm mã chưa xong
    assert res2["AAA"]["status"].startswith("skipped")
    saved = json.loads((tmp_path / "AAA_2026-10-09.json").read_text(encoding="utf-8"))
    assert saved["peers"] and saved["peers"][0]["ticker"] == "CCC"
