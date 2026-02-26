import pandas as pd
from sqlalchemy import create_engine
engine = create_engine("postgresql://postgres:Maheart1622!@127.0.0.1:5433/postgres")
df = pd.read_sql("SELECT DISTINCT home_team FROM model_training_data WHERE league = 'NBA' ORDER BY home_team", engine)
print(df['home_team'].tolist())
