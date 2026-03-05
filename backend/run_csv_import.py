import sys
import os
import argparse
import csv
from datetime import datetime
from typing import Dict, Any, Set

# Ensure local app modules are discoverable
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from loguru import logger
from app.database import SessionLocal
from app.models.historical_game_line import HistoricalGameLine

def detect_season_from_date(date_str: str) -> int:
    """
    Detect NBA season year from date string.
    NBA season usually starts in Oct. If month >= 10, it's the start of that season.
    """
    try:
        date = datetime.strptime(date_str, "%Y-%m-%d")
        return date.year if date.month >= 10 else date.year - 1
    except (ValueError, TypeError):
        return datetime.now().year

def parse_numeric(val: Any, default: Any = None, is_float: bool = False) -> Any:
    """Helper to safely parse CSV strings to numbers."""
    if val is None or str(val).strip() == "":
        return default
    try:
        clean_val = str(val).replace("PK", "0").replace("pk", "0")
        return float(clean_val) if is_float else int(float(clean_val))
    except (ValueError, TypeError):
        return default

def transform_csv_row_to_model(row: Dict[str, str], source: str = "kaggle") -> Optional[Dict[str, Any]]:
    """Transform CSV row to HistoricalGameLine model dictionary."""
    try:
        team = row.get("Team", "").strip()
        opponent = row.get("Opponent", "").strip()
        
        # Kaggle 'VH' column usually uses 'V' (Visitor), 'H' (Home), or 'N' (Neutral)
        # We normalize these to determine which team is which.
        venue = row.get("VH", "N").strip().upper()

        if venue in ["H", "HOME"]:
            home_team, away_team = team, opponent
            home_score = parse_numeric(row.get("Team Score"))
            away_score = parse_numeric(row.get("Opponent Score"))
        elif venue in ["V", "VISITOR", "AWAY"]:
            home_team, away_team = opponent, team
            home_score = parse_numeric(row.get("Opponent Score"))
            away_score = parse_numeric(row.get("Team Score"))
        else:
            home_team, away_team = team, opponent
            home_score = parse_numeric(row.get("Team Score"))
            away_score = parse_numeric(row.get("Opponent Score"))

        game_date_str = row.get("Date", "")
        game_date = datetime.strptime(game_date_str, "%Y-%m-%d") if game_date_str else None
        
        return {
            "game_date": game_date,
            "season": detect_season_from_date(game_date_str),
            "home_team": home_team,
            "away_team": away_team,
            "home_score": home_score,
            "away_score": away_score,
            "total_score": (home_score + away_score) if (home_score is not None and away_score is not None) else None,
            "margin": (home_score - away_score) if (home_score is not None and away_score is not None) else None,
            "home_ml": parse_numeric(row.get("Team Moneyline")),
            "away_ml": parse_numeric(row.get("Opponent Moneyline")),
            "home_spread": parse_numeric(row.get("Team Spread"), is_float=True),
            "away_spread": parse_numeric(row.get("Opponent Spread"), is_float=True),
            "spread_odds": parse_numeric(row.get("Spread Odds")),
            "over_under": parse_numeric(row.get("Over/Under"), is_float=True),
            "over_odds": parse_numeric(row.get("Over Odds")),
            "under_odds": parse_numeric(row.get("Under Odds")),
            "source": source,
            "external_game_id": f"{game_date_str}_{home_team}_{away_team}",
            "external_line_id": f"{source}_{game_date_str}_{home_team}_{away_team}_{venue}",
            "raw_data": row,
        }
    except Exception as e:
        logger.error(f"Error transforming row: {e}")
        return None

def import_csv(file_path: str, source: str = "kaggle", dry_run: bool = False) -> int:
    """Import game lines from CSV file with optimized database lookups."""
    if not os.path.exists(file_path):
        logger.error(f"File not found: {file_path}")
        return 0

    logger.info(f"Reading records from: {file_path}")
    
    parsed_rows = []
    with open(file_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            data = transform_csv_row_to_model(row, source)
            if data:
                parsed_rows.append(data)

    if not parsed_rows:
        logger.warning("No valid data found in CSV.")
        return 0

    if dry_run:
        logger.info(f"[DRY RUN] {len(parsed_rows)} records processed. No changes saved.")
        return len(parsed_rows)

    db = SessionLocal()
    try:
        # Optimization: Fetch all existing IDs for this source in one query
        existing_ids: Set[str] = {
            res[0] for res in db.query(HistoricalGameLine.external_line_id)
            .filter(HistoricalGameLine.source == source)
            .all()
        }
        
        saved_count = 0
        for data in parsed_rows:
            ext_id = data.get("external_line_id")
            if ext_id and ext_id not in existing_ids:
                record = HistoricalGameLine(**data)
                db.add(record)
                existing_ids.add(ext_id) # Avoid duplicates within the same file
                saved_count += 1
                
                if saved_count % 1000 == 0:
                    db.flush() # Send to DB but don't commit yet
                    logger.info(f"Prepared {saved_count} records...")

        db.commit()
        logger.success(f"Import complete! Added {saved_count} new records.")
        return saved_count

    except Exception as e:
        db.rollback()
        logger.error(f"Critical error during database import: {e}")
        return 0
    finally:
        db.close()

def main():
    parser = argparse.ArgumentParser(description="Kaggle NBA betting data import")
    parser.add_argument("--file", type=str, required=True, help="Path to CSV file")
    parser.add_argument("--source", type=str, default="kaggle", help="Source identifier")
    parser.add_argument("--dry-run", action="store_true", help="Preview without saving")
    args = parser.parse_args()

    import_csv(args.file, args.source, args.dry_run)

if __name__ == "__main__":
    main()