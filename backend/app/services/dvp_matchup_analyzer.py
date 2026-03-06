"""
Defense vs Position Matchup Analyzer

Identifies players with favorable matchups based on opponent defensive weaknesses.
"""

from typing import Dict, List, Optional, Any
from datetime import datetime
from loguru import logger
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.defense_vs_position import DefenseVsPosition
from app.services.nba_stats_service import NBAStatsService


class DvPMatchupAnalyzer:
    """Analyzes player matchups against weak defenses"""

    def __init__(self):
        self.nba_stats = NBAStatsService()

    def get_weak_defenses(
        self,
        session: Session,
        position: str,
        threshold_rank: int = 100,
        limit: int = 10,
    ) -> List[DefenseVsPosition]:
        """Get teams with weak defenses vs a position (high rank = bad defense)"""

        weak_defenses = (
            session.query(DefenseVsPosition)
            .filter(
                DefenseVsPosition.source == "hashtag",
                DefenseVsPosition.position == position,
                DefenseVsPosition.rank >= threshold_rank,
            )
            .order_by(DefenseVsPosition.rank.desc())
            .limit(limit)
            .all()
        )

        return weak_defenses

    def analyze_todays_matchups(
        self, games: List[Dict[str, Any]], threshold_rank: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Analyze today's games and identify players with favorable DvP matchups.

        Args:
            games: List of today's games with teams
            threshold_rank: Minimum DvP rank to consider weak defense (default 100)

        Returns:
            List of matchup opportunities with player, opponent, position, DvP rank
        """

        session = SessionLocal()
        try:
            matchup_opportunities = []

            for game in games:
                # Get both teams
                home_team = game.get("home_team")
                away_team = game.get("away_team")

                if not home_team or not away_team:
                    continue

                # Check home team's defense (opportunities for away players)
                for pos in ["PG", "SG", "SF", "PF", "C"]:
                    dvp = (
                        session.query(DefenseVsPosition)
                        .filter(
                            DefenseVsPosition.source == "hashtag",
                            DefenseVsPosition.position == pos,
                            DefenseVsPosition.team == home_team,
                            DefenseVsPosition.rank >= threshold_rank,
                        )
                        .first()
                    )

                    if dvp:
                        matchup_opportunities.append(
                            {
                                "game": f"{away_team} @ {home_team}",
                                "team": away_team,
                                "opponent": home_team,
                                "position": pos,
                                "dvp_rank": dvp.rank,
                                "pts_allowed": dvp.pts,
                                "ast_allowed": dvp.ast,
                                "reb_allowed": dvp.reb,
                                "threes_allowed": dvp.threes,
                                "matchup_quality": "Excellent"
                                if dvp.rank >= 140
                                else "Good",
                            }
                        )

                # Check away team's defense (opportunities for home players)
                for pos in ["PG", "SG", "SF", "PF", "C"]:
                    dvp = (
                        session.query(DefenseVsPosition)
                        .filter(
                            DefenseVsPosition.source == "hashtag",
                            DefenseVsPosition.position == pos,
                            DefenseVsPosition.team == away_team,
                            DefenseVsPosition.rank >= threshold_rank,
                        )
                        .first()
                    )

                    if dvp:
                        matchup_opportunities.append(
                            {
                                "game": f"{away_team} @ {home_team}",
                                "team": home_team,
                                "opponent": away_team,
                                "position": pos,
                                "dvp_rank": dvp.rank,
                                "pts_allowed": dvp.pts,
                                "ast_allowed": dvp.ast,
                                "reb_allowed": dvp.reb,
                                "threes_allowed": dvp.threes,
                                "matchup_quality": "Excellent"
                                if dvp.rank >= 140
                                else "Good",
                            }
                        )

            # Sort by DvP rank (worst defenses first)
            matchup_opportunities.sort(key=lambda x: x["dvp_rank"], reverse=True)

            logger.info(
                f"Found {len(matchup_opportunities)} favorable matchups (rank >= {threshold_rank})"
            )
            return matchup_opportunities

        finally:
            session.close()


if __name__ == "__main__":
    # Example usage
    analyzer = DvPMatchupAnalyzer()

    # Example games
    games = [
        {"home_team": "UTA", "away_team": "LAL"},
        {"home_team": "MIL", "away_team": "BOS"},
        {"home_team": "WAS", "away_team": "NYK"},
    ]

    matchups = analyzer.analyze_todays_matchups(games, threshold_rank=100)

    logger.info("\n=== Today's Favorable Matchups ===")
    for m in matchups[:15]:
        logger.info(
            f"{m['team']:4s} {m['position']} vs {m['opponent']:4s} - "
            f"Rank {m['dvp_rank']} ({m['matchup_quality']}) - "
            f"Allow {m['pts_allowed']:.1f} pts, {m['ast_allowed']:.1f} ast"
        )
