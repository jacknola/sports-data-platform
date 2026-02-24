"""
NCAAB Team Efficiency +EV Analyzer Service

NCAAB equivalent of the NBA DvP analyzer. Since positional defense data
isn't available for college basketball, this uses team-level efficiency
metrics (ORtg, DRtg, pace) derived from ESPN and Odds API data.

Pipeline:
    1. Load slate from Odds API or static config
    2. Fetch team efficiency metrics (ORtg, DRtg, pace)
    3. Compute implied team totals from spread + O/U
    4. Apply efficiency-based matchup modifiers
    5. Flag value based on implied totals vs efficiency projections
    6. Output recommendations for game totals and team totals
"""
import asyncio
import json
import os
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from loguru import logger

from app.services.ncaab_stats_service import NCAABStatsService


# League-average baselines (D1 NCAAB 2024-25)
LEAGUE_AVG_ORTG = 106.0
LEAGUE_AVG_DRTG = 106.0
LEAGUE_AVG_PACE = 68.0  # NCAAB pace is much lower than NBA (~100)
LEAGUE_AVG_TOTAL = 144.0  # typical D1 game total

DEFAULT_NCAAB_SLATE_PATH = os.path.join(
    os.path.dirname(__file__), "..", "config", "ncaab_dvp_slate.json"
)


class NCAABDvPAnalyzer:
    """
    Identifies +EV NCAAB game total and team total opportunities via
    team efficiency analysis.

    Since NCAAB lacks positional DvP data, this uses team-level metrics:
        - Offensive Rating (ORtg): points per 100 possessions
        - Defensive Rating (DRtg): points allowed per 100 possessions
        - Tempo/Pace: possessions per 40 minutes
        - Implied totals from Vegas spread + O/U
    """

    def __init__(self, season: str = "2025-26"):
        self.season = season
        self.slate: Dict[str, Any] = {}
        self.team_efficiency: Dict[str, Dict[str, float]] = {}
        self.league_avg_ortg: float = LEAGUE_AVG_ORTG
        self.league_avg_drtg: float = LEAGUE_AVG_DRTG
        self.league_avg_pace: float = LEAGUE_AVG_PACE
        self.stats_service = NCAABStatsService()
        logger.info("NCAABDvPAnalyzer created (season={})", self.season)

    # ------------------------------------------------------------------
    # 1. SLATE LOADING
    # ------------------------------------------------------------------

    def load_slate(self, slate_data: Optional[Dict[str, Any]] = None) -> None:
        """Load today's matchup slate from dict or file."""
        if slate_data:
            self.slate = slate_data
            logger.info("NCAAB slate loaded from dict: {} games", len(self.slate.get("games", [])))
            return

        try:
            with open(DEFAULT_NCAAB_SLATE_PATH, "r") as f:
                self.slate = json.load(f)
            logger.info("NCAAB slate loaded from file: {} games", len(self.slate.get("games", [])))
        except FileNotFoundError:
            logger.warning("NCAAB slate file not found. Using empty slate.")
            self.slate = {"date": datetime.now().strftime("%Y-%m-%d"), "games": []}

    async def load_slate_from_odds_api(self) -> None:
        """Auto-populate NCAAB slate from live Odds API data."""
        try:
            from app.services.sports_api import SportsAPIService

            api = SportsAPIService()
            odds_data = await api.get_odds("basketball_ncaab", markets="spreads,totals")

            if not odds_data:
                logger.warning("No Odds API data for NCAAB — using empty slate")
                self.slate = {"date": datetime.now().strftime("%Y-%m-%d"), "games": []}
                return

            games = []
            for game in odds_data:
                home = game.get("home_team", "")
                away = game.get("away_team", "")
                if not home or not away:
                    continue

                spread = 0.0
                total = 0.0
                for book in game.get("bookmakers", []):
                    book_key = book.get("key", "")
                    for market in book.get("markets", []):
                        if market.get("key") == "spreads":
                            for out in market.get("outcomes", []):
                                if out.get("name", "") == home:
                                    candidate = float(out.get("point", 0))
                                    if spread == 0.0 or book_key in ("pinnacle", "fanduel"):
                                        spread = candidate
                        elif market.get("key") == "totals":
                            for out in market.get("outcomes", []):
                                if out.get("name") == "Over":
                                    candidate = float(out.get("point", 0))
                                    if total == 0.0 or book_key in ("pinnacle", "fanduel"):
                                        total = candidate

                if total == 0.0:
                    continue

                games.append({
                    "home": home,
                    "away": away,
                    "spread": spread,
                    "over_under": total,
                })

            self.slate = {
                "date": datetime.now().strftime("%Y-%m-%d"),
                "games": games,
            }
            logger.info("NCAAB slate auto-populated: {} games", len(games))

        except Exception as e:
            logger.error("Failed to load NCAAB slate from Odds API: {}", e)
            self.load_slate()

    # ------------------------------------------------------------------
    # 2. IMPLIED TEAM TOTALS
    # ------------------------------------------------------------------

    @staticmethod
    def calculate_implied_team_total(
        over_under: float, spread: float, is_favorite: bool
    ) -> float:
        """Standard implied team total formula."""
        abs_spread = abs(spread)
        if is_favorite:
            return (over_under + abs_spread) / 2.0
        return (over_under - abs_spread) / 2.0

    def compute_all_implied_totals(self) -> Dict[str, float]:
        """Compute implied team totals for every team on today's slate."""
        implied = {}
        for game in self.slate.get("games", []):
            ou = game["over_under"]
            spread = game["spread"]
            home = game["home"]
            away = game["away"]

            home_is_fav = spread < 0
            implied[home] = self.calculate_implied_team_total(ou, spread, home_is_fav)
            implied[away] = self.calculate_implied_team_total(ou, spread, not home_is_fav)

        return implied

    # ------------------------------------------------------------------
    # 3. TEAM EFFICIENCY DATA
    # ------------------------------------------------------------------

    async def fetch_team_efficiency(self) -> Dict[str, Dict[str, float]]:
        """Fetch real team efficiency data from NCAABStatsService (ESPN BPI).
        Falls back to deriving from spread + O/U if service fails.

        Returns:
            { team_name: { "ORtg": x, "DRtg": y, "PACE": z, "NET": w } }
        """
        # 1. Try to fetch from real stats service
        try:
            real_stats = await self.stats_service.fetch_all_team_stats()
            if real_stats:
                efficiency = {}
                for game in self.slate.get("games", []):
                    for team in [game["home"], game["away"]]:
                        if team not in efficiency:
                            stats = self.stats_service.get_team_stats(team)
                            if stats:
                                efficiency[team] = {
                                    "ORtg": stats["AdjOE"],
                                    "DRtg": stats["AdjDE"],
                                    "PACE": self.league_avg_pace, # Pace not in BPI, use avg
                                    "NET": stats["AdjOE"] - stats["AdjDE"],
                                    "BPI": stats["BPI"],
                                    "source": "espn_bpi"
                                }
                
                if efficiency:
                    logger.info("NCAAB efficiency fetched from ESPN BPI for {} teams", len(efficiency))
                    self.team_efficiency = efficiency
                    # Check if we need to fall back for any teams missing in BPI
                    for game in self.slate.get("games", []):
                        if game["home"] not in self.team_efficiency or game["away"] not in self.team_efficiency:
                            self._derive_missing_efficiency(game)
                    return self.team_efficiency
        except Exception as e:
            logger.warning("Failed to fetch real NCAAB stats: {}", e)

        # 2. Fallback: Derive efficiency from Vegas lines
        logger.info("Deriving NCAAB efficiency from Vegas lines (fallback)")
        efficiency = {}
        for game in self.slate.get("games", []):
            self._derive_missing_efficiency(game, efficiency)

        logger.info("NCAAB efficiency computed for {} teams (Vegas fallback)", len(efficiency))
        self.team_efficiency = efficiency
        return efficiency

    def _derive_missing_efficiency(self, game: Dict[str, Any], efficiency_dict: Optional[Dict] = None) -> None:
        """Helper to derive efficiency from Vegas lines for a single game."""
        target = efficiency_dict if efficiency_dict is not None else self.team_efficiency
        
        home = game["home"]
        away = game["away"]
        spread = game["spread"]
        ou = game["over_under"]

        # Derive efficiency from Vegas lines
        home_implied = self.calculate_implied_team_total(ou, spread, spread < 0)
        away_implied = self.calculate_implied_team_total(ou, spread, spread >= 0)

        # Estimate pace from total: pace ≈ total / 2 / (avg_efficiency / 100)
        est_pace = ou / 2.0 / (self.league_avg_ortg / 100.0) if self.league_avg_ortg > 0 else LEAGUE_AVG_PACE

        if home not in target:
            home_ortg = home_implied * (100.0 / est_pace) if est_pace > 0 else LEAGUE_AVG_ORTG
            target[home] = {
                "ORtg": round(home_ortg, 1),
                "DRtg": round(away_implied * (100.0 / est_pace) if est_pace > 0 else LEAGUE_AVG_DRTG, 1),
                "PACE": round(est_pace, 1),
                "NET": round(home_ortg - (away_implied * (100.0 / est_pace) if est_pace > 0 else LEAGUE_AVG_DRTG), 1),
                "source": "vegas_derived"
            }

        if away not in target:
            away_ortg = away_implied * (100.0 / est_pace) if est_pace > 0 else LEAGUE_AVG_ORTG
            target[away] = {
                "ORtg": round(away_ortg, 1),
                "DRtg": round(home_implied * (100.0 / est_pace) if est_pace > 0 else LEAGUE_AVG_DRTG, 1),
                "PACE": round(est_pace, 1),
                "NET": round(away_ortg - (home_implied * (100.0 / est_pace) if est_pace > 0 else LEAGUE_AVG_DRTG), 1),
                "source": "vegas_derived"
            }

    # ------------------------------------------------------------------
    # 4. EFFICIENCY-BASED PROJECTION
    # ------------------------------------------------------------------

    def project_game_total(
        self,
        home: str,
        away: str,
    ) -> float:
        """Project game total from team efficiency metrics.

        Formula: projected_total = (home_ortg + away_ortg) / 2 × game_pace / 100 × 2

        The ×2 accounts for both teams scoring.
        """
        home_eff = self.team_efficiency.get(home, {})
        away_eff = self.team_efficiency.get(away, {})

        home_ortg = home_eff.get("ORtg", self.league_avg_ortg)
        away_ortg = away_eff.get("ORtg", self.league_avg_ortg)
        home_drtg = home_eff.get("DRtg", self.league_avg_drtg)
        away_drtg = away_eff.get("DRtg", self.league_avg_drtg)
        home_pace = home_eff.get("PACE", self.league_avg_pace)
        away_pace = away_eff.get("PACE", self.league_avg_pace)

        game_pace = (home_pace + away_pace) / 2.0

        # Each team's expected points:
        # home_pts = (home_ortg vs away_drtg) × pace / 100
        # Average home offense with what away defense allows
        home_expected_ortg = (home_ortg + away_drtg) / 2.0
        away_expected_ortg = (away_ortg + home_drtg) / 2.0

        home_pts = home_expected_ortg * game_pace / 100.0
        away_pts = away_expected_ortg * game_pace / 100.0

        return round(home_pts + away_pts, 1)

    def compute_matchup_modifier(
        self,
        team: str,
        opponent: str,
    ) -> float:
        """Compute efficiency-based matchup modifier for a team.

        modifier = (team_ortg / league_avg_ortg) × (league_avg_drtg / opp_drtg) × pace_factor

        >1 means the team should score more than average in this matchup.
        """
        team_eff = self.team_efficiency.get(team, {})
        opp_eff = self.team_efficiency.get(opponent, {})

        team_ortg = team_eff.get("ORtg", self.league_avg_ortg)
        opp_drtg = opp_eff.get("DRtg", self.league_avg_drtg)
        team_pace = team_eff.get("PACE", self.league_avg_pace)
        opp_pace = opp_eff.get("PACE", self.league_avg_pace)

        ortg_factor = team_ortg / self.league_avg_ortg if self.league_avg_ortg > 0 else 1.0
        drtg_factor = opp_drtg / self.league_avg_drtg if self.league_avg_drtg > 0 else 1.0
        pace_factor = ((team_pace + opp_pace) / 2.0) / self.league_avg_pace if self.league_avg_pace > 0 else 1.0

        return ortg_factor * drtg_factor * pace_factor

    # ------------------------------------------------------------------
    # 5. DISCREPANCY FLAGGING
    # ------------------------------------------------------------------

    @staticmethod
    def flag_discrepancy(
        projected: float,
        vegas_line: float,
        threshold: float = 0.04,
    ) -> Tuple[str, float]:
        """Compare projected vs Vegas total.

        Returns (recommendation, advantage_pct).
        """
        if vegas_line == 0:
            return ("NO LINE", 0.0)

        diff_pct = (projected - vegas_line) / vegas_line

        if diff_pct > threshold * 2:
            return ("HIGH VALUE OVER", round(diff_pct * 100, 1))
        elif diff_pct < -threshold * 2:
            return ("HIGH VALUE UNDER", round(diff_pct * 100, 1))
        elif diff_pct > threshold:
            return ("LEAN OVER", round(diff_pct * 100, 1))
        elif diff_pct < -threshold:
            return ("LEAN UNDER", round(diff_pct * 100, 1))
        return ("NO EDGE", round(diff_pct * 100, 1))

    # ------------------------------------------------------------------
    # 6. FULL PIPELINE
    # ------------------------------------------------------------------

    async def run_analysis(
        self,
        slate_data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Execute the full NCAAB efficiency analysis pipeline.

        Returns:
            {
                "sport": "ncaab",
                "game_count": int,
                "projections": List[dict],
                "high_value_count": int,
            }
        """
        logger.info("=== Starting NCAAB Efficiency Analysis ===")

        if slate_data or not self.slate.get("games"):
            self.load_slate(slate_data)

        await self.fetch_team_efficiency()
        implied_totals = self.compute_all_implied_totals()

        projections = []
        for game in self.slate.get("games", []):
            home = game["home"]
            away = game["away"]
            ou = game["over_under"]
            spread = game["spread"]

            projected_total = self.project_game_total(home, away)
            rec, adv_pct = self.flag_discrepancy(projected_total, ou)

            home_modifier = self.compute_matchup_modifier(home, away)
            away_modifier = self.compute_matchup_modifier(away, home)

            home_implied = implied_totals.get(home, ou / 2)
            away_implied = implied_totals.get(away, ou / 2)

            projections.append({
                "Matchup": f"{away} @ {home}",
                "Home": home,
                "Away": away,
                "Spread": spread,
                "Vegas_Total": ou,
                "Projected_Total": projected_total,
                "Recommendation": rec,
                "Advantage_%": adv_pct,
                "Home_Implied": round(home_implied, 1),
                "Away_Implied": round(away_implied, 1),
                "Home_Modifier": round(home_modifier, 3),
                "Away_Modifier": round(away_modifier, 3),
                "Home_ORtg": self.team_efficiency.get(home, {}).get("ORtg", 0),
                "Home_DRtg": self.team_efficiency.get(home, {}).get("DRtg", 0),
                "Away_ORtg": self.team_efficiency.get(away, {}).get("ORtg", 0),
                "Away_DRtg": self.team_efficiency.get(away, {}).get("DRtg", 0),
            })

        # Sort by absolute advantage
        projections.sort(key=lambda p: abs(p["Advantage_%"]), reverse=True)

        high_value = [p for p in projections if "HIGH VALUE" in p.get("Recommendation", "")]

        logger.info(
            "=== NCAAB Analysis Complete: {} games, {} flagged ===",
            len(projections), len(high_value),
        )

        return {
            "sport": "ncaab",
            "task_type": "ncaab_efficiency",
            "game_count": len(projections),
            "count": len(projections),
            "high_value_count": len(high_value),
            "projections": projections,
        }

    async def get_high_value_plays(self, result: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Filter to only HIGH VALUE recommendations."""
        if result is None:
            result = await self.run_analysis()
        return [p for p in result.get("projections", []) if "HIGH VALUE" in p.get("Recommendation", "")]
