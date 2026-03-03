"""
NBA Defense vs. Position (DvP) +EV Prop Analyzer Service

Uses DvP metrics, Pace, and Vegas Implied Totals to identify
+EV NBA player prop bets. Integrates with nba_api for data sourcing.

Architecture references:
  - swar/nba_api for NBA.com endpoint mapping and data fetching
  - chevyphillip/plus-ev-model for rolling averages and edge math
  - parlayparlor/nba-prop-prediction-model for projection logic
  - bendominguez0111/nba-models for odds integration patterns
"""
import json
import os
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime

import numpy as np
import pandas as pd
from loguru import logger

try:
    from nba_api.stats.endpoints import (
        leaguedashteamstats,
        leaguedashplayerstats,
        teamdashboardbygeneralsplits,
    )
    from nba_api.stats.static import teams as nba_teams
    NBA_API_AVAILABLE = True
except ImportError:
    NBA_API_AVAILABLE = False
    logger.warning("nba_api not installed — DvP analyzer will use fallback data")

# League-average defensive rating (2024-25 baseline, updated at runtime)
LEAGUE_AVG_DRTG = 113.5


# ---------------------------------------------------------------------------
# NBA team abbreviation mapping
# ---------------------------------------------------------------------------
TEAM_ABBREV_MAP = {
    "ATL": "Atlanta Hawks", "BOS": "Boston Celtics", "BKN": "Brooklyn Nets",
    "CHA": "Charlotte Hornets", "CHI": "Chicago Bulls", "CLE": "Cleveland Cavaliers",
    "DAL": "Dallas Mavericks", "DEN": "Denver Nuggets", "DET": "Detroit Pistons",
    "GS": "Golden State Warriors", "HOU": "Houston Rockets", "IND": "Indiana Pacers",
    "LAC": "LA Clippers", "LAL": "Los Angeles Lakers", "MEM": "Memphis Grizzlies",
    "MIA": "Miami Heat", "MIL": "Milwaukee Bucks", "MIN": "Minnesota Timberwolves",
    "NO": "New Orleans Pelicans", "NYK": "New York Knicks", "OKC": "Oklahoma City Thunder",
    "ORL": "Orlando Magic", "PHI": "Philadelphia 76ers", "PHX": "Phoenix Suns",
    "POR": "Portland Trail Blazers", "SAC": "Sacramento Kings", "SA": "San Antonio Spurs",
    "TOR": "Toronto Raptors", "UTA": "Utah Jazz", "WAS": "Washington Wizards",
}

# Reverse lookup: full name -> abbreviation
TEAM_NAME_TO_ABBREV = {v: k for k, v in TEAM_ABBREV_MAP.items()}

# Position labels used throughout
POSITIONS = ["PG", "SG", "SF", "PF", "C"]

# Stat categories we project
STAT_CATEGORIES = ["PTS", "REB", "AST", "PTS+REB+AST"]

# Default config path
DEFAULT_SLATE_PATH = os.path.join(
    os.path.dirname(__file__), "..", "config", "nba_dvp_slate.json"
)

# Path to historical NBA advanced stats CSV (project root)
ADVANCED_CSV_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "..", "Advanced.csv"
)

# Empirical multipliers for deriving per-game counting stats from advanced CSV columns.
# Validated against known 2025-26 baselines (e.g., Jokic: pts=26.6, reb=12.4).
_USG_TO_PTS: float = 0.85      # avg_PTS  ≈ usg_percent × 0.85
_TRB_TO_REB: float = 0.60      # avg_REB  ≈ trb_percent × 0.60
_AST_PCT_TO_AST: float = 0.25  # avg_AST  ≈ ast_percent × 0.25

# Map CSV team codes → internal abbreviations
_CSV_TEAM_MAP = {
    "ATL": "ATL", "BOS": "BOS", "BRK": "BKN", "CHO": "CHA",
    "CHI": "CHI", "CLE": "CLE", "DAL": "DAL", "DEN": "DEN",
    "DET": "DET", "GSW": "GS", "HOU": "HOU", "IND": "IND",
    "LAC": "LAC", "LAL": "LAL", "MEM": "MEM", "MIA": "MIA",
    "MIL": "MIL", "MIN": "MIN", "NOP": "NO", "NYK": "NYK",
    "OKC": "OKC", "ORL": "ORL", "PHI": "PHI", "PHO": "PHX",
    "POR": "POR", "SAC": "SAC", "SAS": "SA", "TOR": "TOR",
    "UTA": "UTA", "WAS": "WAS",
}


def _load_advanced_csv(
    season: int = 2026,
    min_games: int = 15,
    min_minutes: int = 300,
) -> List[Dict[str, Any]]:
    """Load NBA player advanced stats from Advanced.csv.

    Derives approximate per-game counting stats using empirical formulas:
        avg_PTS  ≈ usg_percent × 0.85
        avg_REB  ≈ trb_percent × 0.60
        avg_AST  ≈ ast_percent × 0.25

    Returns a list of player dicts compatible with _fallback_player_baselines().
    """
    csv_path = os.path.abspath(ADVANCED_CSV_PATH)
    if not os.path.exists(csv_path):
        logger.debug("Advanced.csv not found at {}", csv_path)
        return []

    try:
        import csv as _csv

        players: List[Dict[str, Any]] = []
        with open(csv_path, newline="", encoding="utf-8") as fh:
            reader = _csv.DictReader(fh)
            for row in reader:
                if int(row.get("season", 0)) != season:
                    continue
                if row.get("lg", "NBA") != "NBA":
                    continue
                team_csv = row.get("team", "")
                team = _CSV_TEAM_MAP.get(team_csv)
                if not team:
                    continue  # skip traded (2TM/3TM) or unknown teams
                g = int(row.get("g") or 0)
                mp_total = float(row.get("mp") or 0)
                if g < min_games or mp_total < min_minutes:
                    continue
                mpg = mp_total / g

                usg = float(row.get("usg_percent") or 0)
                trb = float(row.get("trb_percent") or 0)
                ast_pct = float(row.get("ast_percent") or 0)

                pts = round(usg * _USG_TO_PTS, 1)
                reb = round(trb * _TRB_TO_REB, 1)
                ast = round(ast_pct * _AST_PCT_TO_AST, 1)

                if pts <= 0:
                    continue

                # Position: take first token (e.g. "PG-SG" → "PG")
                raw_pos = row.get("pos", "SF")
                pos = raw_pos.split("-")[0] if raw_pos else "SF"
                if pos not in POSITIONS:
                    pos = "SF"

                players.append({
                    "name": row.get("player", ""),
                    "player_id": row.get("player_id", ""),
                    "team": team,
                    "position": pos,
                    "avg_PTS": pts,
                    "avg_REB": reb,
                    "avg_AST": ast,
                    "avg_PTS+REB+AST": round(pts + reb + ast, 1),
                    "games_played": g,
                    "minutes": round(mpg, 1),
                    # Advanced stats (informational)
                    "bpm": float(row.get("bpm") or 0),
                    "vorp": float(row.get("vorp") or 0),
                    "per": float(row.get("per") or 0),
                })

        logger.info(
            "Loaded {} players from Advanced.csv (season={})", len(players), season
        )
        return players

    except Exception as e:
        logger.warning("Failed to load Advanced.csv: {}", e)
        return []


class NBADvPAnalyzer:
    """
    Identifies +EV NBA player prop bets via Defense-vs-Position analysis.

    Pipeline:
        1. Load today's slate (matchups, spreads, O/U)
        2. Fetch team DvP stats, pace, and player baselines from nba_api
        3. Compute implied team totals from spread + O/U
        4. Apply DvP matchup modifier + pace multiplier to player baselines
        5. Flag discrepancies between projected lines and sportsbook lines
        6. Output a clean DataFrame with recommendations
    """

    def __init__(self, slate_path: Optional[str] = None, season: Optional[str] = None):
        from app.config import settings
        self.season = season or settings.CURRENT_SEASON
        self.slate_path = slate_path or DEFAULT_SLATE_PATH
        self.slate: Dict[str, Any] = {}
        self.team_pace: Dict[str, float] = {}
        self.league_avg_pace: float = 100.0
        self.team_dvp: Dict[str, Dict[str, Dict[str, float]]] = {}
        self.player_baselines: List[Dict[str, Any]] = []
        self.team_season_avg_totals: Dict[str, float] = {}
        # Advanced team stats: { abbrev: { "OFF_RATING": x, "DEF_RATING": y, "NET_RATING": z } }
        self.team_advanced: Dict[str, Dict[str, float]] = {}
        self.league_avg_drtg: float = LEAGUE_AVG_DRTG
        self._initialized = False
        logger.info("NBADvPAnalyzer created (season={})", self.season)

    # ------------------------------------------------------------------
    # 1. SLATE LOADING
    # ------------------------------------------------------------------

    def load_slate(self, slate_data: Optional[Dict[str, Any]] = None) -> None:
        """Load today's matchup slate from JSON file or dict."""
        if slate_data:
            self.slate = slate_data
            logger.info("Slate loaded from dict: {} games", len(self.slate.get("games", [])))
            return

        try:
            with open(self.slate_path, "r") as f:
                self.slate = json.load(f)
            logger.info(
                "Slate loaded from {}: {} games",
                self.slate_path,
                len(self.slate.get("games", [])),
            )
        except FileNotFoundError:
            logger.warning("Slate file not found at {}. Using empty slate.", self.slate_path)
            self.slate = {"date": datetime.now().strftime("%Y-%m-%d"), "games": []}

    async def load_slate_from_odds_api(self) -> None:
        """Auto-populate slate from live Odds API data.

        Calls SportsAPIService.get_odds('basketball_nba') and builds the
        slate dict dynamically from current spreads and totals.
        Eliminates dependency on static nba_dvp_slate.json.
        """
        try:
            from app.services.sports_api import SportsAPIService

            api = SportsAPIService()
            odds_data = await api.get_odds("basketball_nba", markets="spreads,totals")

            if not odds_data:
                logger.warning("No Odds API data for NBA — falling back to file slate")
                self.load_slate()
                return

            games = []
            for game in odds_data:
                home = game.get("home_team", "")
                away = game.get("away_team", "")
                if not home or not away:
                    continue

                # Extract spread and total from best available bookmaker
                spread = 0.0
                total = 0.0
                for book in game.get("bookmakers", []):
                    book_key = book.get("key", "")
                    for market in book.get("markets", []):
                        if market.get("key") == "spreads":
                            for out in market.get("outcomes", []):
                                if out.get("name", "") == home:
                                    candidate = float(out.get("point", 0))
                                    # Prefer pinnacle/fanduel
                                    if spread == 0.0 or book_key in ("pinnacle", "fanduel"):
                                        spread = candidate
                        elif market.get("key") == "totals":
                            for out in market.get("outcomes", []):
                                if out.get("name") == "Over":
                                    candidate = float(out.get("point", 0))
                                    if total == 0.0 or book_key in ("pinnacle", "fanduel"):
                                        total = candidate

                if total == 0.0:
                    continue  # no total = can't compute implied team totals

                # Map full team names to abbreviations
                home_abbrev = self._full_name_to_abbrev(home)
                away_abbrev = self._full_name_to_abbrev(away)

                if not home_abbrev or not away_abbrev:
                    logger.debug("Skipping unmapped teams: {} vs {}", home, away)
                    continue

                games.append({
                    "home": home_abbrev,
                    "away": away_abbrev,
                    "spread": spread,
                    "over_under": total,
                })

            self.slate = {
                "date": datetime.now().strftime("%Y-%m-%d"),
                "season": self.season,
                "games": games,
            }
            logger.info(
                "Slate auto-populated from Odds API: {} games", len(games)
            )

        except Exception as e:
            logger.error("Failed to load slate from Odds API: {}. Falling back to file.", e)
            self.load_slate()

    @staticmethod
    def _full_name_to_abbrev(full_name: str) -> Optional[str]:
        """Map Odds API full team name to internal abbreviation."""
        # Direct lookup
        abbrev = TEAM_NAME_TO_ABBREV.get(full_name)
        if abbrev:
            return abbrev
        # Partial match: check if full_name contains a known team name
        fn_lower = full_name.lower()
        for name, ab in TEAM_NAME_TO_ABBREV.items():
            if name.lower() in fn_lower or fn_lower in name.lower():
                return ab
        return None

    # ------------------------------------------------------------------
    # 2. IMPLIED TEAM TOTALS
    # ------------------------------------------------------------------

    @staticmethod
    def calculate_implied_team_total(
        over_under: float, spread: float, is_favorite: bool
    ) -> float:
        """
        Implied Team Total = (O/U + |Spread|) / 2  for the favorite
        Implied Team Total = (O/U - |Spread|) / 2  for the underdog
        """
        abs_spread = abs(spread)
        if is_favorite:
            return (over_under + abs_spread) / 2.0
        return (over_under - abs_spread) / 2.0

    def compute_all_implied_totals(self) -> Dict[str, float]:
        """Compute implied team totals for every team on today's slate."""
        implied = {}
        for game in self.slate.get("games", []):
            ou = game["over_under"]
            spread = game["spread"]  # negative means home is favored
            home = game["home"]
            away = game["away"]

            home_is_fav = spread < 0
            implied[home] = self.calculate_implied_team_total(ou, spread, home_is_fav)
            implied[away] = self.calculate_implied_team_total(ou, spread, not home_is_fav)

        logger.info("Implied totals computed for {} teams", len(implied))
        return implied

    # ------------------------------------------------------------------
    # 3. DATA FETCHING (nba_api or fallback)
    # ------------------------------------------------------------------

    def fetch_team_pace(self) -> Dict[str, float]:
        """Fetch team pace (possessions per 48 min) for all NBA teams."""
        if NBA_API_AVAILABLE:
            try:
                stats = leaguedashteamstats.LeagueDashTeamStats(
                    season=self.season,
                    per_mode_detailed="PerGame",
                    measure_type_detailed_defense="Base",
                )
                df = stats.get_data_frames()[0]
                pace_data = {}
                for _, row in df.iterrows():
                    abbrev = self._team_name_to_abbrev(row["TEAM_NAME"])
                    if abbrev:
                        pace_data[abbrev] = float(row.get("PACE", 100.0))

                self.league_avg_pace = float(df["PACE"].mean()) if "PACE" in df.columns else 100.0
                logger.info("Fetched pace for {} teams via nba_api", len(pace_data))
                return pace_data
            except Exception as e:
                logger.warning("nba_api pace fetch failed ({}), using fallback", e)

        return self._fallback_pace_data()

    def fetch_team_dvp(self) -> Dict[str, Dict[str, Dict[str, float]]]:
        """
        Fetch Defense-vs-Position data: points / rebounds / assists
        allowed per position by each team.

        Returns nested dict:
            { team_abbrev: { position: { "PTS": x, "REB": y, "AST": z } } }
        """
        if NBA_API_AVAILABLE:
            try:
                return self._fetch_dvp_from_api()
            except Exception as e:
                logger.warning("nba_api DvP fetch failed ({}), using fallback", e)

        return self._fallback_dvp_data()

    def fetch_player_baselines(
        self, num_recent_games: int = 15
    ) -> List[Dict[str, Any]]:
        """
        Fetch player season averages for starting-caliber players.

        Mirrors parlayparlor/nba-prop-prediction-model approach:
        uses a recent-game window to compute rolling averages.
        """
        if NBA_API_AVAILABLE:
            try:
                return self._fetch_players_from_api(num_recent_games)
            except Exception as e:
                logger.warning("nba_api player fetch failed ({}), using fallback", e)

        return self._fallback_player_baselines()

    # ------------------------------------------------------------------
    # 4. DVP CALCULATION ENGINE
    # ------------------------------------------------------------------

    def compute_matchup_modifier(
        self,
        opponent_dvp_for_position: Dict[str, float],
        league_avg_dvp: Dict[str, float],
        implied_team_total: float,
        team_season_avg_total: float,
        pace_multiplier: float,
        opponent: str = "",
    ) -> Dict[str, float]:
        """
        Matchup Modifier per stat category.

        modifier = dvp_factor * environment_factor * pace_multiplier * drtg_factor

        dvp_factor        = opp_dvp_allowed / league_avg_dvp  (>1 means soft matchup)
        environment_factor = implied_total / season_avg_total  (>1 means game-script boost)
        drtg_factor        = opp_drtg / league_avg_drtg        (>1 means bad defense → boost)
        """
        # Defensive rating factor: higher DRtg = worse defense = higher stat output
        opp_adv = self.team_advanced.get(opponent, {})
        opp_drtg = opp_adv.get("DEF_RATING", self.league_avg_drtg)
        drtg_factor = opp_drtg / self.league_avg_drtg if self.league_avg_drtg > 0 else 1.0

        modifiers = {}
        for stat in ["PTS", "REB", "AST"]:
            opp_allowed = opponent_dvp_for_position.get(stat, 0)
            lg_avg = league_avg_dvp.get(stat, 1)
            if lg_avg == 0:
                lg_avg = 1

            dvp_factor = opp_allowed / lg_avg

            env_factor = 1.0
            if team_season_avg_total > 0:
                env_factor = implied_team_total / team_season_avg_total

            # For PTS, DRtg is most relevant; for REB/AST weight it less
            stat_drtg_weight = 1.0 if stat == "PTS" else 0.5
            blended_drtg = 1.0 + (drtg_factor - 1.0) * stat_drtg_weight

            modifiers[stat] = dvp_factor * env_factor * pace_multiplier * blended_drtg

        # Combo stat modifier is the average of component modifiers
        modifiers["PTS+REB+AST"] = np.mean(
            [modifiers["PTS"], modifiers["REB"], modifiers["AST"]]
        )
        return modifiers

    def compute_pace_multiplier(self, team: str, opponent: str) -> float:
        """
        Pace-Up / Pace-Down multiplier.

        game_pace = (team_pace + opp_pace) / 2
        multiplier = game_pace / league_avg_pace
        """
        t_pace = self.team_pace.get(team, self.league_avg_pace)
        o_pace = self.team_pace.get(opponent, self.league_avg_pace)
        game_pace = (t_pace + o_pace) / 2.0
        if self.league_avg_pace == 0:
            return 1.0
        return game_pace / self.league_avg_pace

    def project_player_line(
        self,
        season_avg: float,
        matchup_modifier: float,
    ) -> float:
        """Apply matchup modifier to baseline to get projected line."""
        return round(season_avg * matchup_modifier, 1)

    # ------------------------------------------------------------------
    # 5. DISCREPANCY FLAGGING
    # ------------------------------------------------------------------

    @staticmethod
    def flag_discrepancy(
        projected_line: float,
        sportsbook_line: float,
        threshold: float = 0.12,
    ) -> Tuple[str, float]:
        """
        Compare projected vs. sportsbook line.

        Returns (recommendation, dvp_advantage_pct).
        Flags >12 % higher as HIGH VALUE OVER,
              <12 % lower  as HIGH VALUE UNDER.
        """
        if sportsbook_line == 0:
            return ("NO LINE", 0.0)

        diff_pct = (projected_line - sportsbook_line) / sportsbook_line

        if diff_pct > threshold:
            return ("HIGH VALUE OVER", round(diff_pct * 100, 1))
        elif diff_pct < -threshold:
            return ("HIGH VALUE UNDER", round(diff_pct * 100, 1))
        elif diff_pct > 0.05:
            return ("LEAN OVER", round(diff_pct * 100, 1))
        elif diff_pct < -0.05:
            return ("LEAN UNDER", round(diff_pct * 100, 1))
        return ("NO EDGE", round(diff_pct * 100, 1))

    # ------------------------------------------------------------------
    # 6. FULL PIPELINE
    # ------------------------------------------------------------------

    def run_analysis(
        self,
        slate_data: Optional[Dict[str, Any]] = None,
        num_recent_games: int = 15,
        export_csv: Optional[str] = None,
    ) -> pd.DataFrame:
        """
        Execute the full DvP analysis pipeline.

        Returns a DataFrame:
            Player | Position | Team | Opponent | Stat_Category |
            Season_Avg | Projected_Line | DvP_Advantage_% | Recommendation
        """
        logger.info("=== Starting DvP +EV Analysis ===")

        # Step 1: Load slate (skip if already populated via load_slate_from_odds_api)
        if slate_data or not self.slate.get("games"):
            self.load_slate(slate_data)

        # Step 2: Fetch data
        self.team_pace = self.fetch_team_pace()
        self.team_advanced = self.fetch_team_advanced_stats()
        self.team_dvp = self.fetch_team_dvp()
        self.player_baselines = self.fetch_player_baselines(num_recent_games)

        # Step 3: Implied totals
        implied_totals = self.compute_all_implied_totals()

        # Build team season-avg totals (approximation from pace + league avg efficiency)
        self._estimate_team_season_totals()

        # Compute league-average DvP for normalization
        league_avg_dvp = self._compute_league_avg_dvp()

        # Step 4: Build opponent lookup from slate
        matchup_map = self._build_matchup_map()

        # Step 5: Iterate players and compute projections
        rows = []
        for player in self.player_baselines:
            team = player.get("team")
            opponent = matchup_map.get(team)
            if not opponent:
                continue  # player's team not on today's slate

            position = player.get("position", "SF")
            opp_dvp = self.team_dvp.get(opponent, {}).get(position, {})
            if not opp_dvp:
                # Fall back to generic position data
                opp_dvp = league_avg_dvp

            pace_mult = self.compute_pace_multiplier(team, opponent)
            imp_total = implied_totals.get(team, 110.0)
            season_total = self.team_season_avg_totals.get(team, 110.0)

            modifiers = self.compute_matchup_modifier(
                opp_dvp, league_avg_dvp, imp_total, season_total, pace_mult,
                opponent=opponent,
            )

            for stat in STAT_CATEGORIES:
                baseline = player.get(f"avg_{stat}", 0)
                if baseline == 0:
                    continue

                mod = modifiers.get(stat, 1.0)
                projected = self.project_player_line(baseline, mod)

                # Use mock sportsbook line if provided, else use baseline
                sb_line = player.get(f"line_{stat}", baseline)

                recommendation, dvp_pct = self.flag_discrepancy(projected, sb_line)

                rows.append({
                    "Player": player["name"],
                    "Position": position,
                    "Team": team,
                    "Opponent": opponent,
                    "Stat_Category": stat,
                    "Season_Avg": baseline,
                    "Projected_Line": projected,
                    "Sportsbook_Line": sb_line,
                    "DvP_Advantage_%": dvp_pct,
                    "Recommendation": recommendation,
                })

        df = pd.DataFrame(rows)

        if df.empty:
            logger.warning("No projections generated — check slate and player data")
            return df

        # Sort by absolute DvP advantage descending
        df = df.reindex(
            df["DvP_Advantage_%"].abs().sort_values(ascending=False).index
        )
        df = df.reset_index(drop=True)

        if export_csv:
            df.to_csv(export_csv, index=False)
            logger.info("Results exported to {}", export_csv)

        logger.info(
            "=== DvP Analysis Complete: {} projections, {} flagged ===",
            len(df),
            len(df[df["Recommendation"].str.contains("HIGH VALUE")]),
        )
        return df

    def get_high_value_plays(self, df: Optional[pd.DataFrame] = None) -> pd.DataFrame:
        """Filter to only HIGH VALUE OVER / UNDER recommendations."""
        if df is None:
            df = self.run_analysis()
        return df[df["Recommendation"].str.contains("HIGH VALUE")].reset_index(drop=True)

    # ------------------------------------------------------------------
    # INTERNAL HELPERS
    # ------------------------------------------------------------------

    def _build_matchup_map(self) -> Dict[str, str]:
        """Return { team_abbrev: opponent_abbrev } for each team on the slate."""
        m = {}
        for game in self.slate.get("games", []):
            m[game["home"]] = game["away"]
            m[game["away"]] = game["home"]
        return m

    def _estimate_team_season_totals(self) -> None:
        """Estimate a team's season average total from ORtg + pace when available."""
        # If we have advanced stats, use ORtg directly: total ≈ ORtg * pace / 100
        # Otherwise fall back to pace * league-avg efficiency (1.12)
        for abbrev, pace in self.team_pace.items():
            adv = self.team_advanced.get(abbrev, {})
            ortg = adv.get("OFF_RATING", 0)
            if ortg > 0:
                self.team_season_avg_totals[abbrev] = round(ortg * pace / 100.0, 1)
            else:
                self.team_season_avg_totals[abbrev] = round(pace * 1.12, 1)

    def _compute_league_avg_dvp(self) -> Dict[str, float]:
        """Average DvP across all teams for normalization."""
        sums: Dict[str, float] = {"PTS": 0, "REB": 0, "AST": 0}
        counts: Dict[str, int] = {"PTS": 0, "REB": 0, "AST": 0}

        for team_data in self.team_dvp.values():
            for pos_data in team_data.values():
                for stat in sums:
                    val = pos_data.get(stat, 0)
                    if val > 0:
                        sums[stat] += val
                        counts[stat] += 1

        avg = {}
        for stat in sums:
            avg[stat] = sums[stat] / max(counts[stat], 1)
        return avg

    @staticmethod
    def _team_name_to_abbrev(name: str) -> Optional[str]:
        """Convert full team name to abbreviation."""
        return TEAM_NAME_TO_ABBREV.get(name)

    # ------------------------------------------------------------------
    # nba_api FETCH IMPLEMENTATIONS
    # ------------------------------------------------------------------

    def fetch_team_advanced_stats(self) -> Dict[str, Dict[str, float]]:
        """
        Fetch team-level ORtg, DRtg, NET_RATING, PACE via LeagueDashTeamStats
        with MeasureType='Advanced'.

        Returns:
            { team_abbrev: { "OFF_RATING": x, "DEF_RATING": y, "NET_RATING": z, "PACE": w } }
        """
        if NBA_API_AVAILABLE:
            try:
                stats = leaguedashteamstats.LeagueDashTeamStats(
                    season=self.season,
                    per_mode_detailed="PerGame",
                    measure_type_detailed_defense="Advanced",
                )
                df = stats.get_data_frames()[0]
                advanced: Dict[str, Dict[str, float]] = {}

                for _, row in df.iterrows():
                    abbrev = self._team_name_to_abbrev(row.get("TEAM_NAME", ""))
                    if not abbrev:
                        continue
                    advanced[abbrev] = {
                        "OFF_RATING": float(row.get("OFF_RATING", 0)),
                        "DEF_RATING": float(row.get("DEF_RATING", 0)),
                        "NET_RATING": float(row.get("NET_RATING", 0)),
                        "PACE": float(row.get("PACE", 100.0)),
                    }

                # Update league-average DRtg from real data
                drtg_vals = [v["DEF_RATING"] for v in advanced.values() if v["DEF_RATING"] > 0]
                if drtg_vals:
                    self.league_avg_drtg = float(np.mean(drtg_vals))

                logger.info(
                    "Fetched advanced stats for {} teams (avg DRtg={:.1f})",
                    len(advanced), self.league_avg_drtg,
                )
                return advanced
            except Exception as e:
                logger.warning("nba_api advanced stats fetch failed ({}), using fallback", e)

        return self._fallback_advanced_stats()

    def _fallback_advanced_stats(self) -> Dict[str, Dict[str, float]]:
        """Estimated 2025-26 team advanced stats when nba_api is unavailable."""
        logger.info("Using fallback advanced stats")
        # ORtg/DRtg approximations based on team strength tiers
        data = {
            "ATL": {"OFF_RATING": 114.0, "DEF_RATING": 117.0, "NET_RATING": -3.0},
            "BOS": {"OFF_RATING": 120.5, "DEF_RATING": 109.0, "NET_RATING": 11.5},
            "BKN": {"OFF_RATING": 110.0, "DEF_RATING": 118.5, "NET_RATING": -8.5},
            "CHA": {"OFF_RATING": 109.0, "DEF_RATING": 117.5, "NET_RATING": -8.5},
            "CHI": {"OFF_RATING": 111.5, "DEF_RATING": 114.5, "NET_RATING": -3.0},
            "CLE": {"OFF_RATING": 118.0, "DEF_RATING": 107.5, "NET_RATING": 10.5},
            "DAL": {"OFF_RATING": 117.0, "DEF_RATING": 113.0, "NET_RATING": 4.0},
            "DEN": {"OFF_RATING": 117.5, "DEF_RATING": 112.0, "NET_RATING": 5.5},
            "DET": {"OFF_RATING": 110.5, "DEF_RATING": 115.5, "NET_RATING": -5.0},
            "GS":  {"OFF_RATING": 116.0, "DEF_RATING": 112.5, "NET_RATING": 3.5},
            "HOU": {"OFF_RATING": 113.0, "DEF_RATING": 110.5, "NET_RATING": 2.5},
            "IND": {"OFF_RATING": 118.5, "DEF_RATING": 116.0, "NET_RATING": 2.5},
            "LAC": {"OFF_RATING": 112.0, "DEF_RATING": 111.5, "NET_RATING": 0.5},
            "LAL": {"OFF_RATING": 114.5, "DEF_RATING": 112.0, "NET_RATING": 2.5},
            "MEM": {"OFF_RATING": 115.0, "DEF_RATING": 112.5, "NET_RATING": 2.5},
            "MIA": {"OFF_RATING": 112.5, "DEF_RATING": 111.0, "NET_RATING": 1.5},
            "MIL": {"OFF_RATING": 117.0, "DEF_RATING": 113.0, "NET_RATING": 4.0},
            "MIN": {"OFF_RATING": 114.0, "DEF_RATING": 108.5, "NET_RATING": 5.5},
            "NO":  {"OFF_RATING": 112.0, "DEF_RATING": 115.0, "NET_RATING": -3.0},
            "NYK": {"OFF_RATING": 118.0, "DEF_RATING": 110.5, "NET_RATING": 7.5},
            "OKC": {"OFF_RATING": 119.5, "DEF_RATING": 107.0, "NET_RATING": 12.5},
            "ORL": {"OFF_RATING": 109.5, "DEF_RATING": 106.5, "NET_RATING": 3.0},
            "PHI": {"OFF_RATING": 113.0, "DEF_RATING": 112.5, "NET_RATING": 0.5},
            "PHX": {"OFF_RATING": 116.0, "DEF_RATING": 115.0, "NET_RATING": 1.0},
            "POR": {"OFF_RATING": 110.0, "DEF_RATING": 117.0, "NET_RATING": -7.0},
            "SAC": {"OFF_RATING": 115.5, "DEF_RATING": 114.5, "NET_RATING": 1.0},
            "SA":  {"OFF_RATING": 111.0, "DEF_RATING": 116.0, "NET_RATING": -5.0},
            "TOR": {"OFF_RATING": 110.5, "DEF_RATING": 116.5, "NET_RATING": -6.0},
            "UTA": {"OFF_RATING": 111.0, "DEF_RATING": 117.0, "NET_RATING": -6.0},
            "WAS": {"OFF_RATING": 108.0, "DEF_RATING": 119.5, "NET_RATING": -11.5},
        }
        for v in data.values():
            v["PACE"] = 100.0  # pace comes from fetch_team_pace
        # Update league average from fallback
        drtg_vals = [v["DEF_RATING"] for v in data.values()]
        self.league_avg_drtg = float(np.mean(drtg_vals))
        return data

    def _fetch_dvp_from_api(self) -> Dict[str, Dict[str, Dict[str, float]]]:
        """
        Fetch DvP using opponent player stats grouped by position.

        Strategy: fetch LeagueDashPlayerStats per position, then scale the
        league-average positional stats by each team's DRtg to approximate
        what opponents at that position score against them.

        If team advanced stats are available, DvP = league_pos_avg × (opp_drtg / league_drtg).
        This is far more accurate than the previous approach of returning
        identical league averages for every team.
        """
        dvp: Dict[str, Dict[str, Dict[str, float]]] = {}

        # Get all team IDs
        all_teams = nba_teams.get_teams()

        # First, compute league-average stats per position
        pos_league_avg: Dict[str, Dict[str, float]] = {}
        for pos in POSITIONS:
            try:
                stats = leaguedashplayerstats.LeagueDashPlayerStats(
                    season=self.season,
                    per_mode_detailed="PerGame",
                    player_position_abbreviation_nullable=pos,
                )
                df = stats.get_data_frames()[0]
                pos_league_avg[pos] = {
                    "PTS": float(df["PTS"].mean()),
                    "REB": float(df["REB"].mean()),
                    "AST": float(df["AST"].mean()),
                }
            except Exception as e:
                logger.warning("DvP fetch for position {} failed: {}", pos, e)
                pos_league_avg[pos] = {"PTS": 15.0, "REB": 5.0, "AST": 3.0}

        # Scale by team DRtg: worse defense → opponents score more
        for team in all_teams:
            nba_abbrev = team["abbreviation"]
            mapped = self._nba_abbrev_to_ours(nba_abbrev)
            if not mapped:
                continue

            adv = self.team_advanced.get(mapped, {})
            team_drtg = adv.get("DEF_RATING", self.league_avg_drtg)
            # DRtg ratio: >1 means bad defense (opponents produce more)
            drtg_ratio = team_drtg / self.league_avg_drtg if self.league_avg_drtg > 0 else 1.0

            dvp[mapped] = {}
            for pos in POSITIONS:
                lg = pos_league_avg.get(pos, {"PTS": 15.0, "REB": 5.0, "AST": 3.0})
                dvp[mapped][pos] = {
                    "PTS": round(lg["PTS"] * drtg_ratio, 1),
                    "REB": round(lg["REB"] * (1.0 + (drtg_ratio - 1.0) * 0.5), 1),  # REB less DRtg-sensitive
                    "AST": round(lg["AST"] * (1.0 + (drtg_ratio - 1.0) * 0.5), 1),  # AST less DRtg-sensitive
                }

        logger.info("Fetched DvP data for {} teams (DRtg-weighted)", len(dvp))
        return dvp

    def _fetch_players_from_api(
        self, num_recent_games: int = 15
    ) -> List[Dict[str, Any]]:
        """Fetch player baselines using LeagueDashPlayerStats."""
        players = []

        # Get players on today's slate teams
        slate_teams = set()
        for game in self.slate.get("games", []):
            slate_teams.add(game["home"])
            slate_teams.add(game["away"])

        try:
            last_n = f"Last {num_recent_games}" if num_recent_games else None
            stats = leaguedashplayerstats.LeagueDashPlayerStats(
                season=self.season,
                per_mode_detailed="PerGame",
                last_n_games=num_recent_games,
            )
            df = stats.get_data_frames()[0]

            # Filter to starters / high-minute players (>= 20 min)
            df = df[df["MIN"] >= 20.0]

            for _, row in df.iterrows():
                team_abbrev = self._nba_abbrev_to_ours(row.get("TEAM_ABBREVIATION", ""))
                if team_abbrev not in slate_teams:
                    continue

                pts = float(row.get("PTS", 0))
                reb = float(row.get("REB", 0))
                ast = float(row.get("AST", 0))

                players.append({
                    "name": row.get("PLAYER_NAME", "Unknown"),
                    "player_id": str(row.get("PLAYER_ID", "")),
                    "team": team_abbrev,
                    "position": self._infer_position(row),
                    "avg_PTS": pts,
                    "avg_REB": reb,
                    "avg_AST": ast,
                    "avg_PTS+REB+AST": round(pts + reb + ast, 1),
                    "games_played": int(row.get("GP", 0)),
                    "minutes": float(row.get("MIN", 0)),
                })
        except Exception as e:
            logger.error("Player fetch failed: {}", e)

        if not players:
            logger.warning("No players fetched from API, using fallback player baselines")
            return self._fallback_player_baselines()

        logger.info("Fetched baselines for {} players on slate", len(players))
        return players

    @staticmethod
    def _infer_position(row) -> str:
        """Best-effort position inference from nba_api data."""
        # nba_api doesn't always provide clean positional data in
        # LeagueDashPlayerStats — use PLAYER_POSITION if available
        pos = str(row.get("PLAYER_POSITION", ""))
        if pos and pos in POSITIONS:
            return pos
        # Heuristic: high AST → guard, high REB → forward/center
        ast = float(row.get("AST", 0))
        reb = float(row.get("REB", 0))
        if ast >= 6:
            return "PG"
        if reb >= 8:
            return "C"
        if reb >= 5:
            return "PF"
        return "SF"

    @staticmethod
    def _nba_abbrev_to_ours(nba_abbrev: str) -> Optional[str]:
        """Map nba_api team abbreviations to our internal abbreviations."""
        mapping = {
            "ATL": "ATL", "BOS": "BOS", "BKN": "BKN", "CHA": "CHA",
            "CHI": "CHI", "CLE": "CLE", "DAL": "DAL", "DEN": "DEN",
            "DET": "DET", "GSW": "GS", "HOU": "HOU", "IND": "IND",
            "LAC": "LAC", "LAL": "LAL", "MEM": "MEM", "MIA": "MIA",
            "MIL": "MIL", "MIN": "MIN", "NOP": "NO", "NYK": "NYK",
            "OKC": "OKC", "ORL": "ORL", "PHI": "PHI", "PHX": "PHX",
            "POR": "POR", "SAC": "SAC", "SAS": "SA", "TOR": "TOR",
            "UTA": "UTA", "WAS": "WAS",
        }
        return mapping.get(nba_abbrev)

    # ------------------------------------------------------------------
    # FALLBACK DATA (when nba_api is unavailable)
    # ------------------------------------------------------------------

    def _fallback_pace_data(self) -> Dict[str, float]:
        """Estimated 2025-26 pace values for all 30 teams."""
        logger.info("Using fallback pace data")
        return {
            "ATL": 100.8, "BOS": 98.5, "BKN": 99.2, "CHA": 101.3,
            "CHI": 98.7, "CLE": 97.4, "DAL": 99.5, "DEN": 98.1,
            "DET": 99.8, "GS": 100.2, "HOU": 101.5, "IND": 103.7,
            "LAC": 97.6, "LAL": 100.0, "MEM": 101.2, "MIA": 96.8,
            "MIL": 99.9, "MIN": 98.3, "NO": 100.5, "NYK": 97.8,
            "OKC": 99.0, "ORL": 96.5, "PHI": 98.6, "PHX": 100.4,
            "POR": 101.0, "SAC": 102.1, "SA": 100.6, "TOR": 99.3,
            "UTA": 99.1, "WAS": 102.5,
        }

    def _fallback_dvp_data(self) -> Dict[str, Dict[str, Dict[str, float]]]:
        """
        Approximate DvP data (points / rebounds / assists allowed per
        position) when nba_api is unavailable.
        """
        logger.info("Using fallback DvP data")
        # League-average baselines per position
        pos_avg = {
            "PG": {"PTS": 22.0, "REB": 4.0, "AST": 7.0},
            "SG": {"PTS": 20.0, "REB": 4.5, "AST": 4.5},
            "SF": {"PTS": 18.0, "REB": 6.0, "AST": 3.5},
            "PF": {"PTS": 17.0, "REB": 7.5, "AST": 3.0},
            "C":  {"PTS": 16.0, "REB": 10.0, "AST": 2.5},
        }

        # Team-specific DvP multiplier (>1.0 = weaker defense vs position)
        # These approximate real defensive strengths/weaknesses
        team_dvp_multipliers = {
            "ATL": {"PG": 1.10, "SG": 1.08, "SF": 1.05, "PF": 1.02, "C": 0.98},
            "BOS": {"PG": 0.90, "SG": 0.88, "SF": 0.92, "PF": 0.95, "C": 0.93},
            "BKN": {"PG": 1.08, "SG": 1.12, "SF": 1.06, "PF": 1.04, "C": 1.10},
            "CHA": {"PG": 1.12, "SG": 1.10, "SF": 1.08, "PF": 1.06, "C": 1.05},
            "CHI": {"PG": 1.02, "SG": 1.05, "SF": 1.00, "PF": 0.98, "C": 1.03},
            "CLE": {"PG": 0.88, "SG": 0.90, "SF": 0.85, "PF": 0.87, "C": 0.82},
            "DAL": {"PG": 1.05, "SG": 1.02, "SF": 0.98, "PF": 1.00, "C": 1.06},
            "DEN": {"PG": 0.98, "SG": 1.00, "SF": 0.95, "PF": 0.92, "C": 0.90},
            "DET": {"PG": 1.06, "SG": 1.04, "SF": 1.08, "PF": 1.10, "C": 1.02},
            "GS":  {"PG": 0.95, "SG": 0.93, "SF": 0.97, "PF": 1.00, "C": 1.05},
            "HOU": {"PG": 0.96, "SG": 0.98, "SF": 1.00, "PF": 0.95, "C": 0.92},
            "IND": {"PG": 1.08, "SG": 1.06, "SF": 1.10, "PF": 1.05, "C": 1.08},
            "LAC": {"PG": 0.94, "SG": 0.96, "SF": 0.93, "PF": 0.97, "C": 0.95},
            "LAL": {"PG": 1.00, "SG": 1.02, "SF": 0.98, "PF": 0.96, "C": 0.94},
            "MEM": {"PG": 0.97, "SG": 1.00, "SF": 0.95, "PF": 0.98, "C": 1.02},
            "MIA": {"PG": 0.92, "SG": 0.90, "SF": 0.94, "PF": 0.96, "C": 0.98},
            "MIL": {"PG": 0.96, "SG": 0.98, "SF": 0.94, "PF": 0.90, "C": 0.88},
            "MIN": {"PG": 0.90, "SG": 0.92, "SF": 0.88, "PF": 0.86, "C": 0.85},
            "NO":  {"PG": 1.04, "SG": 1.06, "SF": 1.02, "PF": 1.00, "C": 1.04},
            "NYK": {"PG": 0.94, "SG": 0.96, "SF": 0.92, "PF": 0.94, "C": 0.90},
            "OKC": {"PG": 0.86, "SG": 0.88, "SF": 0.90, "PF": 0.88, "C": 0.92},
            "ORL": {"PG": 0.88, "SG": 0.90, "SF": 0.86, "PF": 0.84, "C": 0.82},
            "PHI": {"PG": 0.98, "SG": 1.00, "SF": 0.96, "PF": 0.94, "C": 0.92},
            "PHX": {"PG": 1.06, "SG": 1.04, "SF": 1.02, "PF": 1.08, "C": 1.05},
            "POR": {"PG": 1.10, "SG": 1.08, "SF": 1.12, "PF": 1.06, "C": 1.04},
            "SAC": {"PG": 1.04, "SG": 1.02, "SF": 1.06, "PF": 1.00, "C": 1.02},
            "SA":  {"PG": 1.06, "SG": 1.08, "SF": 1.04, "PF": 1.02, "C": 1.00},
            "TOR": {"PG": 1.08, "SG": 1.06, "SF": 1.10, "PF": 1.04, "C": 1.02},
            "UTA": {"PG": 1.10, "SG": 1.12, "SF": 1.08, "PF": 1.06, "C": 1.04},
            "WAS": {"PG": 1.14, "SG": 1.12, "SF": 1.10, "PF": 1.08, "C": 1.06},
        }

        dvp = {}
        for team, mults in team_dvp_multipliers.items():
            dvp[team] = {}
            for pos in POSITIONS:
                m = mults.get(pos, 1.0)
                dvp[team][pos] = {
                    stat: round(pos_avg[pos][stat] * m, 1)
                    for stat in ["PTS", "REB", "AST"]
                }
        return dvp

    def _fallback_player_baselines(self) -> List[Dict[str, Any]]:
        """
        Representative starting-player baselines for slate teams.
        Prefers Advanced.csv data (current season) over hardcoded values.
        Used when nba_api is unavailable.
        """
        logger.info("Using fallback player baselines")
        slate_teams = set()
        for game in self.slate.get("games", []):
            slate_teams.add(game["home"])
            slate_teams.add(game["away"])

        # ── Try Advanced.csv first ──
        try:
            season_year = int(self.season.split("-")[0]) + 1  # "2025-26" → 2026
        except Exception:
            season_year = 2026

        csv_players = _load_advanced_csv(season=season_year)
        if csv_players:
            slate_players = [p for p in csv_players if p["team"] in slate_teams]
            if slate_players:
                logger.info(
                    "Using {} Advanced.csv baselines for {} slate teams",
                    len(slate_players),
                    len(slate_teams),
                )
                return slate_players
            logger.debug("Advanced.csv loaded but no players matched slate teams {}", slate_teams)

        # Representative starters for common teams
        all_players = {
            "CLE": [
                {"name": "Donovan Mitchell", "position": "SG", "avg_PTS": 24.0, "avg_REB": 4.5, "avg_AST": 5.2},
                {"name": "Darius Garland", "position": "PG", "avg_PTS": 21.5, "avg_REB": 2.8, "avg_AST": 6.8},
                {"name": "Evan Mobley", "position": "PF", "avg_PTS": 18.5, "avg_REB": 9.2, "avg_AST": 3.0},
                {"name": "Jarrett Allen", "position": "C", "avg_PTS": 14.0, "avg_REB": 10.5, "avg_AST": 1.8},
            ],
            "OKC": [
                {"name": "Shai Gilgeous-Alexander", "position": "PG", "avg_PTS": 31.5, "avg_REB": 5.5, "avg_AST": 6.2},
                {"name": "Jalen Williams", "position": "SF", "avg_PTS": 21.0, "avg_REB": 5.8, "avg_AST": 5.0},
                {"name": "Chet Holmgren", "position": "C", "avg_PTS": 16.5, "avg_REB": 8.2, "avg_AST": 2.5},
            ],
            "BKN": [
                {"name": "Cam Thomas", "position": "SG", "avg_PTS": 24.5, "avg_REB": 3.5, "avg_AST": 4.8},
                {"name": "Dennis Schroder", "position": "PG", "avg_PTS": 15.0, "avg_REB": 3.0, "avg_AST": 6.5},
            ],
            "ATL": [
                {"name": "Trae Young", "position": "PG", "avg_PTS": 25.5, "avg_REB": 3.8, "avg_AST": 10.8},
                {"name": "Jalen Johnson", "position": "SF", "avg_PTS": 19.0, "avg_REB": 8.5, "avg_AST": 4.2},
            ],
            "TOR": [
                {"name": "Scottie Barnes", "position": "SF", "avg_PTS": 20.0, "avg_REB": 8.0, "avg_AST": 6.5},
                {"name": "RJ Barrett", "position": "SG", "avg_PTS": 21.5, "avg_REB": 6.0, "avg_AST": 4.0},
            ],
            "MIL": [
                {"name": "Giannis Antetokounmpo", "position": "PF", "avg_PTS": 31.0, "avg_REB": 12.0, "avg_AST": 5.8},
                {"name": "Damian Lillard", "position": "PG", "avg_PTS": 25.5, "avg_REB": 4.5, "avg_AST": 7.0},
            ],
            "DEN": [
                {"name": "Nikola Jokic", "position": "C", "avg_PTS": 26.5, "avg_REB": 12.5, "avg_AST": 9.5},
                {"name": "Jamal Murray", "position": "PG", "avg_PTS": 21.0, "avg_REB": 4.0, "avg_AST": 6.5},
            ],
            "GS": [
                {"name": "Stephen Curry", "position": "PG", "avg_PTS": 27.0, "avg_REB": 5.0, "avg_AST": 6.0},
                {"name": "Andrew Wiggins", "position": "SF", "avg_PTS": 17.0, "avg_REB": 5.0, "avg_AST": 2.5},
            ],
            "DAL": [
                {"name": "Luka Doncic", "position": "PG", "avg_PTS": 28.5, "avg_REB": 8.5, "avg_AST": 8.0},
                {"name": "Kyrie Irving", "position": "SG", "avg_PTS": 24.0, "avg_REB": 5.0, "avg_AST": 5.5},
            ],
            "IND": [
                {"name": "Tyrese Haliburton", "position": "PG", "avg_PTS": 20.5, "avg_REB": 4.0, "avg_AST": 10.0},
                {"name": "Pascal Siakam", "position": "PF", "avg_PTS": 21.5, "avg_REB": 7.0, "avg_AST": 3.8},
            ],
            "CHA": [
                {"name": "LaMelo Ball", "position": "PG", "avg_PTS": 23.0, "avg_REB": 5.5, "avg_AST": 8.0},
            ],
            "WAS": [
                {"name": "Jordan Poole", "position": "SG", "avg_PTS": 17.5, "avg_REB": 3.0, "avg_AST": 4.5},
            ],
            "BOS": [
                {"name": "Jayson Tatum", "position": "SF", "avg_PTS": 27.0, "avg_REB": 8.5, "avg_AST": 4.8},
                {"name": "Jaylen Brown", "position": "SG", "avg_PTS": 23.0, "avg_REB": 5.5, "avg_AST": 3.5},
            ],
            "LAL": [
                {"name": "LeBron James", "position": "SF", "avg_PTS": 25.5, "avg_REB": 7.5, "avg_AST": 8.0},
                {"name": "Anthony Davis", "position": "PF", "avg_PTS": 24.0, "avg_REB": 12.0, "avg_AST": 3.5},
            ],
            "PHI": [
                {"name": "Tyrese Maxey", "position": "PG", "avg_PTS": 25.5, "avg_REB": 3.5, "avg_AST": 6.0},
                {"name": "Joel Embiid", "position": "C", "avg_PTS": 27.0, "avg_REB": 11.0, "avg_AST": 3.5},
            ],
            "MIN": [
                {"name": "Anthony Edwards", "position": "SG", "avg_PTS": 26.5, "avg_REB": 5.5, "avg_AST": 5.0},
                {"name": "Julius Randle", "position": "PF", "avg_PTS": 20.0, "avg_REB": 8.5, "avg_AST": 4.0},
            ],
            "POR": [
                {"name": "Anfernee Simons", "position": "SG", "avg_PTS": 22.5, "avg_REB": 3.0, "avg_AST": 5.5},
            ],
            "PHX": [
                {"name": "Devin Booker", "position": "SG", "avg_PTS": 27.0, "avg_REB": 4.5, "avg_AST": 6.5},
                {"name": "Kevin Durant", "position": "SF", "avg_PTS": 27.5, "avg_REB": 6.5, "avg_AST": 4.0},
            ],
            "NYK": [
                {"name": "Jalen Brunson", "position": "PG", "avg_PTS": 28.0, "avg_REB": 3.5, "avg_AST": 7.5},
                {"name": "Karl-Anthony Towns", "position": "C", "avg_PTS": 25.0, "avg_REB": 12.0, "avg_AST": 3.5},
            ],
            "CHI": [
                {"name": "Zach LaVine", "position": "SG", "avg_PTS": 22.0, "avg_REB": 4.5, "avg_AST": 4.0},
                {"name": "Coby White", "position": "PG", "avg_PTS": 18.5, "avg_REB": 4.0, "avg_AST": 5.0},
            ],
            "ORL": [
                {"name": "Paolo Banchero", "position": "PF", "avg_PTS": 23.0, "avg_REB": 7.5, "avg_AST": 5.0},
                {"name": "Franz Wagner", "position": "SF", "avg_PTS": 21.0, "avg_REB": 5.5, "avg_AST": 5.5},
            ],
            "LAC": [
                {"name": "James Harden", "position": "PG", "avg_PTS": 22.0, "avg_REB": 6.0, "avg_AST": 8.5},
                {"name": "Norman Powell", "position": "SG", "avg_PTS": 23.0, "avg_REB": 3.5, "avg_AST": 2.5},
            ],
        }

        players = []
        for team, roster in all_players.items():
            if team not in slate_teams:
                continue
            for p in roster:
                pts = p.get("avg_PTS", 0)
                reb = p.get("avg_REB", 0)
                ast = p.get("avg_AST", 0)
                players.append({
                    "name": p["name"],
                    "team": team,
                    "position": p["position"],
                    "avg_PTS": pts,
                    "avg_REB": reb,
                    "avg_AST": ast,
                    "avg_PTS+REB+AST": round(pts + reb + ast, 1),
                })
        return players
