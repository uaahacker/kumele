"""
Feedback Analysis Service - Multi-label Classification, Sentiment & Keywords.

Implements ML-based feedback analysis per requirements:
==============================================================================

1. Multi-label Theme Classification
   - UX
   - Bugs/Technical
   - Feature requests
   - Host/Event quality
   - Complaints

2. Sentiment Analysis
   - positive | neutral | negative | mixed
   - Confidence score (0.0 - 1.0)

3. Keyword Extraction
   - 3-8 keywords per feedback
   - KeyBERT-style extraction

Stack (Open Source Only):
==============================================================================
- HuggingFace Transformers (multi-label + sentiment)
- Sentence-Transformers (embeddings)
- KeyBERT (keywords) - or fallback TF-IDF
- No hard-coded rules except fallback
- spaCy optional

Persistence:
==============================================================================
- Results stored in feedback_analysis table
- Themes + keywords as JSONB
- Raw feedback text remains in original table

API:
==============================================================================
- POST /feedback/analyze
"""
from typing import Optional, List, Dict, Any, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime
import logging
import re
import hashlib
import httpx
from collections import Counter

from app.models.database_models import FeedbackAnalysis, User
from app.config import settings

logger = logging.getLogger(__name__)


class FeedbackAnalysisService:
    """
    Service for analyzing user feedback using ML.
    
    Features:
    - Multi-label theme classification
    - Sentiment analysis
    - Keyword extraction
    """
    
    # Theme categories for multi-label classification
    THEME_LABELS = [
        "UX",
        "Bugs/Technical",
        "Feature requests",
        "Host/Event quality",
        "Complaints"
    ]
    
    # Theme keywords for fallback classification
    THEME_KEYWORDS = {
        "UX": [
            "interface", "ui", "ux", "design", "layout", "navigation", "confusing",
            "intuitive", "user experience", "usability", "look", "feel", "screen",
            "button", "menu", "click", "tap", "scroll", "hard to find", "easy to use"
        ],
        "Bugs/Technical": [
            "bug", "crash", "error", "broken", "fix", "issue", "problem", "glitch",
            "not working", "doesn't work", "failed", "loading", "slow", "freeze",
            "stuck", "infinite", "loop", "exception", "500", "404", "timeout"
        ],
        "Feature requests": [
            "feature", "add", "want", "wish", "would be nice", "suggestion", "idea",
            "could you", "please add", "missing", "need", "should have", "improve",
            "enhancement", "new", "integrate", "support for", "ability to"
        ],
        "Host/Event quality": [
            "host", "event", "organizer", "venue", "location", "quality", "experience",
            "attendee", "participant", "speaker", "content", "material", "schedule",
            "timing", "late", "early", "cancelled", "no-show", "professional"
        ],
        "Complaints": [
            "terrible", "awful", "worst", "hate", "angry", "frustrated", "disappointed",
            "unacceptable", "refund", "waste", "scam", "fake", "rude", "unprofessional",
            "never again", "complaint", "report", "unsubscribe", "delete account"
        ]
    }
    
    # Sentiment keywords for fallback
    SENTIMENT_KEYWORDS = {
        "positive": [
            "love", "great", "excellent", "amazing", "awesome", "fantastic", "perfect",
            "wonderful", "best", "thank", "thanks", "appreciate", "helpful", "good",
            "nice", "happy", "enjoy", "recommend", "satisfied", "impressed"
        ],
        "negative": [
            "hate", "terrible", "awful", "worst", "bad", "poor", "horrible", "disappointed",
            "frustrated", "angry", "annoyed", "useless", "waste", "broken", "fail",
            "never", "don't", "didn't", "can't", "won't", "problem", "issue"
        ]
    }
    
    # Stop words for keyword extraction
    STOP_WORDS = {
        "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
        "have", "has", "had", "do", "does", "did", "will", "would", "could",
        "should", "may", "might", "must", "shall", "can", "to", "of", "in",
        "for", "on", "with", "at", "by", "from", "as", "into", "through",
        "during", "before", "after", "above", "below", "between", "under",
        "again", "further", "then", "once", "here", "there", "when", "where",
        "why", "how", "all", "each", "few", "more", "most", "other", "some",
        "such", "no", "nor", "not", "only", "own", "same", "so", "than",
        "too", "very", "just", "and", "but", "if", "or", "because", "until",
        "while", "this", "that", "these", "those", "i", "me", "my", "myself",
        "we", "our", "ours", "ourselves", "you", "your", "yours", "yourself",
        "he", "him", "his", "himself", "she", "her", "hers", "herself", "it",
        "its", "itself", "they", "them", "their", "theirs", "themselves",
        "what", "which", "who", "whom", "am", "app", "really", "get", "got"
    }

    # =========================================================================
    # MAIN ANALYSIS ENTRY POINT
    # =========================================================================
    
    @staticmethod
    async def analyze_feedback(
        text: str,
        feedback_id: str,
        feedback_source: str = "general",
        user_id: Optional[int] = None,
        db: Optional[AsyncSession] = None,
        persist: bool = True
    ) -> Dict[str, Any]:
        """
        Analyze feedback text and return multi-label themes, sentiment, and keywords.
        
        Args:
            text: Feedback text to analyze
            feedback_id: Unique ID of the original feedback
            feedback_source: Source type ('event_rating', 'support_email', 'app_feedback')
            user_id: Optional user ID
            db: Database session for persistence
            persist: Whether to store results in database
        
        Returns:
            Analysis results with themes, sentiment, keywords, and confidence
        """
        start_time = datetime.utcnow()
        
        if not text or len(text.strip()) < 3:
            return {
                "error": "Text too short for analysis",
                "feedback_id": feedback_id
            }
        
        # Clean text
        clean_text = FeedbackAnalysisService._clean_text(text)
        
        # 1. Sentiment Analysis
        sentiment, sentiment_score = await FeedbackAnalysisService._analyze_sentiment(clean_text)
        
        # 2. Multi-label Theme Classification
        themes, theme_scores = await FeedbackAnalysisService._classify_themes(clean_text)
        
        # 3. Keyword Extraction
        keywords, keyword_scores = await FeedbackAnalysisService._extract_keywords(clean_text)
        
        # Calculate overall confidence
        confidence_score = FeedbackAnalysisService._calculate_confidence(
            sentiment_score, theme_scores, keyword_scores
        )
        
        processing_time_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
        
        result = {
            "feedback_id": feedback_id,
            "feedback_source": feedback_source,
            "sentiment": {
                "label": sentiment,
                "score": round(sentiment_score, 4)
            },
            "themes": themes,
            "theme_scores": {k: round(v, 4) for k, v in theme_scores.items()},
            "keywords": keywords,
            "keyword_scores": {k: round(v, 4) for k, v in keyword_scores.items()},
            "confidence_score": round(confidence_score, 4),
            "model_version": "v1.0",
            "processing_time_ms": round(processing_time_ms, 2)
        }
        
        # Persist to database
        if persist and db:
            try:
                analysis = FeedbackAnalysis(
                    feedback_id=feedback_id,
                    feedback_source=feedback_source,
                    user_id=user_id,
                    sentiment=sentiment,
                    sentiment_score=sentiment_score,
                    themes=themes,
                    theme_scores=theme_scores,
                    keywords=keywords,
                    keyword_scores=keyword_scores,
                    confidence_score=confidence_score,
                    model_version="v1.0",
                    processing_time_ms=processing_time_ms
                )
                db.add(analysis)
                await db.flush()
                result["analysis_id"] = str(analysis.analysis_id)
            except Exception as e:
                logger.error(f"Failed to persist feedback analysis: {e}")
        
        return result

    # =========================================================================
    # SENTIMENT ANALYSIS
    # =========================================================================
    
    @staticmethod
    async def _analyze_sentiment(text: str) -> Tuple[str, float]:
        """
        Analyze sentiment using HuggingFace API or fallback.
        
        Returns:
            Tuple of (sentiment_label, confidence_score)
            Labels: positive | neutral | negative | mixed
        """
        # Try HuggingFace Inference API
        try:
            if settings.HUGGINGFACE_API_KEY:
                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        "https://api-inference.huggingface.co/models/cardiffnlp/twitter-roberta-base-sentiment-latest",
                        headers={"Authorization": f"Bearer {settings.HUGGINGFACE_API_KEY}"},
                        json={"inputs": text[:512]},
                        timeout=15.0
                    )
                    
                    if response.status_code == 200:
                        results = response.json()
                        if results and isinstance(results, list) and len(results) > 0:
                            scores = results[0]
                            # Map HuggingFace labels to our labels
                            label_map = {
                                "positive": "positive",
                                "negative": "negative",
                                "neutral": "neutral"
                            }
                            
                            best = max(scores, key=lambda x: x["score"])
                            sentiment = label_map.get(best["label"].lower(), "neutral")
                            
                            # Check for mixed sentiment
                            pos_score = next((s["score"] for s in scores if "positive" in s["label"].lower()), 0)
                            neg_score = next((s["score"] for s in scores if "negative" in s["label"].lower()), 0)
                            
                            if pos_score > 0.3 and neg_score > 0.3:
                                sentiment = "mixed"
                            
                            return sentiment, best["score"]
        except Exception as e:
            logger.warning(f"HuggingFace sentiment API failed: {e}")
        
        # Fallback to keyword-based analysis
        return FeedbackAnalysisService._fallback_sentiment(text)
    
    @staticmethod
    def _fallback_sentiment(text: str) -> Tuple[str, float]:
        """Fallback keyword-based sentiment analysis."""
        text_lower = text.lower()
        words = set(re.findall(r'\b\w+\b', text_lower))
        
        pos_count = sum(1 for w in words if w in FeedbackAnalysisService.SENTIMENT_KEYWORDS["positive"])
        neg_count = sum(1 for w in words if w in FeedbackAnalysisService.SENTIMENT_KEYWORDS["negative"])
        
        total = pos_count + neg_count
        if total == 0:
            return "neutral", 0.5
        
        pos_ratio = pos_count / total
        neg_ratio = neg_count / total
        
        # Check for mixed
        if pos_count > 0 and neg_count > 0 and abs(pos_ratio - neg_ratio) < 0.3:
            return "mixed", 0.6
        
        if pos_ratio > 0.6:
            return "positive", min(0.9, 0.5 + pos_ratio * 0.4)
        elif neg_ratio > 0.6:
            return "negative", min(0.9, 0.5 + neg_ratio * 0.4)
        else:
            return "neutral", 0.5

    # =========================================================================
    # MULTI-LABEL THEME CLASSIFICATION
    # =========================================================================
    
    @staticmethod
    async def _classify_themes(text: str) -> Tuple[List[str], Dict[str, float]]:
        """
        Classify text into multiple theme categories.
        
        Uses zero-shot classification via HuggingFace or fallback.
        
        Returns:
            Tuple of (detected_themes, theme_scores)
        """
        # Try HuggingFace zero-shot classification
        try:
            if settings.HUGGINGFACE_API_KEY:
                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        "https://api-inference.huggingface.co/models/facebook/bart-large-mnli",
                        headers={"Authorization": f"Bearer {settings.HUGGINGFACE_API_KEY}"},
                        json={
                            "inputs": text[:512],
                            "parameters": {
                                "candidate_labels": FeedbackAnalysisService.THEME_LABELS,
                                "multi_label": True
                            }
                        },
                        timeout=20.0
                    )
                    
                    if response.status_code == 200:
                        result = response.json()
                        if "labels" in result and "scores" in result:
                            theme_scores = dict(zip(result["labels"], result["scores"]))
                            # Filter themes with score > 0.3
                            detected = [label for label, score in theme_scores.items() if score > 0.3]
                            return detected, theme_scores
        except Exception as e:
            logger.warning(f"HuggingFace zero-shot API failed: {e}")
        
        # Fallback to keyword matching
        return FeedbackAnalysisService._fallback_themes(text)
    
    @staticmethod
    def _fallback_themes(text: str) -> Tuple[List[str], Dict[str, float]]:
        """Fallback keyword-based theme classification."""
        text_lower = text.lower()
        words = set(re.findall(r'\b\w+\b', text_lower))
        
        theme_scores = {}
        
        for theme, keywords in FeedbackAnalysisService.THEME_KEYWORDS.items():
            matches = sum(1 for kw in keywords if kw in text_lower or kw in words)
            # Normalize score
            score = min(1.0, matches / 3.0)  # 3+ matches = 1.0
            theme_scores[theme] = score
        
        # Filter themes with score > 0.3
        detected = [theme for theme, score in theme_scores.items() if score > 0.3]
        
        # Ensure at least one theme
        if not detected and theme_scores:
            best_theme = max(theme_scores, key=theme_scores.get)
            detected = [best_theme]
        
        return detected, theme_scores

    # =========================================================================
    # KEYWORD EXTRACTION
    # =========================================================================
    
    @staticmethod
    async def _extract_keywords(
        text: str,
        min_keywords: int = 3,
        max_keywords: int = 8
    ) -> Tuple[List[str], Dict[str, float]]:
        """
        Extract important keywords from text.
        
        Uses KeyBERT-style extraction or TF-IDF fallback.
        
        Returns:
            Tuple of (keywords_list, keyword_scores)
        """
        # Try HuggingFace feature extraction for embeddings-based keywords
        try:
            if settings.HUGGINGFACE_API_KEY:
                # Use sentence similarity approach
                keywords = await FeedbackAnalysisService._embedding_keywords(text, max_keywords)
                if keywords:
                    return keywords
        except Exception as e:
            logger.warning(f"Embedding keywords failed: {e}")
        
        # Fallback to TF-IDF style extraction
        return FeedbackAnalysisService._tfidf_keywords(text, min_keywords, max_keywords)
    
    @staticmethod
    async def _embedding_keywords(text: str, max_keywords: int) -> Optional[Tuple[List[str], Dict[str, float]]]:
        """Extract keywords using embedding similarity (KeyBERT style)."""
        # Extract candidate words/phrases
        words = re.findall(r'\b[a-zA-Z]{3,}\b', text.lower())
        words = [w for w in words if w not in FeedbackAnalysisService.STOP_WORDS]
        
        if len(words) < 3:
            return None
        
        # Get unique words
        unique_words = list(set(words))[:50]
        
        try:
            async with httpx.AsyncClient() as client:
                # Get document embedding
                doc_response = await client.post(
                    f"https://api-inference.huggingface.co/pipeline/feature-extraction/sentence-transformers/all-MiniLM-L6-v2",
                    headers={"Authorization": f"Bearer {settings.HUGGINGFACE_API_KEY}"},
                    json={"inputs": text[:512], "options": {"wait_for_model": True}},
                    timeout=15.0
                )
                
                if doc_response.status_code != 200:
                    return None
                
                doc_embedding = doc_response.json()
                if not isinstance(doc_embedding, list):
                    return None
                
                # Get word embeddings (batch)
                word_response = await client.post(
                    f"https://api-inference.huggingface.co/pipeline/feature-extraction/sentence-transformers/all-MiniLM-L6-v2",
                    headers={"Authorization": f"Bearer {settings.HUGGINGFACE_API_KEY}"},
                    json={"inputs": unique_words, "options": {"wait_for_model": True}},
                    timeout=15.0
                )
                
                if word_response.status_code != 200:
                    return None
                
                word_embeddings = word_response.json()
                
                # Calculate cosine similarity
                import numpy as np
                doc_vec = np.mean(doc_embedding, axis=0) if isinstance(doc_embedding[0], list) else doc_embedding
                
                keyword_scores = {}
                for word, emb in zip(unique_words, word_embeddings):
                    word_vec = np.mean(emb, axis=0) if isinstance(emb[0], list) else emb
                    # Cosine similarity
                    similarity = np.dot(doc_vec, word_vec) / (np.linalg.norm(doc_vec) * np.linalg.norm(word_vec) + 1e-10)
                    keyword_scores[word] = float(similarity)
                
                # Sort by score
                sorted_keywords = sorted(keyword_scores.items(), key=lambda x: x[1], reverse=True)
                top_keywords = sorted_keywords[:max_keywords]
                
                keywords = [k for k, _ in top_keywords]
                scores = {k: v for k, v in top_keywords}
                
                return keywords, scores
                
        except Exception as e:
            logger.warning(f"Embedding keywords extraction failed: {e}")
            return None
    
    @staticmethod
    def _tfidf_keywords(
        text: str,
        min_keywords: int = 3,
        max_keywords: int = 8
    ) -> Tuple[List[str], Dict[str, float]]:
        """Fallback TF-IDF style keyword extraction."""
        # Tokenize
        words = re.findall(r'\b[a-zA-Z]{3,}\b', text.lower())
        
        # Remove stop words
        filtered_words = [w for w in words if w not in FeedbackAnalysisService.STOP_WORDS]
        
        if len(filtered_words) < min_keywords:
            filtered_words = words[:max_keywords]
        
        # Count frequency (TF)
        word_counts = Counter(filtered_words)
        total_words = len(filtered_words)
        
        # Calculate TF scores
        tf_scores = {}
        for word, count in word_counts.items():
            # TF with diminishing returns
            tf = (count / total_words) * (1 + 0.5 * min(count - 1, 3))
            tf_scores[word] = tf
        
        # Sort and select top keywords
        sorted_keywords = sorted(tf_scores.items(), key=lambda x: x[1], reverse=True)
        top_keywords = sorted_keywords[:max_keywords]
        
        # Normalize scores
        max_score = top_keywords[0][1] if top_keywords else 1.0
        keywords = [k for k, _ in top_keywords]
        scores = {k: round(v / max_score, 4) for k, v in top_keywords}
        
        return keywords, scores

    # =========================================================================
    # HELPER METHODS
    # =========================================================================
    
    @staticmethod
    def _clean_text(text: str) -> str:
        """Clean and normalize text."""
        # Remove excessive whitespace
        text = re.sub(r'\s+', ' ', text.strip())
        # Remove URLs
        text = re.sub(r'http[s]?://\S+', '', text)
        # Remove email addresses
        text = re.sub(r'\S+@\S+', '', text)
        return text.strip()
    
    @staticmethod
    def _calculate_confidence(
        sentiment_score: float,
        theme_scores: Dict[str, float],
        keyword_scores: Dict[str, float]
    ) -> float:
        """Calculate overall confidence score."""
        # Weighted average
        theme_avg = sum(theme_scores.values()) / len(theme_scores) if theme_scores else 0.5
        keyword_avg = sum(keyword_scores.values()) / len(keyword_scores) if keyword_scores else 0.5
        
        confidence = (
            sentiment_score * 0.4 +
            theme_avg * 0.35 +
            keyword_avg * 0.25
        )
        
        return min(1.0, max(0.0, confidence))

    # =========================================================================
    # BATCH ANALYSIS
    # =========================================================================
    
    @staticmethod
    async def analyze_batch(
        feedbacks: List[Dict[str, Any]],
        db: Optional[AsyncSession] = None,
        persist: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Analyze multiple feedback items in batch.
        
        Args:
            feedbacks: List of {"text": str, "feedback_id": str, "source": str, "user_id": int}
        
        Returns:
            List of analysis results
        """
        results = []
        
        for item in feedbacks:
            try:
                result = await FeedbackAnalysisService.analyze_feedback(
                    text=item.get("text", ""),
                    feedback_id=item.get("feedback_id", str(hash(item.get("text", "")))),
                    feedback_source=item.get("source", "batch"),
                    user_id=item.get("user_id"),
                    db=db,
                    persist=persist
                )
                results.append(result)
            except Exception as e:
                logger.error(f"Batch analysis error: {e}")
                results.append({
                    "feedback_id": item.get("feedback_id"),
                    "error": str(e)
                })
        
        return results

    # =========================================================================
    # AGGREGATION & STATS
    # =========================================================================
    
    @staticmethod
    async def get_feedback_stats(
        db: AsyncSession,
        source: Optional[str] = None,
        days: int = 30
    ) -> Dict[str, Any]:
        """Get aggregated feedback statistics."""
        from sqlalchemy import func
        from datetime import timedelta
        
        cutoff = datetime.utcnow() - timedelta(days=days)
        
        query = select(
            FeedbackAnalysis.sentiment,
            func.count(FeedbackAnalysis.analysis_id).label("count")
        ).where(
            FeedbackAnalysis.created_at >= cutoff
        )
        
        if source:
            query = query.where(FeedbackAnalysis.feedback_source == source)
        
        query = query.group_by(FeedbackAnalysis.sentiment)
        
        result = await db.execute(query)
        rows = result.fetchall()
        
        sentiment_dist = {row[0]: row[1] for row in rows}
        total = sum(sentiment_dist.values())
        
        return {
            "period_days": days,
            "source": source or "all",
            "total_analyzed": total,
            "sentiment_distribution": sentiment_dist,
            "sentiment_percentages": {
                k: round(v / total * 100, 1) if total > 0 else 0
                for k, v in sentiment_dist.items()
            }
        }
