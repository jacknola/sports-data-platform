"""
Google Sheets integration service for sports data platform
"""
import os
from typing import Dict, Any, List, Optional
from loguru import logger
import gspread
from google.oauth2.service_account import Credentials


class GoogleSheetsService:
    """Service for interacting with Google Sheets"""
    
    def __init__(self):
        self.client = None
        self._init_client()
    
    def _init_client(self):
        """Initialize Google Sheets client"""
        try:
            # Path to service account JSON (should be in env)
            credentials_path = os.getenv('GOOGLE_SERVICE_ACCOUNT_PATH')
            
            if not credentials_path:
                logger.warning("Google credentials not configured")
                return
            
            creds = Credentials.from_service_account_file(
                credentials_path,
                scopes=[
                    'https://www.googleapis.com/auth/spreadsheets',
                    'https://www.googleapis.com/auth/drive'
                ]
            )
            
            self.client = gspread.authorize(creds)
            logger.info("Google Sheets client initialized")
            
        except Exception as e:
            logger.error(f"Failed to initialize Google Sheets client: {e}")
    
    async def write_bet_analysis(
        self,
        spreadsheet_id: str,
        analysis: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Write bet analysis to Google Sheet
        
        Args:
            spreadsheet_id: ID of the spreadsheet
            analysis: Analysis data to write
            
        Returns:
            Result of write operation
        """
        if not self.client:
            return {'error': 'Google Sheets not configured'}
        
        try:
            sheet = self.client.open_by_key(spreadsheet_id)
            worksheet = sheet.get_worksheet(0)  # First worksheet
            
            # Prepare data
            row = self._format_bet_analysis_row(analysis)
            
            # Append to sheet
            worksheet.append_row(row)
            
            logger.info(f"Wrote bet analysis to sheet {spreadsheet_id}")
            
            return {
                'status': 'success',
                'spreadsheet_id': spreadsheet_id,
                'rows_written': 1
            }
            
        except Exception as e:
            logger.error(f"Error writing to sheet: {e}")
            return {'error': str(e)}
    
    def _format_bet_analysis_row(self, analysis: Dict[str, Any]) -> List[str]:
        """Format bet analysis data as a row"""
        
        return [
            analysis.get('date', ''),
            analysis.get('sport', ''),
            analysis.get('game', ''),
            analysis.get('market', ''),
            str(analysis.get('edge', '')),
            str(analysis.get('probability', '')),
            str(analysis.get('odds', '')),
            analysis.get('recommendation', ''),
            str(analysis.get('confidence', ''))
        ]
    
    async def sync_predictions(
        self,
        spreadsheet_id: str,
        predictions: List[Dict[str, Any]],
        worksheet_name: str = 'Predictions'
    ) -> Dict[str, Any]:
        """
        Sync predictions to a Google Sheet
        
        Args:
            spreadsheet_id: ID of the spreadsheet
            predictions: List of predictions
            worksheet_name: Name of worksheet
            
        Returns:
            Sync result
        """
        if not self.client:
            return {'error': 'Google Sheets not configured'}
        
        try:
            sheet = self.client.open_by_key(spreadsheet_id)
            
            # Get or create worksheet
            try:
                worksheet = sheet.worksheet(worksheet_name)
            except gspread.WorksheetNotFound:
                worksheet = sheet.add_worksheet(
                    title=worksheet_name,
                    rows=len(predictions) + 1,
                    cols=10
                )
            
            # Clear existing data
            worksheet.clear()
            
            # Write headers
            headers = ['Date', 'Team', 'Opponent', 'Market', 'Prediction', 
                      'Probability', 'Confidence', 'Edge', 'Kelly', 'Recommendation']
            worksheet.append_row(headers)
            
            # Write predictions
            for prediction in predictions:
                row = [
                    prediction.get('date', ''),
                    prediction.get('team', ''),
                    prediction.get('opponent', ''),
                    prediction.get('market', ''),
                    prediction.get('prediction', ''),
                    str(prediction.get('probability', '')),
                    str(prediction.get('confidence', '')),
                    str(prediction.get('edge', '')),
                    str(prediction.get('kelly', '')),
                    prediction.get('recommendation', '')
                ]
                worksheet.append_row(row)
            
            logger.info(f"Synced {len(predictions)} predictions to sheet")
            
            return {
                'status': 'success',
                'predictions_synced': len(predictions),
                'worksheet': worksheet_name
            }
            
        except Exception as e:
            logger.error(f"Error syncing predictions: {e}")
            return {'error': str(e)}
    
    async def create_daily_summary(
        self,
        spreadsheet_id: str,
        summary: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Create a daily summary sheet
        
        Args:
            spreadsheet_id: ID of the spreadsheet
            summary: Summary data
            
        Returns:
            Result
        """
        if not self.client:
            return {'error': 'Google Sheets not configured'}
        
        try:
            sheet = self.client.open_by_key(spreadsheet_id)
            
            # Create date-based worksheet name
            from datetime import datetime
            sheet_name = f"Summary_{datetime.now().strftime('%Y-%m-%d')}"
            
            # Create new worksheet
            worksheet = sheet.add_worksheet(
                title=sheet_name,
                rows=50,
                cols=10
            )
            
            # Write summary data
            summary_data = [
                ['Daily Summary', datetime.now().strftime('%Y-%m-%d %H:%M')],
                [''],
                ['Total Bets Analyzed', summary.get('total_bets', 0)],
                ['Value Bets Found', summary.get('value_bets', 0)],
                ['Average Edge', summary.get('avg_edge', 0)],
                ['Win Rate', summary.get('win_rate', 0)],
                [''],
                ['Top Recommendations'],
                ['Team', 'Market', 'Edge', 'Confidence']
            ]
            
            # Add top bets
            for bet in summary.get('top_bets', [])[:5]:
                summary_data.append([
                    bet.get('team', ''),
                    bet.get('market', ''),
                    str(bet.get('edge', '')),
                    str(bet.get('confidence', ''))
                ])
            
            # Write all data
            for row in summary_data:
                worksheet.append_row(row)
            
            logger.info(f"Created daily summary: {sheet_name}")
            
            return {
                'status': 'success',
                'worksheet_name': sheet_name,
                'rows': len(summary_data)
            }
            
        except Exception as e:
            logger.error(f"Error creating summary: {e}")
            return {'error': str(e)}
    
    async def get_spreadsheet_info(self, spreadsheet_id: str) -> Dict[str, Any]:
        """
        Get information about a spreadsheet
        
        Args:
            spreadsheet_id: ID of the spreadsheet
            
        Returns:
            Spreadsheet info
        """
        if not self.client:
            return {'error': 'Google Sheets not configured'}
        
        try:
            sheet = self.client.open_by_key(spreadsheet_id)
            
            worksheets = [ws.title for ws in sheet.worksheets()]
            
            return {
                'title': sheet.title,
                'url': sheet.url,
                'worksheets': worksheets,
                'worksheet_count': len(worksheets)
            }
            
        except Exception as e:
            logger.error(f"Error getting spreadsheet info: {e}")
            return {'error': str(e)}

