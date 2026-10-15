import csv
import json

from stockai.api.company_profile import company_profile


def test_shared_profile_archive_is_connected_without_copying_current_shares(tmp_path):
    path = tmp_path / "data/company_profiles/profiles.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({"AAA": {"symbol": "AAA", "name": "Tên đầy đủ", "intro": "Thành lập năm 1990.", "data_date": "2026-10-09", "issue_share": 99999}}), encoding="utf-8")
    result = company_profile({"company": {"shares_outstanding": 123}}, "AAA", tmp_path)
    assert result["description"] == "Thành lập năm 1990."
    assert result["founded_year"] == 1990
    assert result["source"] == "company_profile_cache"
    assert result["data_date"] == "2026-10-09"
    assert "shares_outstanding" not in result


def write_overview(root, ticker, rows):
    path = root / "data" / "raw" / ticker / "overview.csv"
    path.parent.mkdir(parents=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def test_local_profile_matches_symbol_and_extracts_only_explicit_founding_year(tmp_path):
    write_overview(tmp_path, "FPT", [
        {"symbol": "OTHER", "organ_name": "Wrong company", "company_profile": "Wrong description", "listing_date": "2000-01-01"},
        {"symbol": "FPT", "organ_name": "Công ty Cổ phần FPT", "company_profile": "Doanh nghiệp được thành lập năm 1988. Công nghệ và giáo dục.", "listing_date": "2006-12-13T00:00:00"},
    ])
    profile = company_profile({"company": {"name": "FPT Corp", "sector": "Technology", "exchange": "HSX"}}, "FPT", tmp_path)
    assert profile["name"] == "Công ty Cổ phần FPT"
    assert profile["founded_year"] == 1988
    assert profile["listing_date"] == "2006-12-13"
    assert profile["sector"] == "Technology"
    assert profile["source"] == "local_overview_cache"
    assert "Wrong" not in str(profile)


def test_missing_profile_keeps_current_company_without_demo_fallback(tmp_path):
    write_overview(tmp_path, "AMC", [{"symbol": "FPT", "organ_name": "FPT", "company_profile": "FPT only"}])
    profile = company_profile({"company": {"name": "Khoáng sản Á Châu", "exchange": "HNX", "sector": "Basic Resources"}}, "AMC", tmp_path)
    assert profile["ticker"] == "AMC"
    assert profile["name"] == "Khoáng sản Á Châu"
    assert profile["description"] is None
    assert profile["founded_year"] is None
    assert profile["listing_date"] is None
    assert profile["source"] == "snapshot"
    assert "FPT" not in str(profile)


def test_snapshot_description_is_preferred_and_other_dates_are_not_founding_years(tmp_path):
    write_overview(tmp_path, "AAA", [{"symbol": "AAA", "organ_name": "AAA", "company_profile": "Bản cache cũ", "listing_date": "invalid"}])
    profile = company_profile({"company": {"description": "Niêm yết năm 2007, mở nhà máy năm 2015."}}, "AAA", tmp_path)
    assert profile["description"] == "Niêm yết năm 2007, mở nhà máy năm 2015."
    assert profile["founded_year"] is None
    assert profile["listing_date"] is None


def test_company_profile_does_not_copy_financial_recommendations_from_raw_cache(tmp_path):
    write_overview(tmp_path, "AAA", [{"symbol": "AAA", "organ_name": "AAA", "rating": "BUY", "target_price": "999999", "current_price": "999999"}])
    profile = company_profile({"company": {}}, "AAA", tmp_path)
    assert "rating" not in profile
    assert "target_price" not in profile
    assert "current_price" not in profile
