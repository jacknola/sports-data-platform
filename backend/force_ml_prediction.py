
import asyncio
import pickle
import pandas as pd
from datetime import datetime
from app.services.nba_stats_service import NBAStatsService
from app.services.sports_api import SportsAPIService

async def run_forced_ml_prediction():
    print("="*60)
    print("NBA ML PREDICTIONS (FORCED INFERENCE)")
    print("="*60)
    try:
        with open('models/nba_ml/moneyline_model.pkl', 'rb') as f:
            ml_model = pickle.load(f)
        with open('models/nba_ml/underover_model.pkl', 'rb') as f:
            uo_model = pickle.load(f)
        print("[✓] Models loaded")
    except Exception as e:
        print(f"[✗] Model error: {e}")
        return
    stats_service = NBAStatsService()
    team_stats = await stats_service._nba_api_all_team_stats()
    if not team_stats:
        print("[✗] No stats")
        return
    from run_tomorrow_slate import scrape_action_network
    games = await scrape_action_network("nba")
    if not games:
        print("[!] No tomorrow games from scrape, checking cache...")
        api = SportsAPIService()
        disc = await api.discover_games("basketball_nba")
        for g in disc.data:
            games.append({"home": g.get("home_team"), "away": g.get("away_team")})
    if not games:
        print("[✗] No games found")
        return
    full_to_abbr = {v['team_name']: k for k, v in team_stats.items()}
    print(f"{'AWAY':<20} @ {'HOME':<20} | {'WIN %':<10} | {'FAIR':<10} | {'PROJ TOTAL'}")
    print("-" * 76)
    for g in games:
        h_name, a_name = g['home'], g['away']
        h_abbr = full_to_abbr.get(h_name)
        if not h_abbr: h_abbr = next((abbr for name, abbr in full_to_abbr.items() if h_name in name or name in h_name), None)
        a_abbr = full_to_abbr.get(a_name)
        if not a_abbr: a_abbr = next((abbr for name, abbr in full_to_abbr.items() if a_name in name or name in a_name), None)
        if not h_abbr or not a_abbr:
            print(f"{a_name[:18]:<20} @ {h_name[:18]:<20} | MAPPING FAILED")
            continue
        hs, as_ = team_stats[h_abbr], team_stats[a_abbr]
        feat = pd.DataFrame([{
            'home_off_rating': hs['off_rating'], 'home_def_rating': hs['def_rating'],
            'away_off_rating': as_['off_rating'], 'away_def_rating': as_['def_rating'],
            'home_win_pct': hs.get('win_pct', 0.5), 'away_win_pct': as_.get('win_pct', 0.5)
        }])
        probs = ml_model.predict_proba(feat)[0]
        h_prob = probs[1]
        winner = h_name if h_prob >= 0.5 else a_name
        win_p = h_prob if h_prob >= 0.5 else (1 - h_prob)
        fair = int(-100 * (win_p / (1 - win_p))) if win_p >= 0.5 else int(100 * ((1 - win_p) / win_p))
        total_proj = uo_model.predict(feat)[0]
        print(f"{a_name[:18]:<20} @ {h_name[:18]:<20} | {win_p:.1%} ({winner[:3]}) | {fair:+d} | {total_proj:.1f}")

if __name__ == "__main__":
    asyncio.run(run_forced_ml_prediction())
