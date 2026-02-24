#!/usr/bin/env python3
"""
Google Sheets Reporting MCP Server
Export betting slates, track performance, and generate reports
"""
import asyncio
import json
import os
import sys
from datetime import datetime
from typing import Dict, List, Any, Optional
from loguru import logger

# MCP SDK imports
try:
    from mcp.server import Server
    from mcp.types import Tool, TextContent
except ImportError:
    logger.error("MCP SDK not installed. Run: pip install mcp")
    sys.exit(1)

# Google Sheets imports
try:
    import gspread
    from google.oauth2.service_account import Credentials
except ImportError:
    logger.error("Google Sheets dependencies not installed. Run: pip install gspread google-auth")
    sys.exit(1)

# Configure logger
logger.remove()
logger.add(sys.stderr, level="INFO")

# Initialize MCP server
app = Server("google-sheets-reporting")

# Google Sheets configuration
SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive'
]


def get_sheets_client() -> Optional[gspread.Client]:
    """Initialize Google Sheets client with service account credentials."""
    try:
        creds_path = os.environ.get(
            'GOOGLE_CREDENTIALS_PATH',
            '/app/credentials/google-sa.json'
        )
        
        if not os.path.exists(creds_path):
            logger.error(f"Credentials file not found: {creds_path}")
            return None
            
        creds = Credentials.from_service_account_file(creds_path, scopes=SCOPES)
        return gspread.authorize(creds)
    except Exception as e:
        logger.error(f"Failed to initialize Google Sheets client: {e}")
        return None


@app.list_tools()
async def list_tools() -> List[Tool]:
    """List all available tools."""
    return [
        Tool(
            name="export_betting_slate",
            description="Export a betting slate (recommended bets) to Google Sheets",
            inputSchema={
                "type": "object",
                "properties": {
                    "spreadsheet_id": {
                        "type": "string",
                        "description": "Google Sheets spreadsheet ID"
                    },
                    "bets": {
                        "type": "array",
                        "description": "Array of bet objects with game, pick, odds, stake, ev, etc.",
                        "items": {
                            "type": "object"
                        }
                    },
                    "sheet_name": {
                        "type": "string",
                        "description": "Name of the sheet/tab (default: 'Daily Slate')",
                        "default": "Daily Slate"
                    },
                    "date": {
                        "type": "string",
                        "description": "Date for the slate (YYYY-MM-DD, default: today)"
                    }
                },
                "required": ["spreadsheet_id", "bets"]
            }
        ),
        Tool(
            name="log_bet_results",
            description="Log bet results and update performance tracking",
            inputSchema={
                "type": "object",
                "properties": {
                    "spreadsheet_id": {
                        "type": "string",
                        "description": "Google Sheets spreadsheet ID"
                    },
                    "results": {
                        "type": "array",
                        "description": "Array of bet result objects with bet_id, outcome, profit, clv, etc.",
                        "items": {
                            "type": "object"
                        }
                    },
                    "sheet_name": {
                        "type": "string",
                        "description": "Name of the results sheet (default: 'Bet Results')",
                        "default": "Bet Results"
                    }
                },
                "required": ["spreadsheet_id", "results"]
            }
        ),
        Tool(
            name="generate_performance_report",
            description="Generate comprehensive performance report in Google Sheets",
            inputSchema={
                "type": "object",
                "properties": {
                    "spreadsheet_id": {
                        "type": "string",
                        "description": "Google Sheets spreadsheet ID"
                    },
                    "stats": {
                        "type": "object",
                        "description": "Performance stats: win_rate, roi, total_profit, clv_avg, etc."
                    },
                    "sheet_name": {
                        "type": "string",
                        "description": "Name of the report sheet (default: 'Performance')",
                        "default": "Performance"
                    },
                    "period": {
                        "type": "string",
                        "description": "Reporting period (e.g., 'Last 30 Days', 'Season 2024')"
                    }
                },
                "required": ["spreadsheet_id", "stats"]
            }
        ),
        Tool(
            name="create_betting_tracker",
            description="Create a new betting tracker spreadsheet with all necessary tabs",
            inputSchema={
                "type": "object",
                "properties": {
                    "spreadsheet_name": {
                        "type": "string",
                        "description": "Name for the new spreadsheet"
                    },
                    "share_with_emails": {
                        "type": "array",
                        "description": "Email addresses to share the spreadsheet with",
                        "items": {
                            "type": "string"
                        }
                    }
                },
                "required": ["spreadsheet_name"]
            }
        ),
        Tool(
            name="update_bankroll_snapshot",
            description="Update bankroll snapshot with current balance and risk metrics",
            inputSchema={
                "type": "object",
                "properties": {
                    "spreadsheet_id": {
                        "type": "string",
                        "description": "Google Sheets spreadsheet ID"
                    },
                    "snapshot": {
                        "type": "object",
                        "description": "Bankroll snapshot: balance, pending_risk, max_drawdown, etc."
                    },
                    "sheet_name": {
                        "type": "string",
                        "description": "Name of the bankroll sheet (default: 'Bankroll')",
                        "default": "Bankroll"
                    }
                },
                "required": ["spreadsheet_id", "snapshot"]
            }
        )
    ]


@app.call_tool()
async def call_tool(name: str, arguments: Any) -> List[TextContent]:
    """Handle tool calls."""
    try:
        client = get_sheets_client()
        if not client:
            return [TextContent(
                type="text",
                text="Error: Google Sheets client not initialized. Check credentials."
            )]
        
        if name == "export_betting_slate":
            result = await export_betting_slate(
                client,
                arguments["spreadsheet_id"],
                arguments["bets"],
                arguments.get("sheet_name", "Daily Slate"),
                arguments.get("date")
            )
            return [TextContent(type="text", text=json.dumps(result, indent=2))]
            
        elif name == "log_bet_results":
            result = await log_bet_results(
                client,
                arguments["spreadsheet_id"],
                arguments["results"],
                arguments.get("sheet_name", "Bet Results")
            )
            return [TextContent(type="text", text=json.dumps(result, indent=2))]
            
        elif name == "generate_performance_report":
            result = await generate_performance_report(
                client,
                arguments["spreadsheet_id"],
                arguments["stats"],
                arguments.get("sheet_name", "Performance"),
                arguments.get("period")
            )
            return [TextContent(type="text", text=json.dumps(result, indent=2))]
            
        elif name == "create_betting_tracker":
            result = await create_betting_tracker(
                client,
                arguments["spreadsheet_name"],
                arguments.get("share_with_emails", [])
            )
            return [TextContent(type="text", text=json.dumps(result, indent=2))]
            
        elif name == "update_bankroll_snapshot":
            result = await update_bankroll_snapshot(
                client,
                arguments["spreadsheet_id"],
                arguments["snapshot"],
                arguments.get("sheet_name", "Bankroll")
            )
            return [TextContent(type="text", text=json.dumps(result, indent=2))]
            
        else:
            return [TextContent(type="text", text=f"Unknown tool: {name}")]
            
    except Exception as e:
        logger.error(f"Error calling tool {name}: {e}")
        return [TextContent(type="text", text=f"Error: {str(e)}")]


async def export_betting_slate(
    client: gspread.Client,
    spreadsheet_id: str,
    bets: List[Dict[str, Any]],
    sheet_name: str,
    date: Optional[str]
) -> Dict[str, Any]:
    """Export betting slate to Google Sheets."""
    try:
        spreadsheet = client.open_by_key(spreadsheet_id)
        
        # Try to get or create sheet
        try:
            worksheet = spreadsheet.worksheet(sheet_name)
        except gspread.WorksheetNotFound:
            worksheet = spreadsheet.add_worksheet(title=sheet_name, rows=1000, cols=20)
        
        # Clear existing content
        worksheet.clear()
        
        # Set date
        slate_date = date or datetime.now().strftime("%Y-%m-%d")
        
        # Headers
        headers = [
            "Date", "Game", "Sport", "Market", "Pick", "Odds", 
            "Stake", "EV%", "Kelly%", "Confidence", "Sharp Signals", "Notes"
        ]
        
        # Prepare data rows
        rows = [headers]
        for bet in bets:
            row = [
                slate_date,
                bet.get("game", ""),
                bet.get("sport", ""),
                bet.get("market", ""),
                bet.get("pick", ""),
                bet.get("odds", ""),
                bet.get("stake", ""),
                bet.get("ev_percent", ""),
                bet.get("kelly_percent", ""),
                bet.get("confidence", ""),
                bet.get("sharp_signals", ""),
                bet.get("notes", "")
            ]
            rows.append(row)
        
        # Write to sheet
        worksheet.update(range_name='A1', values=rows)
        
        # Format header row
        worksheet.format('A1:L1', {
            "backgroundColor": {"red": 0.2, "green": 0.2, "blue": 0.8},
            "textFormat": {"bold": True, "foregroundColor": {"red": 1, "green": 1, "blue": 1}}
        })
        
        return {
            "success": True,
            "spreadsheet_id": spreadsheet_id,
            "sheet_name": sheet_name,
            "bets_exported": len(bets),
            "date": slate_date,
            "url": spreadsheet.url
        }
        
    except Exception as e:
        logger.error(f"Failed to export betting slate: {e}")
        return {"success": False, "error": str(e)}


async def log_bet_results(
    client: gspread.Client,
    spreadsheet_id: str,
    results: List[Dict[str, Any]],
    sheet_name: str
) -> Dict[str, Any]:
    """Log bet results to Google Sheets."""
    try:
        spreadsheet = client.open_by_key(spreadsheet_id)
        
        try:
            worksheet = spreadsheet.worksheet(sheet_name)
        except gspread.WorksheetNotFound:
            worksheet = spreadsheet.add_worksheet(title=sheet_name, rows=10000, cols=15)
            # Add headers
            headers = [
                "Date", "Bet ID", "Game", "Pick", "Odds", "Stake", 
                "Outcome", "Profit/Loss", "ROI%", "CLV", "Closing Odds", 
                "Win Probability", "Actual Result", "Notes"
            ]
            worksheet.update(range_name='A1', values=[headers])
            worksheet.format('A1:N1', {
                "backgroundColor": {"red": 0.2, "green": 0.2, "blue": 0.8},
                "textFormat": {"bold": True, "foregroundColor": {"red": 1, "green": 1, "blue": 1}}
            })
        
        # Append results
        rows = []
        for result in results:
            row = [
                result.get("date", datetime.now().strftime("%Y-%m-%d")),
                result.get("bet_id", ""),
                result.get("game", ""),
                result.get("pick", ""),
                result.get("odds", ""),
                result.get("stake", ""),
                result.get("outcome", ""),
                result.get("profit_loss", ""),
                result.get("roi_percent", ""),
                result.get("clv", ""),
                result.get("closing_odds", ""),
                result.get("win_probability", ""),
                result.get("actual_result", ""),
                result.get("notes", "")
            ]
            rows.append(row)
        
        worksheet.append_rows(rows)
        
        return {
            "success": True,
            "spreadsheet_id": spreadsheet_id,
            "sheet_name": sheet_name,
            "results_logged": len(results),
            "url": spreadsheet.url
        }
        
    except Exception as e:
        logger.error(f"Failed to log bet results: {e}")
        return {"success": False, "error": str(e)}


async def generate_performance_report(
    client: gspread.Client,
    spreadsheet_id: str,
    stats: Dict[str, Any],
    sheet_name: str,
    period: Optional[str]
) -> Dict[str, Any]:
    """Generate performance report in Google Sheets."""
    try:
        spreadsheet = client.open_by_key(spreadsheet_id)
        
        try:
            worksheet = spreadsheet.worksheet(sheet_name)
            worksheet.clear()
        except gspread.WorksheetNotFound:
            worksheet = spreadsheet.add_worksheet(title=sheet_name, rows=100, cols=10)
        
        report_period = period or f"As of {datetime.now().strftime('%Y-%m-%d')}"
        
        # Build report
        report_data = [
            ["SPORTS BETTING PERFORMANCE REPORT", "", "", ""],
            ["Period:", report_period, "", ""],
            ["", "", "", ""],
            ["KEY METRICS", "", "", ""],
            ["Total Bets", stats.get("total_bets", 0), "", ""],
            ["Win Rate", f"{stats.get('win_rate', 0):.2f}%", "", ""],
            ["ROI", f"{stats.get('roi', 0):.2f}%", "", ""],
            ["Total Profit/Loss", f"${stats.get('total_profit', 0):.2f}", "", ""],
            ["Average CLV", f"{stats.get('clv_avg', 0):.2f}%", "", ""],
            ["Bankroll", f"${stats.get('bankroll', 0):.2f}", "", ""],
            ["", "", "", ""],
            ["RISK METRICS", "", "", ""],
            ["Max Drawdown", f"{stats.get('max_drawdown', 0):.2f}%", "", ""],
            ["Sharpe Ratio", f"{stats.get('sharpe_ratio', 0):.2f}", "", ""],
            ["Kelly Efficiency", f"{stats.get('kelly_efficiency', 0):.2f}%", "", ""],
            ["", "", "", ""],
            ["BY SPORT", "", "", ""],
            ["NBA ROI", f"{stats.get('nba_roi', 0):.2f}%", "", ""],
            ["NCAAB ROI", f"{stats.get('ncaab_roi', 0):.2f}%", "", ""],
            ["NFL ROI", f"{stats.get('nfl_roi', 0):.2f}%", "", ""],
        ]
        
        worksheet.update(range_name='A1', values=report_data)
        
        # Format title
        worksheet.format('A1:D1', {
            "backgroundColor": {"red": 0.2, "green": 0.8, "blue": 0.2},
            "textFormat": {"bold": True, "fontSize": 14}
        })
        
        # Format section headers
        worksheet.format('A4', {"textFormat": {"bold": True}})
        worksheet.format('A12', {"textFormat": {"bold": True}})
        worksheet.format('A17', {"textFormat": {"bold": True}})
        
        return {
            "success": True,
            "spreadsheet_id": spreadsheet_id,
            "sheet_name": sheet_name,
            "period": report_period,
            "url": spreadsheet.url
        }
        
    except Exception as e:
        logger.error(f"Failed to generate performance report: {e}")
        return {"success": False, "error": str(e)}


async def create_betting_tracker(
    client: gspread.Client,
    spreadsheet_name: str,
    share_with_emails: List[str]
) -> Dict[str, Any]:
    """Create a new betting tracker spreadsheet."""
    try:
        # Create new spreadsheet
        spreadsheet = client.create(spreadsheet_name)
        
        # Create standard tabs
        tabs = ["Daily Slate", "Bet Results", "Performance", "Bankroll", "Notes"]
        
        # Rename first sheet
        worksheet = spreadsheet.get_worksheet(0)
        worksheet.update_title("Daily Slate")
        
        # Add additional sheets
        for tab in tabs[1:]:
            spreadsheet.add_worksheet(title=tab, rows=1000, cols=20)
        
        # Share with specified emails
        for email in share_with_emails:
            spreadsheet.share(email, perm_type='user', role='writer')
        
        return {
            "success": True,
            "spreadsheet_id": spreadsheet.id,
            "spreadsheet_name": spreadsheet_name,
            "tabs_created": tabs,
            "shared_with": share_with_emails,
            "url": spreadsheet.url
        }
        
    except Exception as e:
        logger.error(f"Failed to create betting tracker: {e}")
        return {"success": False, "error": str(e)}


async def update_bankroll_snapshot(
    client: gspread.Client,
    spreadsheet_id: str,
    snapshot: Dict[str, Any],
    sheet_name: str
) -> Dict[str, Any]:
    """Update bankroll snapshot."""
    try:
        spreadsheet = client.open_by_key(spreadsheet_id)
        
        try:
            worksheet = spreadsheet.worksheet(sheet_name)
        except gspread.WorksheetNotFound:
            worksheet = spreadsheet.add_worksheet(title=sheet_name, rows=100, cols=10)
        
        # Build snapshot data
        snapshot_data = [
            ["BANKROLL SNAPSHOT", "", ""],
            ["Timestamp", datetime.now().strftime("%Y-%m-%d %H:%M:%S"), ""],
            ["", "", ""],
            ["Current Balance", f"${snapshot.get('balance', 0):.2f}", ""],
            ["Pending Risk", f"${snapshot.get('pending_risk', 0):.2f}", ""],
            ["Available Capital", f"${snapshot.get('available_capital', 0):.2f}", ""],
            ["", "", ""],
            ["Max Drawdown", f"{snapshot.get('max_drawdown', 0):.2f}%", ""],
            ["Current Drawdown", f"{snapshot.get('current_drawdown', 0):.2f}%", ""],
            ["Peak Balance", f"${snapshot.get('peak_balance', 0):.2f}", ""],
            ["", "", ""],
            ["Open Positions", snapshot.get('open_positions', 0), ""],
            ["Total Exposure", f"${snapshot.get('total_exposure', 0):.2f}", ""],
        ]
        
        # Append to history
        worksheet.append_rows(snapshot_data)
        
        return {
            "success": True,
            "spreadsheet_id": spreadsheet_id,
            "sheet_name": sheet_name,
            "timestamp": datetime.now().isoformat(),
            "url": spreadsheet.url
        }
        
    except Exception as e:
        logger.error(f"Failed to update bankroll snapshot: {e}")
        return {"success": False, "error": str(e)}


async def main():
    """Run the MCP server."""
    from mcp.server.stdio import stdio_server
    
    async with stdio_server() as (read_stream, write_stream):
        logger.info("Google Sheets Reporting MCP Server starting...")
        await app.run(
            read_stream,
            write_stream,
            app.create_initialization_options()
        )


if __name__ == "__main__":
    asyncio.run(main())
