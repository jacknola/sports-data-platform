"""
Bet Settlement Engine

Responsible for pulling pending bets from the BetTracker,
fetching actual game scores/results via the Odds API (or scraper),
and grading the bets as Won, Lost, or Push.
"""

from typing import List, Dict, Any
from datetime import datetime, timedelta
from loguru import logger

from app.services.bet_tracker import BetTracker
from app.services.sports_api import SportsAPIService


class BetSettlementEngine:
    def __init__(self):
        self.tracker = BetTracker()
        self.sports_api = SportsAPIService()
        
    async def settle_pending_bets(self, sport: str = "basketball_ncaab"):
        """Find pending bets, fetch final scores, and grade them."""
        # Note: mapping bet tracker sport 'ncaab' to odds api 'basketball_ncaab'
        api_sport = "basketball_ncaab" if sport == "ncaab" else sport
        
        pending_bets = self.tracker.get_pending_bets(sport=sport)
        if not pending_bets:
            logger.info(f"No pending bets found for {sport}.")
            return
            
        logger.info(f"Found {len(pending_bets)} pending bets to settle.")
        
        if not self.sports_api.odds_api_key:
            # MOCK IMPLEMENTATION (Replace with actual score fetching later when key available)
            logger.warning("Automated settlement via API disabled (No Odds API Key). Mocking settlement for testing.")
            
            # Here we mock grading any bet older than 1 day as "won" randomly for testing
            now = datetime.utcnow()
            for bet in pending_bets:
                bet_date_str = bet.get("date", "")
                try:
                    bet_date = datetime.strptime(bet_date_str, "%Y-%m-%d")
                    # If bet is from yesterday or older, simulate settlement
                    if (now - bet_date).days >= 1:
                        # Mock logic: 60% win rate for demonstration
                        import random
                        status = "won" if random.random() < 0.60 else "lost"
                        self.tracker.update_bet_result(bet["id"], status, clv=1.5)
                        logger.info(f"Mock settled bet {bet['id']} ({bet['side']}) as {status}")
                except Exception as e:
                    logger.error(f"Error parsing date for bet {bet['id']}: {e}")
            return
            
        # LIVE IMPLEMENTATION
        scores = await self.sports_api.get_scores(api_sport, days_from=3)
        if not scores:
            logger.info("No completed scores fetched from Odds API.")
            return
            
        # Build lookup table for completed games by game_id
        # Note: Depending on how game_id was generated in run_ncaab_analysis vs Odds API,
        # you might need fuzzy matching by team names. For now, we assume the IDs match
        # or we match by home/away teams.
        score_lookup = {}
        for game in scores:
            if not game.get('completed'):
                continue
                
            home = game.get('home_team')
            away = game.get('away_team')
            
            # Find scores
            home_score = 0
            away_score = 0
            for score_entry in game.get('scores', []):
                if score_entry['name'] == home:
                    home_score = int(score_entry['score'])
                elif score_entry['name'] == away:
                    away_score = int(score_entry['score'])
                    
            score_lookup[f"{away} @ {home}"] = {
                'home_team': home,
                'away_team': away,
                'home_score': home_score,
                'away_score': away_score
            }
            # Add reverse mapping for robustness
            score_lookup[home] = {'home_team': home, 'away_team': away, 'home_score': home_score, 'away_score': away_score}
            score_lookup[away] = {'home_team': home, 'away_team': away, 'home_score': home_score, 'away_score': away_score}
            
        for bet in pending_bets:
            side = bet['side']
            market = bet['market']
            
            # Find matching game in score_lookup
            game_result = score_lookup.get(side)
            if not game_result:
                continue
                
            home = game_result['home_team']
            away = game_result['away_team']
            home_score = game_result['home_score']
            away_score = game_result['away_score']
            
            status = "pending"
            
            # Spread settlement logic
            if market == "spread":
                # Need to extract the spread value from somewhere.
                # In our tracker, we don't currently save the explicit spread line,
                # we just save the 'side' (e.g., 'Auburn Tigers'). 
                # To grade properly, we need the spread line. 
                # For this implementation, let's assume we can fetch it or we fall back.
                
                # TODO: Update BetTracker to store the line (e.g. -3.5)
                # For now, we can't fully grade without the line value.
                logger.warning(f"Cannot grade spread bet {bet['id']} because line is missing from tracker.")
                continue
                
            elif market == "moneyline":
                if side == home:
                    if home_score > away_score:
                        status = "won"
                    elif home_score < away_score:
                        status = "lost"
                    else:
                        status = "push"
                elif side == away:
                    if away_score > home_score:
                        status = "won"
                    elif away_score < home_score:
                        status = "lost"
                    else:
                        status = "push"
                        
            if status != "pending":
                self.tracker.update_bet_result(bet['id'], status)
                logger.info(f"Settled bet {bet['id']} ({side}) as {status} [{away} {away_score} - {home} {home_score}]")

