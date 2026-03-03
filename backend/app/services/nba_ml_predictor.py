"""
NBA Machine Learning Predictor Service
Integrated with kyleskom/NBA-Machine-Learning-Sports-Betting approach
"""

import os
import pickle
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
import numpy as np
import pandas as pd
from loguru import logger

from app.services.sports_api import SportsAPIService

try:
    from app.services.stats_feature_engineering import StatsFeatureEngineer
    from app.services.elo_service import EloService

    STATS_FEATURES_AVAILABLE = True
except ImportError:
    STATS_FEATURES_AVAILABLE = False
    logger.warning("StatsFeatureEngineer not available - using legacy features")

try:
    from nba_api.stats.endpoints import leaguedashteamstats
    from nba_api.stats.static import teams

    NBA_API_AVAILABLE = True
except ImportError:
    NBA_API_AVAILABLE = False
    logger.warning("nba_api not installed, live stats disabled")

try:
    import xgboost as xgb

    XGBOOST_AVAILABLE = True
except ImportError:
    XGBOOST_AVAILABLE = False
    logger.warning("XGBoost not installed, ML predictions disabled")


def _american_to_decimal(odds: float) -> float:
    """Convert American odds to decimal odds."""
    if odds > 0:
        return odds / 100.0 + 1.0
    return 100.0 / abs(odds) + 1.0


# Priority order for bookmaker selection (sharp books first, then retail)
PRIORITY_BOOKS = ["pinnacle", "fanduel", "draftkings", "circa", "bovada"]

# NBA advanced stats columns sourced from nba_api LeagueDashTeamStats
_TEAM_STAT_COLS = ("OFF_RATING", "DEF_RATING", "W_PCT", "PACE")

# Default values used when live team stats are unavailable
_DEFAULT_RATING = 110.0
_DEFAULT_WIN_PCT = 0.5


class NBAMLPredictor:
    """NBA betting predictions using machine learning"""

    def __init__(self):
        self.models = {}
        self.data_cache = {}
        self.sports_api = SportsAPIService()
        self._load_models()
        self.team_stats_cache = None
        self.nba_teams = []
        if NBA_API_AVAILABLE:
            self.nba_teams = teams.get_teams()

        if STATS_FEATURES_AVAILABLE:
            self.stats_engineer = StatsFeatureEngineer(sport="nba")
            self.elo_service = EloService(sport="nba")
            logger.info("StatsFeatureEngineer initialized for stats-only predictions")
        else:
            self.stats_engineer = None
            self.elo_service = None

    def _load_models(self):
        """Load trained ML models"""
        try:
            model_path = os.getenv("NBA_MODEL_PATH", "./models/nba_ml")

            # Load XGBoost models if available
            if XGBOOST_AVAILABLE and os.path.exists(model_path):
                try:
                    with open(f"{model_path}/moneyline_model.pkl", "rb") as f:
                        self.models["moneyline"] = pickle.load(f)

                    with open(f"{model_path}/underover_model.pkl", "rb") as f:
                        self.models["underover"] = pickle.load(f)

                    logger.info("NBA ML models loaded successfully")
                except Exception as e:
                    logger.warning(f"Could not load NBA models: {e}")
                    self._initialize_placeholder_models()
            else:
                logger.warning("Model files not found, using placeholder models")
                self._initialize_placeholder_models()

        except Exception as e:
            logger.error(f"Error loading NBA models: {e}")
            self._initialize_placeholder_models()

    def _initialize_placeholder_models(self):
        """Initialize placeholder models for testing"""
        logger.info("Initializing placeholder models")
        # These would be replaced with actual trained models

    def _get_team_id(self, team_name: str) -> Optional[int]:
        """Find NBA API team ID by name"""
        # Sometimes Odds API has names like 'Los Angeles Lakers', nba_api uses full names too
        # We'll do a simple substring match
        for t in self.nba_teams:
            if (
                team_name.lower() in t["full_name"].lower()
                or t["full_name"].lower() in team_name.lower()
            ):
                return t["id"]
            if t["nickname"].lower() in team_name.lower():
                return t["id"]
        return None

    def _fetch_live_team_stats(self) -> pd.DataFrame:
        """Fetch live stats using nba_api and cache them"""
        if self.team_stats_cache is not None:
            return self.team_stats_cache

        if not NBA_API_AVAILABLE:
            logger.warning("nba_api unavailable, returning empty stats")
            return pd.DataFrame()

        try:
            logger.info("Fetching live advanced team stats from NBA API...")
            stats = leaguedashteamstats.LeagueDashTeamStats(
                measure_type_detailed_defense="Advanced"
            )
            df = stats.get_data_frames()[0]
            self.team_stats_cache = df
            return df
        except Exception as e:
            logger.error(f"Failed to fetch nba_api stats: {e}")
            return pd.DataFrame()

    async def predict_game(
        self, home_team: str, away_team: str, features: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Predict game outcome using ML models

        Args:
            home_team: Home team name
            away_team: Away team name
            features: Team features and statistics

        Returns:
            Prediction with probabilities and expected value
        """
        logger.info(f"Predicting {away_team} @ {home_team}")

        try:
            # Prepare features for model
            model_features = self._prepare_features(features)

            # Get predictions
            moneyline_pred = self._predict_moneyline(model_features)
            underover_pred = self._predict_underover(model_features)

            # Calculate expected value
            ev = self._calculate_expected_value(
                moneyline_pred, features.get("odds", {})
            )

            # Kelly Criterion
            kelly = self._calculate_kelly(
                ev.get("home_ev", 0)
                if ev.get("best_bet") == "home"
                else ev.get("away_ev", 0),
                moneyline_pred.get("home_win_prob", 0.5)
                if ev.get("best_bet") == "home"
                else moneyline_pred.get("away_win_prob", 0.5),
            )

            # Extract season win percentage values for the two teams, if available
            # These values come from the features used to build the model input
            # and/or from the moneyline prediction when available.
            season_w_pct_home = None
            season_w_pct_away = None
            try:
                # moneyline_pred may include the raw season W_PCT values if _predict_moneyline
                # already populated them (new in this patch). Fall back to input features.
                season_w_pct_home = moneyline_pred.get("home_season_w_pct")
                season_w_pct_away = moneyline_pred.get("away_season_w_pct")
            except Exception:
                season_w_pct_home = None
                season_w_pct_away = None

            if season_w_pct_home is None or season_w_pct_away is None:
                season_w_pct_home = features.get("home_win_pct", _DEFAULT_WIN_PCT)  # type: ignore
                season_w_pct_away = features.get("away_win_pct", _DEFAULT_WIN_PCT)  # type: ignore

            return {
                "home_team": home_team,
                "away_team": away_team,
                "moneyline_prediction": moneyline_pred,
                "underover_prediction": underover_pred,
                "expected_value": ev,
                "kelly_criterion": kelly,
                "confidence": float(moneyline_pred.get("confidence", 0.5)),
                # Expose season win percentage data for downstream exports (e.g., Google Sheets)
                "season_w_pct_home": season_w_pct_home,
                "season_w_pct_away": season_w_pct_away,
                # Core feature snapshot used for this prediction (for traceability)
                "features": {
                    "home_off_rating": features.get("home_off_rating", _DEFAULT_RATING),
                    "home_def_rating": features.get("home_def_rating", _DEFAULT_RATING),
                    "away_off_rating": features.get("away_off_rating", _DEFAULT_RATING),
                    "away_def_rating": features.get("away_def_rating", _DEFAULT_RATING),
                    "home_win_pct": features.get("home_win_pct", _DEFAULT_WIN_PCT),
                    "away_win_pct": features.get("away_win_pct", _DEFAULT_WIN_PCT),
                },
                # Market data – populated by predict_today_games(); empty by default
                "spread": {},
                "total": {},
                "book": "",
                "method": "ml_xgboost"
                if XGBOOST_AVAILABLE and "moneyline" in self.models
                else "placeholder",
            }

        except Exception as e:
            logger.error(f"Prediction error: {e}")
            return {"error": str(e), "home_team": home_team, "away_team": away_team}

    def _prepare_features(self, features: Dict[str, Any]) -> pd.DataFrame:
        """Prepare features for ML model input"""

        if STATS_FEATURES_AVAILABLE and self.stats_engineer is not None:
            home_team = features.get("home_team") or features.get("home_team_name")
            away_team = features.get("away_team") or features.get("away_team_name")

            if home_team and away_team:
                try:
                    stats_features = self.stats_engineer.prepare_features(
                        home_team, away_team
                    )
                    logger.debug(
                        f"Using stats-only features for {home_team} vs {away_team}"
                    )
                    return stats_features
                except Exception as e:
                    logger.warning(f"Stats feature engineering failed: {e}")

        feature_dict = {
            "home_off_rating": features.get("home_off_rating", _DEFAULT_RATING),
            "home_def_rating": features.get("home_def_rating", _DEFAULT_RATING),
            "away_off_rating": features.get("away_off_rating", _DEFAULT_RATING),
            "away_def_rating": features.get("away_def_rating", _DEFAULT_RATING),
            "home_win_pct": features.get("home_win_pct", _DEFAULT_WIN_PCT),
            "away_win_pct": features.get("away_win_pct", _DEFAULT_WIN_PCT),
            "home_recent_form": features.get("home_recent_form", [1, 1, 1, 0, 1]),
            "away_recent_form": features.get("away_recent_form", [1, 1, 0, 1, 0]),
            "home_pace": features.get("home_pace", 100.0),
            "away_pace": features.get("away_pace", 100.0),
        }

        return pd.DataFrame([feature_dict])

    def _predict_moneyline(self, features: pd.DataFrame) -> Dict[str, Any]:
        """Predict moneyline winner"""
        if "moneyline" in self.models:
            model = self.models["moneyline"]
            try:
                # Get prediction
                pred = model.predict_proba(features)[0]
                winner_prob = pred[1]  # Assuming 1 is home win

                # Determine season win percentages from input features if available
                home_w_pct = 0.5
                away_w_pct = 0.5
                try:
                    if (
                        isinstance(features, pd.DataFrame)
                        and "home_win_pct" in features.columns
                    ):
                        home_w_pct = float(features["home_win_pct"].iloc[0])
                    if (
                        isinstance(features, pd.DataFrame)
                        and "away_win_pct" in features.columns
                    ):
                        away_w_pct = float(features["away_win_pct"].iloc[0])
                except Exception:
                    home_w_pct, away_w_pct = 0.5, 0.5

                return {
                    "winner": "home" if winner_prob > 0.5 else "away",
                    "home_win_prob": float(winner_prob),
                    "away_win_prob": float(1 - winner_prob),
                    "confidence": float(abs(winner_prob - 0.5) * 2),  # 0 to 1 scale
                    # Expose season win percentage data for downstream exports (e.g., Google Sheets)
                    "home_season_w_pct": float(home_w_pct),
                    "away_season_w_pct": float(away_w_pct),
                }
            except Exception as e:
                logger.error(f"Moneyline prediction error: {e}")

        # Fallback to robust statistical model (Pythagorean Expectation)
        home_win_prob = 0.54
        if (
            "home_off_rating" in features.columns
            and "away_off_rating" in features.columns
        ):
            h_off = features["home_off_rating"].iloc[0]
            h_def = features["home_def_rating"].iloc[0]
            a_off = features["away_off_rating"].iloc[0]
            a_def = features["away_def_rating"].iloc[0]

            # League average baseline
            league_avg = 115.0

            # Projected points per 100 possessions
            h_proj = (h_off * a_def) / league_avg
            a_proj = (a_off * h_def) / league_avg

            logger.debug(
                f"Ratings: H_Off={h_off}, H_Def={h_def}, A_Off={a_off}, A_Def={a_def} | Proj: H={h_proj:.1f}, A={a_proj:.1f}"
            )

            try:
                # Pythagorean win prob
                home_win_prob = (h_proj**14.0) / (h_proj**14.0 + a_proj**14.0)
                # Home court advantage (~3% boost)
                home_win_prob += 0.03
                home_win_prob = max(0.05, min(0.95, home_win_prob))
            except (OverflowError, ZeroDivisionError):
                home_win_prob = 0.54

        return {
            "winner": "home" if home_win_prob > 0.5 else "away",
            "home_win_prob": float(home_win_prob),
            "away_win_prob": float(1.0 - home_win_prob),
            "confidence": float(abs(home_win_prob - 0.5) * 2),
        }

    def _predict_underover(self, features: pd.DataFrame) -> Dict[str, Any]:
        """Predict over/under"""
        if "underover" in self.models:
            model = self.models["underover"]
            try:
                pred = model.predict(features)[0]
                prob = model.predict_proba(features)[0]

                return {
                    "total_points": pred,
                    "over_prob": prob[1] if len(prob) > 1 else 0.5,
                    "under_prob": prob[0] if len(prob) > 1 else 0.5,
                    "recommendation": "over" if prob[1] > 0.5 else "under",
                }
            except Exception as e:
                logger.error(f"Under/over prediction error: {e}")

        # Fallback using stats if available
        projected_total = 220.0
        if "home_pace" in features.columns and "home_off_rating" in features.columns:
            try:
                h_pace = features["home_pace"].iloc[0]
                a_pace = features["away_pace"].iloc[0]
                h_off = features["home_off_rating"].iloc[0]
                a_off = features["away_off_rating"].iloc[0]
                h_def = features["home_def_rating"].iloc[0]
                a_def = features["away_def_rating"].iloc[0]

                # Estimate game pace
                game_pace = (h_pace + a_pace) / 2.0

                # Estimate points per 100 possessions
                # Simple avg of offense and opposing defense
                h_ppp = (h_off + a_def) / 2.0
                a_ppp = (a_off + h_def) / 2.0

                projected_total = (game_pace / 100.0) * (h_ppp + a_ppp)
            except (IndexError, KeyError, TypeError):
                pass

        return {
            "total_points": round(projected_total, 1),
            "over_prob": 0.52,
            "under_prob": 0.48,
            "recommendation": "over",
        }

    def _calculate_expected_value(
        self, moneyline_pred: Dict[str, Any], odds: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Calculate expected value for bets"""

        home_odds = odds.get("home", -110)
        away_odds = odds.get("away", 110)

        home_decimal = _american_to_decimal(home_odds)
        away_decimal = _american_to_decimal(away_odds)

        # Calculate EV
        home_ev = (moneyline_pred["home_win_prob"] * (home_decimal - 1)) - (
            1 - moneyline_pred["home_win_prob"]
        )
        away_ev = (moneyline_pred["away_win_prob"] * (away_decimal - 1)) - (
            1 - moneyline_pred["away_win_prob"]
        )

        best_bet: Optional[str] = None
        if home_ev > away_ev and home_ev > 0:
            best_bet = "home"
        elif away_ev > home_ev and away_ev > 0:
            best_bet = "away"

        return {
            "home_ev": home_ev,
            "away_ev": away_ev,
            "best_bet": best_bet,
            "home_odds": home_odds,
            "away_odds": away_odds,
        }

    def _calculate_kelly(self, edge: float, probability: float) -> float:
        """Calculate Kelly Criterion bet size using dynamic settings"""
        from app.config import settings

        if edge <= 0 or probability <= 0 or probability >= 1:
            return 0.0

        # Kelly fraction = p - (q / b) = edge / b
        # where p = win prob, q = lose prob = 1-p
        # edge = p * b - q (if b is decimal odds - 1)
        # kelly = edge / b
        # Re-derive b from edge and p: b = (edge + q) / p
        q = 1.0 - probability
        b = (edge + q) / probability
        full_kelly = edge / b

        # Determine fractional multiplier based on edge thresholds
        if edge >= settings.EDGE_THRESHOLD_MEDIUM:
            multiplier = settings.KELLY_FRACTION_HALF
        elif edge >= settings.EDGE_THRESHOLD_LOW:
            multiplier = settings.KELLY_FRACTION_QUARTER
        else:
            return 0.0

        kelly_stake = full_kelly * multiplier

        # Cap at global max bet percentage (5% by default)
        return max(0.0, min(kelly_stake, settings.MAX_BET_PERCENTAGE))

    def _parse_game_bookmakers(
        self,
        game: Dict[str, Any],
        stats_df: pd.DataFrame,
    ) -> Dict[str, Any]:
        """
        Parse bookmaker data for a single Odds API game object into a normalised
        game dict ready for ``predict_game()``.

        Returns a dict with keys: home_team, away_team, features, spread, total, book.
        """
        home_team = game.get("home_team")
        away_team = game.get("away_team")
        bookmakers = game.get("bookmakers", [])
        home_odds = -110
        away_odds = -110

        spread_data: Dict[str, Any] = {}
        total_data: Dict[str, Any] = {}
        best_book_used = ""

        for book in PRIORITY_BOOKS:
            b_data = next((b for b in bookmakers if b["key"] == book), None)
            if not b_data:
                continue

            # --- h2h (moneyline) ---
            h2h = next((m for m in b_data["markets"] if m["key"] == "h2h"), None)
            if h2h and len(h2h["outcomes"]) == 2:
                for out in h2h["outcomes"]:
                    if out["name"] == home_team:
                        home_odds = round(out["price"])
                    elif out["name"] == away_team:
                        away_odds = round(out["price"])

            # --- spreads ---
            sp = next((m for m in b_data["markets"] if m["key"] == "spreads"), None)
            if sp and not spread_data:
                for out in sp.get("outcomes", []):
                    if out["name"] == home_team:
                        spread_data["home_point"] = out.get("point", 0)
                        spread_data["home_odds"] = round(out.get("price", -110))
                    elif out["name"] == away_team:
                        spread_data["away_point"] = out.get("point", 0)
                        spread_data["away_odds"] = round(out.get("price", -110))
                spread_data["book"] = b_data["key"]

            # --- totals ---
            tot = next((m for m in b_data["markets"] if m["key"] == "totals"), None)
            if tot and not total_data:
                for out in tot.get("outcomes", []):
                    if out["name"] == "Over":
                        total_data["over_odds"] = round(out.get("price", -110))
                        total_data["point"] = out.get("point", 0)
                    elif out["name"] == "Under":
                        total_data["under_odds"] = round(out.get("price", -110))
                total_data["book"] = b_data["key"]

            if not best_book_used:
                best_book_used = b_data["key"]
            break

        features: Dict[str, Any] = {"odds": {"home": home_odds, "away": away_odds}}

        # Inject live stats if available
        if not stats_df.empty:
            home_id = self._get_team_id(str(home_team)) if home_team else None
            away_id = self._get_team_id(str(away_team)) if away_team else None

            # Column → feature-key prefixes for home and away
            stat_prefixes = (("home", home_id, stats_df), ("away", away_id, stats_df))
            for prefix, team_id, df in stat_prefixes:
                if not team_id:
                    continue
                row = df[df["TEAM_ID"] == team_id]
                if row.empty:
                    continue
                r = row.iloc[0]
                features[f"{prefix}_off_rating"] = float(r["OFF_RATING"])
                features[f"{prefix}_def_rating"] = float(r["DEF_RATING"])
                features[f"{prefix}_win_pct"] = float(r["W_PCT"])
                features[f"{prefix}_pace"] = float(r["PACE"])

        return {
            "home_team": home_team,
            "away_team": away_team,
            "features": features,
            "spread": spread_data,
            "total": total_data,
            "book": best_book_used,
        }

    async def predict_today_games(self, sport: str = "nba", prediction_only: bool = False) -> List[Dict[str, Any]]:
        """
        Get predictions for today's games using multi-source discovery + live odds.

        Game discovery waterfall:
            1. ESPN NBA Scoreboard (free, no key)
            2. Odds API /odds (existing path)
            3. No more hardcoded placeholder — return empty if both fail

        Args:
            sport: Sport to predict (currently NBA only)

        Returns:
            List of game predictions
        """
        logger.info(f"Getting live predictions for today's {sport.upper()} games")

        # 1. Discover games via ESPN first (free, no credit cost)
        discovery = await self.sports_api.discover_games("basketball_nba")
        espn_games = discovery.data

        if espn_games:
            logger.info(
                f"NBA game discovery: {len(espn_games)} games via {discovery.source}"
            )

        odds_data = await self.sports_api.get_odds("basketball_nba")
        games = []

        if odds_data:
            # 2. Fetch Live Stats
            stats_df = self._fetch_live_team_stats()

            for game in odds_data:
                games.append(self._parse_game_bookmakers(game, stats_df))

        elif espn_games:
            logger.warning(
                f"Odds API returned no NBA data. Using {len(espn_games)} ESPN games "
                f"with default -110/-110 odds."
            )
            for eg in espn_games:
                games.append(
                    {
                        "home_team": eg.get("home_team", ""),
                        "away_team": eg.get("away_team", ""),
                        "features": {"odds": {"home": -110, "away": -110}},
                    }
                )
        else:
            logger.error(
                "NBA: Both ESPN and Odds API returned no games. "
                "No placeholder — returning empty predictions."
            )

        predictions = []
        for game in games:
            pred = await self.predict_game(
                game["home_team"], game["away_team"], game["features"]
            )
            # Attach market data from raw odds
            pred["spread"] = game.get("spread", {})
            pred["total"] = game.get("total", {})
            pred["book"] = game.get("book", "")
            predictions.append(pred)

        return predictions
