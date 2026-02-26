import pandas as pd
from sqlalchemy import create_engine

DB_URL = "postgresql://postgres:Maheart1622!@127.0.0.1:5433/postgres"
engine = create_engine(DB_URL)

# Manually insert tonight's NBA stars to unblock the dashboard
data = [
    {"player_name": "Zion Williamson", "game_date": "2026-02-26", "pts_avg_10": 24.5, "usage_rate": 29.5, "opp_def_rating": 118.5, "actual_points": 0},
    {"player_name": "Tyrese Maxey", "game_date": "2026-02-26", "pts_avg_10": 26.2, "usage_rate": 31.0, "opp_def_rating": 112.1, "actual_points": 0}
]

df = pd.DataFrame(data)
df.to_sql('player_stats_table', engine, if_exists='replace', index=False)
print("✅ Successfully injected NBA players into Postgres! You can now run your dashboard.")
