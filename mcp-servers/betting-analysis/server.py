#!/usr/bin/env python3
"""
Sports Betting Analysis MCP Server
Exposes sharp money detection, EV calculation, Kelly sizing, and devigging tools
"""
import asyncio
import json
import sys
from typing import Dict, List, Optional, Any
from loguru import logger

# MCP SDK imports
try:
    from mcp.server import Server
    from mcp.types import Tool, TextContent
except ImportError:
    logger.error("MCP SDK not installed. Run: pip install mcp")
    sys.exit(1)

# Configure logger
logger.remove()
logger.add(sys.stderr, level="INFO")

# Initialize MCP server
app = Server("sports-betting-analysis")


def american_to_decimal(american_odds: int) -> float:
    """Convert American odds to decimal odds."""
    if american_odds > 0:
        return (american_odds / 100) + 1
    else:
        return (100 / abs(american_odds)) + 1


def decimal_to_probability(decimal_odds: float) -> float:
    """Convert decimal odds to implied probability."""
    return 1 / decimal_odds


def devig_odds(side_a_odds: float, side_b_odds: float) -> tuple[float, float]:
    """
    Devig two-way market using multiplicative method.
    Returns true probabilities for each side.
    """
    prob_a = decimal_to_probability(side_a_odds)
    prob_b = decimal_to_probability(side_b_odds)
    total_prob = prob_a + prob_b
    
    true_prob_a = prob_a / total_prob
    true_prob_b = prob_b / total_prob
    
    return true_prob_a, true_prob_b


def calculate_ev(true_probability: float, decimal_odds: float) -> float:
    """Calculate expected value (EV) of a bet."""
    return (true_probability * decimal_odds) - 1


def calculate_kelly_stake(
    bankroll: float,
    true_probability: float,
    decimal_odds: float,
    kelly_fraction: float = 0.25,
    max_stake_pct: float = 0.05
) -> Dict[str, float]:
    """
    Calculate Kelly Criterion stake size.
    
    Args:
        bankroll: Total bankroll
        true_probability: True win probability (devigged)
        decimal_odds: Decimal odds offered
        kelly_fraction: Fractional Kelly (0.25 = Quarter Kelly)
        max_stake_pct: Maximum stake as % of bankroll
        
    Returns:
        Dict with stake amount, percentage, and EV
    """
    ev = calculate_ev(true_probability, decimal_odds)
    
    if ev <= 0:
        return {
            "stake_amount": 0.0,
            "stake_pct": 0.0,
            "ev_percent": round(ev * 100, 2),
            "recommendation": "NO BET - Negative EV"
        }
    
    # Kelly formula: (bp - q) / b where b = decimal_odds - 1, p = true_prob, q = 1 - p
    b = decimal_odds - 1
    p = true_probability
    q = 1 - p
    
    kelly_pct = ((b * p) - q) / b
    fractional_kelly_pct = kelly_pct * kelly_fraction
    
    # Cap at max stake percentage
    final_pct = min(fractional_kelly_pct, max_stake_pct)
    stake_amount = bankroll * final_pct
    
    # Round to human-like amounts to avoid algorithmic profiling
    if stake_amount >= 100:
        stake_amount = round(stake_amount / 25) * 25
    elif stake_amount >= 50:
        stake_amount = round(stake_amount / 10) * 10
    else:
        stake_amount = round(stake_amount / 5) * 5
    
    return {
        "stake_amount": float(stake_amount),
        "stake_pct": round(final_pct * 100, 2),
        "ev_percent": round(ev * 100, 2),
        "kelly_fraction": kelly_fraction,
        "recommendation": "BET" if ev > 0.03 else "MARGINAL BET"
    }


def detect_rlm(
    public_pct: float,
    money_pct: Optional[float],
    line_movement: float,
    ticket_pct: Optional[float] = None
) -> Dict[str, Any]:
    """
    Detect Reverse Line Movement (RLM).
    
    Args:
        public_pct: Percentage of public bets on this side
        money_pct: Percentage of money on this side (optional)
        line_movement: Point/odds movement (positive = moved in favor, negative = moved against)
        ticket_pct: Ticket percentage (optional, used if different from public_pct)
        
    Returns:
        RLM analysis with signal strength
    """
    ticket_pct = ticket_pct or public_pct
    money_pct = money_pct or public_pct
    
    # RLM conditions: ≥65% public + line moves against public + ≥10% ticket/money gap
    is_rlm = (
        public_pct >= 65 and
        line_movement < 0 and
        abs(ticket_pct - money_pct) >= 10
    )
    
    # Calculate signal strength
    if is_rlm:
        strength_score = (
            (public_pct - 65) * 0.3 +  # Public percentage weight
            abs(line_movement) * 0.4 +  # Line movement weight
            abs(ticket_pct - money_pct - 10) * 0.3  # Ticket/money gap weight
        )
        
        if strength_score > 20:
            strength = "STRONG"
        elif strength_score > 10:
            strength = "MEDIUM"
        else:
            strength = "WEAK"
    else:
        strength = "NONE"
        strength_score = 0
    
    return {
        "is_rlm": is_rlm,
        "strength": strength,
        "strength_score": round(strength_score, 2),
        "public_pct": public_pct,
        "money_pct": money_pct,
        "line_movement": line_movement,
        "recommendation": "FADE PUBLIC" if is_rlm else "NO SIGNAL"
    }


def detect_steam_move(
    line_changes: List[Dict[str, Any]],
    time_window_seconds: int = 60,
    min_books: int = 3,
    min_movement: float = 0.5
) -> Dict[str, Any]:
    """
    Detect steam moves across multiple books.
    
    Args:
        line_changes: List of {book: str, old_line: float, new_line: float, timestamp: int}
        time_window_seconds: Time window for steam detection
        min_books: Minimum number of books moving line
        min_movement: Minimum point/odds movement
        
    Returns:
        Steam analysis with signal strength
    """
    if len(line_changes) < min_books:
        return {
            "is_steam": False,
            "strength": "NONE",
            "books_moved": len(line_changes),
            "recommendation": "NO STEAM"
        }
    
    # Check if all changes happened within time window
    timestamps = [change["timestamp"] for change in line_changes]
    time_spread = max(timestamps) - min(timestamps)
    
    # Check movement magnitude
    movements = [abs(change["new_line"] - change["old_line"]) for change in line_changes]
    avg_movement = sum(movements) / len(movements)
    
    is_steam = (
        time_spread <= time_window_seconds and
        len(line_changes) >= min_books and
        avg_movement >= min_movement
    )
    
    if is_steam:
        # Steam strength based on speed, number of books, and movement size
        strength_score = (
            (len(line_changes) - min_books) * 5 +
            avg_movement * 10 +
            (time_window_seconds - time_spread) / 10
        )
        
        if strength_score > 30:
            strength = "STRONG"
        elif strength_score > 15:
            strength = "MEDIUM"
        else:
            strength = "WEAK"
    else:
        strength = "NONE"
        strength_score = 0
    
    return {
        "is_steam": is_steam,
        "strength": strength,
        "strength_score": round(strength_score, 2),
        "books_moved": len(line_changes),
        "avg_movement": round(avg_movement, 2),
        "time_spread_seconds": time_spread,
        "recommendation": "FOLLOW STEAM" if is_steam else "NO STEAM"
    }


@app.list_tools()
async def list_tools() -> List[Tool]:
    """List all available tools."""
    return [
        Tool(
            name="calculate_ev",
            description="Calculate expected value (EV) of a bet given true probability and odds",
            inputSchema={
                "type": "object",
                "properties": {
                    "true_probability": {
                        "type": "number",
                        "description": "True win probability (0.0 to 1.0) after devigging"
                    },
                    "decimal_odds": {
                        "type": "number",
                        "description": "Decimal odds offered by bookmaker"
                    }
                },
                "required": ["true_probability", "decimal_odds"]
            }
        ),
        Tool(
            name="devig_two_way_market",
            description="Devig a two-way market to find true probabilities using sharp book odds",
            inputSchema={
                "type": "object",
                "properties": {
                    "side_a_odds": {
                        "type": "number",
                        "description": "Decimal odds for side A"
                    },
                    "side_b_odds": {
                        "type": "number",
                        "description": "Decimal odds for side B"
                    }
                },
                "required": ["side_a_odds", "side_b_odds"]
            }
        ),
        Tool(
            name="calculate_kelly_stake",
            description="Calculate optimal stake size using Fractional Kelly Criterion",
            inputSchema={
                "type": "object",
                "properties": {
                    "bankroll": {
                        "type": "number",
                        "description": "Total bankroll amount"
                    },
                    "true_probability": {
                        "type": "number",
                        "description": "True win probability (0.0 to 1.0)"
                    },
                    "decimal_odds": {
                        "type": "number",
                        "description": "Decimal odds offered"
                    },
                    "kelly_fraction": {
                        "type": "number",
                        "description": "Kelly fraction (0.25 = Quarter Kelly, 0.5 = Half Kelly)",
                        "default": 0.25
                    },
                    "max_stake_pct": {
                        "type": "number",
                        "description": "Maximum stake as percentage of bankroll (0.05 = 5%)",
                        "default": 0.05
                    }
                },
                "required": ["bankroll", "true_probability", "decimal_odds"]
            }
        ),
        Tool(
            name="detect_rlm",
            description="Detect Reverse Line Movement (sharp money indicator)",
            inputSchema={
                "type": "object",
                "properties": {
                    "public_pct": {
                        "type": "number",
                        "description": "Percentage of public bets on this side (0-100)"
                    },
                    "money_pct": {
                        "type": "number",
                        "description": "Percentage of money on this side (0-100)"
                    },
                    "line_movement": {
                        "type": "number",
                        "description": "Point/odds movement (negative = moved against public)"
                    },
                    "ticket_pct": {
                        "type": "number",
                        "description": "Ticket percentage if different from public_pct"
                    }
                },
                "required": ["public_pct", "line_movement"]
            }
        ),
        Tool(
            name="detect_steam_move",
            description="Detect steam moves (synchronized sharp money across multiple books)",
            inputSchema={
                "type": "object",
                "properties": {
                    "line_changes": {
                        "type": "array",
                        "description": "Array of line changes: [{book: str, old_line: float, new_line: float, timestamp: int}]",
                        "items": {
                            "type": "object"
                        }
                    },
                    "time_window_seconds": {
                        "type": "number",
                        "description": "Time window for steam detection (default 60)",
                        "default": 60
                    },
                    "min_books": {
                        "type": "number",
                        "description": "Minimum number of books moving (default 3)",
                        "default": 3
                    },
                    "min_movement": {
                        "type": "number",
                        "description": "Minimum point/odds movement (default 0.5)",
                        "default": 0.5
                    }
                },
                "required": ["line_changes"]
            }
        ),
        Tool(
            name="convert_american_odds",
            description="Convert American odds to decimal odds and implied probability",
            inputSchema={
                "type": "object",
                "properties": {
                    "american_odds": {
                        "type": "number",
                        "description": "American odds (e.g., -110, +150)"
                    }
                },
                "required": ["american_odds"]
            }
        )
    ]


@app.call_tool()
async def call_tool(name: str, arguments: Any) -> List[TextContent]:
    """Handle tool calls."""
    try:
        if name == "calculate_ev":
            result = calculate_ev(
                arguments["true_probability"],
                arguments["decimal_odds"]
            )
            return [TextContent(
                type="text",
                text=json.dumps({"ev_percent": round(result * 100, 2)}, indent=2)
            )]
            
        elif name == "devig_two_way_market":
            true_prob_a, true_prob_b = devig_odds(
                arguments["side_a_odds"],
                arguments["side_b_odds"]
            )
            return [TextContent(
                type="text",
                text=json.dumps({
                    "side_a_true_probability": round(true_prob_a, 4),
                    "side_b_true_probability": round(true_prob_b, 4),
                    "side_a_true_odds": round(1 / true_prob_a, 2),
                    "side_b_true_odds": round(1 / true_prob_b, 2)
                }, indent=2)
            )]
            
        elif name == "calculate_kelly_stake":
            result = calculate_kelly_stake(
                arguments["bankroll"],
                arguments["true_probability"],
                arguments["decimal_odds"],
                arguments.get("kelly_fraction", 0.25),
                arguments.get("max_stake_pct", 0.05)
            )
            return [TextContent(type="text", text=json.dumps(result, indent=2))]
            
        elif name == "detect_rlm":
            result = detect_rlm(
                arguments["public_pct"],
                arguments.get("money_pct"),
                arguments["line_movement"],
                arguments.get("ticket_pct")
            )
            return [TextContent(type="text", text=json.dumps(result, indent=2))]
            
        elif name == "detect_steam_move":
            result = detect_steam_move(
                arguments["line_changes"],
                arguments.get("time_window_seconds", 60),
                arguments.get("min_books", 3),
                arguments.get("min_movement", 0.5)
            )
            return [TextContent(type="text", text=json.dumps(result, indent=2))]
            
        elif name == "convert_american_odds":
            decimal = american_to_decimal(arguments["american_odds"])
            probability = decimal_to_probability(decimal)
            return [TextContent(
                type="text",
                text=json.dumps({
                    "american_odds": arguments["american_odds"],
                    "decimal_odds": round(decimal, 3),
                    "implied_probability": round(probability, 4),
                    "implied_probability_pct": round(probability * 100, 2)
                }, indent=2)
            )]
            
        else:
            return [TextContent(type="text", text=f"Unknown tool: {name}")]
            
    except Exception as e:
        logger.error(f"Error calling tool {name}: {e}")
        return [TextContent(type="text", text=f"Error: {str(e)}")]


async def main():
    """Run the MCP server."""
    from mcp.server.stdio import stdio_server
    
    async with stdio_server() as (read_stream, write_stream):
        logger.info("Sports Betting Analysis MCP Server starting...")
        await app.run(
            read_stream,
            write_stream,
            app.create_initialization_options()
        )


if __name__ == "__main__":
    asyncio.run(main())
