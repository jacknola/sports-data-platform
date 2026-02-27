"""Historical Data Fetcher for ML Training.

Fetches historical game data from nba_api for training ML models.
Uses the free nba_api (no API key required).
"""

import time
from pathlib import Path
from typing import Dict, List

import pandas as pd
from loguru import logger

try:
    from nba_api.stats.endpoints import leaguegamefinder
    from nba_api.stats.static import teams

    _NBA_API_AVAILABLE = True
except ImportError:
    _NBA_API_AVAILABLE = False
    logger.warning("nba_api not available")


# Rate limit: 0.6s between calls (nba_api limit)
API_RATE_LIMIT = 0.6

# Cache directory
CACHE_DIR = Path("/tmp/nba_ml_cache")


class HistoricalDataFetcher:
    """Fetches historical NBA game data for model training."""

    def __init__(self):
        self._teams_cache = None
        self._team_id_map = {}

    def _get_teams(self) -> List[Dict]:
        """Get list of NBA teams."""
        if self._teams_cache is not None:
            return self._teams_cache

        if not _NBA_API_AVAILABLE:
            raise RuntimeError("nba_api not available")

        self._teams_cache = teams.get_teams()

        # Build ID map
        for t in self._teams_cache:
            self._team_id_map[t["full_name"]] = t["id"]

        return self._teams_cache

    def get_team_id_by_name(self, team_name: str) -> int:
        """Get team ID by team name."""
        self._get_teams()
        return self._team_id_map.get(team_name)

    def fetch_nba_seasons(
        self, start_year: int = 2024, end_year: int = 2025
    ) -> Dict[str, pd.DataFrame]:
        """Fetch NBA games organized by season."""
        seasons = {}

        for year in range(start_year, end_year + 1):
            season = f"{year}-{str(year + 1)[2:]}"
            logger.info(f"Fetching {season} season...")

            # Check cache
            cache_file = CACHE_DIR / f"nba_{season}.pkl"
            if cache_file.exists():
                logger.info(f"Loading {season} from cache")
                seasons[season] = pd.read_pickle(cache_file)
                continue

            if not _NBA_API_AVAILABLE:
                raise RuntimeError("nba_api not available")

            try:
                time.sleep(API_RATE_LIMIT)

                game_finder = leaguegamefinder.LeagueGameFinder(
                    season_nullable=season,
                    season_type_nullable="Regular Season",
                )
                games = game_finder.get_data_frames()[0]

                if games is not None and not games.empty:
                    games["season"] = season
                    games.to_pickle(cache_file)
                    seasons[season] = games
                    logger.info(f"  Fetched {len(games)} games")

            except Exception as e:
                logger.error(f"Error fetching {season}: {e}")
                continue

        return seasons

    def fetch_nba_games(
        self, start_year: int = 2024, end_year: int = 2025
    ) -> pd.DataFrame:
        """Fetch NBA games for a range of seasons."""
        cache_key = f"nba_seasons_{start_year}_{end_year}"
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        cache_file = CACHE_DIR / f"{cache_key}.pkl"

        # Check file cache
        if cache_file.exists():
            logger.info(f"Loading cached games from {cache_file}")
            return pd.read_pickle(cache_file)

        all_games = []
        teams = self._get_teams()

        for year in range(start_year, end_year + 1):
            season = f"{year}-{str(year + 1)[2:]}"
            logger.info(f"Fetching {season} season ({year})...")

            try:
                time.sleep(API_RATE_LIMIT)

                game_finder = leaguegamefinder.LeagueGameFinder(
                    season_nullable=season,
                    season_type_nullable="Regular Season",
                )
                games = game_finder.get_data_frames()[0]

                if games is not None and not games.empty:
                    games["season"] = season
                    all_games.append(games)
                    logger.info(f"  Fetched {len(games)} games")

            except Exception as e:
                logger.error(f"Error fetching {season}: {e}")
                continue

        if not all_games:
            logger.warning("No games fetched")
            return pd.DataFrame()

        df = pd.concat(all_games, ignore_index=True)
        df.to_pickle(cache_file)
        logger.info(f"Cached {len(df)} games to {cache_file}")

        return df

    def _pair_game_rows(self, raw: pd.DataFrame) -> pd.DataFrame:
        """Convert per-team rows (leaguegamefinder) to per-game paired rows.

        leaguegamefinder returns one row per team per game. This method pairs
        home/away rows using GAME_ID + MATCHUP pattern ("vs." = home, "@" = away).

        Returns:
            DataFrame with: game_id, date, season, home_team, away_team,
            home_score, away_score, home_win
        """
        if raw.empty:
            return pd.DataFrame()

        required = {
            "GAME_ID",
            "GAME_DATE",
            "TEAM_NAME",
            "PTS",
            "WL",
            "MATCHUP",
            "season",
        }
        missing = required - set(raw.columns)
        if missing:
            logger.warning(f"Raw data missing columns for pairing: {missing}")
            return pd.DataFrame()

        home_mask = raw["MATCHUP"].str.contains("vs.", na=False, regex=False)

        home_df = raw[home_mask][
            ["GAME_ID", "GAME_DATE", "TEAM_NAME", "PTS", "WL", "season"]
        ].copy()
        away_df = raw[~home_mask][["GAME_ID", "TEAM_NAME", "PTS"]].copy()

        home_df = home_df.rename(
            columns={
                "TEAM_NAME": "home_team",
                "PTS": "home_score",
                "WL": "home_wl",
                "GAME_DATE": "date",
            }
        )
        away_df = away_df.rename(
            columns={
                "TEAM_NAME": "away_team",
                "PTS": "away_score",
            }
        )

        paired = home_df.merge(away_df, on="GAME_ID", how="inner")
        paired["home_win"] = paired["home_wl"] == "W"
        paired = paired.drop(columns=["home_wl"])
        paired["date"] = pd.to_datetime(paired["date"])
        paired = paired.sort_values("date").reset_index(drop=True)
        paired = paired.rename(columns={"GAME_ID": "game_id"})

        logger.info(f"Paired {len(paired)} games from {len(raw)} team-game rows")
        return paired

    def fetch_nba_games_paired(
        self, start_year: int = 2024, end_year: int = 2025
    ) -> pd.DataFrame:
        """Fetch NBA games as paired home/away records.

        Wraps fetch_nba_games() and converts the raw one-row-per-team-per-game
        format into one row per game with home_team, away_team, home_score,
        away_score, and home_win columns.

        Returns:
            DataFrame with: game_id, date, season, home_team, away_team,
            home_score, away_score, home_win
        """
        raw = self.fetch_nba_games(start_year=start_year, end_year=end_year)

        paired_cols = {"home_team", "away_team", "home_score", "away_score"}
        if paired_cols.issubset(set(raw.columns)):
            paired = raw.copy()
            if "date" in paired.columns:
                paired["date"] = pd.to_datetime(paired["date"])
                paired = paired.sort_values("date").reset_index(drop=True)
            logger.info(f"Loaded {len(paired)} already-paired games from cache")
            return paired

        return self._pair_game_rows(raw)

    def fetch_nba_games_by_team(
        self, team_id: int, season: str = "2024-25"
    ) -> pd.DataFrame:
        """Fetch games for a specific team and season."""
        if not _NBA_API_AVAILABLE:
            raise RuntimeError("nba_api not available")

        try:
            time.sleep(API_RATE_LIMIT)

            game_finder = leaguegamefinder.LeagueGameFinder(
                team_id_nullable=team_id,
                season_nullable=season,
                season_type_nullable="Regular Season",
            )
            return game_finder.get_data_frames()[0]

        except Exception as e:
            logger.error(f"Error fetching games for team {team_id}: {e}")
            return pd.DataFrame()


def fetch_nba_games(start_year: int = 2024, end_year: int = 2025) -> pd.DataFrame:
    """Convenience function to fetch NBA games."""
    fetcher = HistoricalDataFetcher()
    return fetcher.fetch_nba_games(start_year, end_year)


def fetch_nba_games_paired(
    start_year: int = 2024, end_year: int = 2025
) -> pd.DataFrame:
    """Convenience function to fetch paired NBA game records."""
    fetcher = HistoricalDataFetcher()
    return fetcher.fetch_nba_games_paired(start_year, end_year)


def fetch_ncaab_games(start_year: int = 2024, end_year: int = 2025) -> pd.DataFrame:
    """Placeholder for NCAAB - nba_api doesn't support college basketball."""
    logger.warning(
        "NCAAB fetching not implemented - nba_api doesn't support college basketball"
    )
    return pd.DataFrame()
