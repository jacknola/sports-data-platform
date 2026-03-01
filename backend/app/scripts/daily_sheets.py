import asyncio
import pandas as pd
from loguru import logger

from app.services.nba_ml_predictor import NBAMLPredictor
from app.services.ncaab_ml_predictor import NCAABMLPredictor


async def generate_nba_predictions():
    """Generates and saves NBA predictions to a CSV file."""
    logger.info("Generating NBA predictions for daily sheet...")
    predictor = NBAMLPredictor()
    predictions = await predictor.predict_today_games()

    if predictions:
        df = pd.DataFrame(predictions)
        df.to_csv("sheets/nba_predictions.csv", index=False)
        logger.info("NBA predictions saved to sheets/nba_predictions.csv")
    else:
        logger.warning("No NBA predictions were generated.")


async def generate_ncaab_predictions():
    """Generates and saves NCAAB predictions to a CSV file."""
    logger.info("Generating NCAAB predictions for daily sheet...")
    predictor = NCAABMLPredictor()
    predictions = await predictor.predict_today_games()

    if predictions:
        df = pd.DataFrame(predictions)
        df.to_csv("sheets/ncaab_predictions.csv", index=False)
        logger.info("NCAAB predictions saved to sheets/ncaab_predictions.csv")
    else:
        logger.warning("No NCAAB predictions were generated.")


async def main():
    """Main function to run both prediction generators."""
    await generate_nba_predictions()
    await generate_ncaab_predictions()


if __name__ == "__main__":
    asyncio.run(main())
