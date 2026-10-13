"""US4: regex classify + resolve refs (Q2:B)."""
from __future__ import annotations

from stockai.m7_scoring.debate_validate import (
    classify_ref,
    is_ref_grounded,
    resolve_metric_ref,
    resolve_news_ref,
)


def test_classify_valid_and_invalid():
    assert classify_ref("m4.pe") == "metric"
    assert classify_ref("n12") == "news"
    assert classify_ref("bad") == "invalid"
    assert classify_ref("m4") == "invalid"
    assert classify_ref("nX") == "invalid"
    assert classify_ref("m2.roe") == "metric"


def test_resolve_metric_and_news():
    allowed = ["m4.pe", "m2.roe"]
    upstream = {"m4": {"metrics": {"pe": {"value": 10}}}, "m2": {"metrics": {"roe": {"value": 1}}}}
    assert resolve_metric_ref("m4.pe", allowed, upstream) is True
    assert resolve_metric_ref("m6.beta", allowed, upstream) is False
    assert resolve_metric_ref("m6.beta", [], {"m6": {"metrics": {"beta": {"value": 1}}}}) is True

    nmap = {"n12": "news-real-id"}
    assert resolve_news_ref("n12", nmap) is True
    assert resolve_news_ref("n99", nmap) is False
    assert is_ref_grounded("bad", metrics_allowed=allowed, news_ref_map=nmap) is False
    assert is_ref_grounded("m4.pe", metrics_allowed=allowed, news_ref_map=nmap, upstream=upstream) is True
