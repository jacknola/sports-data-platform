"""
Stats-Only Feature Engineering Pipeline.

Produces model-ready features using ONLY statistics data (no odds).
Designed to work independently of the betting/odds pipeline.

Features (30 columns):
- Team ratings: off_rating, def_rating, win_pct, pace
- Elo: rating, differential
- Rolling Four Factors: eFG%, TOV%, OREB%, FTr (5g and 10g windows)
- Net rating: rolling net rating
- Game context: is_home, rest_days, back-to-back
"""

from typing import Dict, List, Optional, Tuple
from datetime import date

import numpy as np
import pandas as pd
from loguru import logger

from app.services.elo_service import EloService
from app.services.rolling_stats import RollingStatsCalculator

# League average defaults (NBA 2023-24)
LEAGUE_AVERAGES = {
    "off_rating": 115.0,
    "def_rating": 115.0,
    "win_pct": 0.5,
    "pace": 100.0,
    "eFG_pct": 0.540,
    "TOV_pct": 0.130,
    "OREB_pct": 0.280,
    "FTr": 0.350,
    "net_rating": 0.0,
    "ts_pct": 0.580,
}


class StatsFeatureEngineer:
    """
    Feature engineer for stats-only predictions.

    Integrates Elo ratings, rolling advanced stats, and team
    ratings to produce model-ready features without any odds data.
    """

    def __init__(self, sport: str = "nba", season: str = "2024-25"):
        """
        Initialize the feature engineer.

        Args:
            sport: Sport type ('nba' or 'ncaab').
            season: Season to use for stats.
        """
        self.sport = sport.lower()
        self.season = season

        # Initialize services
        self.elo_service = EloService(sport=self.sport)
        self.rolling_calc = RollingStatsCalculator()

        # Schedule context service — provides real rest/travel features from DB
        from app.services.schedule_context_service import ScheduleContextService
        self._schedule_ctx = ScheduleContextService()

        # Team stats cache
        self._team_stats_cache: Dict[str, Dict] = {}

        logger.info(f"Initialized StatsFeatureEngineer for {self.sport}")

    def _get_team_stats(self, team_name: str) -> Dict[str, float]:
        """
        Fetch team stats from nba_api.

        Args:
            team_name: Team name.

        Returns:
            Dict of team stats.
        """
        if team_name in self._team_stats_cache:
            return self._team_stats_cache[team_name]

        try:
            stats = self.rolling_calc.get_team_rolling_stats_by_name(
                team_name=team_name, window=10, season=self.season
            )
            self._team_stats_cache[team_name] = stats
            return stats
        except Exception as e:
            logger.warning(f"Error fetching stats for {team_name}: {e}")
            return LEAGUE_AVERAGES.copy()

    def _calculate_win_pct(self, team_name: str) -> float:
        """
        Calculate current win percentage from Elo.

        Args:
            team_name: Team name.

        Returns:
            Win percentage (0-1).
        """
        rating = self.elo_service.get_rating(team_name)
        # Convert Elo to win% relative to 1500 baseline
        # Using logistic: 1 / (1 + 10^((1500 - rating) / 400))
        win_pct = 1 / (1 + 10 ** ((1500 - rating) / 400))
        return win_pct

    def _get_rest_days(self, team_name: str, game_date: Optional[date] = None) -> int:
        """
        Return rest days since last game from the database.

        Falls back to 1 if no schedule context is available.
        """
        today = game_date or date.today()
        ctx = self._schedule_ctx.get_context(team_name, today, self.sport)
        return ctx.get("rest_days") if ctx.get("rest_days") is not None else 1

    def _is_back_to_back(self, team_name: str, game_date: Optional[date] = None) -> bool:
        """
        Check if the team is playing on back-to-back nights from the database.

        Falls back to False if no schedule context is available.
        """
        today = game_date or date.today()
        ctx = self._schedule_ctx.get_context(team_name, today, self.sport)
        return bool(ctx.get("is_back_to_back", False))

    def prepare_features(
        self, home_team: str, away_team: str, sport: Optional[str] = None
    ) -> pd.DataFrame:
        """
        Prepare features for a single game prediction.

        Args:
            home_team: Home team name.
            away_team: Away team name.
            sport: Override sport (optional).

        Returns:
            DataFrame with 30 feature columns.
        """
        sport = sport or self.sport

        # Get Elo ratings
        home_elo = self.elo_service.get_rating(home_team)
        away_elo = self.elo_service.get_rating(away_team)
        elo_diff = home_elo - away_elo

        # Get Elo-based win probability
        elo_home_prob = self.elo_service.predict_win_prob(home_team, away_team)

        # Get rolling stats (5-game and 10-game windows)
        home_stats_5g = self.rolling_calc.get_team_rolling_stats_by_name(
            home_team, window=5, season=self.season, use_kalman_filter=True
        )
        home_stats_10g = self.rolling_calc.get_team_rolling_stats_by_name(
            home_team, window=10, season=self.season, use_kalman_filter=True
        )
        away_stats_5g = self.rolling_calc.get_team_rolling_stats_by_name(
            away_team, window=5, season=self.season, use_kalman_filter=True
        )
        away_stats_10g = self.rolling_calc.get_team_rolling_stats_by_name(
            away_team, window=10, season=self.season, use_kalman_filter=True
        )

        # Calculate win percentages
        home_win_pct = self._calculate_win_pct(home_team)
        away_win_pct = self._calculate_win_pct(away_team)

        # Rest and schedule context
        rest_days_home = self._get_rest_days(home_team)
        rest_days_away = self._get_rest_days(away_team)
        is_b2b_home = self._is_back_to_back(home_team)
        is_b2b_away = self._is_back_to_back(away_team)

        # Build feature dict
        features = {
            # Team ratings
            "home_off_rating": home_stats_10g.get(
                "off_rating", LEAGUE_AVERAGES["off_rating"]
            ),
            "home_def_rating": home_stats_10g.get(
                "def_rating", LEAGUE_AVERAGES["def_rating"]
            ),
            "away_off_rating": away_stats_10g.get(
                "off_rating", LEAGUE_AVERAGES["off_rating"]
            ),
            "away_def_rating": away_stats_10g.get(
                "def_rating", LEAGUE_AVERAGES["def_rating"]
            ),
            "home_win_pct": home_win_pct,
            "away_win_pct": away_win_pct,
            "home_pace": home_stats_10g.get("pace", LEAGUE_AVERAGES["pace"]),
            "away_pace": away_stats_10g.get("pace", LEAGUE_AVERAGES["pace"]),
            # Elo features
            "home_elo": home_elo,
            "away_elo": away_elo,
            "elo_differential": elo_diff,
            # Rolling 5-game Four Factors (home)
            "home_eFG_5g": home_stats_5g.get("eFG_pct", LEAGUE_AVERAGES["eFG_pct"]),
            "home_TOV_5g": home_stats_5g.get("TOV_pct", LEAGUE_AVERAGES["TOV_pct"]),
            "home_OREB_5g": home_stats_5g.get("OREB_pct", LEAGUE_AVERAGES["OREB_pct"]),
            "home_FTr_5g": home_stats_5g.get("FTr", LEAGUE_AVERAGES["FTr"]),
            # Rolling 5-game Four Factors (away)
            "away_eFG_5g": away_stats_5g.get("eFG_pct", LEAGUE_AVERAGES["eFG_pct"]),
            "away_TOV_5g": away_stats_5g.get("TOV_pct", LEAGUE_AVERAGES["TOV_pct"]),
            "away_OREB_5g": away_stats_5g.get("OREB_pct", LEAGUE_AVERAGES["OREB_pct"]),
            "away_FTr_5g": away_stats_5g.get("FTr", LEAGUE_AVERAGES["FTr"]),
            # Rolling 10-game Four Factors (home)
            "home_eFG_10g": home_stats_10g.get("eFG_pct", LEAGUE_AVERAGES["eFG_pct"]),
            "home_TOV_10g": home_stats_10g.get("TOV_pct", LEAGUE_AVERAGES["TOV_pct"]),
            "home_OREB_10g": home_stats_10g.get(
                "OREB_pct", LEAGUE_AVERAGES["OREB_pct"]
            ),
            "home_FTr_10g": home_stats_10g.get("FTr", LEAGUE_AVERAGES["FTr"]),
            # Rolling 10-game Four Factors (away)
            "away_eFG_10g": away_stats_10g.get("eFG_pct", LEAGUE_AVERAGES["eFG_pct"]),
            "away_TOV_10g": away_stats_10g.get("TOV_pct", LEAGUE_AVERAGES["TOV_pct"]),
            "away_OREB_10g": away_stats_10g.get(
                "OREB_pct", LEAGUE_AVERAGES["OREB_pct"]
            ),
            "away_FTr_10g": away_stats_10g.get("FTr", LEAGUE_AVERAGES["FTr"]),
            # Rolling net rating
            "home_net_rating_5g": home_stats_5g.get(
                "net_rating", LEAGUE_AVERAGES["net_rating"]
            ),
            "away_net_rating_5g": away_stats_5g.get(
                "net_rating", LEAGUE_AVERAGES["net_rating"]
            ),
            # Game context
            "is_home": 1,
            "rest_days_home": rest_days_home,
            "rest_days_away": rest_days_away,
            "is_back_to_back_home": 1 if is_b2b_home else 0,
            "is_back_to_back_away": 1 if is_b2b_away else 0,
        }

        # Create DataFrame
        df = pd.DataFrame([features])

        # Fill any NaN values with league averages
        df = df.fillna(0)

        available = sum(1 for v in features.values() if v != 0)
        total = len(features)
        logger.info(
            f"Features: {available}/{total} available for {home_team} vs {away_team}"
        )

        return df

    def prepare_training_features(
        self, historical_games: List[Dict]
    ) -> Tuple[pd.DataFrame, np.ndarray]:
        """
        Prepare features for training from historical games.

        Args:
            historical_games: List of game dicts with:
                - home_team, away_team
                - home_score, away_score
                - (optional) date, stats data

        Returns:
            Tuple of (X features DataFrame, y labels array).
        """
        rows = []
        labels = []

        for game in historical_games:
            home_team = game.get("home_team")
            away_team = game.get("away_team")
            home_score = game.get("home_score")
            away_score = game.get("away_score")

            if not all([home_team, away_team, home_score, away_score]):
                continue

            try:
                # Get features for this game
                # Note: For training, we'd need historical stats at that point in time
                # This is a simplified version using current stats
                features = self.prepare_features(home_team, away_team)

                rows.append(features.iloc[0].to_dict())

                # Label: 1 if home team won
                labels.append(1 if home_score > away_score else 0)

            except Exception as e:
                logger.warning(f"Error preparing training features: {e}")
                continue

        if not rows:
            logger.warning("No valid training samples generated")
            return pd.DataFrame(), np.array([])

        X = pd.DataFrame(rows)
        y = np.array(labels)

        # Fill NaN with 0
        X = X.fillna(0)

        logger.info(f"Prepared {len(X)} training samples with {X.shape[1]} features")

        return X, y

    def get_feature_columns(self) -> List[str]:
        """
        Get list of feature column names.

        Returns:
            List of column names.
        """
        return [
            # Team ratings
            "home_off_rating",
            "home_def_rating",
            "away_off_rating",
            "away_def_rating",
            "home_win_pct",
            "away_win_pct",
            "home_pace",
            "away_pace",
            # Elo
            "home_elo",
            "away_elo",
            "elo_differential",
            # Rolling 5-game
            "home_eFG_5g",
            "home_TOV_5g",
            "home_OREB_5g",
            "home_FTr_5g",
            "away_eFG_5g",
            "away_TOV_5g",
            "away_OREB_5g",
            "away_FTr_5g",
            # Rolling 10-game
            "home_eFG_10g",
            "home_TOV_10g",
            "home_OREB_10g",
            "home_FTr_10g",
            "away_eFG_10g",
            "away_TOV_10g",
            "away_OREB_10g",
            "away_FTr_10g",
            # Net rating
            "home_net_rating_5g",
            "away_net_rating_5g",
            # Game context
            "is_home",
            "rest_days_home",
            "rest_days_away",
            "is_back_to_back_home",
            "is_back_to_back_away",
        ]

    def clear_cache(self) -> None:
        """Clear all cached data."""
        self._team_stats_cache.clear()
        self.rolling_calc.clear_cache()
        logger.info("StatsFeatureEngineer cache cleared")


# Convenience function
def get_stats_feature_engineer(sport: str = "nba") -> StatsFeatureEngineer:
    """
    Get or create a StatsFeatureEngineer instance.

    Args:
        sport: Sport type.

    Returns:
        Configured StatsFeatureEngineer.
    """
    return StatsFeatureEngineer(sport=sport)
