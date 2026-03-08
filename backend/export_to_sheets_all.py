import asyncio
import os
import json
import pandas as pd
from loguru import logger
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from qdrant_client.http import models as qmodels

from app.services.nba_ml_predictor import NBAMLPredictor
from app.services.ncaab_ml_predictor import NCAABMLPredictor
from app.services.google_sheets import GoogleSheetsService
from app.services.nba_stats_service import NBAStatsService
from app.services.prop_probability import PropProbabilityModel
from app.services.vector_store import VectorStoreService
from app.config import settings

# --- LOCAL DATA HELPERS ---

def get_cached_slate(engine, sport_key="basketball_nba"):
    """Fetch the latest slate from the local api_cache table"""
    try:
        query = f"SELECT data FROM api_cache WHERE key = 'oddsapi_events_{sport_key}' ORDER BY timestamp DESC LIMIT 1"
        df = pd.read_sql(query, engine)
        if df.empty:
            return []
        return json.loads(df.iloc[0]['data'])
    except Exception as e:
        logger.error(f"Failed to read cached slate: {e}")
        return []

def get_team_players(engine, team_name):
    """Find players who played for this team recently in the DB"""
    try:
        # Match team name (handling full name vs abbreviations)
        team_query = f"SELECT id FROM teams WHERE name ILIKE '%%{team_name}%%' LIMIT 1"
        team_df = pd.read_sql(team_query, engine)
        
        if team_df.empty:
            logger.warning(f"No team found matching '{team_name}'")
            return []
            
        team_id = team_df.iloc[0]['id']
        # Use a large interval since logs are from early 2025
        query = f"""
            SELECT DISTINCT p.name 
            FROM players p
            JOIN player_game_logs l ON p.id = l.player_id
            WHERE l.team_id = {team_id} 
            AND l.game_date > '2024-01-01'
        """
        players = pd.read_sql(query, engine)['name'].tolist()
        return players
    except Exception as e:
        logger.error(f"Failed to get players for {team_name}: {e}")
        return []

# --- MAIN EXPORT ---

async def run_full_export():
    logger.info("🚀 Starting STRICTLY LOCAL Export to Google Sheets...")
    
    # 1. Initialize Services
    engine = create_engine(settings.DATABASE_URL)
    nba_predictor = NBAMLPredictor()
    ncaab_predictor = NCAABMLPredictor()
    sheets_service = GoogleSheetsService()
    nba_stats = NBAStatsService()
    prop_model = PropProbabilityModel()
    vector_store = VectorStoreService()
    
    spreadsheet_id = settings.GOOGLE_SPREADSHEET_ID or "1Ape6MIzwQeJEBApRyyXjz9YSrZYyBWV2S6xP__IpWs0"
    
    # 2. NBA Game Predictions
    logger.info("🏀 Loading NBA Slate from local cache...")
    nba_events = get_cached_slate(engine, "basketball_nba")
    nba_predictions = []
    
    for ev in nba_events:
        home, away = ev.get("home_team"), ev.get("away_team")
        pred = await nba_predictor.predict_game(home, away, {"odds": {"home": -110, "away": -110}})
        nba_predictions.append(pred)
    
    logger.success(f"Generated {len(nba_predictions)} NBA game predictions from local data")

    # 3. NCAAB Game Predictions
    logger.info("🎓 Loading NCAAB Slate from local cache...")
    ncaab_events = get_cached_slate(engine, "basketball_ncaab")
    ncaab_data = {"game_analyses": [], "bets": []}
    
    for ev in ncaab_events:
        home, away = ev.get("home_team"), ev.get("away_team")
        pred = ncaab_predictor._predict_game(home, away, {})
        analysis = {
            "game": {"home": home, "away": away, "game_id": ev.get("id", f"{home}_{away}"), "conference": "", "spread": 0, "total": "", "pinnacle_home_odds": -110, "pinnacle_away_odds": -110},
            "sharp_signals": ["LOCAL_ML"],
            "home_edge": pred.get("expected_value", {}).get("home_ev", 0),
            "away_edge": pred.get("expected_value", {}).get("away_ev", 0),
            "true_home_prob": pred.get("home_win_probability", 0.5),
            "true_away_prob": pred.get("away_win_probability", 0.5),
            "confidence_level": "MEDIUM", "historical_context": []
        }
        ncaab_data["game_analyses"].append(analysis)

    # 4. NBA Player Prop Projections
    logger.info("👤 Discovering players from tonight's teams for prop projections...")
    analyzed_props = []
    team_stats_map = await nba_stats._nba_api_all_team_stats()

    # Build reverse map: full team name (lowercase) → abbreviation
    _name_to_abbrev = {v["team_name"].lower(): k for k, v in (team_stats_map or {}).items()}

    # Build abbrev → opponent abbrev map from tonight's slate
    abbrev_opponent_map: dict = {}
    for ev in nba_events:
        h_abbrev = _name_to_abbrev.get((ev.get("home_team") or "").lower(), "")
        a_abbrev = _name_to_abbrev.get((ev.get("away_team") or "").lower(), "")
        if h_abbrev and a_abbrev:
            abbrev_opponent_map[h_abbrev] = a_abbrev
            abbrev_opponent_map[a_abbrev] = h_abbrev

    active_teams = set()
    for ev in nba_events:
        active_teams.add(ev["home_team"])
        active_teams.add(ev["away_team"])
    
    all_target_players = []
    for team in active_teams:
        players = get_team_players(engine, team)
        logger.info(f"Found {len(players)} players for {team}")
        all_target_players.extend([(p, team) for p in players])

    logger.info(f"Processing {len(all_target_players)} potential player props...")
    
    for player_name, team in all_target_players:
        prop_type = "points"
        research = await nba_stats.get_player_prop_research(player_name, prop_type, 0.0)
        if "error" in research: continue
            
        home_abbrev = research["player"]["team_abbreviation"]
        
        # 5. QDRANT situational context
        situational_context = "No historical analogs in Qdrant."
        try:
            hits = vector_store.client.scroll(
                collection_name="nba_historical_props",
                scroll_filter=qmodels.Filter(
                    must=[qmodels.FieldCondition(key="player_name", match=qmodels.MatchValue(value=player_name))]
                ),
                limit=3
            )[0]
            if hits:
                recent_actuals = [str(int(h.payload.get('actual_points_scored', 0))) for h in hits]
                situational_context = f"Qdrant History: {', '.join(recent_actuals)} | Avg: {research['season_averages'].get(research['stat_keys'][0], 'N/A') if research['season_averages'] else 'N/A'}"
        except Exception as e:
            logger.debug(f"Qdrant retrieval failed for {player_name}: {e}")

        h_stats = team_stats_map.get(home_abbrev, {})
        opp_abbrev = abbrev_opponent_map.get(home_abbrev, "")
        opp_stats = team_stats_map.get(opp_abbrev, {})
        game_context = {
            "team_pace": float(h_stats.get("pace") or 100.0),
            "opponent_pace": float(opp_stats.get("pace") or 100.0),
            "opponent_def_rating": float(opp_stats.get("def_rating") or 113.5),
            "is_home": True,
        }
        
        player_data = {
            "player_id": str(research["player"]["id"]), "player_name": research["player"]["name"], "stat_type": prop_type, "line": 0.0,
            "season_avg": research["season_averages"].get(research["stat_keys"][0], 0.0) if research["season_averages"] else 0.0,
            "last_5_avg": research["rolling_averages"].get("L5", {}).get(research["stat_keys"][0], 0.0),
            "usage_rate": 0.20, "usage_trend": 0.0, "injury_status": "ACTIVE", "rest_days": 2,
        }
        
        try:
            projection = prop_model.project(player_data, game_context, -110, -110)
            analyzed_props.append({
                "player_name": player_name, "stat_type": prop_type, "line": 0.0,
                "best_side": "PROJECTION", "over_odds": -110, "under_odds": -110,
                "bayesian_edge": 0.0, "ev_classification": "local_projection",
                "kelly_fraction": 0.0, "home_team": team, "away_team": "OPP",
                "sharp_signals": ["DATABASE"],
                "projected_mean": projection.projected_mean,
                "situational_context": situational_context,
                "best_over_book": "DB", "best_under_book": "DB",
            })
        except Exception as e:
            logger.error(f"Failed projection for {player_name}: {e}")

    prop_data = {"props": analyzed_props, "total_props": len(analyzed_props), "positive_ev_count": 0}

    # 6. Export to Sheets
    logger.info(f"📊 Exporting to Google Sheet: {spreadsheet_id}")
    results = sheets_service.export_daily_picks(
        spreadsheet_id=spreadsheet_id,
        ncaab_data=ncaab_data,
        nba_predictions=nba_predictions,
        nba_bets=[],
        prop_data=prop_data
    )
    
    logger.success("✅ Strictly Local Export Complete!")
    return results

if __name__ == "__main__":
    asyncio.run(run_full_export())
