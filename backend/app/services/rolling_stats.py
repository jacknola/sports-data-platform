"""Rolling Advanced Stats Calculator.

Computes rolling window advanced statistics (Four Factors + efficiency metrics)
for NBA teams. Uses nba_api for game logs and calculates:
- eFG% (effective field goal percentage)
- TOV% (turnover rate)
- OREB% (offensive rebound rate)
- FTr (free throw rate)
- Net Rating
- Pace
- TS% (true shooting percentage)
"""

import time
from pathlib import Path
from typing import Dict, Optional

import numpy as np
import pandas as pd
from loguru import logger

# nba_api imports
try:
    from nba_api.stats.endpoints import teamgamelog

    _NBA_API_AVAILABLE = True
except ImportError:
    _NBA_API_AVAILABLE = False
    logger.warning("nba_api not available - install with: pip install nba_api")

# Cache TTL in seconds (15 minutes)
DEFAULT_CACHE_TTL = 900

# Cache directory for persistent caching
ROLLING_STATS_CACHE_DIR = Path("/tmp/nba_rolling_stats_cache")


class RollingStatsCalculator:
    """Calculator for rolling window advanced stats.

    Fetches game logs from nba_api and computes Four Factors
    and efficiency metrics with configurable rolling windows.
    """

    def __init__(self, cache_ttl: int = DEFAULT_CACHE_TTL):
        """Initialize the rolling stats calculator."""
        self.cache_ttl = cache_ttl
        self._cache: Dict[str, pd.DataFrame] = {}
        self._cache_times: Dict[str, float] = {}

        # League average defaults (2023-24 NBA season)
        self._league_averages = {
            "eFG_pct": 0.540,
            "TOV_pct": 0.130,
            "OREB_pct": 0.280,
            "FTr": 0.350,
            "net_rating": 0.0,
            "pace": 100.0,
            "ts_pct": 0.580,
            "off_rating": 115.0,
            "def_rating": 115.0,
        }

    def _is_cache_valid(self, cache_key: str) -> bool:
        """Check if cached data is still valid."""
        if cache_key not in self._cache:
            return False
        if cache_key not in self._cache_times:
            return False
        return (time.time() - self._cache_times[cache_key]) < self.cache_ttl

    def _set_cache(self, cache_key: str, data: pd.DataFrame) -> None:
        """Store data in cache with timestamp."""
        self._cache[cache_key] = data
        self._cache_times[cache_key] = time.time()

    def fetch_team_game_logs(
        self, team_id: int, season: str = "2024-25", season_type: str = "Regular Season"
    ) -> pd.DataFrame:
        """Fetch game logs for a Team."""
        cache_key = f"game_logs_{team_id}_{season}"

        # Check in-memory cache first
        if self._is_cache_valid(cache_key):
            return self._cache[cache_key]

        # Check file-based cache
        ROLLING_STATS_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        cache_file = ROLLING_STATS_CACHE_DIR / f"{cache_key}.pkl"
        if cache_file.exists():
            logger.info(f"Loading cached game logs from {cache_file}")
            df = pd.read_pickle(cache_file)
            self._set_cache(cache_key, df)
            return df

        if not _NBA_API_AVAILABLE:
            raise RuntimeError("nba_api not available")

        try:
            # Rate limit to respect API limits
            time.sleep(0.5)

            logger.info(f"Fetching game logs for team {team_id}, season {season}")
            game_log = teamgamelog.TeamGameLog(
                team_id=team_id,
                season=season,
                season_type_all_star=season_type,
            )
            df = game_log.get_data_frames()[0]

            # Save to file cache
            df.to_pickle(cache_file)
            logger.info(f"Cached game logs to {cache_file}")

            # Store in memory cache
            self._set_cache(cache_key, df)
            return df

        except Exception as e:
            logger.error(f"Error fetching game logs for team {team_id}: {e}")
            raise

    def apply_kalman_filter(
        self,
        series: pd.Series,
        process_variance: float = 1e-4,
        measurement_variance: float = 1e-2,
    ) -> pd.Series:
        """Apply a simple 1D Kalman filter to smooth noisy series."""
        if series.empty:
            return series

        float_values = series.astype(float)  # ensure numeric even if upstream sends object dtype
        # Preserve temporal continuity: forward fill recent observations, backfill early gaps,
        # then fall back to the mean to avoid injecting zeros into percentage metrics.
        filled_values = float_values.ffill().bfill()
        if filled_values.isna().any():
            mean_value = filled_values.mean()
            if np.isnan(mean_value):
                mean_value = 0.0
            filled_values = filled_values.fillna(mean_value)
        if filled_values.isna().any():
            filled_values = filled_values.fillna(0.0)
        values = filled_values
        estimates = []

        # Initial guesses
        x_hat = values.iloc[0]
        # Initial covariance tuned for stat ranges that typically sit between 0-200
        # (e.g., efficiency, pace). Keeping this at 1.0 yields a large early Kalman gain
        # with the default measurement variance, so the filter adapts quickly without
        # exploding on typical basketball metrics.
        p = 1.0

        for z in values:
            # Predict
            x_hat_minus = x_hat
            p_minus = p + process_variance

            # Update
            k = p_minus / (p_minus + measurement_variance)
            x_hat = x_hat_minus + k * (z - x_hat_minus)
            p = (1 - k) * p_minus
            estimates.append(x_hat)

        return pd.Series(estimates, index=series.index)

    def calculate_four_factors(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate Four Factors metrics from game log data."""
        if df.empty:
            return df

        # Rename columns to lowercase for consistency
        df = df.copy()
        rename_map = {
            "GAME_ID": "game_id",
            "GAME_DATE": "game_date",
            "TEAM_ID": "team_id",
            "TEAM_NAME": "team_name",
            "FGM": "fgm",
            "FGA": "fga",
            "FG_PCT": "fg_pct",
            "FG3M": "fg3m",
            "FG3A": "fg3a",
            "FG3_PCT": "fg3_pct",
            "FTM": "ftm",
            "FTA": "fta",
            "FT_PCT": "ft_pct",
            "OREB": "oreb",
            "DREB": "dreb",
            "REB": "reb",
            "AST": "ast",
            "TOV": "tov",
            "STL": "stl",
            "BLK": "blk",
            "BLKA": "blka",
            "PF": "pf",
            "PFD": "pfd",
            "PTS": "pts",
            "PLUS_MINUS": "plus_minus",
            "MIN": "min",
        }

        # Only rename columns that exist
        for old_col, new_col in rename_map.items():
            if old_col in df.columns:
                df = df.rename(columns={old_col: new_col})

        # Calculate Four Factors
        # eFG% = (FG + 0.5 * FG3) / FGA
        if "fga" in df.columns:
            df["eFG_pct"] = np.where(
                df["fga"] > 0,
                (df["fgm"] + 0.5 * df["fg3m"]) / df["fga"],
                0,
            )

        # TOV% = TOV / (FGA + 0.44 * FTA + TOV)
        if all(c in df.columns for c in ["tov", "fga", "fta"]):
            denominator = df["fga"] + 0.44 * df["fta"] + df["tov"]
            df["TOV_pct"] = np.where(denominator > 0, df["tov"] / denominator, 0)

        # OREB% = OREB / (OREB + opp DREB) - simplified: OREB / (OREB + DREB)
        if all(c in df.columns for c in ["oreb", "dreb"]):
            total_rebs = df["oreb"] + df["dreb"]
            df["OREB_pct"] = np.where(total_rebs > 0, df["oreb"] / total_rebs, 0)

        # FTr = FTA / FGA
        if all(c in df.columns for c in ["fta", "fga"]):
            df["FTr"] = np.where(df["fga"] > 0, df["fta"] / df["fga"], 0)

        # TS% = PTS / (2 * (FGA + 0.44 * FTA))
        if all(c in df.columns for c in ["pts", "fga", "fta"]):
            denominator = 2 * (df["fga"] + 0.44 * df["fta"])
            df["TS_pct"] = np.where(denominator > 0, df["pts"] / denominator, 0)

        return df

    def calculate_rolling_stats(
        self,
        team_id: int,
        season: str = "2024-25",
        window: int = 10,
        use_kalman_filter: bool = False,
    ) -> pd.DataFrame:
        """Calculate rolling advanced stats for a team.

        When enabled, the Kalman filter post-processes the rolling averages
        to reduce noise while keeping the window-based context.

        Args:
            team_id: NBA team id.
            season: Season string (e.g., "2024-25").
            window: Rolling window size for averages.
            use_kalman_filter: Apply a Kalman smoother to the rolling averages.
        """
        # Fetch game logs
        df = self.fetch_team_game_logs(team_id, season)

        if df.empty:
            return df

        # Calculate Four Factors
        df = self.calculate_four_factors(df)

        # Sort by date (most recent last)
        if "GAME_DATE" in df.columns:
            df = df.sort_values("GAME_DATE")

        # Calculate rolling averages
        numeric_cols = [
            "eFG_pct",
            "TOV_pct",
            "OREB_pct",
            "FTr",
            "TS_pct",
            "PTS",
            "REB",
            "AST",
            "TOV",
            "STL",
            "BLK",
        ]

        # Only use columns that exist
        rolling_cols = [c for c in numeric_cols if c in df.columns]

        for col in rolling_cols:
            rolling_mean = df[col].rolling(window=window, min_periods=1).mean()
            if use_kalman_filter:
                rolling_mean = self.apply_kalman_filter(rolling_mean)
            df[f"{col}_rolling_{window}"] = rolling_mean

        return df

    def get_team_season_stats(
        self, team_id: int, season: str = "2024-25"
    ) -> Dict[str, float]:
        """Get average stats for a team over a season."""
        df = self.calculate_rolling_stats(team_id, season, window=10)

        if df.empty:
            return self._league_averages.copy()

        # Get the last N games average
        last_n = min(10, len(df))

        stats = {}
        for col in [
            "eFG_pct_rolling_10",
            "TOV_pct_rolling_10",
            "OREB_pct_rolling_10",
            "FTr_rolling_10",
            "TS_pct_rolling_10",
        ]:
            if col in df.columns:
                key = col.replace("_rolling_10", "")
                stats[key] = df[col].iloc[-last_n:].mean()

        # Fill missing with league averages
        for key, value in self._league_averages.items():
            if key not in stats:
                stats[key] = value

        return stats

    def get_team_rolling_stats_by_name(
        self,
        team_name: str,
        season: str = "2024-25",
        window: int = 10,
        use_kalman_filter: bool = False,
    ) -> Dict[str, float]:
        """Get rolling stats for a team by name.

        Args:
            team_name: Team name (e.g., "Los Angeles Lakers")
            season: Season string (e.g., "2024-25")
            window: Rolling window size

        Returns:
            Dict with rolling stat averages
        """
        # Import teams here to avoid circular imports
        try:
            from nba_api.stats.static import teams

            _teams = teams.get_teams()
            team_id = None
            for t in _teams:
                if (
                    team_name.lower() in t["full_name"].lower()
                    or team_name.lower() in t["nickname"].lower()
                ):
                    team_id = t["id"]
                    break
            if team_id is None:
                logger.warning(f"Team not found: {team_name}")
                return self._league_averages.copy()
        except Exception as e:
            logger.error(f"Error finding team {team_name}: {e}")
            return self._league_averages.copy()

        df = self.calculate_rolling_stats(team_id, season, window, use_kalman_filter)

        if df.empty:
            return self._league_averages.copy()

        # Get last N games average
        last_n = min(window, len(df))

        stats = {}
        for col in df.columns:
            suffix = f"_rolling_{window}"
            if col.endswith(suffix):
                key = col.replace(suffix, "")
                stats[key] = df[col].iloc[-last_n:].mean()

        # Fill missing with league averages
        for key, value in self._league_averages.items():
            if key not in stats:
                stats[key] = value

        return stats

    def clear_cache(self) -> None:
        """Clear all cached data."""
        self._cache.clear()
        self._cache_times.clear()
        logger.info("Rolling stats cache cleared")


def compute_ncaab_rolling_stats(
    adj_oe: float, adj_de: float, recent_games, window: int = 10
) -> Dict[str, float]:
    """
    Compute rolling-style stats for NCAAB teams.
    """
    import numpy as np

    if not recent_games or len(recent_games) < 3:
        return {
            "adj_oe": adj_oe,
            "adj_de": adj_de,
            "net_rating": adj_oe - adj_de,
            "win_pct": 0.5,
            "pace": 70.0,
        }

    wins = sum(1 for g in recent_games[-window:] if g.get("win", False))
    win_pct = wins / min(len(recent_games), window)

    recent_pts = np.mean([g.get("points", 70) for g in recent_games[-window:]])
    recent_opp_pts = np.mean([g.get("opp_points", 70) for g in recent_games[-window:]])

    return {
        "adj_oe": adj_oe,
        "adj_de": adj_de,
        "net_rating": adj_oe - adj_de,
        "win_pct": win_pct,
        "pace": 70.0,
        "recent_off_rating": recent_pts * (adj_oe / 100),
        "recent_def_rating": recent_opp_pts * (adj_de / 100),
    }
