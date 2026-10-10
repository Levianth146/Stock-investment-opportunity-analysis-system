"""M1 - thu thập dữ liệu (N2). Chỉ sửa trong m1_data/.

Luồng: sources.py (gọi vnstock, cache) -> normalize.py (đưa về schema) -> fetch.py (ghép snapshot).
Quy tắc: mọi dữ liệu có ngày > as_of bị loại; 1 khối lỗi chỉ đánh dấu thiếu + cờ, không làm sập snapshot.
Cờ phát sinh khi chuẩn hóa được ghi vào snapshot["meta"]["flags"] (qua cfg["_flags"])."""
from __future__ import annotations

import json
import re
from datetime import datetime, timedelta
from pathlib import Path

from stockai.contracts.helpers import check_no_lookahead
from stockai.contracts.schemas import assert_valid
from stockai.m1_data import bank_kpis, icb_sector, news_extra, news_portals, vnf_source
from stockai.m1_data import normalize as nz
from stockai.m1_data import sources as src

PROVIDER_URL = {"VCI": "https://trading.vietcap.com.vn", "TCBS": "https://tcinvest.tcbs.com.vn"}


def _window_start(as_of: str, years: int) -> str:
    return (datetime.strptime(as_of, "%Y-%m-%d") - timedelta(days=365 * years)).strftime("%Y-%m-%d")


def _flag(cfg: dict, msg: str) -> None:
    cfg.setdefault("_flags", []).append(msg)


def _source(sid: str, provider: str, what: str) -> dict:
    return {"id": sid, "name": f"vnstock ({provider}) - {what}", "url": PROVIDER_URL.get(provider, "https://github.com/thinh-vu/vnstock"),
            "fetched_at": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"), "note": "thư viện vnstock; xem docs/CONTRACTS.md"}


# ------------------------------------------------------------------ từng khối
def fetch_prices(ticker: str, start: str, as_of: str, cfg: dict) -> tuple[dict, dict]:
    df, provider = src.get_history(ticker, start, as_of, cfg)
    rows, flags = nz.normalize_prices(df, start, as_of, cfg.get("price_multiplier", "auto"))
    for f in flags:
        _flag(cfg, f)
    # vnstock/VCI trả giá đã điều chỉnh; không có cách tự kiểm chứng 100% -> cờ suspect_* ở trên là lưới an toàn
    return {"adjusted": True, "source_id": "src_price", "rows": rows}, _source("src_price", provider, "quote.history (giá điều chỉnh)")


def fetch_index(symbol: str, start: str, as_of: str, cfg: dict) -> tuple[dict, dict]:
    df, provider = src.get_history(symbol, start, as_of, cfg)
    rows = nz.normalize_index(df, start, as_of)
    return {"symbol": symbol, "source_id": "src_index", "rows": rows}, _source("src_index", provider, f"quote.history {symbol}")


def _safe_fin(ticker: str, kind: str, period: str, cfg: dict):
    try:
        return src.get_finance(ticker, kind, period, cfg)
    except Exception as e:  # noqa: BLE001 - thiếu 1 bảng thì dùng các bảng còn lại
        _flag(cfg, f"fin_{kind}_{period}_error: {str(e)[:120]}")
        return None, None


def fetch_financials(ticker: str, as_of: str, cfg: dict, is_bank: bool = False) -> tuple[dict, list[dict]]:
    sources, blocks = [], {}
    for period, annual, keep in (("year", True, 6), ("quarter", False, 8)):
        frames, providers = [], set()
        for kind in ("income", "balance", "cashflow"):      # bảng ratio của vnstock trả dữ liệu lỗi cấu trúc -> bỏ, tự tính từ BCTC
            df, provider = _safe_fin(ticker, kind, period, cfg)
            if df is not None:
                frames.append(df); providers.add(provider)
        sid = "src_fin_year" if annual else "src_fin_quarter"
        periods, cmap, flags = nz.normalize_financials(frames, annual, as_of, sid, is_bank, cfg.get("financial_multiplier", "auto"), keep)
        for f in flags:
            _flag(cfg, f)
        blocks["annual" if annual else "quarterly"] = (periods, cmap)
        if providers:
            sources.append(_source(sid, sorted(providers)[0], f"finance {period} (income/balance/cashflow)"))
    return {"unit": "VND", "annual": blocks["annual"][0], "quarterly": blocks["quarterly"][0],
            "column_map": {"annual": blocks["annual"][1], "quarterly": blocks["quarterly"][1]},
            "published_at_note": "ngày công bố được ước lượng (quý +45 ngày, năm +90 ngày) vì nguồn không cung cấp"}, sources


def _peer_list(ticker: str, cfg: dict) -> list[str]:
    peers = (cfg.get("peers_map") or {}).get(ticker) or src.get_industry_peers(ticker, cfg)
    if not peers:
        _flag(cfg, "peers_list_empty")
    return list(peers)[: int(cfg.get("max_peers", 8))]


def _peer_multiples(p: str, as_of: str, cfg: dict) -> dict:
    """PE/PB/ROE của 1 peer, tự tính từ giá + BCTC năm tại as_of (4 request/peer). Chạy hàng loạt thì dùng universe.fill_peers."""
    start = (datetime.strptime(as_of, "%Y-%m-%d") - timedelta(days=20)).strftime("%Y-%m-%d")
    df, _ = src.get_history(p, start, as_of, cfg)
    rows, _ = nz.normalize_prices(df, start, as_of, cfg.get("price_multiplier", "auto"))
    ov, _ = src.get_overview(p, cfg)
    comp, _ = nz.normalize_company(ov, p, cfg.get("banks", []))
    inc, _ = src.get_finance(p, "income", "year", cfg)
    bal, _ = src.get_finance(p, "balance", "year", cfg)
    per, _, _ = nz.normalize_financials([inc, bal], True, as_of, "x", comp["is_bank"], cfg.get("financial_multiplier", "auto"), keep=1)
    return nz.multiples(rows, per, comp["shares_outstanding"])


def fetch_company(ticker: str, as_of: str, cfg: dict) -> tuple[dict, list[dict], dict]:
    """Trả (company, peers, source). Gọi TRƯỚC fetch_financials vì is_bank quyết định bộ chỉ tiêu."""
    try:
        df, provider = src.get_overview(ticker, cfg)
        ex_map = src.get_exchange_map(cfg) if "exchange" not in " ".join(nz.norm(c) for c in df.columns) else {}
        company, flags = nz.normalize_company(df, ticker, cfg.get("banks", []), ex_map)
        for f in flags:
            _flag(cfg, f)
    except Exception as e:  # noqa: BLE001
        provider = cfg.get("vnstock_sources", ["VCI"])[0]
        _flag(cfg, f"company_overview_error: {str(e)[:120]}")
        company = {"name": ticker, "exchange": "", "sector": "", "industry": None,
                   "is_bank": ticker in cfg.get("banks", []), "shares_outstanding": None}
    # ICB cấp 2 (listing_icb.csv): điền sector khi thiếu; giữ vnstock nếu đã có
    if cfg.get("icb_sector_enabled", True):
        for f in icb_sector.apply_to_company(company, ticker, map_path=cfg.get("icb_sector_map")):
            _flag(cfg, f)
    company["source_id"] = "src_company"
    peers = []
    for p in ([] if cfg.get("skip_peer_fetch") else _peer_list(ticker, cfg)):   # chạy hàng loạt: peers tính sau từ chính universe
        try:
            m = _peer_multiples(p, as_of, cfg)
            if m:
                peers.append({"ticker": p, **{k: (round(v, 4) if v is not None else None) for k, v in m.items()}, "source_id": "src_company"})
            else:
                _flag(cfg, f"peer_{p}_no_data")
        except Exception as e:  # noqa: BLE001
            _flag(cfg, f"peer_{p}_error: {str(e)[:80]}")
    if peers:
        _flag(cfg, "peers_multiples_self_computed_from_latest_annual")
    return company, peers, _source("src_company", provider, "company.overview + tự tính PE/PB/ROE peers")


def fetch_news(ticker: str, start: str, as_of: str, cfg: dict) -> tuple[list[dict], dict]:
    max_items = int(cfg.get("max_news", 50))
    months = int(cfg.get("news_months", 12))
    nstart = max(start, (datetime.strptime(as_of, "%Y-%m-%d") - timedelta(days=30 * months)).strftime("%Y-%m-%d"))
    items: list[dict] = []
    provider = cfg.get("vnstock_sources", ["VCI"])[0]
    try:
        df, provider = src.get_news(ticker, cfg)
        items, flags = nz.normalize_news(df, nstart, as_of, f"vnstock/{provider}", max_items)
        for f in flags:
            _flag(cfg, f)
    except Exception as e:  # noqa: BLE001
        _flag(cfg, f"news_vnstock_error: {str(e)[:120]}")
    extra: list[dict] = []
    if cfg.get("news_google"):                                           # tin bổ sung có URL, phủ cả cửa sổ 12 tháng
        rows, fl = news_extra.google_news(ticker, nstart, as_of, cfg)
        extra += rows
        for f in fl:
            _flag(cfg, f)
    if cfg.get("news_rss"):
        rows, fl = news_extra.feed_news(ticker, cfg["news_rss"])
        extra += rows
        for f in fl:
            _flag(cfg, f)
    if extra:
        import pandas as pd
        more, _ = nz.normalize_news(pd.DataFrame(extra), nstart, as_of, "Google News/RSS", 10 ** 6)
        outlet = {nz.norm(r["title"]): r.get("source") for r in extra}
        for m in more:                                                   # ghi tên báo thật để trích dẫn
            o = outlet.get(nz.norm(m["title"]))
            m["source"] = f"{o} (qua Google News)" if o and o != "rss" else m["source"]
        seen = {nz.norm(i["title"]) for i in items}
        items = [*items, *[m for m in more if nz.norm(m["title"]) not in seen]]
        items.sort(key=lambda x: x["published_at"], reverse=True)
        cfg["_flags"][:] = [f for f in cfg["_flags"] if f != "news_url_missing"]
        _flag(cfg, "news_urls_partly_google_redirect")

    if news_portals.portals_enabled(cfg):
        portal_fetch = cfg.get("_news_portal_fetch") or news_extra.http_get
        portal_articles, pflags = news_portals.fetch_portals(
            ticker, cfg.get("_company_name") or "", nstart, as_of, cfg, fetch=portal_fetch,
        )
        # FR-007: ok/empty sau lọc ngày/trùng, trước cắt max_news (chỉ slug active)
        pre_cap = news_portals.merge_pre_cap_for_flags(items, portal_articles)
        pflags = news_portals.refine_portal_flags_after_dedupe(
            pflags, portal_articles, pre_cap,
            active_slugs=news_portals.active_portal_slugs(cfg),
        )
        for f in pflags:
            _flag(cfg, f)
        items = news_portals.merge_news(items, portal_articles, max_items)
        final_urls = {news_portals.normalize_url(i.get("url")) for i in items}
        final_titles = {news_portals.normalize_title(i.get("title")) for i in items}
        contrib: set[str] = set()
        for a in portal_articles:
            nu = news_portals.normalize_url(a.get("url"))
            nt = news_portals.normalize_title(a.get("title"))
            if (nu and nu in final_urls) or (nt and nt in final_titles):
                contrib.add(a["portal_slug"])
        for slug in sorted(contrib):
            meta = news_portals.PORTAL_META[slug]
            cfg.setdefault("_portal_sources", []).append({
                "id": meta["source_id"],
                "name": meta["source"],
                "url": meta["home"],
                "fetched_at": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
                "note": "cổng tin M1 (HTML); xem specs/003-news-portals/",
            })
        for it in items:
            it.pop("_source_id", None)
            it.pop("_portal_slug", None)
            it.pop("portal_slug", None)
    else:
        items = items[:max_items]

    if items:
        days = (datetime.strptime(as_of, "%Y-%m-%d") - datetime.strptime(items[-1]["published_at"][:10], "%Y-%m-%d")).days
        if days < 30 * months * 0.5:
            _flag(cfg, f"news_coverage_only_{days}d_of_{30 * months}d")     # nguồn chỉ trả ~50 tin gần nhất
        if all(i["url"] == "n/a" for i in items):
            _flag(cfg, "news_has_no_article_url")                          # chỉ trích dẫn được theo tiêu đề + ngày + id
    return items, _source("src_news", provider, "company.news / RSS")


# ------------------------------------------------------------------ ghép snapshot
def build_snapshot(ticker: str, as_of: str, cfg: dict) -> dict:
    cfg = {**cfg, "_flags": []}
    start = _window_start(as_of, cfg.get("window_years", 5))
    status = {k: "missing" for k in ("prices", "index", "financials", "company", "peers", "news")}
    snap = {
        "meta": {"schema_version": "1.0", "ticker": ticker, "as_of": as_of, "window_start": start, "synthetic": False,
                 "fetched_at": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"), "flags": cfg["_flags"], "data_status": status},
        "company": {"name": ticker, "exchange": "", "sector": "", "is_bank": ticker in cfg.get("banks", [])},
        "prices": {"adjusted": True, "source_id": "", "rows": []},
        "index": {"symbol": cfg.get("index_symbol", "VNINDEX"), "source_id": "", "rows": []},
        "financials": {"unit": "VND", "annual": [], "quarterly": []},
        "peers": [], "news": [], "sources": [],
    }

    def step(name: str, fn):
        try:
            return fn()
        except Exception as e:  # noqa: BLE001 - 1 khối lỗi không được làm sập snapshot
            cfg["_flags"].append(f"m1_{name}_error: {str(e)[:160]}")
            return None

    r = step("prices", lambda: fetch_prices(ticker, start, as_of, cfg))
    if r:
        snap["prices"], s = r; snap["sources"].append(s)
        n = len(snap["prices"]["rows"])
        status["prices"] = "ok" if n >= 250 else ("partial" if n else "missing")
    r = step("index", lambda: fetch_index(snap["index"]["symbol"], start, as_of, cfg))
    if r:
        snap["index"], s = r; snap["sources"].append(s)
        n = len(snap["index"]["rows"])
        status["index"] = "ok" if n >= 250 else ("partial" if n else "missing")
    r = step("company", lambda: fetch_company(ticker, as_of, cfg))
    if r:
        snap["company"], snap["peers"], s = r; snap["sources"].append(s)
        status["company"] = "ok" if snap["company"]["sector"] else "partial"
        status["peers"] = "ok" if len(snap["peers"]) >= 3 else ("partial" if snap["peers"] else "missing")
    r = step("financials", lambda: fetch_financials(ticker, as_of, cfg, snap["company"]["is_bank"]))
    if r:
        snap["financials"], ss = r; snap["sources"].extend(ss)
        a = len(snap["financials"]["annual"])
        status["financials"] = "ok" if a >= 5 else ("partial" if a else "missing")
    if snap["financials"]["annual"]:
        step("vnf", lambda: vnf_source.apply(snap, cfg))               # đối chiếu/bổ sung/kéo dài lịch sử từ vnfinancialdata (tùy chọn)
        # VNF (và mọi bước trước tin) phải giữ cùng list với cfg["_flags"]; gắn lại phòng gán nhầm list mới
        cfg["_flags"] = snap["meta"]["flags"]
    if snap["company"]["is_bank"] and snap["financials"]["annual"]:
        bank_kpis.apply(snap, cfg.get("bank_kpis_file", "config/bank_kpis.csv"))
        cfg["_flags"] = snap["meta"]["flags"]
    r = step("news", lambda: fetch_news(ticker, start, as_of, cfg)) if cfg.get("news_enabled", True) else None
    if not cfg.get("news_enabled", True):
        cfg["_flags"].append("news_skipped_by_config")
    if r:
        snap["news"], s = r; snap["sources"].append(s)
        for ps in cfg.pop("_portal_sources", []) or []:
            snap["sources"].append(ps)
        status["news"] = "ok" if len(snap["news"]) >= 10 else ("partial" if snap["news"] else "missing")

    sh, eps_ni = snap["company"].get("shares_outstanding"), None
    if sh is None and snap["financials"]["annual"]:                     # dự phòng: số cổ phiếu ≈ LNST / EPS
        it = snap["financials"]["annual"][0]["items"]
        if it.get("net_income") and it.get("eps"):
            snap["company"]["shares_outstanding"] = it["net_income"] / it["eps"]
            cfg["_flags"].append("shares_derived_from_net_income_over_eps")
    assert_valid(snap, "snapshot")
    bad = check_no_lookahead(snap)
    if bad:
        raise ValueError("Snapshot vi phạm as_of (look-ahead): " + "; ".join(bad[:5]))
    return snap


def save_snapshot(snap: dict, out_dir: str = "data/snapshots") -> Path:
    p = Path(out_dir) / f"{snap['meta']['ticker']}_{snap['meta']['as_of']}.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    snap["meta"]["flags"] = list(dict.fromkeys(snap["meta"]["flags"]))   # bỏ cờ trùng
    p.write_text(json.dumps(snap, ensure_ascii=False, indent=1), encoding="utf-8")
    st = snap["meta"]["data_status"]
    print("data_status:", ", ".join(f"{k}={v}" for k, v in st.items()))
    if any(v != "ok" for v in st.values()):
        print(f"  !! Snapshot CHƯA ĐỦ DỮ LIỆU - đừng dùng cho báo cáo thật. {len(snap['meta']['flags'])} cờ, xem meta.flags:")
        for fl in snap["meta"]["flags"][:12]:
            print("    -", fl)
    return p


def load_snapshot(path: str) -> dict:
    snap = json.loads(Path(path).read_text(encoding="utf-8"))
    assert_valid(snap, "snapshot")
    return snap
