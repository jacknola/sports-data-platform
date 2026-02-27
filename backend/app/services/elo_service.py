"""
Elo Rating System for NBA and NCAAB teams.

Provides persistent Elo ratings with MOV-adjusted updates, home advantage,
and win probability calculations. Used as a feature for ML models and
as a standalone predictor.
"""

import os
import pickle
from pathlib import Path
from threading import Lock
from typing import Dict, Optional, Tuple, List

import numpy as np
from loguru import logger

# Default Elo parameters
DEFAULT_K_FACTOR = 20
DEFAULT_HOME_ADVANTAGE = 100
DEFAULT_INITIAL_RATING = 1500


class EloService:
    """
    Elo rating tracker with MOV-adjusted updates for sports teams.

    Supports NBA and NCAAB with configurable parameters. Thread-safe
    for concurrent updates. Persists ratings to disk.
    """

    def __init__(
        self,
        k_factor: float = DEFAULT_K_FACTOR,
        home_advantage: float = DEFAULT_HOME_ADVANTAGE,
        initial_rating: float = DEFAULT_INITIAL_RATING,
        sport: str = "nba",
    ):
        """
        Initialize Elo service.

        Args:
            k_factor: K-factor for rating updates (default 20).
            home_advantage: Elo points for home advantage (default 100).
            initial_rating: Starting rating for new teams (default 1500).
            sport: Sport type ('nba' or 'ncaab').
        """
        self.k_factor = k_factor
        self.home_advantage = home_advantage
        self.initial_rating = initial_rating
        self.sport = sport.lower()

        # Thread-safe storage
        self._ratings: Dict[str, float] = {}
        self._lock = Lock()

        # Try to load existing ratings
        self._load_from_disk()

    def _get_save_path(self) -> Path:
        """Get the file path for saving ratings."""
        base_dir = Path("models") / "elo"
        base_dir.mkdir(parents=True, exist_ok=True)
        return base_dir / f"{self.sport}_elo.pkl"

    def _load_from_disk(self) -> None:
        """Load ratings from disk if they exist."""
        path = self._get_save_path()
        if path.exists():
            try:
                with open(path, "rb") as f:
                    self._ratings = pickle.load(f)
                logger.info(f"Loaded {len(self._ratings)} Elo ratings from {path}")
            except Exception as e:
                logger.warning(f"Failed to load Elo ratings: {e}")
                self._ratings = {}

    def get_rating(self, team_name: str) -> float:
        """
        Get current Elo rating for a team.

        Args:
            team_name: Name of the team.

        Returns:
            Current Elo rating (initial_rating if team not found).
        """
        with self._lock:
            normalized = self._normalize_team_name(team_name)
            return self._ratings.get(normalized, self.initial_rating)

    def _normalize_team_name(self, team_name: str) -> str:
        """Normalize team name for consistent storage."""
        return team_name.strip().lower()

    def get_differential(self, home_team: str, away_team: str) -> float:
        """
        Calculate Elo differential (home rating - away rating).

        Args:
            home_team: Home team name.
            away_team: Away team name.

        Returns:
            Elo differential in points.
        """
        home_rating = self.get_rating(home_team)
        away_rating = self.get_rating(away_team)
        return home_rating - away_rating

    def predict_win_prob(self, home_team: str, away_team: str) -> float:
        """
        Predict win probability for home team.

        Uses Elo formula: P(home_win) = 1 / (1 + 10^((away_elo - home_elo - home_adv) / 400))

        Args:
            home_team: Home team name.
            away_team: Away team name.

        Returns:
            Probability of home team winning (0-1).
        """
        home_elo = self.get_rating(home_team)
        away_elo = self.get_rating(away_team)

        # Adjusted Elo includes home advantage
        adjusted_home_elo = home_elo + self.home_advantage

        # Calculate win probability using standard Elo formula
        rating_diff = adjusted_home_elo - away_elo
        win_prob = 1 / (1 + 10 ** (-rating_diff / 400))

        return win_prob

    def update(
        self, home_team: str, away_team: str, home_score: int, away_score: int
    ) -> Tuple[float, float]:
        """
        Update Elo ratings after a game.

        Uses MOV-adjusted K-factor: K * (1 + ln(1 + MOV)) * (actual - expected)

        Args:
            home_team: Home team name.
            away_team: Away team name.
            home_score: Home team score.
            away_team_score: Away team score.

        Returns:
            Tuple of (new_home_rating, new_away_rating).
        """
        # Get current ratings
        home_elo = self.get_rating(home_team)
        away_elo = self.get_rating(away_team)

        # Calculate expected scores
        adjusted_home_elo = home_elo + self.home_advantage
        home_win_prob = 1 / (1 + 10 ** ((away_elo - adjusted_home_elo) / 400))
        away_win_prob = 1 - home_win_prob

        # Actual results (1 for win, 0 for loss, 0.5 for tie)
        home_actual = (
            1.0
            if home_score > away_score
            else (0.5 if home_score == away_score else 0.0)
        )
        away_actual = 1.0 - home_actual

        # Calculate margin of victory
        mov = abs(home_score - away_score)

        # MOV-adjusted K-factor (capped at 2.0)
        mov_mult = min(2.0, 1 + np.log1p(mov))
        k_adjusted = self.k_factor * mov_mult

        # Calculate rating changes
        home_change = k_adjusted * (home_actual - home_win_prob)
        away_change = k_adjusted * (away_actual - away_win_prob)

        # Update ratings
        new_home_elo = home_elo + home_change
        new_away_elo = away_elo + away_change

        with self._lock:
            normalized_home = self._normalize_team_name(home_team)
            normalized_away = self._normalize_team_name(away_team)
            self._ratings[normalized_home] = new_home_elo
            self._ratings[normalized_away] = new_away_elo

        logger.debug(
            f"Elo update: {home_team} {home_elo:.1f} -> {new_home_elo:.1f} "
            f"({'+' if home_change >= 0 else ''}{home_change:.1f}), "
            f"{away_team} {away_elo:.1f} -> {new_away_elo:.1f} "
            f"({'+' if away_change >= 0 else ''}{away_change:.1f})"
        )

        return new_home_elo, new_away_elo

    def backfill_season(self, games: List[Dict]) -> None:
        """
        Process historical games to compute Elo ratings.

        Games should be ordered chronologically (oldest first).

        Args:
            games: List of game dicts with keys:
                - home_team: str
                - away_team: str
                - home_score: int
                - away_score: int
        """
        logger.info(f"Backfilling Elo from {len(games)} historical games")

        for i, game in enumerate(games):
            try:
                self.update(
                    home_team=game["home_team"],
                    away_team=game["away_team"],
                    home_score=game["home_score"],
                    away_score=game["away_score"],
                )
            except Exception as e:
                logger.warning(f"Error processing game {i}: {e}")

        logger.info(
            f"Elo backfill complete. Final ratings for {len(self._ratings)} teams. "
            f"Top: {self.get_top_teams(5)}"
        )

    def get_top_teams(self, n: int = 10) -> List[Tuple[str, float]]:
        """
        Get top N teams by Elo rating.

        Args:
            n: Number of teams to return.

        Returns:
            List of (team_name, rating) tuples, sorted by rating descending.
        """
        with self._lock:
            sorted_teams = sorted(
                self._ratings.items(), key=lambda x: x[1], reverse=True
            )
            return [(name.title(), rating) for name, rating in sorted_teams[:n]]

    def save(self, path: Optional[str] = None) -> None:
        """
        Save Elo ratings to disk.

        Args:
            path: Optional custom path. Uses default if not provided.
        """
        save_path = Path(path) if path else self._get_save_path()
        save_path.parent.mkdir(parents=True, exist_ok=True)

        with self._lock:
            with open(save_path, "wb") as f:
                pickle.dump(self._ratings, f)

        logger.info(f"Saved {len(self._ratings)} Elo ratings to {save_path}")

    def load(self, path: str) -> None:
        """
        Load Elo ratings from disk.

        Args:
            path: Path to saved ratings file.
        """
        with open(path, "rb") as f:
            self._ratings = pickle.load(f)

        logger.info(f"Loaded {len(self._ratings)} Elo ratings from {path}")

    def reset(self) -> None:
        """Reset all ratings to initial value."""
        with self._lock:
            self._ratings = {}
        logger.info("Elo ratings reset")


# Convenience function for quick use
def get_elo_service(sport: str = "nba") -> EloService:
    """
    Get or create an EloService instance.

    Args:
        sport: Sport type ('nba' or 'ncaab').

    Returns:
        Configured EloService instance.
    """
    return EloService(sport=sport)
