from __future__ import annotations

import pytest

from stockai.m3_technical.indicators import (
    ema,
    five_day_return,
    macd,
    rsi_wilder,
    sma,
    volume_ma,
    volume_ratio,
)


def test_sma_known_sequence_and_insufficient_history():
    assert sma([1, 2, 3, 4, 5], 3) == [None, None, 2.0, 3.0, 4.0]
    assert sma([1, 2], 3) == [None, None]


def test_ema_uses_sma_seed_and_recursive_formula():
    values = ema([1, 2, 3, 4, 5], 3)
    assert values[:2] == [None, None]
    assert values[2:] == pytest.approx([2.0, 3.0, 4.0])
    assert ema([1, 2], 3) == [None, None]


def test_ema_resets_warmup_and_state_after_missing_observation():
    assert ema([1, 2, None, 4, 5], 3) == [None, None, None, None, None]

    values = ema([1, 2, 3, None, 4, 5, 6, 7], 3)
    assert values[:3] == pytest.approx([None, None, 2.0])
    assert values[3:6] == [None, None, None]
    assert values[6:] == pytest.approx([5.0, 6.0])


def test_rsi_wilder_edge_cases_and_insufficient_history():
    assert rsi_wilder(list(range(15)), 14)[-1] == pytest.approx(100.0)
    assert rsi_wilder(list(range(15, 0, -1)), 14)[-1] == pytest.approx(0.0)
    constant = rsi_wilder([10] * 15, 14)
    assert constant[:14] == [None] * 14
    assert constant[-1] == pytest.approx(50.0)
    assert rsi_wilder([1] * 14, 14) == [None] * 14


def test_macd_is_aligned_and_signal_has_warmup():
    values = macd([100] * 60)
    assert len(values["macd"]) == len(values["signal"]) == len(values["histogram"]) == 60
    assert values["signal"][:33] == [None] * 33
    assert values["signal"][33] == pytest.approx(0.0)
    assert values["macd"][-1] == pytest.approx(0.0)
    assert values["signal"][-1] == pytest.approx(0.0)
    assert values["histogram"][-1] == pytest.approx(0.0)
    for macd_value, signal_value, histogram_value in zip(
        values["macd"], values["signal"], values["histogram"]
    ):
        if macd_value is not None and signal_value is not None:
            assert histogram_value == pytest.approx(macd_value - signal_value)


def test_macd_does_not_bridge_missing_close_or_macd_gaps():
    values = macd(
        [float(index) for index in range(40)],
        fast_period=3,
        slow_period=5,
        signal_period=2,
    )
    with_gap = macd(
        [float(index) if index != 20 else None for index in range(40)],
        fast_period=3,
        slow_period=5,
        signal_period=2,
    )

    assert with_gap["macd"][20] is None
    assert with_gap["signal"][20] is None
    assert with_gap["histogram"][20] is None
    assert with_gap["macd"][21:25] == [None, None, None, None]
    assert with_gap["signal"][21:26] == [None, None, None, None, None]
    assert with_gap["macd"][25] is not None
    assert with_gap["signal"][25] is None
    assert with_gap["signal"][26] is not None
    assert values["signal"][25] is not None


def test_volume_ma_and_ratio():
    volumes = list(range(1, 21))
    averages = volume_ma(volumes, 20)
    assert averages[-1] == pytest.approx(10.5)
    assert volume_ratio(21, averages[-1]) == pytest.approx(2.0)
    assert volume_ratio(10, 0) is None
    assert volume_ratio(10, None) is None


def test_five_day_return_is_aligned_and_exact():
    values = five_day_return([100, 101, 102, 103, 104, 110], 5)
    assert values[:5] == [None] * 5
    assert values[-1] == pytest.approx(0.1)
    assert five_day_return([100, 101], 5) == [None, None]
