"""
ML Service using Hugging Face models
"""
import os
from typing import List, Dict, Any
from transformers import pipeline, AutoTokenizer, AutoModelForSequenceClassification
from transformers import AutoModel
from loguru import logger


class MLService:
    """Machine Learning service for sentiment analysis and predictions"""
    
    def __init__(self):
        self._sentiment_analyzer = None
        self._model_name = os.getenv('HUGGINGFACE_MODEL', 'cardiffnlp/twitter-roberta-base-sentiment-latest')
        self._load_model()
    
    def _load_model(self):
        """Load sentiment analysis model"""
        try:
            logger.info(f"Loading Hugging Face model: {self._model_name}")
            
            self._sentiment_analyzer = pipeline(
                "sentiment-analysis",
                model=self._model_name,
                return_all_scores=True
            )
            
            logger.info("Model loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load model: {e}")
            self._sentiment_analyzer = None
    
    def analyze_sentiment(self, texts: List[str]) -> Dict[str, Any]:
        """
        Analyze sentiment of a list of texts
        
        Args:
            texts: List of text strings to analyze
            
        Returns:
            Dictionary with sentiment scores
        """
        if not self._sentiment_analyzer:
            return {"error": "Model not loaded"}
        
        try:
            results = self._sentiment_analyzer(texts)
            
            # Aggregate results
            sentiments = []
            for text, result in zip(texts, results):
                # Get the highest confidence label
                best = max(result, key=lambda x: x['score'])
                sentiments.append({
                    'text': text,
                    'label': best['label'],
                    'score': best['score'],
                    'all_scores': result
                })
            
            # Compute aggregate sentiment
            label_counts = {}
            total_score = 0
            
            for sent in sentiments:
                label = sent['label']
                score = sent['score']
                label_counts[label] = label_counts.get(label, 0) + 1
                total_score += score
            
            overall_label = max(label_counts, key=label_counts.get)
            avg_score = total_score / len(sentiments) if sentiments else 0
            
            return {
                'overall_sentiment': overall_label,
                'average_confidence': avg_score,
                'label_distribution': label_counts,
                'total_texts': len(texts),
                'detailed_results': sentiments
            }
            
        except Exception as e:
            logger.error(f"Sentiment analysis error: {e}")
            return {"error": str(e)}
    
    def predict_bet_outcome(self, features: Dict[str, Any]) -> Dict[str, Any]:
        """
        Predict bet outcome using ML models
        
        Args:
            features: Dictionary of feature values
            
        Returns:
            Dictionary with prediction and confidence
        """
        # This is a placeholder for actual ML prediction logic
        # In a real implementation, you would load a trained model
        
        logger.info("ML prediction called (placeholder)")
        
        return {
            'prediction': 'placeholder',
            'confidence': 0.5,
            'note': 'ML prediction not yet implemented'
        }

