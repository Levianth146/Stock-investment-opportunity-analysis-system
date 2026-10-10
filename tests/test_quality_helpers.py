from stockai.contracts.helpers import quality_reasons, quality_tier


def _snap(flags: list[str]) -> dict:
    return {"meta": {"flags": flags}}


def test_quality_tier_and_reasons():
    s = _snap(["quality_tier_limited", "quality_news_few", "quality_low_liquidity", "other"])
    assert quality_tier(s) == "limited"
    assert quality_reasons(s) == ["news_few", "low_liquidity"]


def test_quality_tier_absent():
    assert quality_tier(_snap([])) is None
    assert quality_tier(_snap(["unrelated"])) is None
    assert quality_reasons(_snap(["quality_tier_full"])) == []
