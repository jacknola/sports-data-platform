import pandas as pd
import pytest

from app.services.rolling_stats import RollingStatsCalculator


def test_kalman_filter_smooths_noisy_series():
    calc = RollingStatsCalculator()

    noisy = pd.Series([1.0, 10.0, 1.0, 10.0, 1.0])
    smoothed = calc.apply_kalman_filter(
        noisy, process_variance=1e-4, measurement_variance=0.5
    )

    assert len(smoothed) == len(noisy)
    # Smoothed series should reduce variance and dampen spikes
    assert smoothed.var() < noisy.var()
    assert smoothed.iloc[1] < noisy.iloc[1]


def test_kalman_filter_handles_empty_series():
    calc = RollingStatsCalculator()

    empty = pd.Series(dtype=float)
    smoothed = calc.apply_kalman_filter(empty)

    assert smoothed.empty


def test_kalman_filter_handles_constant_and_nans():
    calc = RollingStatsCalculator()

    series = pd.Series([float("nan"), 5.0, 5.0, float("nan")])
    smoothed = calc.apply_kalman_filter(series)

    assert not smoothed.isna().any()
    assert smoothed.iloc[-1] == pytest.approx(5.0, rel=1e-2)
    assert smoothed.var() < 1e-6
