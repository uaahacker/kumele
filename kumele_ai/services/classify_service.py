"""
Classification Service - Handles text classification using Hugging Face models
"""
import logging
import hashlib
from typing import Dict, Any, List, Optional
from transformers import pipeline
from sqlalchemy.orm import Session
from kumele_ai.config import settings
from kumele_ai.db.models import NLPSentiment, AIActionLog

logger = logging.getLogger(__name__)


class ClassifyService:
    """Service for text classification tasks"""
    
    def __init__(self):
        self._sentiment_pipeline = None
        self._toxicity_pipeline = None
        self._spam_pipeline = None
    
    @property
    def sentiment_pipeline(self):
        """Lazy load sentiment analysis pipeline"""
        if self._sentiment_pipeline is None:
            logger.info("Loading sentiment analysis model...")
            self._sentiment_pipeline = pipeline(
                "sentiment-analysis",
                model="distilbert-base-uncased-finetuned-sst-2-english"
            )
            logger.info("Sentiment model loaded")
        return self._sentiment_pipeline
    
    @property
    def toxicity_pipeline(self):
        """Lazy load toxicity detection pipeline"""
        if self._toxicity_pipeline is None:
            logger.info("Loading toxicity detection model...")
            self._toxicity_pipeline = pipeline(
                "text-classification",
                model="unitary/toxic-bert"
            )
            logger.info("Toxicity model loaded")
        return self._toxicity_pipeline
    
    def analyze_sentiment(
        self,
        text: str,
        content_id: Optional[str] = None,
        db: Optional[Session] = None
    ) -> Dict[str, Any]:
        """Analyze sentiment of text"""
        try:
            # Check if we have a cached result
            if db and content_id:
                content_hash = hashlib.sha256(text.encode()).hexdigest()
                existing = db.query(NLPSentiment).filter(
                    NLPSentiment.content_hash == content_hash
                ).first()
                
                if existing:
                    return {
                        "sentiment": existing.sentiment,
                        "confidence": existing.confidence,
                        "cached": True
                    }
            
            # Run sentiment analysis
            result = self.sentiment_pipeline(text[:512])[0]
            
            # Map to our schema
            sentiment = "positive" if result["label"] == "POSITIVE" else "negative"
            if result["score"] < 0.6:
                sentiment = "neutral"
            
            output = {
                "sentiment": sentiment,
                "confidence": result["score"],
                "cached": False
            }
            
            # Store result
            if db and content_id:
                content_hash = hashlib.sha256(text.encode()).hexdigest()
                nlp_result = NLPSentiment(
                    content_id=content_id,
                    content_hash=content_hash,
                    text=text[:1000],
                    sentiment=sentiment,
                    confidence=result["score"]
                )
                db.add(nlp_result)
                db.commit()
            
            return output
            
        except Exception as e:
            logger.error(f"Sentiment analysis error: {e}")
            return {
                "sentiment": "neutral",
                "confidence": 0.0,
                "error": str(e)
            }
    
    def detect_toxicity(self, text: str) -> Dict[str, Any]:
        """Detect toxicity in text"""
        try:
            result = self.toxicity_pipeline(text[:512])[0]
            
            is_toxic = result["label"] == "toxic" and result["score"] > settings.MODERATION_TEXT_TOXICITY_THRESHOLD
            
            return {
                "is_toxic": is_toxic,
                "toxicity_score": result["score"] if result["label"] == "toxic" else 1 - result["score"],
                "label": result["label"]
            }
        except Exception as e:
            logger.error(f"Toxicity detection error: {e}")
            return {
                "is_toxic": False,
                "toxicity_score": 0.0,
                "error": str(e)
            }
    
    def detect_spam(self, text: str) -> Dict[str, Any]:
        """Detect spam in text using heuristics and patterns"""
        try:
            # Simple spam detection heuristics
            spam_indicators = 0
            total_checks = 5
            
            # Check for excessive capitalization
            upper_ratio = sum(1 for c in text if c.isupper()) / max(len(text), 1)
            if upper_ratio > 0.5:
                spam_indicators += 1
            
            # Check for excessive punctuation
            punct_count = sum(1 for c in text if c in "!?$%")
            if punct_count > len(text) * 0.1:
                spam_indicators += 1
            
            # Check for repeated characters
            if any(text.count(c * 4) > 0 for c in text.lower()):
                spam_indicators += 1
            
            # Check for suspicious patterns
            spam_words = ["free", "winner", "click here", "act now", "limited time"]
            text_lower = text.lower()
            if any(word in text_lower for word in spam_words):
                spam_indicators += 1
            
            # Check for excessive links
            if text.count("http") > 3:
                spam_indicators += 1
            
            spam_score = spam_indicators / total_checks
            is_spam = spam_score > settings.MODERATION_TEXT_SPAM_THRESHOLD
            
            return {
                "is_spam": is_spam,
                "spam_score": spam_score,
                "indicators": spam_indicators
            }
        except Exception as e:
            logger.error(f"Spam detection error: {e}")
            return {
                "is_spam": False,
                "spam_score": 0.0,
                "error": str(e)
            }
    
    def classify_support_email(self, text: str) -> Dict[str, Any]:
        """Classify support email into categories"""
        try:
            # Define categories and keywords
            categories = {
                "account": ["account", "login", "password", "profile", "settings", "delete"],
                "billing": ["payment", "charge", "refund", "invoice", "subscription", "price"],
                "events": ["event", "booking", "attend", "host", "cancel", "reschedule"],
                "technical": ["bug", "error", "crash", "not working", "issue", "problem"],
                "feedback": ["suggestion", "feedback", "improve", "feature", "request"],
                "general": []
            }
            
            text_lower = text.lower()
            scores = {}
            
            for category, keywords in categories.items():
                if keywords:
                    score = sum(1 for kw in keywords if kw in text_lower)
                    scores[category] = score
                else:
                    scores[category] = 0
            
            # Find best category
            best_category = max(scores, key=scores.get) if max(scores.values()) > 0 else "general"
            
            # Analyze urgency
            urgency_words = ["urgent", "asap", "immediately", "emergency", "critical"]
            urgency = "high" if any(w in text_lower for w in urgency_words) else "normal"
            
            return {
                "category": best_category,
                "urgency": urgency,
                "confidence": min(max(scores.values()) / 3, 1.0)
            }
        except Exception as e:
            logger.error(f"Email classification error: {e}")
            return {
                "category": "general",
                "urgency": "normal",
                "confidence": 0.0,
                "error": str(e)
            }
    
    def unload(self):
        """Unload models to free memory"""
        self._sentiment_pipeline = None
        self._toxicity_pipeline = None
        self._spam_pipeline = None
        logger.info("Classification models unloaded")


# Singleton instance
classify_service = ClassifyService()
