import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from run_nba_analysis import run_nba_analysis


def main() -> None:
    asyncio.run(run_nba_analysis(prediction_only=True))


if __name__ == "__main__":
    main()
