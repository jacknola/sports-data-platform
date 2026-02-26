import sys
import os
import csv
import argparse
from datetime import datetime
from loguru import logger

# Setup paths
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from app.database import SessionLocal, engine, Base
from app.models.historical_game_line import HistoricalGameLine

def clean_float(val):
    if val is None or str(val).strip() == "" or str(val).lower() == "nan": return None
    try:
        return float(str(val).replace("PK", "0").replace("pk", "0"))
    except: return None

def clean_int(val):
    if val is None or str(val).strip() == "" or str(val).lower() == "nan": return None
    try:
        return int(float(val))
    except: return None

def import_csv(file_path: str, dry_run: bool = False):
    logger.info("Ensuring table exists...")
    Base.metadata.create_all(bind=engine)

    if not os.path.exists(file_path):
        logger.error(f"File not found: {file_path}")
        return

    db = SessionLocal()
    try:
        # Get existing IDs to avoid duplicates
        existing_ids = {id[0] for id in db.query(HistoricalGameLine.external_line_id).all()}
        logger.info(f"Checking against {len(existing_ids)} existing records.")

        with open(file_path, mode='r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            
            to_add = []
            count = 0
            for row in reader:
                # MATCHING YOUR HEADERS: date, home, away
                date_str = row.get("date")
                home = row.get("home")
                away = row.get("away")
                
                if not date_str or not home:
                    continue

                # Create a unique ID to prevent double-importing the same game
                ext_id = f"kaggle_{date_str}_{home}_{away}"

                if ext_id in existing_ids:
                    continue

                game_date = datetime.strptime(date_str, "%Y-%m-%d")
                
                # Create the model instance using your actual CSV column names
                line = HistoricalGameLine(
                    game_date=game_date,
                    season=clean_int(row.get("season")),
                    home_team=home,
                    away_team=away,
                    home_score=clean_int(row.get("score_home")),
                    away_score=clean_int(row.get("score_away")),
                    home_ml=clean_int(row.get("moneyline_home")),
                    away_ml=clean_int(row.get("moneyline_away")),
                    home_spread=clean_float(row.get("spread")),
                    # Usually Kaggle spread is for the favorite; 
                    # we'll store the raw spread value here
                    over_under=clean_float(row.get("total")),
                    source="kaggle",
                    external_line_id=ext_id,
                    external_game_id=f"{date_str}_{home}_{away}",
                    raw_data=row
                )
                
                to_add.append(line)
                existing_ids.add(ext_id) # Prevent duplicates within the same file
                count += 1

                if len(to_add) >= 500:
                    if not dry_run:
                        db.add_all(to_add)
                        db.commit()
                        logger.info(f"Committed {count} records...")
                    to_add = []

            # Final batch
            if to_add and not dry_run:
                db.add_all(to_add)
                db.commit()
            
            logger.success(f"Import Finished. Total new records: {count} (Dry run: {dry_run})")

    except Exception as e:
        logger.exception(f"Fatal error during import: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    import_csv(args.file, args.dry_run)