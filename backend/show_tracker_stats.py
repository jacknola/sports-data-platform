"""
Show Betting Performance Stats
Prints win/loss, ROI, and total units from the local BetTracker.
"""

import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from loguru import logger
from app.services.bet_tracker import BetTracker

def main():
    tracker = BetTracker()
    
    # Force use of local SQLite for this script if Supabase isn't explicitly wanted
    if tracker.use_supabase:
        logger.info("Fetching stats from Supabase...")
    else:
        logger.info("Fetching stats from local SQLite database...")

    stats = tracker.get_performance_metrics()
    
    print("
" + "=" * 50)
    print("  BETTING PERFORMANCE TRACKER")
    print("=" * 50)
    print(f"  Total Bets Settled : {stats['total_bets']}")
    print(f"  Record             : {stats['wins']}-{stats['losses']}-{stats['pushes']} (W-L-P)")
    print(f"  Win Rate           : {stats['win_rate'] * 100:.2f}%")
    print(f"  Net Units          : {stats['units']:+.2f} U")
    print(f"  ROI                : {stats['roi'] * 100:+.2f}%")
    print("=" * 50 + "
")
    
    pending = tracker.get_pending_bets("ncaab") + tracker.get_pending_bets("nba")
    if pending:
        print(f"  Active Pending Bets: {len(pending)}")
    else:
        print("  No active pending bets.")

if __name__ == "__main__":
    main()
