import pytest

from stockai.m3_technical.scoring import (
    calculate_technical_score,
    score_macd,
    score_momentum,
    score_rsi,
    score_trend,
    score_volume,
    technical_rating,
)


def test_trend_and_component_sum():
    assert score_trend(110, 100, 90, 80) == 45
    assert score_momentum(60, 1, 0) == 35
    assert score_volume(0.02, 1.2) == 20
    assert calculate_technical_score(45, 35, 20) == 100


@pytest.mark.parametrize("rsi, expected", [(29.9, 5), (30, 10), (44.9, 10), (45, 15), (54.9, 15), (55, 20), (70, 20), (70.1, 15)])
def test_rsi_boundaries(rsi, expected):
    assert score_rsi(rsi) == expected


@pytest.mark.parametrize(
    "macd, signal, expected",
    [(1, 0, 15), (-1, -2, 10), (1, 2, 5), (-1, 0, 0)],
)
def test_macd_cases(macd, signal, expected):
    assert score_macd(macd, signal) == expected


@pytest.mark.parametrize(
    "change, ratio, expected",
    [(0.02, 1.2, 20), (0.02, 1.19, 15), (0, 2, 10), (-0.02, 1.19, 5), (-0.02, 1.2, 0)],
)
def test_volume_cases(change, ratio, expected):
    assert score_volume(change, ratio) == expected


@pytest.mark.parametrize(
    "score, expected",
    [(100, "Strong Bullish"), (80, "Strong Bullish"), (79, "Bullish"), (65, "Bullish"),
     (64, "Neutral / Mixed"), (45, "Neutral / Mixed"), (44, "Bearish"), (30, "Bearish"), (29, "Strong Bearish")],
)
def test_rating_boundaries(score, expected):
    assert technical_rating(score) == expected
