"""
NLP Router - NLP analysis endpoints
"""
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.orm import Session

from kumele_ai.dependencies import get_db
from kumele_ai.services.classify_service import classify_service
from kumele_ai.services.nlp_service import nlp_service

router = APIRouter()


class SentimentRequest(BaseModel):
    text: str
    content_id: Optional[str] = None


class KeywordsRequest(BaseModel):
    text: str
    content_id: Optional[str] = None
    top_k: int = 10


@router.post("/sentiment")
async def analyze_sentiment(
    request: SentimentRequest,
    db: Session = Depends(get_db)
):
    """
    Analyze sentiment of text.
    
    Returns:
    - sentiment: positive | neutral | negative
    - confidence: 0.0 - 1.0
    
    Results are stored in nlp_sentiment table.
    """
    result = classify_service.analyze_sentiment(
        text=request.text,
        content_id=request.content_id,
        db=db
    )
    
    return result


@router.post("/keywords")
async def extract_keywords(
    request: KeywordsRequest,
    db: Session = Depends(get_db)
):
    """
    Extract keywords and entities from text.
    
    Uses HF embeddings + TF-IDF-based keyword extraction.
    
    Returns:
    - keywords: List of extracted keywords with types and scores
    - types: topic, entity, phrase, hobby
    """
    result = nlp_service.extract_keywords(
        db=db,
        text=request.text,
        content_id=request.content_id,
        top_k=request.top_k
    )
    
    return result


@router.get("/trends")
async def get_keyword_trends(
    days: int = Query(30, ge=1, le=365, description="Number of days to analyze"),
    top_k: int = Query(20, ge=1, le=100, description="Number of top keywords"),
    db: Session = Depends(get_db)
):
    """
    Get aggregated keyword trends over time.
    
    Ranks keywords by frequency and growth rate.
    Uses PostgreSQL aggregates daily.
    
    Returns:
    - trends: List of trending keywords with frequency and growth
    - rising_count: Number of rising keywords
    - falling_count: Number of falling keywords
    """
    result = nlp_service.get_keyword_trends(
        db=db,
        days=days,
        top_k=top_k
    )
    
    return result
