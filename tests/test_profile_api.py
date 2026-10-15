"""API hồ sơ công ty: có / không có dữ liệu."""
from __future__ import annotations

import json

from stockai.api.profiles import company_profile
from tests.test_api_017b_watchlist_live import api_env  # noqa: F401


def test_company_profile_missing_file(tmp_path):
    out = company_profile(tmp_path, "AAA")
    assert out == {"symbol": "AAA", "available": False, "profile": None}


def test_company_profile_reads_file(tmp_path):
    d = tmp_path / "data" / "company_profiles"
    d.mkdir(parents=True)
    (d / "profiles.json").write_text(
        json.dumps({"AAA": {"symbol": "AAA", "intro": "Giới thiệu"}}, ensure_ascii=False),
        encoding="utf-8",
    )
    out = company_profile(tmp_path, "AAA")
    assert out["available"] is True and out["profile"]["intro"] == "Giới thiệu"
    assert company_profile(tmp_path, "ZZZ")["available"] is False


def test_profile_endpoint(api_env):  # noqa: F811
    client, *_ = api_env
    r = client.get("/api/tickers/AAA/profile")
    assert r.status_code == 200
    body = r.json()
    assert body["symbol"] == "AAA" and "available" in body
    assert client.get("/api/tickers/BAD!!/profile").status_code in (400, 404)


def test_news_includes_unclassified(api_env):  # noqa: F811
    client, *_ = api_env
    r = client.get("/api/tickers/AAA/news")
    assert r.status_code == 200
    body = r.json()
    assert "other_items" in body and "latest_news_date" in body


def test_dividends_for(tmp_path):
    from stockai.api.dividends import dividends_for

    assert dividends_for(tmp_path, "AAA")["reason"] == "no_file"
    d = tmp_path / "data" / "dividends"
    d.mkdir(parents=True)
    from datetime import date

    recent = date.today().isoformat()
    (d / "dividends.json").write_text(
        json.dumps(
            {
                "AAA": {"symbol": "AAA", "source": "vnstock/TCBS", "events": [
                    {"ex_date": recent, "kind": "cash", "dps_vnd": 1000.0},
                    {"ex_date": "2001-01-01", "kind": "cash", "dps_vnd": 500.0},
                ]},
                "BBB": {"symbol": "BBB", "events": []},
            }
        ),
        encoding="utf-8",
    )
    a = dividends_for(tmp_path, "AAA")
    assert a["available"] and a["dps_ttm_vnd"] == 1000.0
    assert dividends_for(tmp_path, "BBB")["reason"] == "no_events"
    assert dividends_for(tmp_path, "ZZZ")["reason"] == "not_fetched"
