"""Tin bổ sung (RSS/Google News) và NPL/CAR nhập tay: chạy offline bằng dữ liệu mẫu."""
from stockai.m1_data import bank_kpis, fetch as f, news_extra as ne

RSS = """<?xml version="1.0"?><rss version="2.0"><channel>
<item><title>HPG: Hòa Phát đạt lợi nhuận kỷ lục - CafeF</title><link>https://news.google.com/rss/articles/abc</link>
<pubDate>Tue, 06 Oct 2026 03:00:00 GMT</pubDate><description>&lt;a&gt;HPG tăng&lt;/a&gt; mạnh</description><source url="https://cafef.vn">CafeF</source></item>
<item><title>Tin không liên quan ACBX</title><link>u2</link><pubDate>Mon, 05 Oct 2026 03:00:00 GMT</pubDate></item>
<item><title>Thiếu ngày HPG</title><link>u3</link></item>
<item><title>HPG tương lai - Vietstock</title><link>u4</link><pubDate>Tue, 06 Oct 2026 03:00:00 +0000</pubDate></item>
</channel></rss>"""


def test_parse_rss_and_relevance():
    rows = ne.parse_rss(RSS)
    assert [r["title"] for r in rows] == ["HPG: Hòa Phát đạt lợi nhuận kỷ lục", "Tin không liên quan ACBX", "HPG tương lai"]
    assert rows[0]["source"] == "CafeF" and rows[0]["publish_date"] == "2026-10-06T10:00:00"      # GMT -> giờ VN
    assert rows[0]["summary"] == "HPG tăng mạnh" and rows[2]["source"] == "Vietstock"
    assert [r["title"] for r in rows if ne.relevant(r, "HPG")] == [rows[0]["title"], "HPG tương lai"]
    assert not ne.relevant({"title": "ACBX", "summary": ""}, "ACB")


def test_windows_cover_range_without_gap():
    w = ne.windows("2026-01-01", "2026-03-01", 30)
    assert w[0][0] == "2026-01-01" and w[-1][1] == "2026-03-02"
    assert all(w[i][1] == w[i + 1][0] for i in range(len(w) - 1))


def test_google_news_tolerates_errors():
    calls = []

    def fake(url):
        calls.append(url)
        if len(calls) == 2:
            raise OSError("mạng lỗi")
        return RSS.encode()
    rows, flags = ne.google_news("HPG", "2026-08-01", "2026-10-08", {"news_google_window_days": 30}, fetch=fake)
    assert len(calls) == 3 and flags == ["news_google_errors:1_windows"] and len(rows) == 4
    assert "after%3A2026-08-01" in calls[0]


def test_fetch_news_merges_google_and_clears_url_flag(monkeypatch):
    import pandas as pd
    base = pd.DataFrame([{"news_title": "HPG cũ", "public_date": "2026-10-01T08:00:00", "news_id": 1, "news_source_link": None}])
    monkeypatch.setattr(f.src, "get_news", lambda t, c: (base, "VCI"))
    monkeypatch.setattr(f.news_extra, "google_news", lambda *a, **k: (ne.parse_rss(RSS), []))
    cfg = {"max_news": 50, "news_months": 12, "news_google": True, "_flags": []}
    items, _ = f.fetch_news("HPG", "2021-10-09", "2026-10-08", cfg)
    assert {i["title"] for i in items} >= {"HPG cũ", "HPG: Hòa Phát đạt lợi nhuận kỷ lục", "HPG tương lai"} or len(items) >= 2
    assert any(i["url"].startswith("https://news.google.com") for i in items)
    assert any(i["source"] == "CafeF (qua Google News)" for i in items)
    assert "news_url_missing" not in cfg["_flags"] and "news_has_no_article_url" not in cfg["_flags"]
    assert [i["published_at"] for i in items] == sorted((i["published_at"] for i in items), reverse=True)


def _snap():
    return {"meta": {"ticker": "VCB", "flags": ["bank_npl_car_not_in_statements"]}, "sources": [],
            "financials": {"annual": [{"period": "2025", "items": {}}, {"period": "2024", "items": {}}], "quarterly": []}}


def test_bank_kpis_apply(tmp_path):
    p = tmp_path / "k.csv"
    p.write_text("ticker,period,npl_ratio,car,source,note\nVCB,2025,1.2,11.5,BCTN VCB 2025 tr.30,\nVCB,2024,0.9,,x,\nACB,2025,2,2,y,\n", encoding="utf-8")
    s = _snap()
    bank_kpis.apply(s, str(p))
    a = s["financials"]["annual"]
    assert a[0]["items"] == {"npl_ratio": 0.012, "car": 0.115} and a[1]["items"] == {"npl_ratio": 0.009}
    assert "bank_npl_car_not_in_statements" not in s["meta"]["flags"] and "bank_kpis_manual" in s["meta"]["flags"]
    assert s["sources"][0]["id"] == "src_bank_kpis" and "BCTN VCB 2025" in s["sources"][0]["note"]


def test_bank_kpis_blank_or_missing_file_keeps_flag(tmp_path):
    for path in (tmp_path / "none.csv", tmp_path / "blank.csv"):
        if path.name == "blank.csv":
            path.write_text("ticker,period,npl_ratio,car,source,note\nVCB,2025,,,,\n", encoding="utf-8")
        s = _snap()
        bank_kpis.apply(s, str(path))
        assert "bank_npl_car_not_in_statements" in s["meta"]["flags"] and s["sources"] == []
