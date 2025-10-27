"""
Bet storage service for saving cleaned betting data to database
Handles game and bet creation/updates with proper data integrity
"""
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from loguru import logger
from datetime import datetime

from app.models.game import Game
from app.models.bet import Bet
from app.services.data_cleaner import data_cleaner


class BetStorageService:
    """Service for storing betting data in the database"""
    
    def get_or_create_game(
        self, 
        db: Session, 
        game_data: Dict[str, Any]
    ) -> Optional[Game]:
        """
        Get existing game or create new one
        
        Args:
            db: Database session
            game_data: Cleaned game data
            
        Returns:
            Game instance or None if error
        """
        try:
            # Check if game exists by external_game_id
            external_id = game_data.get('external_game_id')
            existing_game = db.query(Game).filter(
                Game.external_game_id == external_id
            ).first()
            
            if existing_game:
                logger.debug(f"Found existing game: {external_id}")
                
                # Update game if new data is provided
                if game_data.get('home_score') is not None:
                    existing_game.home_score = game_data['home_score']
                if game_data.get('away_score') is not None:
                    existing_game.away_score = game_data['away_score']
                if game_data.get('game_date'):
                    existing_game.game_date = game_data['game_date']
                
                existing_game.updated_at = datetime.utcnow()
                db.commit()
                db.refresh(existing_game)
                return existing_game
            
            # Create new game
            new_game = Game(
                external_game_id=external_id,
                sport=game_data.get('sport'),
                home_team=game_data.get('home_team'),
                away_team=game_data.get('away_team'),
                game_date=game_data.get('game_date'),
                home_score=game_data.get('home_score'),
                away_score=game_data.get('away_score')
            )
            
            db.add(new_game)
            db.commit()
            db.refresh(new_game)
            
            logger.info(f"Created new game: {external_id}")
            return new_game
            
        except IntegrityError as e:
            db.rollback()
            logger.error(f"Database integrity error creating game: {e}")
            # Try to fetch the game again (might have been created by another process)
            return db.query(Game).filter(
                Game.external_game_id == external_id
            ).first()
        except Exception as e:
            db.rollback()
            logger.error(f"Error creating game: {e}")
            return None
    
    def save_bet(
        self,
        db: Session,
        bet_data: Dict[str, Any],
        game_id: Optional[int] = None
    ) -> Optional[Bet]:
        """
        Save or update a bet in the database
        
        Args:
            db: Database session
            bet_data: Cleaned bet data
            game_id: Optional game ID to associate with
            
        Returns:
            Bet instance or None if error
        """
        try:
            selection_id = bet_data.get('selection_id')
            
            # Check if bet exists
            existing_bet = db.query(Bet).filter(
                Bet.selection_id == selection_id
            ).first()
            
            if existing_bet:
                logger.debug(f"Updating existing bet: {selection_id}")
                
                # Update all provided fields
                for key, value in bet_data.items():
                    if hasattr(existing_bet, key) and value is not None:
                        setattr(existing_bet, key, value)
                
                if game_id:
                    existing_bet.game_id = game_id
                
                existing_bet.updated_at = datetime.utcnow()
                db.commit()
                db.refresh(existing_bet)
                return existing_bet
            
            # Create new bet
            new_bet = Bet(
                selection_id=selection_id,
                sport=bet_data.get('sport'),
                game_id=game_id,
                team=bet_data.get('team'),
                market=bet_data.get('market'),
                current_odds=bet_data.get('current_odds'),
                implied_prob=bet_data.get('implied_prob'),
                devig_prob=bet_data.get('devig_prob'),
                posterior_prob=bet_data.get('posterior_prob'),
                fair_american_odds=bet_data.get('fair_american_odds'),
                edge=bet_data.get('edge'),
                kelly_fraction=bet_data.get('kelly_fraction'),
                features=bet_data.get('features'),
                confidence_interval=bet_data.get('confidence_interval')
            )
            
            db.add(new_bet)
            db.commit()
            db.refresh(new_bet)
            
            logger.info(f"Created new bet: {selection_id}")
            return new_bet
            
        except IntegrityError as e:
            db.rollback()
            logger.error(f"Database integrity error saving bet: {e}")
            # Try to fetch the bet again
            return db.query(Bet).filter(
                Bet.selection_id == selection_id
            ).first()
        except Exception as e:
            db.rollback()
            logger.error(f"Error saving bet: {e}")
            return None
    
    def store_best_bets(
        self,
        db: Session,
        raw_bets: List[Dict[str, Any]],
        game_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Store a list of best bets with cleaning and validation
        
        Args:
            db: Database session
            raw_bets: List of raw bet data
            game_context: Optional game context data
            
        Returns:
            Storage results with counts
        """
        results = {
            'total_bets': len(raw_bets),
            'saved': 0,
            'updated': 0,
            'failed': 0,
            'errors': []
        }
        
        for raw_bet in raw_bets:
            try:
                # Clean bet data
                cleaned_bet = data_cleaner.clean_bet_data(raw_bet)
                
                # If game context is provided, create/update game
                game_id = None
                if game_context or raw_bet.get('game'):
                    game_data = game_context or raw_bet.get('game')
                    
                    # Clean game data if needed
                    if 'external_game_id' not in game_data:
                        game_data = data_cleaner.clean_game_data(game_data)
                    
                    game = self.get_or_create_game(db, game_data)
                    if game:
                        game_id = game.id
                
                # Check if bet already exists to determine if it's an update
                existing = db.query(Bet).filter(
                    Bet.selection_id == cleaned_bet['selection_id']
                ).first()
                
                # Save bet
                bet = self.save_bet(db, cleaned_bet, game_id)
                
                if bet:
                    if existing:
                        results['updated'] += 1
                    else:
                        results['saved'] += 1
                else:
                    results['failed'] += 1
                    
            except ValueError as e:
                results['failed'] += 1
                error_msg = f"Validation error: {str(e)}"
                results['errors'].append(error_msg)
                logger.warning(error_msg)
            except Exception as e:
                results['failed'] += 1
                error_msg = f"Storage error: {str(e)}"
                results['errors'].append(error_msg)
                logger.error(error_msg)
        
        logger.info(
            f"Stored best bets - Saved: {results['saved']}, "
            f"Updated: {results['updated']}, Failed: {results['failed']}"
        )
        
        return results
    
    def store_odds_api_data(
        self,
        db: Session,
        raw_odds_data: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Store odds data from Odds API format
        
        Args:
            db: Database session
            raw_odds_data: Raw odds API response
            
        Returns:
            Storage results
        """
        # Clean odds API data
        cleaned_games = data_cleaner.clean_odds_api_response(raw_odds_data)
        
        results = {
            'total_games': len(cleaned_games),
            'games_saved': 0,
            'bets_saved': 0,
            'bets_updated': 0,
            'errors': []
        }
        
        for game_data in cleaned_games:
            try:
                # Create/update game
                game = self.get_or_create_game(db, game_data['game'])
                
                if game:
                    results['games_saved'] += 1
                    
                    # Store bets for this game
                    for bet_data in game_data['bets']:
                        existing = db.query(Bet).filter(
                            Bet.selection_id == bet_data['selection_id']
                        ).first()
                        
                        bet = self.save_bet(db, bet_data, game.id)
                        
                        if bet:
                            if existing:
                                results['bets_updated'] += 1
                            else:
                                results['bets_saved'] += 1
                
            except Exception as e:
                error_msg = f"Error storing game data: {str(e)}"
                results['errors'].append(error_msg)
                logger.error(error_msg)
        
        logger.info(
            f"Stored odds data - Games: {results['games_saved']}, "
            f"Bets saved: {results['bets_saved']}, "
            f"Bets updated: {results['bets_updated']}"
        )
        
        return results
    
    def get_recent_bets(
        self,
        db: Session,
        sport: Optional[str] = None,
        min_edge: Optional[float] = None,
        limit: int = 50
    ) -> List[Bet]:
        """
        Retrieve recent bets from database
        
        Args:
            db: Database session
            sport: Filter by sport
            min_edge: Minimum edge threshold
            limit: Maximum number of bets
            
        Returns:
            List of Bet instances
        """
        query = db.query(Bet)
        
        if sport:
            query = query.filter(Bet.sport == sport.upper())
        
        if min_edge is not None:
            query = query.filter(Bet.edge >= min_edge)
        
        bets = query.order_by(Bet.created_at.desc()).limit(limit).all()
        
        logger.info(f"Retrieved {len(bets)} recent bets")
        return bets


# Singleton instance
bet_storage = BetStorageService()
