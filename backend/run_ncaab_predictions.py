import asyncio
import os
import sys
from datetime import datetime
from typing import Any, Dict, List

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from loguru import logger

from app.services.ncaab_stats_service import NCAABStatsService
from app.services.sports_api import SportsAPIService, normalize_team_name
from run_ncaab_analysis import calculate_model_prob


async def run_ncaab_predictions() -> Dict[str, Any]:
    sports_api = SportsAPIService()
    stats_service = NCAABStatsService()

    team_stats = await stats_service.fetch_all_team_stats()
    discovery = await sports_api.discover_games("basketball_ncaab")
    games = discovery.data or []

    print("\n" + "=" * 76)
    print(
        f"  NCAAB PREDICTION-ONLY ANALYSIS — {datetime.now().strftime('%A, %B %d, %Y')}"
    )
    print(f"  Data: {discovery.source} | {len(games)} games on slate")
    print("  Methodology: Team Stats + Model Probability (No Odds, No Sharp Signals)")
    print("=" * 76)

    predictions: List[Dict[str, Any]] = []

    for g in games:
        home = normalize_team_name(g.get("home_team", ""))
        away = normalize_team_name(g.get("away_team", ""))
        if not home or not away:
            continue

        model_home_prob = calculate_model_prob(
            home, away, spread=0.0, team_stats=team_stats
        )
        model_away_prob = 1.0 - model_home_prob
        winner = home if model_home_prob >= 0.5 else away
        confidence = abs(model_home_prob - 0.5) * 2

        predictions.append(
            {
                "home": home,
                "away": away,
                "model_home_prob": model_home_prob,
                "model_away_prob": model_away_prob,
                "winner": winner,
                "confidence": confidence,
            }
        )

    predictions.sort(key=lambda x: x["confidence"], reverse=True)

    print("\n" + "─" * 76)
    print("  TOP MODEL PLAYS")
    print("─" * 76)
    for idx, p in enumerate(predictions[:12], 1):
        print(
            f"#{idx:>2} {p['away']} @ {p['home']} | "
            f"Model: {p['home']} {p['model_home_prob']:.1%} / {p['away']} {p['model_away_prob']:.1%} | "
            f"Pick: {p['winner']} | Confidence: {p['confidence']:.1%}"
        )

    return {
        "sport": "ncaab",
        "mode": "prediction_only",
        "game_count": len(games),
        "predictions": predictions,
        "data_source": discovery.source,
    }


def main() -> None:
    result = asyncio.run(run_ncaab_predictions())
    logger.info(f"NCAAB prediction-only complete: {result['game_count']} games")


if __name__ == "__main__":
    main()
