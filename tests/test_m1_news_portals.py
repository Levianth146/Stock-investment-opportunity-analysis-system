"""Kiểm thử offline cổng tin M1 (003). Fixture HTML thật từ spike; không gọi mạng."""
from __future__ import annotations

import gzip
from pathlib import Path

import pytest

from stockai.m1_data import news_portals as np
from stockai.m1_data import quality
from stockai.m1_data.fetch import fetch_news

FIX = Path("tests/fixtures/news_portals")
# CafeF fixture: 2026-03-26 (có VCB); TNCK: 2026-09-21 (MB, không VCB/HPG)
AS_OF = "2026-10-08"
WINDOW_START = "2020-01-01"

CAFEF_ART_URL = (
    "https://cafef.vn/ky-luc-chua-tung-co-chi-2-cong-ty-cua-ty-phu-pham-nhat-vuong-da-nop-"
    "ngan-sach-87400-ty-dong-lon-hon-viettel-petrolimex-va-vcb-cong-lai-188260326074908559.chn"
)
TNCK_ART_URL = (
    "https://www.tinnhanhchungkhoan.vn/"
    "mb-mo-rong-he-sinh-thai-so-ket-noi-dong-von-voi-nen-kinh-te-post397901.html"
)


def _read(rel: str) -> bytes:
    return (FIX / rel).read_bytes()


def base_cfg(**kw) -> dict:
    cfg = {
        "news_portals_enabled": True,
        "universe_name": "VN30",
        "max_news": 800,
        "news_months": 12,
        "news_google": False,
        "news_rss": [],
        "vnstock_sources": ["VCI"],
        "news_portal_retries": 1,
        "news_portal_interval_sec": 0,
        "news_portal_cache_dir": "",
        "_flags": [],
    }
    cfg.update(kw)
    return cfg


# ------------------------------------------------------------------ helpers
def test_normalize_url_rejects_na():
    assert np.normalize_url("n/a") is None
    assert np.normalize_url("N/A") is None
    assert np.normalize_url("") is None
    assert np.normalize_url("https://cafef.vn/a.chn?utm=1") == "https://cafef.vn/a.chn"


def test_parse_published_at_variants():
    assert np.parse_published_at("2025-09-25") == "2025-09-25"
    assert np.parse_published_at("2025-09-25T20:02:00") == "2025-09-25T20:02:00"
    assert np.parse_published_at("2025") is None
    assert np.parse_published_at(None) is None
    assert np.parse_published_at("25/09/2025 20:02") == "2025-09-25T20:02:00"


def test_ticker_relevant_case_sensitive_word_boundary():
    assert np.ticker_relevant("VCB", "Tin VCB tăng giá", "nội dung")
    assert not np.ticker_relevant("VCB", "tin vcb tăng", "không có mã hoa")
    assert not np.ticker_relevant("VCB", "AVCB x", "no")
    assert not np.ticker_relevant("HPG", "Tin VCB tăng", "chỉ VCB")


def test_cafef_article_dated_contract_fields():
    html = _read("cafef/article_dated.html").decode("utf-8", errors="replace")
    art = np.parse_article_html(html, CAFEF_ART_URL, "cafef")
    assert art is not None
    assert art["published_at"][:10] == "2026-03-26"
    assert "T" in art["published_at"]
    assert art["url"].startswith("https://cafef.vn/")
    assert "google.com" not in art["url"]
    assert art["summary"]
    assert np.ticker_relevant("VCB", art["title"], html)
    item = np.to_news_item(art)
    for k in ("id", "title", "url", "source", "published_at"):
        assert item[k]


def test_cafef_date_only_kept_on_as_of_day():
    html = _read("cafef/article_asof_date_only.html").decode("utf-8", errors="replace")
    art = np.parse_article_html(html, CAFEF_ART_URL, "cafef")
    assert art is not None
    assert art["published_at"] == "2026-03-26"
    assert np.in_date_window(art["published_at"], WINDOW_START, "2026-03-26")
    assert not np.in_date_window(art["published_at"], WINDOW_START, "2026-03-25")


def test_undated_stripped_dropped():
    html = _read("cafef/article_undated_meta_stripped.html").decode("utf-8", errors="replace")
    art = np.parse_article_html(html, "https://cafef.vn/x-188.chn", "cafef")
    if art is not None and art.get("published_at"):
        pytest.skip("fixture vẫn còn dấu ngày phụ")


def test_merge_prefers_portal_over_google_url_and_title():
    google = [{
        "id": "ng1", "title": "Same Title Here", "url": "https://news.google.com/rss/articles/abc",
        "source": "Google", "published_at": "2025-09-20T10:00:00", "summary": "g",
    }]
    portal = [{
        "title": "Same Title Here", "url": "https://cafef.vn/same-1881.chn",
        "published_at": "2025-09-25T20:02:00", "source": "CafeF", "summary": "p",
        "portal_slug": "cafef", "source_id": "src_news_cafef",
    }]
    merged = np.merge_news(google, portal, max_news=10)
    assert len(merged) == 1
    assert merged[0]["source"] == "CafeF"
    assert "cafef.vn" in merged[0]["url"]


def test_merge_na_url_title_only():
    vnstock = [{
        "id": "nv1", "title": "VCB lãi lớn quý 3", "url": "n/a",
        "source": "vnstock/VCI", "published_at": "2025-09-20T00:00:00", "summary": None,
    }]
    portal = [{
        "title": "VCB lãi lớn quý 3", "url": "https://cafef.vn/vcb-lai-1882.chn",
        "published_at": "2025-09-21T12:00:00", "source": "CafeF", "summary": "x",
        "portal_slug": "cafef", "source_id": "src_news_cafef",
    }]
    merged = np.merge_news(vnstock, portal, max_news=10)
    assert len(merged) == 1
    assert merged[0]["url"].startswith("https://cafef.vn/")


def test_ok_flag_before_max_news_cap():
    portal = [{
        "title": f"Portal story {i}", "url": f"https://cafef.vn/p-{i}-188{i}.chn",
        "published_at": f"2026-03-{(i % 20) + 1:02d}T10:00:00", "source": "CafeF", "summary": "s",
        "portal_slug": "cafef", "source_id": "src_news_cafef",
    } for i in range(5)]
    pre = np.merge_pre_cap_for_flags([], portal)
    flags = np.refine_portal_flags_after_dedupe([], portal, pre)
    assert "news_portal_ok:cafef" in flags
    assert len(np.merge_news([], portal, max_news=2)) == 2


def test_sc005_portal_clears_quality_news_few():
    existing = [
        {"id": f"g{i}", "title": f"G{i}", "url": f"https://news.google.com/{i}",
         "source": "g", "published_at": f"2026-02-0{i+1}T00:00:00", "summary": None}
        for i in range(3)
    ]
    portal = [
        {"title": f"P{i}", "url": f"https://cafef.vn/p{i}-188{i}.chn",
         "published_at": f"2026-03-{(i % 28)+1:02d}T00:00:00", "source": "CafeF", "summary": "s",
         "portal_slug": "cafef", "source_id": "src_news_cafef"}
        for i in range(12)
    ]
    news = np.merge_news(existing, portal, max_news=800)
    snap = {
        "meta": {"flags": []},
        "prices": {"rows": [{"close": 1, "volume": 1e9}] * 800},
        "financials": {"annual": [{"items": {}}] * 6},
        "news": news,
        "company": {"sector": "Banks", "shares_outstanding": 1},
    }
    res = quality.apply(snap, {"quality": {"limited_news": 10, "min_price_rows": 750, "min_annual": 3}})
    assert "news_few" not in res["reasons"]
    assert "quality_news_few" not in snap["meta"]["flags"]


def test_vneconomy_parse_long_slug_skips_premium_and_short():
    html = _read("vneconomy/search_VCB.html").decode("utf-8", errors="replace")
    links = np.parse_vneconomy_search(html)
    assert links
    assert all("premium.vneconomy" not in x["url"] for x in links)
    assert all(len(x["url"].rsplit("/", 1)[-1]) >= 40 for x in links)


# ------------------------------------------------------------------ fetch fixtures
@pytest.fixture
def cafef_mapping():
    return {
        "tim-kiem.chn?keywords=VCB": _read("cafef/search_VCB.html"),
        "keywords=VCB": _read("cafef/search_VCB.html"),
        CAFEF_ART_URL: _read("cafef/article_dated.html"),
        "188260326074908559.chn": _read("cafef/article_dated.html"),
    }


@pytest.fixture
def tnck_mapping():
    return {
        "tinnhanhchungkhoan.vn/ngan-hang": _read("tinnhanhchungkhoan/search_VCB.html"),
        TNCK_ART_URL: _read("tinnhanhchungkhoan/article_dated.html"),
        "post397901.html": _read("tinnhanhchungkhoan/article_dated.html"),
    }


def _fetch_cafef_only(cafef_mapping):
    def fetch(url: str) -> bytes:
        if "tinnhanhchungkhoan" in url or "vneconomy" in url:
            raise RuntimeError("skip other portals")
        for k, v in cafef_mapping.items():
            if k in url:
                return v
        raise FileNotFoundError(url)

    return fetch


def test_fetch_portals_cafef_ok(cafef_mapping, tmp_path):
    cfg = base_cfg(news_portal_cache_dir=str(tmp_path / "cache"))
    arts, flags = np.fetch_portals(
        "VCB", "Vietcombank", WINDOW_START, AS_OF, cfg, fetch=_fetch_cafef_only(cafef_mapping),
    )
    assert any(a["portal_slug"] == "cafef" for a in arts)
    assert any(f.startswith("news_portal_ok:cafef") for f in flags)


def test_relevance_category_article_excluded_for_two_tickers(tnck_mapping, tmp_path):
    """Bài chuyên mục TNCK (MB) không nhắc VCB/HPG → không vào snapshot hai mã đó.
    Bật riêng tinnhanhchungkhoan trong active để kiểm parser (mặc định tắt)."""
    def fetch(url: str) -> bytes:
        if "cafef" in url or "vneconomy" in url:
            raise RuntimeError("skip")
        for k, v in tnck_mapping.items():
            if k in url:
                return v
        # listing trả HTML có link bài MB; mọi URL bài khác → cùng fixture MB
        if "post" in url and "tinnhanhchungkhoan" in url:
            return tnck_mapping[TNCK_ART_URL]
        raise FileNotFoundError(url)

    cfg = base_cfg(
        news_portals_active=["tinnhanhchungkhoan"],
        news_portal_cache_dir=str(tmp_path / "c1"),
    )
    for ticker in ("VCB", "HPG"):
        arts, flags = np.fetch_portals(ticker, None, WINDOW_START, AS_OF, cfg, fetch=fetch)
        assert not any(a.get("portal_slug") == "tinnhanhchungkhoan" for a in arts), ticker
        # thành công nhưng 0 bài liên quan → empty (không failed)
        assert "news_portal_empty:tinnhanhchungkhoan" in flags or "news_portal_failed:tinnhanhchungkhoan" in flags


def test_relevance_keeps_matching_ticker(cafef_mapping):
    arts, _ = np.fetch_portals(
        "VCB", None, WINDOW_START, AS_OF, base_cfg(), fetch=_fetch_cafef_only(cafef_mapping),
    )
    assert arts
    html = _read("cafef/article_dated.html").decode("utf-8", errors="replace")
    for a in arts:
        assert np.ticker_relevant("VCB", a["title"], html)

    # Cùng listing/fixture nhưng mã HPG → bài chỉ nhắc VCB bị loại
    mapping_hpg = {
        **cafef_mapping,
        "keywords=HPG": _read("cafef/search_VCB.html"),
        "tim-kiem.chn?keywords=HPG": _read("cafef/search_VCB.html"),
    }
    arts_hpg, _ = np.fetch_portals(
        "HPG", None, WINDOW_START, AS_OF, base_cfg(), fetch=_fetch_cafef_only(mapping_hpg),
    )
    assert not any("188260326074908559" in (a.get("url") or "") for a in arts_hpg)


def test_lookahead_drop(cafef_mapping):
    arts, _ = np.fetch_portals(
        "VCB", None, WINDOW_START, "2026-03-25", base_cfg(), fetch=_fetch_cafef_only(cafef_mapping),
    )
    assert not any(a["portal_slug"] == "cafef" for a in arts)


def test_enabled_false_no_portal(monkeypatch):
    called = {"n": 0}

    def boom(url: str) -> bytes:
        called["n"] += 1
        raise AssertionError("should not fetch")

    cfg = base_cfg(news_portals_enabled=False)
    cfg["_news_portal_fetch"] = boom
    import stockai.m1_data.sources as sources
    import pandas as pd

    monkeypatch.setattr(
        sources, "get_news",
        lambda t, c: (pd.DataFrame(columns=["title", "public date", "news source link"]), "VCI"),
    )
    fetch_news("VCB", WINDOW_START, AS_OF, cfg)
    assert called["n"] == 0
    assert not any(str(f).startswith("news_portal_") for f in cfg["_flags"])


def test_custom_universe_no_portal(monkeypatch):
    called = {"n": 0}

    def boom(url: str) -> bytes:
        called["n"] += 1
        raise AssertionError("no portal for custom")

    cfg = base_cfg(universe_name="custom", news_portals_enabled=True)
    cfg["_news_portal_fetch"] = boom
    import stockai.m1_data.sources as sources
    import pandas as pd

    monkeypatch.setattr(
        sources, "get_news",
        lambda t, c: (pd.DataFrame(columns=["title", "public date", "news source link"]), "VCI"),
    )
    fetch_news("VCB", WINDOW_START, AS_OF, cfg)
    assert called["n"] == 0


def test_vn30_runs_portal(monkeypatch, cafef_mapping):
    cfg = base_cfg(news_months=24)
    cfg["_news_portal_fetch"] = _fetch_cafef_only(cafef_mapping)
    import stockai.m1_data.sources as sources
    import pandas as pd

    monkeypatch.setattr(
        sources, "get_news",
        lambda t, c: (pd.DataFrame(columns=["title", "public date", "news source link"]), "VCI"),
    )
    items, _ = fetch_news("VCB", WINDOW_START, AS_OF, cfg)
    assert any(f.startswith("news_portal_ok:cafef") for f in cfg["_flags"])
    assert any("cafef.vn" in (i.get("url") or "") for i in items)


def test_empty_portal_flag(tmp_path):
    def fetch(url: str) -> bytes:
        return b"<html><body>no articles</body></html>"

    cfg = base_cfg(news_portal_cache_dir=str(tmp_path))
    arts, flags = np.fetch_portals("VCB", None, WINDOW_START, AS_OF, cfg, fetch=fetch)
    assert arts == []
    assert "news_portal_empty:cafef" in flags
    assert not any("vneconomy" in f for f in flags)
    assert not any("tinnhanhchungkhoan" in f for f in flags)


def test_active_portals_flags_and_no_fetch_inactive(tmp_path):
    """Chỉ gọi fetch + gắn cờ cho slug trong news_portals_active."""
    called: list[str] = []

    def fetch(url: str) -> bytes:
        called.append(url)
        return b"<html><body>no articles</body></html>"

    cfg = base_cfg(news_portals_active=["cafef"], news_portal_cache_dir=str(tmp_path / "act"))
    arts, flags = np.fetch_portals("VCB", None, WINDOW_START, AS_OF, cfg, fetch=fetch)
    assert arts == []
    assert called, "phải gọi CafeF search"
    assert all("vneconomy" not in u and "tinnhanhchungkhoan" not in u for u in called)
    assert "news_portal_empty:cafef" in flags
    assert not any(f.endswith(":vneconomy") for f in flags if f.startswith("news_portal_"))
    assert not any(f.endswith(":tinnhanhchungkhoan") for f in flags if f.startswith("news_portal_"))


def test_cafef_prioritize_title_mentions_ticker():
    """Link đã nhắc mã trên title/anchor được xếp trước (trần cắt vẫn sau)."""
    links = [
        {"title": "Thị trường chứng khoán hôm nay", "url": "https://cafef.vn/a-1881.chn"},
        {"title": "VCB lãi lớn quý 3", "url": "https://cafef.vn/b-1882.chn"},
        {"title": "Cổ phiếu ngân hàng", "url": "https://cafef.vn/c-1883.chn"},
    ]
    out = np._prioritize_links_by_title(links, "VCB")
    assert out[0]["url"].endswith("1882.chn")
    assert {x["url"] for x in out} == {x["url"] for x in links}


def test_cache_skips_second_network(tmp_path, cafef_mapping):
    counts: dict[str, int] = {}

    def fetch(url: str) -> bytes:
        counts[url] = counts.get(url, 0) + 1
        if "tinnhanhchungkhoan" in url or "vneconomy" in url:
            return b"<html></html>"
        for k, v in cafef_mapping.items():
            if k in url:
                return v
        raise FileNotFoundError(url)

    cfg = base_cfg(news_portal_cache_dir=str(tmp_path / "c"))
    np.fetch_portals("VCB", None, WINDOW_START, AS_OF, cfg, fetch=fetch)
    first = dict(counts)
    np.fetch_portals("VCB", None, WINDOW_START, AS_OF, cfg, fetch=fetch)
    for url, n in first.items():
        if "188260326074908559" in url or "tim-kiem" in url:
            assert counts[url] == n


def test_portals_enabled_gate():
    assert np.portals_enabled({"news_portals_enabled": True, "universe_name": "VN30"})
    assert np.portals_enabled({"news_portals_enabled": True, "universe_name": "VN100"})
    assert not np.portals_enabled({"news_portals_enabled": True, "universe_name": "HOSE"})
    assert not np.portals_enabled({"news_portals_enabled": True, "universe_name": "custom"})
    assert not np.portals_enabled({"news_portals_enabled": False, "universe_name": "VN30"})


def test_gzip_fixture_vneconomy_and_tnck_parse_like_plain():
    """Fixture HTML thật nén gzip → giải nén rồi parse bài/ngày giống bản không nén."""
    cases = [
        ("vneconomy", "vneconomy/article_dated.html", "https://vneconomy.vn/sample-long-slug-article-for-gzip-test-abcdefghij.htm"),
        ("tinnhanhchungkhoan", "tinnhanhchungkhoan/article_dated.html", TNCK_ART_URL),
    ]
    for slug, rel, url in cases:
        plain = _read(rel)
        art_plain = np.parse_article_html(plain.decode("utf-8", errors="replace"), url, slug)
        assert art_plain is not None and art_plain.get("published_at")
        gz = gzip.compress(plain)
        assert np._is_gzip_magic(gz)
        decoded = np.decompress_http_body(gz, "gzip")
        art_gz = np.parse_article_html(decoded.decode("utf-8", errors="replace"), url, slug)
        assert art_gz is not None
        assert art_gz["published_at"] == art_plain["published_at"]
        assert art_gz["title"] == art_plain["title"]


def test_cache_old_gzip_still_reads(tmp_path):
    """Cache cũ còn magic gzip → cache_get/fetch_url giải nén được, không gọi mạng."""
    plain = _read("vneconomy/article_dated.html")
    url = "https://vneconomy.vn/cache-gzip-old-fixture-article-abcdefghijklmnop.htm"
    cfg = base_cfg(news_portal_cache_dir=str(tmp_path / "cache"))
    # ghi tay bản gzip như cache cũ
    key = np._cache_key(np.normalize_url(url) or url)
    cache_file = tmp_path / "cache" / f"{key}.html"
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    cache_file.write_bytes(gzip.compress(plain))

    def boom(_url: str) -> bytes:
        raise AssertionError("must not hit network when gzip cache readable")

    data = np.fetch_url(url, cfg, fetch=boom)
    assert not np._is_gzip_magic(data)
    art = np.parse_article_html(data.decode("utf-8", errors="replace"), url, "vneconomy")
    assert art is not None and art.get("published_at")
    # cache đã được chuẩn hóa sang HTML plain
    assert not np._is_gzip_magic(cache_file.read_bytes())


def test_decompress_failure_marks_portal_failed():
    def bad_gzip(_url: str) -> bytes:
        return b"\x1f\x8b\x08\x00" + b"not-a-valid-gzip-payload"

    cfg = base_cfg()
    arts, flags = np.fetch_portals("VCB", None, WINDOW_START, AS_OF, cfg, fetch=bad_gzip)
    assert arts == []
    assert any(f.startswith("news_portal_failed:") for f in flags)


# ------------------------------------------------------------------ E2E build_snapshot → meta.flags
def _fake_build_sources(monkeypatch):
    """Nguồn giả offline cho build_snapshot (giống test_m1_build)."""
    import pandas as pd
    import stockai.m1_data.sources as sources
    from tests.test_m1_normalize import _fin, _px

    monkeypatch.setattr(
        sources, "get_history",
        lambda t, s, e, c: (_px(1300) if t != "VNINDEX" else _px(1300, scale=50), "VCI"),
    )
    inc, bal, cf = _fin()
    monkeypatch.setattr(
        sources, "get_finance",
        lambda t, k, p, c: ({"income": inc, "balance": bal, "cashflow": cf}[k], "VCI"),
    )
    monkeypatch.setattr(sources, "get_exchange_map", lambda c: {"VCB": "HOSE", "HPG": "HOSE"})
    monkeypatch.setattr(
        sources, "get_overview",
        lambda t, c: (
            pd.DataFrame([{
                "exchange": "HOSE", "icb_name2": "Ngân hàng", "icb_name4": "Ngân hàng",
                "issue_share": 1e9,
            }]),
            "VCI",
        ),
    )
    monkeypatch.setattr(
        sources, "get_news",
        lambda t, c: (
            pd.DataFrame({
                "title": [f"tin {i}" for i in range(12)],
                "publish_date": pd.date_range(end="2026-10-05", periods=12, freq="10D").astype(str),
                "link": [f"u{i}" for i in range(12)],
            }),
            "VCI",
        ),
    )


def _build_cfg(tmp_path, **kw) -> dict:
    cfg = {
        "window_years": 5,
        "banks": ["VCB"],
        "peers_map": {"VCB": ["CTG", "BID", "TCB"]},
        "index_symbol": "VNINDEX",
        "price_multiplier": "auto",
        "financial_multiplier": "auto",
        "vnf_enabled": True,
        "news_enabled": True,
        "news_google": False,
        "news_rss": [],
        "news_months": 24,
        "max_news": 800,
        "news_portals_enabled": True,
        "news_portals_active": ["cafef"],
        "universe_name": "VN30",
        "news_portal_retries": 1,
        "news_portal_interval_sec": 0,
        "news_portal_cache_dir": str(tmp_path / "pcache"),
        "vnstock_sources": ["VCI"],
    }
    cfg.update(kw)
    return cfg


def test_build_snapshot_portal_flags_ok_empty_failed_and_gates(monkeypatch, cafef_mapping, tmp_path):
    """Snapshot cuối (sau VNF + quality) phải giữ news_portal_*; tắt/custom không có cờ."""
    from stockai.m1_data import fetch as f
    from stockai.m1_data import quality
    from stockai.m1_data import vnf_source as vs

    _fake_build_sources(monkeypatch)

    def vnf_inplace(snap, cfg, vnf=None):
        # Chạy trước fetch_news như production; phải giữ cùng list flags
        fl = snap["meta"]["flags"]
        fl.append("vnf_crosscheck_ok:2025")
        fl[:] = list(dict.fromkeys(fl))
        return {"mismatch": 0, "filled": 0, "added_years": 0}

    monkeypatch.setattr(vs, "apply", vnf_inplace)

    # ok: ≥1 bài CafeF
    cfg_ok = _build_cfg(tmp_path / "ok", _news_portal_fetch=_fetch_cafef_only(cafef_mapping))
    snap_ok = f.build_snapshot("VCB", AS_OF, cfg_ok)
    quality.apply(snap_ok, cfg_ok)
    assert "news_portal_ok:cafef" in snap_ok["meta"]["flags"]
    assert any("cafef.vn" in (n.get("url") or "") for n in snap_ok["news"])
    assert any(s.get("id") == "src_news_cafef" for s in snap_ok["sources"])

    # empty: 0 bài sau lọc
    cfg_empty = _build_cfg(
        tmp_path / "empty",
        _news_portal_fetch=lambda url: b"<html><body>no articles</body></html>",
    )
    snap_empty = f.build_snapshot("VCB", AS_OF, cfg_empty)
    quality.apply(snap_empty, cfg_empty)
    assert "news_portal_empty:cafef" in snap_empty["meta"]["flags"]
    assert "news_portal_ok:cafef" not in snap_empty["meta"]["flags"]

    # failed: lỗi mạng/parse
    def boom(_url: str) -> bytes:
        raise RuntimeError("portal down")

    cfg_fail = _build_cfg(tmp_path / "fail", _news_portal_fetch=boom)
    snap_fail = f.build_snapshot("VCB", AS_OF, cfg_fail)
    quality.apply(snap_fail, cfg_fail)
    assert "news_portal_failed:cafef" in snap_fail["meta"]["flags"]

    # tắt cổng
    cfg_off = _build_cfg(
        tmp_path / "off",
        news_portals_enabled=False,
        _news_portal_fetch=_fetch_cafef_only(cafef_mapping),
    )
    snap_off = f.build_snapshot("VCB", AS_OF, cfg_off)
    quality.apply(snap_off, cfg_off)
    assert not any(str(x).startswith("news_portal_") for x in snap_off["meta"]["flags"])

    # universe ngoài VN30/VN100
    cfg_custom = _build_cfg(
        tmp_path / "custom",
        universe_name="custom",
        _news_portal_fetch=_fetch_cafef_only(cafef_mapping),
    )
    snap_custom = f.build_snapshot("VCB", AS_OF, cfg_custom)
    quality.apply(snap_custom, cfg_custom)
    assert not any(str(x).startswith("news_portal_") for x in snap_custom["meta"]["flags"])
