import asyncio
import pandas as pd
from typing import List, Dict, Any
from loguru import logger

from app.services.sports_api import SportsAPIService


def american_to_decimal(american_odds: float) -> float:
    """Converts American odds to decimal odds."""
    if american_odds >= 100:
        return (american_odds / 100) + 1
    else:
        return (100 / abs(american_odds)) + 1


async def get_best_props(min_odds: int = -200, max_odds: int = 500):
    """
    Fetches, analyzes, filters, and ranks player props.
    """
    logger.info("Starting prop analysis...")
    sports_api = SportsAPIService()
    all_props_with_edge: List[Dict[str, Any]] = []

    for sport in ["basketball_nba", "basketball_ncaab"]:
        logger.info(f"Fetching props for {sport}...")
        props = await sports_api.get_all_player_props(sport)
        logger.info(f"Found {len(props)} props for {sport}.")

        for prop in props:
            # Calculate EV edge for both over and under
            over_decimal_odds = american_to_decimal(prop["over_odds"])
            under_decimal_odds = american_to_decimal(prop["under_odds"])

            over_ev = (prop["devigged_over_prob"] * over_decimal_odds) - 1
            under_ev = (prop["devigged_under_prob"] * under_decimal_odds) - 1

            prop["over_edge_pct"] = over_ev * 100
            prop["under_edge_pct"] = under_ev * 100

            # Determine the best edge for this prop
            if over_ev > under_ev:
                prop["best_edge_pct"] = prop["over_edge_pct"]
                prop["best_side"] = "Over"
                prop["best_odds"] = prop["over_odds"]
            else:
                prop["best_edge_pct"] = prop["under_edge_pct"]
                prop["best_side"] = "Under"
                prop["best_odds"] = prop["under_odds"]

            all_props_with_edge.append(prop)

    logger.info(f"Total props analyzed: {len(all_props_with_edge)}")

    # Filter props based on odds criteria
    filtered_props = [
        p
        for p in all_props_with_edge
        if min_odds <= p["over_odds"] <= max_odds
        and min_odds <= p["under_odds"] <= max_odds
    ]
    logger.info(
        f"Props after filtering (odds {min_odds} to {max_odds}): {len(filtered_props)}"
    )

    # Sort by the best edge in descending order
    ranked_props = sorted(
        filtered_props, key=lambda x: x["best_edge_pct"], reverse=True
    )

    # Display the results
    if ranked_props:
        df = pd.DataFrame(ranked_props)
        # Select and reorder columns for display
        display_cols = [
            "player",
            "prop_type",
            "line",
            "best_side",
            "best_odds",
            "best_edge_pct",
            "best_over_book",
            "best_under_book",
            "home_team",
            "away_team",
        ]
        # Filter df to only columns that exist
        display_cols = [col for col in display_cols if col in df.columns]
        df = df[display_cols]

        # Format edge percentage
        df["best_edge_pct"] = df["best_edge_pct"].map("{:,.2f}%".format)

        print("\n--- Top Player Props by Edge ---")
        print(df.to_string(index=False))
    else:
        logger.warning("No props found matching the specified criteria.")


if __name__ == "__main__":
    asyncio.run(get_best_props())
