"""
NBA Machine Learning Predictor Service
Integrated with kyleskom/NBA-Machine-Learning-Sports-Betting approach
"""

import os
import pickle
from typing import Dict, Any, List, Optional
from datetime import datetime
import numpy as np
import pandas as pd
from loguru import logger

from app.services.sports_api import SportsAPIService

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

            return {
                "home_team": home_team,
                "away_team": away_team,
                "moneyline_prediction": moneyline_pred,
                "underover_prediction": underover_pred,
                "expected_value": ev,
                "kelly_criterion": kelly,
                "confidence": moneyline_pred.get("confidence", 0.5),
                "method": "ml_xgboost"
                if XGBOOST_AVAILABLE and "moneyline" in self.models
                else "placeholder",
            }

        except Exception as e:
            logger.error(f"Prediction error: {e}")
            return {"error": str(e), "home_team": home_team, "away_team": away_team}

    def _prepare_features(self, features: Dict[str, Any]) -> pd.DataFrame:
        """Prepare features for ML model input"""
        feature_dict = {
            "home_off_rating": features.get("home_off_rating", 110.0),
            "home_def_rating": features.get("home_def_rating", 110.0),
            "away_off_rating": features.get("away_off_rating", 110.0),
            "away_def_rating": features.get("away_def_rating", 110.0),
            "home_win_pct": features.get("home_win_pct", 0.5),
            "away_win_pct": features.get("away_win_pct", 0.5),
            "home_recent_form": features.get("home_recent_form", [1, 1, 1, 0, 1]),
            "away_recent_form": features.get("away_recent_form", [1, 1, 0, 1, 0]),
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

                return {
                    "winner": "home" if winner_prob > 0.5 else "away",
                    "home_win_prob": winner_prob,
                    "away_win_prob": 1 - winner_prob,
                    "confidence": abs(winner_prob - 0.5) * 2,  # 0 to 1 scale
                }
            except Exception as e:
                logger.error(f"Moneyline prediction error: {e}")

        # Fallback to placeholder (slight home court advantage)
        home_win_prob = 0.54
        if (
            "home_off_rating" in features.columns
            and "away_off_rating" in features.columns
        ):
            # Simple heuristic for placeholder
            net_home = (
                features["home_off_rating"].iloc[0]
                - features["home_def_rating"].iloc[0]
            )
            net_away = (
                features["away_off_rating"].iloc[0]
                - features["away_def_rating"].iloc[0]
            )
            diff = net_home - net_away
            # 1 point diff ~ 3% win prob change
            home_win_prob = 0.54 + (diff * 0.03)
            home_win_prob = max(0.1, min(0.9, home_win_prob))

        return {
            "winner": "home" if home_win_prob > 0.5 else "away",
            "home_win_prob": home_win_prob,
            "away_win_prob": 1.0 - home_win_prob,
            "confidence": abs(home_win_prob - 0.5) * 2,
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

        # Fallback
        return {
            "total_points": 220,
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

        # Convert American odds to decimal
        def american_to_decimal(odds):
            if odds > 0:
                return odds / 100 + 1
            else:
                return 100 / abs(odds) + 1

        home_decimal = american_to_decimal(home_odds)
        away_decimal = american_to_decimal(away_odds)

        # Calculate EV
        home_ev = (moneyline_pred["home_win_prob"] * (home_decimal - 1)) - (
            1 - moneyline_pred["home_win_prob"]
        )
        away_ev = (moneyline_pred["away_win_prob"] * (away_decimal - 1)) - (
            1 - moneyline_pred["away_win_prob"]
        )

        return {
            "home_ev": home_ev,
            "away_ev": away_ev,
            "best_bet": "home" if home_ev > away_ev else "away",
            "home_odds": home_odds,
            "away_odds": away_odds,
        }

    def _calculate_kelly(self, edge: float, probability: float) -> float:
        """Calculate Kelly Criterion bet size"""
        if edge <= 0 or probability <= 0 or probability >= 1:
            return 0.0

        # Kelly fraction = p - (q / b) = edge / b
        # where p = win prob, q = lose prob = 1-p
        # edge = p * b - q (if b is decimal odds - 1)
        # It's better to just do: kelly = edge / (decimal_odds - 1)
        # But based on the original code:
        # edge / (1 - prob) is a simplification (assumes odds = 1/prob_implied)
        kelly = edge / (1 - probability)

        # Scale to quarter Kelly (0.25)
        kelly = kelly * 0.25

        # Cap at 5% of bankroll for safety per bet
        return min(kelly, 0.05)

    async def predict_today_games(self, sport: str = "nba") -> List[Dict[str, Any]]:
        """
        Get predictions for today's games using live Odds API and NBA API stats

        Args:
            sport: Sport to predict (currently NBA only)

        Returns:
            List of game predictions
        """
        logger.info(f"Getting live predictions for today's {sport.upper()} games")

        # 1. Fetch Live Odds
        odds_data = await self.sports_api.get_odds("basketball_nba")

        games = []
        if odds_data:
            # 2. Fetch Live Stats
            stats_df = self._fetch_live_team_stats()

            for game in odds_data:
                home_team = game.get("home_team")
                away_team = game.get("away_team")

                # Extract odds
                bookmakers = game.get("bookmakers", [])
                home_odds = -110
                away_odds = -110

                # Try to find pinnacle or draftkings/fanduel
                target_books = ["pinnacle", "draftkings", "fanduel", "bovada"]
                for book in target_books:
                    b_data = next((b for b in bookmakers if b["key"] == book), None)
                    if b_data:
                        h2h = next(
                            (m for m in b_data["markets"] if m["key"] == "h2h"), None
                        )
                        if h2h and len(h2h["outcomes"]) == 2:
                            for out in h2h["outcomes"]:
                                if out["name"] == home_team:
                                    home_odds = out["price"]
                                elif out["name"] == away_team:
                                    away_odds = out["price"]
                            break

                features = {"odds": {"home": home_odds, "away": away_odds}}

                # Inject live stats if available
                if not stats_df.empty:
                    home_id = self._get_team_id(str(home_team)) if home_team else None
                    away_id = self._get_team_id(str(away_team)) if away_team else None

                    if home_id:
                        h_stats = stats_df[stats_df["TEAM_ID"] == home_id]
                        if not h_stats.empty:
                            features["home_off_rating"] = h_stats.iloc[0]["OFF_RATING"]
                            features["home_def_rating"] = h_stats.iloc[0]["DEF_RATING"]
                            features["home_win_pct"] = h_stats.iloc[0]["W_PCT"]

                    if away_id:
                        a_stats = stats_df[stats_df["TEAM_ID"] == away_id]
                        if not a_stats.empty:
                            features["away_off_rating"] = a_stats.iloc[0]["OFF_RATING"]
                            features["away_def_rating"] = a_stats.iloc[0]["DEF_RATING"]
                            features["away_win_pct"] = a_stats.iloc[0]["W_PCT"]

                games.append(
                    {
                        "home_team": home_team,
                        "away_team": away_team,
                        "features": features,
                    }
                )
        else:
            logger.warning("No live odds found. Using placeholder games.")
            games = [
                {
                    "home_team": "Los Angeles Lakers",
                    "away_team": "Golden State Warriors",
                    "features": {
                        "home_off_rating": 115.2,
                        "home_def_rating": 112.5,
                        "away_off_rating": 118.0,
                        "away_def_rating": 113.8,
                        "home_win_pct": 0.55,
                        "away_win_pct": 0.62,
                        "home_recent_form": [1, 1, 0, 1, 1],
                        "away_recent_form": [1, 0, 1, 1, 1],
                        "odds": {"home": -110, "away": -110},
                        "over_under": 230.5,
                    },
                }
            ]

        predictions = []
        for game in games:
            pred = await self.predict_game(
                game["home_team"], game["away_team"], game["features"]
            )
            predictions.append(pred)

        return predictions
