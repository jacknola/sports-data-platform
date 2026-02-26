import pandas as pd
import json
from sqlalchemy import create_engine
engine = create_engine("postgresql://postgres:Maheart1622!@127.0.0.1:5433/postgres")
row = pd.read_sql("SELECT data FROM api_cache WHERE key = 'oddsapi_events_basketball_nba' LIMIT 1", engine).iloc[0]
data = json.loads(row['data'])
print(json.dumps(data[0], indent=2))
