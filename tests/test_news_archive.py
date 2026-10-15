from stockai.api.news_data import news_archive
from stockai.api.store import ResultStore


def test_archive_is_not_limited_to_six_and_excludes_invalid_future_duplicates():
    rows = [{"title": f"FPT doanh thu tăng {i}", "published_at": "2026-10-08T10:00:00", "source": "A"} for i in range(9)]
    rows += [dict(rows[0]), {"title": "Tin tương lai", "published_at": "2026-10-09"},
             {"title": "Sai ngày", "published_at": "invalid"}, None]
    result = news_archive({"news": rows}, "2026-10-08", "FPT")
    assert len(result) == 9
    assert all(row["label"] == "pos" for row in result)
    assert all(row["tickers"] == ["FPT"] for row in result)
    assert len({row["id"] for row in result}) == 9


def test_archive_sanitizes_links_and_html_and_preserves_neutral():
    result = news_archive({"news": [{"title": "FPT họp cổ đông", "summary": "<b>Thông báo</b> &amp; lịch họp", "url": "javascript:alert(1)", "published_at": "2026-10-08"}]}, "2026-10-08", "FPT")
    assert result[0]["url"] is None
    assert result[0]["summary"] == "Thông báo & lịch họp"
    assert result[0]["label"] == "neutral"
    assert news_archive({}, "2026-10-08", "ABR") == []


def test_news_legacy_and_full_archive_share_one_classification_pass(monkeypatch):
    import stockai.api.store as module
    store = object.__new__(ResultStore)
    store.default_profile = "long_term"
    store._asof = "2026-10-08"
    store.load_snapshot = lambda symbol: {"news": []}
    store.get_bundle = lambda *args, **kwargs: {"m5": {"evidence": []}}
    calls = []
    def archive(*args):
        calls.append(1)
        return [{"id": "n1", "title": "Tin A", "date": "2026-10-08", "polarity": .5}]
    monkeypatch.setattr(module, "news_archive", archive)
    result = store.news("AAA")
    assert len(calls) == 1
    assert result["other_items"][0]["label"] == "tích cực"
    assert result["articles"][0]["polarity"] == .5
