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
        
        # In a fully fleshed out system, we would call a `get_scores` endpoint:
        # scores = await self.sports_api.get_scores(api_sport, days_from=1)
        # But since that method isn't implemented in sports_api.py yet, we'll
        # mock the settlement for testing purposes (or until the API is connected).
        
        # MOCK IMPLEMENTATION (Replace with actual score fetching later)
        logger.warning("Automated settlement via API not fully implemented. Manual or Mock settlement required.")
        
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

