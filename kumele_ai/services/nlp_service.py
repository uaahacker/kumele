"""
NLP Service - Handles keyword extraction and trend analysis
"""
import logging
import hashlib
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from collections import Counter
from sqlalchemy.orm import Session
from sqlalchemy import func, and_

from kumele_ai.db.models import NLPKeyword, NLPSentiment
from kumele_ai.services.embed_service import embed_service

logger = logging.getLogger(__name__)


class NLPService:
    """Service for NLP operations - keywords and trends"""
    
    def __init__(self):
        # Common stopwords
        self.stopwords = set([
            "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
            "of", "with", "by", "from", "as", "is", "was", "are", "were", "been",
            "be", "have", "has", "had", "do", "does", "did", "will", "would", "could",
            "should", "may", "might", "must", "shall", "can", "need", "dare", "ought",
            "used", "it", "its", "this", "that", "these", "those", "i", "you", "he",
            "she", "we", "they", "what", "which", "who", "when", "where", "why", "how",
            "all", "each", "every", "both", "few", "more", "most", "other", "some",
            "such", "no", "not", "only", "same", "so", "than", "too", "very", "just",
            "also", "now", "here", "there", "then", "once", "still", "already"
        ])
    
    def _simple_tokenize(self, text: str) -> List[str]:
        """Simple tokenization"""
        import re
        # Remove special characters and split
        words = re.findall(r'\b[a-zA-Z]{3,}\b', text.lower())
        return [w for w in words if w not in self.stopwords]
    
    def _extract_ngrams(self, tokens: List[str], n: int = 2) -> List[str]:
        """Extract n-grams from tokens"""
        ngrams = []
        for i in range(len(tokens) - n + 1):
            ngram = " ".join(tokens[i:i+n])
            ngrams.append(ngram)
        return ngrams
    
    def extract_keywords(
        self,
        db: Session,
        text: str,
        content_id: Optional[str] = None,
        top_k: int = 10
    ) -> Dict[str, Any]:
        """Extract keywords and entities from text"""
        try:
            # Generate content ID if not provided
            if not content_id:
                content_id = hashlib.sha256(text.encode()).hexdigest()[:16]
            
            # Check for existing extraction
            existing = db.query(NLPKeyword).filter(
                NLPKeyword.content_id == content_id
            ).all()
            
            if existing:
                return {
                    "content_id": content_id,
                    "keywords": [
                        {
                            "keyword": k.keyword,
                            "type": k.keyword_type,
                            "score": k.score
                        }
                        for k in existing
                    ],
                    "cached": True
                }
            
            # Tokenize
            tokens = self._simple_tokenize(text)
            
            # TF-IDF-like scoring (simplified - using term frequency)
            word_freq = Counter(tokens)
            total_words = len(tokens)
            
            # Score unigrams
            unigram_scores = {}
            for word, count in word_freq.items():
                # Simple TF score
                tf = count / total_words
                # Boost for longer words (more specific)
                length_boost = min(len(word) / 10, 1.5)
                unigram_scores[word] = tf * length_boost
            
            # Extract bigrams
            bigrams = self._extract_ngrams(tokens, 2)
            bigram_freq = Counter(bigrams)
            
            bigram_scores = {}
            for bigram, count in bigram_freq.items():
                if count >= 2:  # Only frequent bigrams
                    tf = count / (total_words - 1)
                    bigram_scores[bigram] = tf * 1.5  # Boost bigrams
            
            # Combine and sort
            all_keywords = []
            
            for word, score in sorted(unigram_scores.items(), key=lambda x: x[1], reverse=True)[:top_k]:
                all_keywords.append({
                    "keyword": word,
                    "type": "topic",
                    "score": round(score, 4)
                })
            
            for bigram, score in sorted(bigram_scores.items(), key=lambda x: x[1], reverse=True)[:5]:
                all_keywords.append({
                    "keyword": bigram,
                    "type": "phrase",
                    "score": round(score, 4)
                })
            
            # Detect potential entities (simple capitalization heuristic)
            import re
            potential_entities = re.findall(r'\b[A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*\b', text)
            entity_freq = Counter(potential_entities)
            
            for entity, count in entity_freq.most_common(5):
                if count >= 1 and len(entity) > 2:
                    all_keywords.append({
                        "keyword": entity,
                        "type": "entity",
                        "score": round(count / total_words * 2, 4)
                    })
            
            # Store in database
            for kw in all_keywords:
                keyword_record = NLPKeyword(
                    content_id=content_id,
                    keyword=kw["keyword"],
                    keyword_type=kw["type"],
                    score=kw["score"]
                )
                db.add(keyword_record)
            
            db.commit()
            
            return {
                "content_id": content_id,
                "keywords": all_keywords,
                "cached": False
            }
            
        except Exception as e:
            logger.error(f"Keyword extraction error: {e}")
            return {
                "content_id": content_id,
                "keywords": [],
                "error": str(e)
            }
    
    def get_keyword_trends(
        self,
        db: Session,
        days: int = 30,
        top_k: int = 20
    ) -> Dict[str, Any]:
        """Get keyword trends over time"""
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            
            # Aggregate keywords by frequency
            keyword_counts = db.query(
                NLPKeyword.keyword,
                NLPKeyword.keyword_type,
                func.count(NLPKeyword.id).label("count"),
                func.avg(NLPKeyword.score).label("avg_score")
            ).filter(
                NLPKeyword.extracted_at >= cutoff_date
            ).group_by(
                NLPKeyword.keyword,
                NLPKeyword.keyword_type
            ).order_by(
                func.count(NLPKeyword.id).desc()
            ).limit(top_k * 2).all()
            
            # Calculate growth rate (compare first half vs second half)
            half_cutoff = datetime.utcnow() - timedelta(days=days // 2)
            
            trends = []
            for kw, kw_type, count, avg_score in keyword_counts:
                # Count in first half
                first_half = db.query(func.count(NLPKeyword.id)).filter(
                    and_(
                        NLPKeyword.keyword == kw,
                        NLPKeyword.extracted_at >= cutoff_date,
                        NLPKeyword.extracted_at < half_cutoff
                    )
                ).scalar() or 0
                
                # Count in second half
                second_half = db.query(func.count(NLPKeyword.id)).filter(
                    and_(
                        NLPKeyword.keyword == kw,
                        NLPKeyword.extracted_at >= half_cutoff
                    )
                ).scalar() or 0
                
                # Calculate growth
                if first_half > 0:
                    growth_rate = (second_half - first_half) / first_half
                elif second_half > 0:
                    growth_rate = 1.0  # New keyword
                else:
                    growth_rate = 0.0
                
                trends.append({
                    "keyword": kw,
                    "type": kw_type,
                    "frequency": count,
                    "avg_score": round(float(avg_score), 4) if avg_score else 0,
                    "growth_rate": round(growth_rate, 2),
                    "trend": "rising" if growth_rate > 0.2 else "falling" if growth_rate < -0.2 else "stable"
                })
            
            # Sort by combined score of frequency and growth
            trends.sort(key=lambda x: x["frequency"] * (1 + x["growth_rate"]), reverse=True)
            
            return {
                "period_days": days,
                "trends": trends[:top_k],
                "total_keywords_analyzed": len(keyword_counts),
                "rising_count": sum(1 for t in trends if t["trend"] == "rising"),
                "falling_count": sum(1 for t in trends if t["trend"] == "falling")
            }
            
        except Exception as e:
            logger.error(f"Trends analysis error: {e}")
            return {
                "period_days": days,
                "trends": [],
                "error": str(e)
            }


# Singleton instance
nlp_service = NLPService()
