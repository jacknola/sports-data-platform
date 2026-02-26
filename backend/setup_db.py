# setup_db.py
from app.database import engine, Base
from app.models.historical_game_line import HistoricalGameLine

print("Creating tables...")
Base.metadata.create_all(bind=engine)
print("Done! Table 'historical_game_lines' should now exist.")