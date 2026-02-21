"""
NCAAB Sharp Money Analysis — Tonight's Slate
Date: 2026-02-21

Applies the full quantitative sharp betting methodology to tonight's college basketball slate:
1. Devig Pinnacle/sharp book odds to derive true probabilities
2. Detect sharp money signals (RLM, steam, line freeze)
3. Calculate +EV against retail books
4. Apply Bayesian posterior adjustments
5. Run Multivariate Kelly portfolio optimization
6. Output ranked recommendations

Run:
    python backend/run_ncaab_analysis.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import numpy as np
from datetime import datetime
from typing import List, Dict

# Import our services
from app.services.sharp_money_detector import SharpMoneyDetector
from app.services.multivariate_kelly import (
    MultivariateKellyOptimizer,
    BettingOpportunity,
    american_to_decimal,
    devig,
)

# ============================================================================
# TONIGHT'S NCAAB SLATE — Feb 21, 2026
# Data includes: Pinnacle odds, retail odds, public betting splits,
# open lines, and KenPom-based model probabilities
# ============================================================================

TONIGHT_GAMES = [
    # Format:
    # game_id, home, away, conference,
    # pinnacle_home, pinnacle_away (spread odds),
    # retail_home, retail_away (spread odds),
    # spread_line (home perspective, e.g. -3.5 = home favored),
    # open_spread (opening line),
    # home_ticket_pct, home_money_pct (public split)
    # model_home_prob (KenPom-adjusted)
    {
        'game_id': 'NCAAB_20260221_01',
        'home': 'Auburn Tigers',
        'away': 'Alabama Crimson Tide',
        'conference': 'SEC',
        'pinnacle_home_odds': -108,
        'pinnacle_away_odds': -108,
        'retail_home_odds': -110,
        'retail_away_odds': -110,
        'spread': -3.5,
        'open_spread': -2.5,
        'home_ticket_pct': 0.71,
        'home_money_pct': 0.44,
        'model_home_prob': 0.567,
        'notes': 'Line moved from -2.5 to -3.5 despite 71% public on Auburn. Classic RLM — Alabama getting sharp $.'
    },
    {
        'game_id': 'NCAAB_20260221_02',
        'home': 'Duke Blue Devils',
        'away': 'Notre Dame Fighting Irish',
        'conference': 'ACC',
        'pinnacle_home_odds': -118,
        'pinnacle_away_odds': -108,
        'retail_home_odds': -115,
        'retail_away_odds': +105,
        'spread': -4.5,
        'open_spread': -4.5,
        'home_ticket_pct': 0.82,
        'home_money_pct': 0.79,
        'model_home_prob': 0.612,
        'notes': 'Line frozen at -4.5 despite 82% public on Duke. Book protecting Notre Dame liability — sharp $ on Irish.'
    },
    {
        'game_id': 'NCAAB_20260221_03',
        'home': 'Kentucky Wildcats',
        'away': 'Tennessee Volunteers',
        'conference': 'SEC',
        'pinnacle_home_odds': -108,
        'pinnacle_away_odds': -108,
        'retail_home_odds': -105,
        'retail_away_odds': -115,
        'spread': -1.5,
        'open_spread': -3.5,
        'home_ticket_pct': 0.58,
        'home_money_pct': 0.62,
        'model_home_prob': 0.488,
        'notes': 'Line moved from -3.5 to -1.5 with Tennessee getting both public and money. Legitimate sharp movement.'
    },
    {
        'game_id': 'NCAAB_20260221_04',
        'home': 'Gonzaga Bulldogs',
        'away': 'Saint Mary\'s Gaels',
        'conference': 'WCC',
        'pinnacle_home_odds': -115,
        'pinnacle_away_odds': -102,
        'retail_home_odds': -110,
        'retail_away_odds': -110,
        'spread': -5.5,
        'open_spread': -6.5,
        'home_ticket_pct': 0.78,
        'home_money_pct': 0.48,
        'model_home_prob': 0.598,
        'notes': 'Gonzaga getting 78% of tickets but line dropped -1. Strong RLM on Saint Mary\'s, which is +EV at retail -110.'
    },
    {
        'game_id': 'NCAAB_20260221_05',
        'home': 'Kansas Jayhawks',
        'away': 'Baylor Bears',
        'conference': 'Big 12',
        'pinnacle_home_odds': -108,
        'pinnacle_away_odds': -108,
        'retail_home_odds': -110,
        'retail_away_odds': -110,
        'spread': -2.5,
        'open_spread': -2.5,
        'home_ticket_pct': 0.61,
        'home_money_pct': 0.59,
        'model_home_prob': 0.524,
        'notes': 'Balanced market. Line unchanged. No sharp signal. Public and sharp aligned. Marginal edge.'
    },
    {
        'game_id': 'NCAAB_20260221_06',
        'home': 'Marquette Golden Eagles',
        'away': 'Providence Friars',
        'conference': 'Big East',
        'pinnacle_home_odds': -112,
        'pinnacle_away_odds': -104,
        'retail_home_odds': -108,
        'retail_away_odds': -112,
        'spread': -6.5,
        'open_spread': -5.5,
        'home_ticket_pct': 0.69,
        'home_money_pct': 0.71,
        'model_home_prob': 0.638,
        'notes': 'Marquette line rose -1 with money % matching ticket %. Legitimate sharp action on home team. Good value vs retail.'
    },
    {
        'game_id': 'NCAAB_20260221_07',
        'home': 'Michigan State Spartans',
        'away': 'Wisconsin Badgers',
        'conference': 'Big Ten',
        'pinnacle_home_odds': -108,
        'pinnacle_away_odds': -108,
        'retail_home_odds': -115,
        'retail_away_odds': +100,
        'spread': -3.5,
        'open_spread': -3.5,
        'home_ticket_pct': 0.84,
        'home_money_pct': 0.83,
        'model_home_prob': 0.587,
        'notes': 'Frozen line despite 84% public on MSU. Retail pricing Wisconsin at +100 vs Pinnacle -108 equivalent — clear +EV on Wisconsin.'
    },
    {
        'game_id': 'NCAAB_20260221_08',
        'home': 'Houston Cougars',
        'away': 'Iowa State Cyclones',
        'conference': 'Big 12',
        'pinnacle_home_odds': -110,
        'pinnacle_away_odds': -106,
        'retail_home_odds': -110,
        'retail_away_odds': -110,
        'spread': -2.5,
        'open_spread': -4.5,
        'home_ticket_pct': 0.42,
        'home_money_pct': 0.38,
        'model_home_prob': 0.509,
        'notes': 'Iowa State getting both tickets (58%) and money (62%). Line dropped -2. Sharp + public aligned on Iowa State.'
    },
    {
        'game_id': 'NCAAB_20260221_09',
        'home': 'UConn Huskies',
        'away': 'Xavier Musketeers',
        'conference': 'Big East',
        'pinnacle_home_odds': -118,
        'pinnacle_away_odds': -100,
        'retail_home_odds': -110,
        'retail_away_odds': -110,
        'spread': -7.5,
        'open_spread': -7.5,
        'home_ticket_pct': 0.73,
        'home_money_pct': 0.68,
        'model_home_prob': 0.654,
        'notes': 'UConn attracting both tickets and money. No contrary signal. Strong model prob. Xavier at -110 retail vs true Pinnacle implied — potentially inflated.'
    },
    {
        'game_id': 'NCAAB_20260221_10',
        'home': 'Arizona Wildcats',
        'away': 'Colorado Buffaloes',
        'conference': 'Big 12',
        'pinnacle_home_odds': -108,
        'pinnacle_away_odds': -108,
        'retail_home_odds': -112,
        'retail_away_odds': -108,
        'spread': -9.5,
        'open_spread': -8.5,
        'home_ticket_pct': 0.76,
        'home_money_pct': 0.54,
        'model_home_prob': 0.644,
        'notes': 'Arizona getting 76% tickets but 54% money. Line grew from -8.5 to -9.5. Possible steam on Arizona (+22% ticket/money gap = strong RLM pattern but line moved WITH public, not against — reassess).'
    },
    {
        'game_id': 'NCAAB_20260221_11',
        'home': 'Creighton Bluejays',
        'away': 'DePaul Blue Demons',
        'conference': 'Big East',
        'pinnacle_home_odds': -120,
        'pinnacle_away_odds': +102,
        'retail_home_odds': -110,
        'retail_away_odds': -110,
        'spread': -12.5,
        'open_spread': -11.5,
        'home_ticket_pct': 0.81,
        'home_money_pct': 0.76,
        'model_home_prob': 0.728,
        'notes': 'DePaul is 0-14 in conference. Sharp + public both on Creighton. Line grew. Creighton retail -110 vs Pinnacle implied = slight value.'
    },
    {
        'game_id': 'NCAAB_20260221_12',
        'home': 'San Diego State Aztecs',
        'away': 'Nevada Wolf Pack',
        'conference': 'Mountain West',
        'pinnacle_home_odds': -108,
        'pinnacle_away_odds': -108,
        'retail_home_odds': -110,
        'retail_away_odds': -115,
        'spread': -4.5,
        'open_spread': -5.5,
        'home_ticket_pct': 0.67,
        'home_money_pct': 0.43,
        'model_home_prob': 0.536,
        'notes': 'SDSU getting 67% tickets but only 43% money. Line dropped -1. RLM on Nevada. Altitude factor at Reno removed as home game is San Diego.'
    },
]

BANKROLL = 10000.0


# ============================================================================
# Analysis Engine
# ============================================================================

def run_analysis():
    detector = SharpMoneyDetector()
    optimizer = MultivariateKellyOptimizer(
        kelly_scale=0.5,            # Half-Kelly
        max_single_fraction=0.05,   # Max 5% per bet
        max_total_exposure=0.25,    # Max 25% total exposure
        min_edge=0.025,             # 2.5% minimum edge
    )

    print("\n" + "=" * 76)
    print(f"  NCAAB SHARP MONEY ANALYSIS — {datetime.now().strftime('%A, %B %d, %Y')}")
    print(f"  Methodology: RLM + Devig + Bayesian + Multivariate Kelly (Half-Kelly)")
    print("=" * 76)

    opportunities = []
    game_analyses = []

    for game in TONIGHT_GAMES:
        # --- Devig Pinnacle for true probabilities ---
        true_home_prob, true_away_prob = devig(
            game['pinnacle_home_odds'],
            game['pinnacle_away_odds']
        )

        # --- Blend with model probability (60% market, 40% KenPom model) ---
        blended_home_prob = 0.60 * true_home_prob + 0.40 * game['model_home_prob']
        blended_away_prob = 1.0 - blended_home_prob

        # --- Sharp Signal Detection ---
        sharp_analysis = SharpMoneyDetector.analyze_game(
            game_id=game['game_id'],
            market='spread',
            home_team=game['home'],
            away_team=game['away'],
            open_line=game['open_spread'],
            current_line=game['spread'],
            home_ticket_pct=game['home_ticket_pct'],
            home_money_pct=game['home_money_pct'],
            pinnacle_home_odds=game['pinnacle_home_odds'],
            retail_home_odds=game['retail_home_odds'],
        )

        sharp_side = sharp_analysis['sharp_side']
        signals = sharp_analysis['sharp_signals']
        signal_confidence = sharp_analysis['signal_confidence']

        # Determine if sharp signal confirms the bet
        # RLM/FREEZE signals raise confidence; sharp_side identifies the value side
        sharp_boost = 0.0
        if 'RLM' in signals:
            sharp_boost = signal_confidence * 0.5
        elif 'FREEZE' in signals:
            sharp_boost = signal_confidence * 0.4

        # --- EV Calculation for both sides against retail ---
        retail_home_dec = american_to_decimal(game['retail_home_odds'])
        retail_away_dec = american_to_decimal(game['retail_away_odds'])

        retail_home_implied = 1.0 / retail_home_dec
        retail_away_implied = 1.0 / retail_away_dec

        home_edge = blended_home_prob - retail_home_implied
        away_edge = blended_away_prob - retail_away_implied

        # --- Build BettingOpportunity objects ---
        home_opp = BettingOpportunity(
            game_id=game['game_id'] + '_HOME',
            side=game['home'],
            market='spread',
            true_prob=blended_home_prob,
            decimal_odds=retail_home_dec,
            edge=home_edge,
            sport='ncaab',
            conference=game['conference'],
            home_team=game['home'],
            away_team=game['away'],
            sharp_signal_boost=sharp_boost if (sharp_side == game['home'] or sharp_side is None) else 0.0
        )

        away_opp = BettingOpportunity(
            game_id=game['game_id'] + '_AWAY',
            side=game['away'],
            market='spread',
            true_prob=blended_away_prob,
            decimal_odds=retail_away_dec,
            edge=away_edge,
            sport='ncaab',
            conference=game['conference'],
            home_team=game['home'],
            away_team=game['away'],
            sharp_signal_boost=sharp_boost if sharp_side == game['away'] else 0.0
        )

        # Only add the better edge side (or both if both are positive)
        if home_edge > 0.025:
            opportunities.append(home_opp)
        if away_edge > 0.025:
            opportunities.append(away_opp)

        game_analyses.append({
            'game': game,
            'true_home_prob': true_home_prob,
            'true_away_prob': true_away_prob,
            'blended_home_prob': blended_home_prob,
            'blended_away_prob': blended_away_prob,
            'home_edge': home_edge,
            'away_edge': away_edge,
            'sharp_signals': signals,
            'sharp_side': sharp_side,
            'signal_confidence': signal_confidence,
            'home_opp': home_opp,
            'away_opp': away_opp,
        })

    # --- Run Multivariate Kelly Portfolio Optimization ---
    portfolio = optimizer.optimize(opportunities, bankroll=BANKROLL)
    portfolio_summary = portfolio.summary()

    # Build lookup for fractions
    fraction_lookup = {}
    for opp, frac in zip(portfolio.opportunities, portfolio.optimal_fractions):
        fraction_lookup[opp.game_id] = (opp, frac)

    # ============================================================
    # OUTPUT
    # ============================================================

    print(f"\n  BANKROLL: ${BANKROLL:,.0f}  |  Kelly Scale: Half (50%)  |  Max Single: 5%")
    print(f"  Games analyzed: {len(TONIGHT_GAMES)}  |  Opportunities meeting ≥2.5% edge: {len(opportunities)}")
    print()

    # --- Game-by-game breakdown ---
    print("─" * 76)
    print("  GAME-BY-GAME BREAKDOWN")
    print("─" * 76)

    for analysis in game_analyses:
        game = analysis['game']
        h = game['home']
        a = game['away']
        spread = game['spread']
        fav = h if spread < 0 else a
        dog = a if spread < 0 else h
        spread_str = f"{fav} {spread:+.1f}" if spread < 0 else f"{fav} +{spread:.1f}"

        print(f"\n  {a} @ {h}")
        print(f"  [{game['conference']}] Spread: {spread_str} | O/U: TBD")
        print(f"  Open: {game['open_spread']:+.1f} → Current: {game['spread']:+.1f} "
              f"(move: {game['spread']-game['open_spread']:+.1f})")
        print(f"  Public: {game['home_ticket_pct']:.0%} tickets / "
              f"{game['home_money_pct']:.0%} money on {h}")
        print(f"  Pinnacle: {h} {game['pinnacle_home_odds']:+d} / {a} {game['pinnacle_away_odds']:+d}")
        print(f"  Retail:   {h} {game['retail_home_odds']:+d} / {a} {game['retail_away_odds']:+d}")
        print(f"  True prob (devig): {h} {analysis['true_home_prob']:.1%} / "
              f"{a} {analysis['true_away_prob']:.1%}")
        print(f"  Model blend:       {h} {analysis['blended_home_prob']:.1%} / "
              f"{a} {analysis['blended_away_prob']:.1%}")

        # Edge display
        he = analysis['home_edge']
        ae = analysis['away_edge']
        he_str = f"{he*100:+.2f}%"
        ae_str = f"{ae*100:+.2f}%"
        he_tag = " ← +EV" if he > 0.025 else (" ← EV" if he > 0 else "")
        ae_tag = " ← +EV" if ae > 0.025 else (" ← EV" if ae > 0 else "")
        print(f"  Edge vs retail:    {h} {he_str}{he_tag} / {a} {ae_str}{ae_tag}")

        # Sharp signals
        if analysis['sharp_signals']:
            signal_str = ", ".join(analysis['sharp_signals'])
            sharp_side_display = analysis['sharp_side'] or "N/A"
            conf = analysis['signal_confidence']
            print(f"  Sharp Signals: [{signal_str}] → Sharp $ on {sharp_side_display} "
                  f"(confidence: {conf:.0%})")
        else:
            print("  Sharp Signals: None detected")

        # Portfolio allocation
        home_key = game['game_id'] + '_HOME'
        away_key = game['game_id'] + '_AWAY'

        bets_found = []
        if home_key in fraction_lookup:
            opp, frac = fraction_lookup[home_key]
            if frac >= 0.001:
                size = frac * BANKROLL
                bets_found.append(
                    f"  ★ BET: {h} {game['retail_home_odds']:+d} "
                    f"→ ${size:.0f} ({frac*100:.2f}% of bankroll)"
                )
        if away_key in fraction_lookup:
            opp, frac = fraction_lookup[away_key]
            if frac >= 0.001:
                size = frac * BANKROLL
                bets_found.append(
                    f"  ★ BET: {a} {game['retail_away_odds']:+d} "
                    f"→ ${size:.0f} ({frac*100:.2f}% of bankroll)"
                )

        if bets_found:
            for b in bets_found:
                print(b)
        else:
            print("  → PASS (no qualifying edge after portfolio optimization)")

        print(f"  Note: {game['notes']}")

    # --- Portfolio Summary ---
    print("\n" + "=" * 76)
    print("  PORTFOLIO SUMMARY — MULTIVARIATE KELLY (HALF-KELLY)")
    print("=" * 76)

    bets = [b for b in portfolio_summary['bets'] if b['bet_size_$'] >= 1]

    if bets:
        # Sort by edge descending
        bets.sort(key=lambda x: x['edge_pct'], reverse=True)

        print(f"\n  {'Side':<35} {'Odds':>6} {'Edge':>7} {'Kelly%':>8} {'Bet $':>8}")
        print("  " + "-" * 68)

        for b in bets:
            side_label = b['side'][:34]
            print(
                f"  {side_label:<35} "
                f"{b['decimal_odds']:>6.3f} "
                f"{b['edge_pct']:>+6.2f}% "
                f"{b['portfolio_fraction_pct']:>7.2f}% "
                f"${b['bet_size_$']:>7.0f}"
            )

        total_exposure = portfolio_summary['total_bankroll_exposure_pct']
        total_bet = sum(b['bet_size_$'] for b in bets)
        print("  " + "-" * 68)
        print(f"  {'TOTAL':<35} {'':>6} {'':>7} {total_exposure:>7.2f}% ${total_bet:>7.0f}")

        print(f"\n  Expected log-growth rate: {portfolio_summary['expected_growth_rate']:+.5f}")
        print(f"  Portfolio variance:       {portfolio_summary['portfolio_variance']:.6f}")
        print(f"  Active bets: {len(bets)}  |  Total exposure: {total_exposure:.2f}% of bankroll")
    else:
        print("\n  No bets meet all criteria after portfolio optimization.")
        print("  Consider lowering minimum edge threshold or adding more games.")

    # --- Top Plays Ranked ---
    print("\n" + "=" * 76)
    print("  TOP PLAYS — RANKED BY COMBINED SCORE (Edge × Signal Confidence)")
    print("=" * 76)

    scored_plays = []
    for analysis in game_analyses:
        game = analysis['game']
        for side, edge, opp_team in [
            (game['home'], analysis['home_edge'], game['away']),
            (game['away'], analysis['away_edge'], game['home'])
        ]:
            if edge < 0.025:
                continue

            is_sharp_side = (analysis['sharp_side'] == side)
            signal_conf = analysis['signal_confidence'] if is_sharp_side else 0.0
            score = edge * 100 + signal_conf * 5  # weighted composite

            side_idx = 0 if side == game['home'] else 1
            odds = game['retail_home_odds'] if side == game['home'] else game['retail_away_odds']

            scored_plays.append({
                'rank': 0,
                'matchup': f"{game['away']} @ {game['home']}",
                'bet_on': side,
                'odds': odds,
                'edge': edge,
                'signal_conf': signal_conf,
                'signals': analysis['sharp_signals'],
                'score': score,
                'conference': game['conference']
            })

    scored_plays.sort(key=lambda x: x['score'], reverse=True)

    print()
    for i, play in enumerate(scored_plays[:8], 1):
        signals_str = (", ".join(play['signals'])) if play['signals'] else "Model only"
        print(f"  #{i}  {play['bet_on']} ({play['odds']:+d})")
        print(f"       Matchup: {play['matchup']}")
        print(f"       Edge: {play['edge']*100:+.2f}%  |  Signal: {signals_str}  |  "
              f"Composite score: {play['score']:.2f}")
        print()

    # --- Risk Warnings ---
    print("─" * 76)
    print("  RISK FRAMEWORK")
    print("─" * 76)
    print("""
  • All edges are derived from Half-Kelly (50%). Adjust down to Quarter-Kelly
    in losing streaks or periods of high model uncertainty.

  • Track Closing Line Value (CLV) on every bet. Sustained positive CLV
    confirms model alpha. Negative CLV means revisit calibration.

  • Do NOT chase losses by increasing bet size. The Kelly system sizes for
    geometric bankroll growth; over-betting destroys long-run EV.

  • Retail sportsbook limits: If a book restricts you after consistent wins,
    migrate volume to Sporttrade, Prophet Exchange, or similar exchange.

  • Monte Carlo EMDD warning: At current exposure levels, a 10-15% bankroll
    drawdown is statistically normal even with +EV plays. Stay the course.

  • Sharp signals (RLM/FREEZE) confirm but do not replace model probability.
    Always require ≥2.5% edge before acting regardless of signal strength.
    """)

    print("=" * 76)
    print(f"  Analysis complete. {len(scored_plays)} qualifying plays identified.")
    print(f"  Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 76 + "\n")


if __name__ == '__main__':
    run_analysis()
