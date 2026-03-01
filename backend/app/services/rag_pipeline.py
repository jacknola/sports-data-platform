"""
RAG (Retrieval-Augmented Generation) Pipeline for Parlay Data
Stores and retrieves parlay data with semantic search capabilities
"""
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from loguru import logger
import json
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

from app.database import SessionLocal
from app.services.cache import RedisCache
from app.services.ml_service import MLService


class RAGPipeline:
    """
    RAG pipeline for storing and retrieving parlay data
    Uses embeddings for semantic search of similar parlays
    """
    
    def __init__(self):
        self.ml_service = MLService()
        self.redis = None
        self.embedding_dim = 768  # BERT embedding dimension

    @classmethod
    async def create(cls) -> "RAGPipeline":
        """Creates and initializes a RAGPipeline instance."""
        pipeline = cls()
        await pipeline._init_storage()
        return pipeline
    
    async def _init_storage(self):
        """Initialize storage backends"""
        try:
            self.redis = await RedisCache.get_instance()
            logger.info("RAG pipeline storage initialized")
        except Exception as e:
            logger.error(f"Failed to initialize RAG storage: {e}")
    
    def generate_parlay_embedding(self, parlay_data: Dict[str, Any]) -> List[float]:
        """
        Generate embedding vector for a parlay
        
        Args:
            parlay_data: Parlay dictionary with legs, analysis, etc.
            
        Returns:
            Embedding vector as list of floats
        """
        # Create a comprehensive text representation
        text_parts = [
            parlay_data.get('title', ''),
            parlay_data.get('analysis', ''),
            parlay_data.get('sport', '')
        ]
        
        # Add leg information
        for leg in parlay_data.get('legs', []):
            text_parts.extend([
                leg.get('game', ''),
                leg.get('pick', ''),
                leg.get('reasoning', ''),
                leg.get('team', ''),
                leg.get('market', '')
            ])
        
        # Add key factors and tags
        text_parts.extend(parlay_data.get('key_factors', []))
        text_parts.extend(parlay_data.get('tags', []))
        
        # Combine all text
        combined_text = ' '.join(filter(None, text_parts))
        
        # Generate embedding using ML service
        embedding = self.ml_service.generate_embedding(combined_text)
        
        return embedding
    
    async def store_parlay(
        self,
        parlay_id: str,
        parlay_data: Dict[str, Any],
        generate_embedding: bool = True
    ) -> Dict[str, Any]:
        """
        Store parlay data with embedding for semantic search
        
        Args:
            parlay_id: Unique parlay identifier
            parlay_data: Full parlay data
            generate_embedding: Whether to generate embedding
            
        Returns:
            Stored parlay with metadata
        """
        try:
            # Generate embedding if requested
            if generate_embedding:
                embedding = self.generate_parlay_embedding(parlay_data)
                parlay_data['embedding_vector'] = embedding
                
                # Find similar parlays
                similar = await self.find_similar_parlays(
                    embedding,
                    limit=5,
                    exclude_id=parlay_id
                )
                parlay_data['similar_parlays'] = [p['id'] for p in similar]
            
            # Store in database
            from app.models.parlay import Parlay
            db = SessionLocal()
            
            try:
                parlay = Parlay(
                    parlay_id=parlay_id,
                    **parlay_data
                )
                db.add(parlay)
                db.commit()
                db.refresh(parlay)
                
                # Store in Redis for fast retrieval
                if self.redis:
                    cache_key = f"parlay:{parlay_id}"
                    self.redis.set(
                        cache_key,
                        json.dumps(parlay_data),
                        ttl=86400 * 7  # 7 days
                    )
                
                logger.info(f"Stored parlay {parlay_id} in RAG pipeline")
                return {
                    'id': parlay_id,
                    'stored': True,
                    'similar_count': len(parlay_data.get('similar_parlays', []))
                }
                
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"Failed to store parlay in RAG: {e}")
            raise
    
    async def retrieve_parlay(self, parlay_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve parlay by ID
        
        Args:
            parlay_id: Parlay identifier
            
        Returns:
            Parlay data or None
        """
        # Try cache first
        if self.redis:
            cache_key = f"parlay:{parlay_id}"
            cached = self.redis.get(cache_key)
            if cached:
                return json.loads(cached)
        
        # Retrieve from database
        from app.models.parlay import Parlay
        db = SessionLocal()
        
        try:
            parlay = db.query(Parlay).filter(Parlay.parlay_id == parlay_id).first()
            if parlay:
                return self._parlay_to_dict(parlay)
            return None
        finally:
            db.close()
    
    async def find_similar_parlays(
        self,
        query_embedding: List[float],
        limit: int = 10,
        exclude_id: Optional[str] = None,
        min_similarity: float = 0.7
    ) -> List[Dict[str, Any]]:
        """
        Find similar parlays using semantic search
        
        Args:
            query_embedding: Query embedding vector
            limit: Maximum number of results
            exclude_id: Parlay ID to exclude from results
            min_similarity: Minimum cosine similarity threshold
            
        Returns:
            List of similar parlays with similarity scores
        """
        from app.models.parlay import Parlay
        db = SessionLocal()
        
        try:
            # Get all parlays with embeddings
            parlays = db.query(Parlay).filter(
                Parlay.embedding_vector.isnot(None)
            ).all()
            
            if not parlays:
                return []
            
            # Calculate similarities
            similarities = []
            query_vec = np.array(query_embedding).reshape(1, -1)
            
            for parlay in parlays:
                if exclude_id and parlay.parlay_id == exclude_id:
                    continue
                
                if not parlay.embedding_vector:
                    continue
                
                parlay_vec = np.array(parlay.embedding_vector).reshape(1, -1)
                similarity = cosine_similarity(query_vec, parlay_vec)[0][0]
                
                if similarity >= min_similarity:
                    similarities.append({
                        'id': parlay.parlay_id,
                        'similarity': float(similarity),
                        'title': parlay.title,
                        'sport': parlay.sport,
                        'confidence': parlay.confidence_score,
                        'status': parlay.status,
                        'created_at': parlay.created_at.isoformat()
                    })
            
            # Sort by similarity and return top results
            similarities.sort(key=lambda x: x['similarity'], reverse=True)
            return similarities[:limit]
            
        except Exception as e:
            logger.error(f"Error finding similar parlays: {e}")
            return []
        finally:
            db.close()
    
    async def search_parlays_by_text(
        self,
        query_text: str,
        limit: int = 10,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Search parlays using natural language query
        
        Args:
            query_text: Natural language search query
            limit: Maximum number of results
            filters: Additional filters (sport, date range, etc.)
            
        Returns:
            List of matching parlays
        """
        # Generate embedding for query
        query_embedding = self.ml_service.generate_embedding(query_text)
        
        # Find similar parlays
        results = await self.find_similar_parlays(query_embedding, limit=limit)
        
        # Apply additional filters if provided
        if filters:
            results = self._apply_filters(results, filters)
        
        return results
    
    async def get_parlay_insights(
        self,
        parlay_id: str
    ) -> Dict[str, Any]:
        """
        Get insights about a parlay based on similar historical parlays
        
        Args:
            parlay_id: Parlay identifier
            
        Returns:
            Insights and recommendations
        """
        parlay = await self.retrieve_parlay(parlay_id)
        if not parlay:
            return {'error': 'Parlay not found'}
        
        # Find similar historical parlays
        if parlay.get('embedding_vector'):
            similar = await self.find_similar_parlays(
                parlay['embedding_vector'],
                limit=20,
                exclude_id=parlay_id
            )
            
            # Analyze historical performance
            won_count = sum(1 for p in similar if p.get('status') == 'won')
            total = len(similar)
            
            insights = {
                'parlay_id': parlay_id,
                'similar_parlays_found': total,
                'historical_win_rate': won_count / total if total > 0 else 0,
                'similar_parlays': similar[:5],
                'recommendation': self._generate_recommendation(parlay, similar)
            }
            
            return insights
        
        return {'error': 'No embedding available for analysis'}
    
    def _generate_recommendation(
        self,
        parlay: Dict[str, Any],
        similar_parlays: List[Dict[str, Any]]
    ) -> str:
        """Generate recommendation based on similar parlays"""
        if not similar_parlays:
            return "No historical data available"
        
        win_rate = sum(1 for p in similar_parlays if p.get('status') == 'won') / len(similar_parlays)
        
        if win_rate > 0.6:
            return f"STRONG BET - Similar parlays have {win_rate:.1%} win rate"
        elif win_rate > 0.45:
            return f"MODERATE BET - Similar parlays have {win_rate:.1%} win rate"
        else:
            return f"CAUTION - Similar parlays have only {win_rate:.1%} win rate"
    
    def _parlay_to_dict(self, parlay) -> Dict[str, Any]:
        """Convert SQLAlchemy model to dict"""
        return {
            'parlay_id': parlay.parlay_id,
            'title': parlay.title,
            'sport': parlay.sport,
            'confidence_level': parlay.confidence_level,
            'confidence_score': parlay.confidence_score,
            'legs': parlay.legs,
            'total_odds': parlay.total_odds,
            'potential_payout_multiplier': parlay.potential_payout_multiplier,
            'analysis': parlay.analysis,
            'key_factors': parlay.key_factors,
            'risks': parlay.risks,
            'status': parlay.status,
            'result': parlay.result,
            'twitter_post_id': parlay.twitter_post_id,
            'embedding_vector': parlay.embedding_vector,
            'similar_parlays': parlay.similar_parlays,
            'created_at': parlay.created_at.isoformat(),
            'tags': parlay.tags
        }
    
    def _apply_filters(
        self,
        results: List[Dict[str, Any]],
        filters: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Apply additional filters to search results"""
        filtered = results
        
        if 'sport' in filters:
            filtered = [r for r in filtered if r.get('sport') == filters['sport']]
        
        if 'min_confidence' in filters:
            filtered = [r for r in filtered if r.get('confidence', 0) >= filters['min_confidence']]
        
        return filtered
