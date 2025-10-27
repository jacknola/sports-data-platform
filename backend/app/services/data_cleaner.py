"""
Data cleaning service for sports betting data
Validates, normalizes, and cleans data from various sports data platforms
"""
from typing import Dict, Any, List, Optional
from datetime import datetime
import re
from loguru import logger


class DataCleaner:
    """Service for cleaning and validating sports betting data"""
    
    # Sport name mappings
    SPORT_MAPPINGS = {
        'nba': 'NBA',
        'nfl': 'NFL',
        'mlb': 'MLB',
        'nhl': 'NHL',
        'basketball': 'NBA',
        'football': 'NFL',
        'baseball': 'MLB',
        'hockey': 'NHL'
    }
    
    # Market type mappings
    MARKET_MAPPINGS = {
        'h2h': 'moneyline',
        'spreads': 'spread',
        'totals': 'total',
        'moneyline': 'moneyline',
        'spread': 'spread',
        'total': 'total',
        'over_under': 'total',
        'pointspread': 'spread'
    }
    
    def clean_sport_name(self, sport: str) -> str:
        """
        Normalize sport name
        
        Args:
            sport: Raw sport name
            
        Returns:
            Normalized sport name
        """
        sport_lower = sport.lower().strip()
        return self.SPORT_MAPPINGS.get(sport_lower, sport.upper())
    
    def clean_team_name(self, team: str) -> str:
        """
        Normalize team name - remove special characters, extra spaces
        
        Args:
            team: Raw team name
            
        Returns:
            Cleaned team name
        """
        if not team:
            return ""
        
        # Remove extra whitespace
        team = re.sub(r'\s+', ' ', team.strip())
        
        # Remove special characters but keep spaces and hyphens
        team = re.sub(r'[^\w\s\-]', '', team)
        
        return team.strip()
    
    def clean_market_type(self, market: str) -> str:
        """
        Normalize market type
        
        Args:
            market: Raw market type
            
        Returns:
            Normalized market type
        """
        market_lower = market.lower().strip()
        return self.MARKET_MAPPINGS.get(market_lower, market_lower)
    
    def validate_odds(self, odds: Any) -> Optional[float]:
        """
        Validate and convert odds to float
        
        Args:
            odds: Raw odds value
            
        Returns:
            Validated odds as float or None if invalid
        """
        try:
            odds_float = float(odds)
            
            # American odds validation (typically between -10000 and +10000)
            if -10000 <= odds_float <= 10000:
                return odds_float
            
            logger.warning(f"Odds value {odds_float} outside expected range")
            return None
            
        except (ValueError, TypeError) as e:
            logger.warning(f"Invalid odds value {odds}: {e}")
            return None
    
    def validate_probability(self, prob: Any) -> Optional[float]:
        """
        Validate probability is between 0 and 1
        
        Args:
            prob: Raw probability value
            
        Returns:
            Validated probability or None if invalid
        """
        try:
            prob_float = float(prob)
            
            if 0 <= prob_float <= 1:
                return prob_float
            
            # If probability is between 0-100, convert to 0-1
            if 0 <= prob_float <= 100:
                return prob_float / 100
            
            logger.warning(f"Probability {prob_float} outside valid range")
            return None
            
        except (ValueError, TypeError) as e:
            logger.warning(f"Invalid probability value {prob}: {e}")
            return None
    
    def validate_edge(self, edge: Any) -> Optional[float]:
        """
        Validate edge value
        
        Args:
            edge: Raw edge value
            
        Returns:
            Validated edge or None if invalid
        """
        try:
            edge_float = float(edge)
            
            # Edge typically between -1 and 1 (or -100% to 100%)
            if -1 <= edge_float <= 1:
                return edge_float
            
            # If edge is in percentage form (e.g., 5 for 5%)
            if -100 <= edge_float <= 100:
                return edge_float / 100
            
            logger.warning(f"Edge value {edge_float} outside expected range")
            return None
            
        except (ValueError, TypeError) as e:
            logger.warning(f"Invalid edge value {edge}: {e}")
            return None
    
    def parse_datetime(self, date_str: Any) -> Optional[datetime]:
        """
        Parse datetime from various formats
        
        Args:
            date_str: Raw date string or datetime object
            
        Returns:
            Parsed datetime or None if invalid
        """
        if isinstance(date_str, datetime):
            return date_str
        
        if not date_str:
            return None
        
        # Try common datetime formats
        formats = [
            '%Y-%m-%dT%H:%M:%SZ',
            '%Y-%m-%d %H:%M:%S',
            '%Y-%m-%d',
            '%Y/%m/%d',
            '%m/%d/%Y',
            '%Y-%m-%dT%H:%M:%S.%fZ',
        ]
        
        for fmt in formats:
            try:
                return datetime.strptime(str(date_str), fmt)
            except ValueError:
                continue
        
        logger.warning(f"Could not parse datetime: {date_str}")
        return None
    
    def clean_game_data(self, raw_game: Dict[str, Any]) -> Dict[str, Any]:
        """
        Clean and validate game data
        
        Args:
            raw_game: Raw game data from API
            
        Returns:
            Cleaned game data
        """
        cleaned = {
            'external_game_id': str(raw_game.get('id', raw_game.get('game_id', ''))),
            'sport': self.clean_sport_name(raw_game.get('sport', '')),
            'home_team': self.clean_team_name(raw_game.get('home_team', '')),
            'away_team': self.clean_team_name(raw_game.get('away_team', '')),
            'game_date': self.parse_datetime(raw_game.get('commence_time', raw_game.get('game_date')))
        }
        
        # Optional fields
        if 'home_score' in raw_game:
            try:
                cleaned['home_score'] = int(raw_game['home_score'])
            except (ValueError, TypeError):
                pass
        
        if 'away_score' in raw_game:
            try:
                cleaned['away_score'] = int(raw_game['away_score'])
            except (ValueError, TypeError):
                pass
        
        # Validate required fields
        if not cleaned['external_game_id']:
            logger.warning(f"Game missing external_game_id: {raw_game}")
            cleaned['external_game_id'] = f"{cleaned['away_team']}_{cleaned['home_team']}_{cleaned['game_date']}"
        
        if not cleaned['home_team'] or not cleaned['away_team']:
            logger.error(f"Game missing team names: {raw_game}")
            raise ValueError("Game must have home and away teams")
        
        return cleaned
    
    def clean_bet_data(self, raw_bet: Dict[str, Any]) -> Dict[str, Any]:
        """
        Clean and validate bet data
        
        Args:
            raw_bet: Raw bet data from API or ML model
            
        Returns:
            Cleaned bet data
        """
        cleaned = {
            'selection_id': str(raw_bet.get('selection_id', raw_bet.get('id', ''))),
            'sport': self.clean_sport_name(raw_bet.get('sport', '')),
            'team': self.clean_team_name(raw_bet.get('team', raw_bet.get('selection', ''))),
            'market': self.clean_market_type(raw_bet.get('market', '')),
        }
        
        # Clean odds and probabilities
        if 'current_odds' in raw_bet:
            cleaned['current_odds'] = self.validate_odds(raw_bet['current_odds'])
        
        if 'implied_prob' in raw_bet:
            cleaned['implied_prob'] = self.validate_probability(raw_bet['implied_prob'])
        elif 'probability' in raw_bet:
            cleaned['implied_prob'] = self.validate_probability(raw_bet['probability'])
        
        if 'devig_prob' in raw_bet:
            cleaned['devig_prob'] = self.validate_probability(raw_bet['devig_prob'])
        
        if 'posterior_prob' in raw_bet:
            cleaned['posterior_prob'] = self.validate_probability(raw_bet['posterior_prob'])
        elif 'probability' in raw_bet:
            cleaned['posterior_prob'] = self.validate_probability(raw_bet['probability'])
        
        # Clean edge and Kelly
        if 'edge' in raw_bet:
            cleaned['edge'] = self.validate_edge(raw_bet['edge'])
        
        if 'kelly_fraction' in raw_bet or 'kelly_criterion' in raw_bet:
            kelly_value = raw_bet.get('kelly_fraction', raw_bet.get('kelly_criterion'))
            kelly_float = self.validate_probability(kelly_value)
            if kelly_float is not None and 0 <= kelly_float <= 1:
                cleaned['kelly_fraction'] = kelly_float
        
        if 'fair_american_odds' in raw_bet:
            cleaned['fair_american_odds'] = self.validate_odds(raw_bet['fair_american_odds'])
        
        # Clean features and metadata
        if 'features' in raw_bet and isinstance(raw_bet['features'], dict):
            cleaned['features'] = raw_bet['features']
        elif 'ml_prediction' in raw_bet and isinstance(raw_bet['ml_prediction'], dict):
            cleaned['features'] = raw_bet['ml_prediction']
        
        if 'confidence_interval' in raw_bet:
            cleaned['confidence_interval'] = raw_bet['confidence_interval']
        elif 'confidence' in raw_bet:
            try:
                conf = float(raw_bet['confidence'])
                cleaned['confidence_interval'] = {'confidence': conf}
            except (ValueError, TypeError):
                pass
        
        # Generate selection_id if missing
        if not cleaned['selection_id']:
            cleaned['selection_id'] = f"{cleaned['team']}_{cleaned['market']}_{datetime.utcnow().timestamp()}"
        
        # Validate required fields
        if not cleaned['sport']:
            raise ValueError("Bet must have a sport")
        
        if not cleaned['market']:
            raise ValueError("Bet must have a market type")
        
        return cleaned
    
    def clean_odds_api_response(self, raw_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Clean data from Odds API response
        
        Args:
            raw_data: Raw response from Odds API
            
        Returns:
            List of cleaned game and bet data
        """
        cleaned_games = []
        
        for game_data in raw_data:
            try:
                # Clean game info
                cleaned_game = {
                    'game': self.clean_game_data(game_data),
                    'bets': []
                }
                
                # Process bookmaker odds
                bookmakers = game_data.get('bookmakers', [])
                for bookmaker in bookmakers:
                    markets = bookmaker.get('markets', [])
                    for market in markets:
                        market_key = market.get('key')
                        outcomes = market.get('outcomes', [])
                        
                        for outcome in outcomes:
                            bet_data = {
                                'sport': game_data.get('sport_key'),
                                'market': market_key,
                                'team': outcome.get('name'),
                                'current_odds': outcome.get('price'),
                                'bookmaker': bookmaker.get('key'),
                                'selection_id': f"{game_data.get('id')}_{market_key}_{outcome.get('name')}_{bookmaker.get('key')}"
                            }
                            
                            try:
                                cleaned_bet = self.clean_bet_data(bet_data)
                                cleaned_game['bets'].append(cleaned_bet)
                            except ValueError as e:
                                logger.warning(f"Skipping invalid bet: {e}")
                
                cleaned_games.append(cleaned_game)
                
            except ValueError as e:
                logger.error(f"Skipping invalid game: {e}")
                continue
        
        return cleaned_games


# Singleton instance
data_cleaner = DataCleaner()
