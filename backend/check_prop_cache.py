import pandas as pd
from sqlalchemy import create_engine
engine = create_engine("postgresql://postgres:Maheart1622!@127.0.0.1:5433/postgres")
try:
    df = pd.read_sql("SELECT key FROM api_cache WHERE key LIKE '%%props%%'", engine)
    print(df)
except Exception as e:
    print(f"Error: {e}")
