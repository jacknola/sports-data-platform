"""
NBA Machine Learning Analysis — Tonight's Slate

Applies XGBoost machine learning predictions and advanced stats
to the live NBA slate from the Odds API.
"""

import sys
import os
import asyncio
from datetime import datetime
from typing import Any, Dict, List, Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from loguru import logger
from app.services.nba_ml_predictor import NBAMLPredictor
from app.services.bet_tracker import BetTracker


async def run_nba_analysis() -> Dict[str, Any]:
    """Run NBA ML analysis.

    Returns structured data dict in addition to printing to stdout.

    Returns:
        {
            "sport": "nba",
            "game_count": int,
            "predictions": List[dict],
            "bets": List[dict],
        }
    """
    predictor = NBAMLPredictor()

    print("\n" + "=" * 76)
    print(f"  NBA ML ANALYSIS — {datetime.now().strftime('%A, %B %d, %Y')}")
    print(f"  Methodology: Live API Stats + XGBoost ML + Kelly Optimization")
    print("=" * 76)

    predictions = await predictor.predict_today_games("nba")

    if not predictions:
        print("\n  No NBA games found today.")
        return {"sport": "nba", "game_count": 0, "predictions": [], "bets": []}

    BANKROLL = 25.0
    bets_to_save = []

    print("\n" + "─" * 76)
    print("  GAME-BY-GAME ML BREAKDOWN")
    print("─" * 76)

    for p in predictions:
        if "error" in p:
            print(
                f"\n  Error predicting {p['away_team']} @ {p['home_team']}: {p['error']}"
            )
            continue

        h = p["home_team"]
        a = p["away_team"]
        ev = p["expected_value"]
        best_bet = ev["best_bet"]
        home_prob = p["moneyline_prediction"]["home_win_prob"]
        away_prob = p["moneyline_prediction"]["away_win_prob"]

        home_edge = ev.get("home_ev", 0)
        away_edge = ev.get("away_ev", 0)

        print(f"\n  {a} @ {h} [ML]")
        print(f"  ML Probabilities: {h} {home_prob:.1%} / {a} {away_prob:.1%}")
        print(
            f"  Odds (Retail):    {h} {ev['home_odds']:+d} / {a} {ev['away_odds']:+d}"
        )

        he_tag = " ← +EV" if home_edge > 0.025 else (" ← EV" if home_edge > 0 else "")
        ae_tag = " ← +EV" if away_edge > 0.025 else (" ← EV" if away_edge > 0 else "")
        print(
            f"  Edge vs Retail:   {h} {home_edge * 100:+.2f}%{he_tag} / {a} {away_edge * 100:+.2f}%{ae_tag}"
        )

        kelly_fraction = p.get("kelly_criterion", 0)
        bet_size = kelly_fraction * BANKROLL

        best_side_team = h if best_bet == "home" else a
        best_side_odds = ev["home_odds"] if best_bet == "home" else ev["away_odds"]
        best_side_edge = home_edge if best_bet == "home" else away_edge

        if kelly_fraction > 0.001 and best_side_edge > 0.025:
            print(
                f"  ★ ML BET: {best_side_team} {best_side_odds:+d} → ${bet_size:.0f} ({kelly_fraction * 100:.2f}% of bankroll)"
            )

            # Save bet
            bets_to_save.append(
                {
                    "game_id": f"NBA_{h}_{a}_{datetime.now().strftime('%Y%m%d')}".replace(
                        " ", ""
                    ),
                    "sport": "nba",
                    "side": best_side_team,
                    "market": "moneyline",
                    "odds": best_side_odds,
                    "line": 0.0,
                    "edge": best_side_edge,
                    "bet_size": bet_size,
                    "date": datetime.utcnow().strftime("%Y-%m-%d"),
                }
            )
        else:
            print("  → PASS (No qualifying ML edge)")

    print("\n" + "=" * 76)
    print("  PORTFOLIO SUMMARY — NBA ML (QUARTER-KELLY)")
    print("=" * 76)

    if bets_to_save:
        bets_to_save.sort(key=lambda x: x["edge"], reverse=True)

        print(f"\n  {'Side':<35} {'Odds':>6} {'Edge':>7} {'Bet $':>8}")
        print("  " + "-" * 60)

        total_bet = 0
        for b in bets_to_save:
            side_label = b["side"][:34]
            total_bet += b["bet_size"]
            print(
                f"  {side_label:<35} "
                f"{b['odds']:>+6d} "
                f"{b['edge'] * 100:>+6.2f}% "
                f"${b['bet_size']:>7.0f}"
            )

        print("  " + "-" * 60)
        print(f"  {'TOTAL EXPOSURE':<35} {'':>6} {'':>7} ${total_bet:>7.0f}")

        tracker = BetTracker()
        for b in bets_to_save:
            tracker.save_bet(b)
        print(f"\n  Saved {len(bets_to_save)} pending ML bets to tracker.")
    else:
        print("\n  No bets meet all ML criteria today.")

    return {
        "sport": "nba",
        "game_count": len(predictions),
        "predictions": predictions,
        "bets": bets_to_save,
    }


def main():
    asyncio.run(run_nba_analysis())


if __name__ == "__main__":
    main()
