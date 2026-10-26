from datetime import datetime
from zoneinfo import ZoneInfo

from stockai.api.app import _eod_freshness, _expected_eod

ICT = ZoneInfo("Asia/Ho_Chi_Minh")


def test_expected_eod_rules():
    assert _expected_eod(datetime(2026, 10, 15, 16, 0, tzinfo=ICT)) == "2026-10-15"  # Thu sau đóng cửa
    assert _expected_eod(datetime(2026, 10, 15, 9, 0, tzinfo=ICT)) == "2026-10-14"   # Thu trước đóng cửa
    assert _expected_eod(datetime(2026, 10, 17, 12, 0, tzinfo=ICT)) == "2026-10-16"  # Thu Bảy
    assert _expected_eod(datetime(2026, 10, 19, 8, 0, tzinfo=ICT)) == "2026-10-16"   # Thu Hai sáng


def test_eod_stale_flag():
    now = datetime(2026, 10, 15, 16, 0, tzinfo=ICT)
    assert _eod_freshness("2026-10-08", now)["eod_stale"] is True
    assert _eod_freshness("2026-10-15", now)["eod_stale"] is False



def test_merge_news_keeps_old_urls_and_dedupes():
    from stockai.m1_data.fetch import merge_news

    old = [{"title": "Tin A", "url": "https://x/a", "published_at": "2026-10-05T10:00:00"},
           {"title": "Tin B", "url": "https://x/b", "published_at": "2026-10-01T10:00:00"}]
    new = [{"title": "Tin A", "url": "n/a", "published_at": "2026-10-05T10:00:00"},
           {"title": "Tin C", "url": "n/a", "published_at": "2026-10-12T10:00:00"},
           {"title": "Tin tương lai", "url": "n/a", "published_at": "2026-10-20T10:00:00"}]
    out = merge_news(old, new, "2026-01-01", "2026-10-15")
    assert [i["title"] for i in out] == ["Tin C", "Tin A", "Tin B"]
