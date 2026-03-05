"""
NBA Machine Learning Analysis — Tonight's Slate

Applies XGBoost machine learning predictions and advanced stats
to the live NBA slate from the Odds API.
"""

import sys
import os
import asyncio
import argparse
from datetime import datetime
from typing import Any, Dict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from loguru import logger
from app.services.nba_ml_predictor import NBAMLPredictor
from app.services.bet_tracker import BetTracker


async def run_nba_analysis(prediction_only: bool = False) -> Dict[str, Any]:
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
    method = (
        "Live API Stats + XGBoost ML (Prediction-Only)"
        if prediction_only
        else "Live API Stats + XGBoost ML + Kelly Optimization"
    )
    print(f"  Methodology: {method}")
    print("=" * 76)

    predictions = await predictor.predict_today_games("nba")


    if not predictions:
        print("\n  No NBA games found today.")
        return {"sport": "nba", "game_count": 0, "predictions": [], "bets": []}

    try:
        from app.config import settings

        BANKROLL = getattr(settings, "BETTING_BANKROLL", 1000.0)
    except Exception:
        BANKROLL = float(os.getenv("BETTING_BANKROLL", "1000"))
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
        best_bet = ev.get("best_bet")
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

        best_side_team = h if best_bet == "home" else a if best_bet == "away" else ""
        best_side_odds = (
            ev["home_odds"]
            if best_bet == "home"
            else ev["away_odds"]
            if best_bet == "away"
            else 0
        )
        best_side_edge = (
            home_edge if best_bet == "home" else away_edge if best_bet == "away" else 0
        )

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

        # Check under/over if available (use real odds from API)
        total_data = p.get("total", {})
        if p.get("underover_prediction") and total_data.get("over_odds"):
            uo = p["underover_prediction"]
            rec = uo["recommendation"]  # 'over' or 'under'
            uo_prob = uo["over_prob"] if rec == "over" else uo["under_prob"]

            # Use real odds from the API
            uo_odds = (
                total_data["over_odds"]
                if rec == "over"
                else total_data.get("under_odds", -110)
            )

            # Convert American odds to decimal and implied probability
            if uo_odds >= 100:
                uo_decimal = uo_odds / 100.0 + 1.0
                uo_implied = 100.0 / (uo_odds + 100.0)
            else:
                uo_decimal = 100.0 / abs(uo_odds) + 1.0
                uo_implied = abs(uo_odds) / (abs(uo_odds) + 100.0)

            # Proper edge: model probability minus book implied probability
            uo_edge = uo_prob - uo_implied

            # EV = (true_prob * net_payout) - (loss_prob * stake)
            uo_ev = (uo_prob * (uo_decimal - 1)) - (1 - uo_prob)

            if uo_edge > 0.025 and uo_ev > 0:
                uo_kelly = (uo_ev / (uo_decimal - 1)) * 0.25  # quarter-Kelly
                uo_kelly = min(uo_kelly, 0.05)  # cap at 5% per AGENTS.md
                uo_bet_size = uo_kelly * BANKROLL

                if uo_bet_size >= 5.0:  # minimum $5 bet
                    total_line = total_data.get("point", uo["total_points"])
                    print(
                        f"  ★ TOTAL BET: {rec.upper()} {total_line} ({uo_odds:+d}) → ${uo_bet_size:.0f} ({uo_kelly * 100:.2f}% of bankroll) [edge {uo_edge * 100:+.1f}%]"
                    )

                    bets_to_save.append(
                        {
                            "game_id": f"NBA_TOTAL_{h}_{a}_{datetime.now().strftime('%Y%m%d')}".replace(
                                " ", ""
                            ),
                            "sport": "nba",
                            "side": f"{rec.upper()} {total_line}",
                            "market": "total",
                            "odds": uo_odds,
                            "line": total_line,
                            "edge": uo_edge,
                            "bet_size": uo_bet_size,
                            "date": datetime.utcnow().strftime("%Y-%m-%d"),
                        }
                    )

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
    elif not prediction_only:
        print("\n  No bets meet all ML criteria today.")
    else:
        print("\n  Prediction-only mode: no bet sizing or bet persistence executed.")

    # Save predictions to a local CSV file', '    if predictions:', '        try:', '            df = pd.DataFrame(predictions)', '            df.to_csv("sheets/nba_predictions.csv", index=False)', '            logger.info("NBA predictions saved to sheets/nba_predictions.csv")', '        except Exception as e:', '            logger.error(f"Failed to save NBA predictions to CSV: {e}")', '
    # Export predictions to Google Sheets if configured
    try:
        from app.services.google_sheets import GoogleSheetsService

        spreadsheet_id = getattr(settings, "GOOGLE_SPREADSHEET_ID", None)
        if spreadsheet_id:
            sheets_svc = GoogleSheetsService()
            export_result = sheets_svc.export_nba(
                spreadsheet_id, predictions, bets_to_save
            )
            if export_result.get("status") == "success":
                logger.info(
                    f"Exported {export_result.get('rows_written', 0)} NBA rows to Google Sheets"
                )
            else:
                logger.warning(f"Sheets NBA export issue: {export_result.get('error')}")
    except Exception as exc:
        logger.warning(f"Google Sheets export skipped: {exc}")

    return {
        "sport": "nba",
        "game_count": len(predictions),
        "predictions": predictions,
        "bets": bets_to_save,
    }


def main():
    parser = argparse.ArgumentParser(description="Run NBA ML analysis")
    parser.add_argument(
        "--prediction-only",
        action="store_true",
        help="Run without bet sizing and bet persistence",
    )
    args = parser.parse_args()
    asyncio.run(run_nba_analysis(prediction_only=args.prediction_only))


if __name__ == "__main__":
    main()
