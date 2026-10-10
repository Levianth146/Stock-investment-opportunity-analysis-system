"""Universe rộng: danh sách theo sàn, cổng chất lượng, peers có trần, chạy theo lô/dùng lại snapshot."""
import json
from pathlib import Path

import pandas as pd

from stockai.contracts.schemas import validate
from stockai.m1_data import fetch as f
from stockai.m1_data import quality as q
from stockai.m1_data import universe as u

FIX = Path(__file__).resolve().parents[1] / "fixtures" / "snapshot_DEMO.json"


def _snap(ticker, sector="Thép", rows=800, annual=5, vol=1e6, px=20000.0, news=12, mcap_shares=5e9):
    s = json.loads(FIX.read_text(encoding="utf-8"))
    s["meta"]["ticker"], s["meta"]["synthetic"] = ticker, False
    s["company"].update(sector=sector, shares_outstanding=mcap_shares)
    base = s["prices"]["rows"][-1]
    s["prices"]["rows"] = [{**base, "close": px, "volume": vol} for _ in range(rows)]
    ann = s["financials"]["annual"]
    s["financials"]["annual"] = [json.loads(json.dumps(ann[0])) for _ in range(annual)]
    s["news"] = (s["news"] * 20)[:news] if news else []
    s["peers"] = []
    return s


def test_quality_tiers():
    assert q.assess(_snap("A"))["tier"] == "full"
    assert q.assess(_snap("A", rows=300))["tier"] == "insufficient"
    assert q.assess(_snap("A", annual=2))["tier"] == "insufficient"
    r = q.assess(_snap("A", vol=100))                                   # 20000*100 = 2 triệu/ngày << 1 tỷ
    assert r["tier"] == "insufficient" and "illiquid" in r["reasons"]
    r = q.assess(_snap("A", vol=1e5))                                   # 2 tỷ/ngày: giao dịch được nhưng thấp
    assert r["tier"] == "limited" and "low_liquidity" in r["reasons"]
    assert q.assess(_snap("A", annual=4))["tier"] == "limited"
    assert q.assess(_snap("A", news=0))["tier"] == "limited"


def test_quality_apply_is_idempotent_and_schema_valid():
    s = _snap("A", news=0)
    q.apply(s); q.apply(s)
    tiers = [x for x in s["meta"]["flags"] if x.startswith("quality_tier_")]
    assert tiers == ["quality_tier_limited"] and q.tier_of(s) == "limited"
    assert validate(s, "snapshot") == []


def test_peers_capped_to_closest_market_cap():
    snaps = {"AAA": _snap("AAA", mcap_shares=5e9)}
    for i, sh in enumerate([4e9, 5.5e9, 1e8, 9e10]):
        snaps[f"B{i}"] = _snap(f"B{i}", mcap_shares=sh)
    u.fill_peers(snaps, max_peers=2)
    assert {x["ticker"] for x in snaps["AAA"]["peers"]} == {"B0", "B1"}   # 2 mã vốn hóa gần nhất
    u.fill_peers(snaps)                                                    # không trần: giữ hành vi cũ (tất cả cùng ngành)
    assert len(snaps["AAA"]["peers"]) == 4


class _FakeListing:
    def __init__(self, source=None): pass
    def symbols_by_exchange(self):
        return pd.DataFrame({"symbol": ["HPG", "VNM", "E1VFVN30", "CHPG2501", "AAV", "SHB"],
                             "exchange": ["HSX", "HSX", "HSX", "HSX", "HNX", "UPCOM"],
                             "type": ["STOCK", "STOCK", "ETF", "CW", "STOCK", "STOCK"]})
    def symbols_by_group(self, g):
        return pd.Series(["HPG", "VNM"]) if g == "VN100" else pd.Series([], dtype=object)


def test_universe_by_exchange_and_group(tmp_path, monkeypatch):
    import sys, types
    monkeypatch.setitem(sys.modules, "vnstock", types.SimpleNamespace(Listing=_FakeListing))
    monkeypatch.setattr(u, "UNIVERSE_FILE", str(tmp_path / "universe.yaml"))
    assert u.load_universe({}, "HOSE") == ["HPG", "VNM"]                  # bỏ ETF/CW, đổi HSX=HOSE
    assert u.load_universe({}, "HNX") == ["AAV"]
    assert u.load_universe({}, "ALL") == ["AAV", "HPG", "SHB", "VNM"]
    assert u.load_universe({}, "VN100") == ["HPG", "VNM"]
    assert (tmp_path / "universe_hose.yaml").exists() and not (tmp_path / "universe.yaml").exists()


def test_tickers_file(tmp_path):
    p = tmp_path / "l.txt"
    p.write_text("# ghi chú\nhpg, vnm\nFPT;HPG\n", encoding="utf-8")
    assert u.read_tickers_file(str(p)) == ["HPG", "VNM", "FPT"]


def test_fetch_all_reuse_resume_and_shard_peers(tmp_path, monkeypatch):
    main, ext = tmp_path / "main", tmp_path / "ext"
    f.save_snapshot(_snap("AAA"), str(main))                               # mã đã có ở thư mục khác (VN30)
    for p in main.glob("AAA_*.json"):
        p.rename(main / "AAA_2026-10-09.json")
    s_old = json.loads((main / "AAA_2026-10-09.json").read_text(encoding="utf-8"))
    s_old["meta"]["as_of"] = "2026-10-09"; s_old["meta"]["data_status"]["news"] = "partial"
    (main / "AAA_2026-10-09.json").write_text(json.dumps(s_old), encoding="utf-8")
    calls = []

    def fake_build(t, as_of, cfg):
        calls.append(t)
        s = _snap(t); s["meta"]["as_of"] = as_of; s["meta"]["data_status"].update(news="partial")
        return s
    monkeypatch.setattr(f, "build_snapshot", fake_build)
    res = u.fetch_all(["AAA", "BBB", "CCC"], "2026-10-09", {}, out_dir=str(ext), log=lambda *_: None,
                      reuse_dirs=[str(main)], resume=True, peers=False)
    assert calls == ["BBB", "CCC"] and res["AAA"]["status"].startswith("reused")   # AAA dùng lại dù tin partial
    assert all(r["quality"] == "full" for r in res.values())
    assert not json.loads((ext / "BBB_2026-10-09.json").read_text(encoding="utf-8"))["peers"]   # peers=False
    calls.clear()
    u.fetch_all(["AAA", "BBB", "CCC"], "2026-10-09", {}, out_dir=str(ext), log=lambda *_: None, resume=True, peers=False)
    assert calls == []                                                     # resume: không cào lại mã tin partial
    summ = u.fill_peers_dir(["AAA", "BBB", "CCC", "ZZZ"], "2026-10-09", str(ext), {"universe_max_peers": 1}, log=lambda *_: None)
    assert set(summ) == {"AAA", "BBB", "CCC"}                              # ZZZ chưa có file: bỏ qua
    assert all(len(json.loads((ext / f"{t}_2026-10-09.json").read_text(encoding="utf-8"))["peers"]) == 1 for t in summ)
