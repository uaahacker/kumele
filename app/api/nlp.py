"""
NLP API endpoints.
Handles sentiment analysis, keyword extraction, and trend detection.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List
import logging

from app.database import get_db
from app.services.nlp_service import NLPService
from app.schemas.schemas import (
    SentimentRequest,
    SentimentResponse,
    KeywordRequest,
    KeywordResponse,
    TrendingTopicsResponse
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/nlp", tags=["NLP"])


@router.post(
    "/sentiment",
    response_model=SentimentResponse,
    summary="Analyze Sentiment",
    description="""
    Analyze sentiment of user-generated content.
    
    Uses transformer-based sentiment analysis (RoBERTa) to classify:
    - Positive (score > 0.6)
    - Negative (score < 0.4)
    - Neutral (0.4 - 0.6)
    
    Returns:
    - Sentiment label
    - Confidence score (0-1)
    - Detailed emotion breakdown
    """
)
async def analyze_sentiment(
    request: SentimentRequest,
    db: AsyncSession = Depends(get_db)
):
    """Analyze sentiment of text."""
    try:
        result = await NLPService.analyze_sentiment(request.text)
        
        # Store analysis if content_id provided
        if request.content_id:
            await NLPService.store_sentiment(
                db=db,
                content_id=request.content_id,
                content_type=request.content_type or "unknown",
                sentiment=result["sentiment"],
                score=result["score"]
            )
            await db.commit()
        
        return result
        
    except Exception as e:
        await db.rollback()
        logger.error(f"Sentiment analysis error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/keywords",
    response_model=KeywordResponse,
    summary="Extract Keywords",
    description="""
    Extract keywords and key phrases from text.
    
    Extracts:
    - Topic keywords
    - Named entities (people, places, organizations)
    - Hobby-related terms
    - Location indicators
    
    Returns keywords with frequency and relevance scores.
    """
)
async def extract_keywords(
    request: KeywordRequest,
    db: AsyncSession = Depends(get_db)
):
    """Extract keywords from text."""
    try:
        result = await NLPService.extract_keywords(
            text=request.text,
            max_keywords=request.max_keywords or 10
        )
        
        return result
        
    except Exception as e:
        logger.error(f"Keyword extraction error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/trends",
    response_model=TrendingTopicsResponse,
    summary="Get Trending Topics",
    description="""
    Get trending topics based on user-generated content.
    
    Analyzes recent content to identify:
    - Trending keywords and phrases
    - Popular discussion topics
    - Emerging interests
    - Sentiment trends
    
    Configurable by timeframe and category.
    """
)
async def get_trends(
    timeframe: str = Query("24h", description="Timeframe: 1h, 24h, 7d, 30d"),
    category: Optional[str] = Query(None, description="Filter by category"),
    limit: int = Query(20, ge=1, le=100, description="Max results"),
    db: AsyncSession = Depends(get_db)
):
    """Get trending topics."""
    try:
        result = await NLPService.get_trending_topics(
            db=db,
            timeframe=timeframe,
            category=category,
            limit=limit
        )
        
        return result
        
    except Exception as e:
        logger.error(f"Get trends error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/batch-sentiment",
    summary="Batch Sentiment Analysis",
    description="Analyze sentiment for multiple texts."
)
async def batch_sentiment(
    texts: List[str],
    db: AsyncSession = Depends(get_db)
):
    """Analyze sentiment for multiple texts."""
    try:
        results = []
        for text in texts[:50]:  # Limit to 50 texts
            result = await NLPService.analyze_sentiment(text)
            results.append(result)
        
        return {
            "results": results,
            "count": len(results)
        }
        
    except Exception as e:
        logger.error(f"Batch sentiment error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/topics/update",
    summary="Update Topic Stats",
    description="Update daily topic statistics (admin/cron use)."
)
async def update_topics(
    topic: str,
    category: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """Update topic statistics."""
    try:
        await NLPService.update_topic_daily(
            db=db,
            topic=topic,
            category=category
        )
        await db.commit()
        
        return {
            "success": True,
            "message": f"Topic '{topic}' updated"
        }
        
    except Exception as e:
        await db.rollback()
        logger.error(f"Update topics error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
