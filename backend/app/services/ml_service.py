"""
ML Service using Hugging Face models
"""
import os
import torch
import numpy as np
from typing import List, Dict, Any
from transformers import pipeline, AutoTokenizer, AutoModelForSequenceClassification
from transformers import AutoModel
from loguru import logger


class MLService:
    """Machine Learning service for sentiment analysis, embeddings, and predictions"""
    
    def __init__(self):
        self._sentiment_analyzer = None
        self._embedding_model = None
        self._embedding_tokenizer = None
        self._model_name = os.getenv('HUGGINGFACE_MODEL', 'cardiffnlp/twitter-roberta-base-sentiment-latest')
        self._embedding_model_name = os.getenv('EMBEDDING_MODEL', 'sentence-transformers/all-mpnet-base-v2')
        self._load_model()
        self._load_embedding_model()
    
    def _load_model(self):
        """Load sentiment analysis model"""
        try:
            logger.info(f"Loading Hugging Face model: {self._model_name}")
            
            self._sentiment_analyzer = pipeline(
                "sentiment-analysis",
                model=self._model_name,
                return_all_scores=True
            )
            
            logger.info("Sentiment model loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load sentiment model: {e}")
            self._sentiment_analyzer = None
    
    def _load_embedding_model(self):
        """Load embedding model for RAG pipeline"""
        try:
            logger.info(f"Loading embedding model: {self._embedding_model_name}")
            
            self._embedding_tokenizer = AutoTokenizer.from_pretrained(self._embedding_model_name)
            self._embedding_model = AutoModel.from_pretrained(self._embedding_model_name)
            
            logger.info("Embedding model loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load embedding model: {e}")
            self._embedding_model = None
            self._embedding_tokenizer = None
    
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
    
    def generate_embedding(self, text: str) -> List[float]:
        """
        Generate embedding vector for text
        
        Args:
            text: Input text
            
        Returns:
            Embedding vector as list of floats
        """
        if not self._embedding_model or not self._embedding_tokenizer:
            logger.warning("Embedding model not loaded, returning zero vector")
            return [0.0] * 768
        
        try:
            # Tokenize and encode
            inputs = self._embedding_tokenizer(
                text,
                return_tensors="pt",
                truncation=True,
                max_length=512,
                padding=True
            )
            
            # Generate embeddings
            with torch.no_grad():
                outputs = self._embedding_model(**inputs)
            
            # Use mean pooling
            embeddings = outputs.last_hidden_state.mean(dim=1)
            
            # Convert to list
            embedding_list = embeddings[0].cpu().numpy().tolist()
            
            return embedding_list
            
        except Exception as e:
            logger.error(f"Embedding generation error: {e}")
            return [0.0] * 768
    
    def generate_embeddings_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for multiple texts
        
        Args:
            texts: List of input texts
            
        Returns:
            List of embedding vectors
        """
        if not self._embedding_model or not self._embedding_tokenizer:
            logger.warning("Embedding model not loaded, returning zero vectors")
            return [[0.0] * 768 for _ in texts]
        
        try:
            # Tokenize batch
            inputs = self._embedding_tokenizer(
                texts,
                return_tensors="pt",
                truncation=True,
                max_length=512,
                padding=True
            )
            
            # Generate embeddings
            with torch.no_grad():
                outputs = self._embedding_model(**inputs)
            
            # Use mean pooling
            embeddings = outputs.last_hidden_state.mean(dim=1)
            
            # Convert to list
            embeddings_list = embeddings.cpu().numpy().tolist()
            
            return embeddings_list
            
        except Exception as e:
            logger.error(f"Batch embedding generation error: {e}")
            return [[0.0] * 768 for _ in texts]
    
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

