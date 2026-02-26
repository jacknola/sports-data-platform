from qdrant_client import QdrantClient, models
from sqlalchemy import create_engine
import pandas as pd
from loguru import logger
import time

# Config
DB_URL = "postgresql://postgres:Maheart1622!@127.0.0.1:5433/postgres"
QDRANT_URL = "https://352acfb0-6be8-40b1-8e1b-6200017965a3.sa-east-1-0.aws.cloud.qdrant.io"
QDRANT_API_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhY2Nlc3MiOiJtIn0.nh7143g9480DVamRGXe1E6ftgJnmj9zazttqrtZVO10"

engine = create_engine(DB_URL)
client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_API_KEY)

def prepare_and_sync():
    try:
        # 1. Ensure the Index exists (Fixes the 400 error permanently)
        logger.info("Verifying Payload Index for 'player_name'...")
        client.create_payload_index(
            collection_name="player_performances",
            field_name="player_name",
            field_schema=models.PayloadSchemaType.KEYWORD,
        )
        # Give Qdrant a few seconds to breathe and build the index
        time.sleep(5) 

        # 2. Fetch Tonights Stars (Thursday, Feb 26, 2026)
        # Added a few more names for tonight's big slate
        target_players = ["Zion Williamson", "Tyrese Maxey", "Jimmy Butler", "Zach Edey"]
        synced_data = []

        logger.info(f"Fetching vectors for {len(target_players)} players...")
        for p_name in target_players:
            res, _ = client.scroll(
                collection_name="player_performances",
                scroll_filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="player_name",
                            match=models.MatchValue(value=p_name)
                        )
                    ]
                ),
                limit=1,
                with_payload=True
            )
            
            if res:
                p = res[0].payload
                logger.info(f"✅ Found {p_name}")
                synced_data.append({
                    "player_name": p_name,
                    "game_date": "2026-02-26",
                    "pts_avg_10": p.get('pts_avg_10', 0) if p else 0,
                    "usage_rate": p.get('usage_rate', 0) if p else 0,
                    "opp_def_rating": p.get('opp_def_rating', 0) if p else 0
                })

        if synced_data:
            df = pd.DataFrame(synced_data)
            df.to_sql('player_stats_table', engine, if_exists='replace', index=False)
            logger.success(f"Gameday ready! {len(synced_data)} players synced to Postgres.")
        else:
            logger.error("Still couldn't find players. Double-check the spelling in Qdrant!")

    except Exception as e:
        logger.error(f"Gameday Sync Failed: {e}")

if __name__ == "__main__":
    prepare_and_sync()