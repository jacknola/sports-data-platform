import pandas as pd

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
