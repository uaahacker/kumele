"""
NLP API endpoints.

Handles sentiment analysis, keyword extraction, and trend detection.

=============================================================================
NLP PROCESSING SYSTEM (Section 3F of Requirements)
=============================================================================

Overview:
Natural Language Processing for user-generated content analysis.
Powered by HuggingFace transformers.

Capabilities:
- Sentiment Analysis: positive/negative/neutral classification
- Keyword Extraction: TF-IDF + NER based extraction
- Topic Classification: Zero-shot categorization
- Trend Detection: Identify trending topics over time

Sentiment Scoring:
- Range: -1.0 (very negative) to +1.0 (very positive)
- Thresholds: <-0.3 negative, >0.3 positive, else neutral
- Multi-language: Auto-detect and translate to English

Content Types:
- Posts, comments, reviews, messages
- Event descriptions, user bios
- Support emails (for routing)

Endpoints:
- POST /nlp/sentiment: Analyze text sentiment
- POST /nlp/keywords: Extract keywords from text
- POST /nlp/topics: Classify text topics
- GET /nlp/trends: Get trending topics (daily/weekly)

Models Used:
- distilbert-base-uncased-finetuned-sst-2-english (sentiment)
- sentence-transformers/all-MiniLM-L6-v2 (embeddings)
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
    Stores results in nlp_keywords table when content_id provided.
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
        
        # Store keywords if content_id provided
        if hasattr(request, 'content_id') and request.content_id:
            try:
                content_id_int = int(request.content_id)
                keywords = [k["keyword"] for k in result.get("keywords", [])]
                entities = [e["text"] for e in result.get("entities", [])]
                await NLPService.store_keywords(
                    db=db,
                    content_id=content_id_int,
                    keywords=keywords,
                    entities=entities
                )
                await db.commit()
            except Exception as store_err:
                logger.warning(f"Failed to store keywords: {store_err}")
        
        # Update topic daily for trend tracking
        try:
            keywords = [k["keyword"] for k in result.get("keywords", [])]
            if keywords:
                await NLPService.update_topic_daily(
                    db=db,
                    keywords=keywords[:5]  # Top 5 keywords
                )
                await db.commit()
        except Exception as trend_err:
            logger.warning(f"Failed to update trends: {trend_err}")
        
        return result
        
    except Exception as e:
        await db.rollback()
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
    
    Aggregates keywords by frequency and growth.
    Stores trends in nlp_topic_daily and nlp_trends tables.
    
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
        
        # Update nlp_trends table with computed trends
        try:
            await NLPService.update_trends_table(db=db)
            await db.commit()
        except Exception as trend_err:
            logger.warning(f"Failed to update nlp_trends: {trend_err}")
        
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


@router.post(
    "/summarize",
    summary="Summarize Text",
    description="""
    Summarize text using extractive or abstractive methods.
    
    Methods:
    - **extractive**: Selects most important sentences (faster, reliable)
    - **abstractive**: Generates new summary using LLM (via TGI/Mistral)
    
    Use Cases:
    - Event description summaries
    - Blog post abstracts
    - Long review condensation
    - Email thread summaries
    
    Returns:
    - Summary text
    - Method used (extractive/abstractive)
    - Compression ratio
    """
)
async def summarize_text(
    text: str,
    max_length: int = Query(default=150, ge=20, le=500, description="Max words in summary"),
    min_length: int = Query(default=30, ge=10, le=100, description="Min words in summary"),
    style: str = Query(default="extractive", description="extractive or abstractive")
):
    """Summarize text."""
    try:
        if len(text.strip()) < 50:
            return {
                "summary": text.strip(),
                "method": "passthrough",
                "original_length": len(text.split()),
                "summary_length": len(text.split()),
                "compression_ratio": 1.0
            }
        
        result = await NLPService.summarize_text(
            text=text,
            max_length=max_length,
            min_length=min_length,
            style=style
        )
        
        return result
        
    except Exception as e:
        logger.error(f"Summarize error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/batch/summarize",
    summary="Batch Summarize",
    description="Summarize multiple texts in batch."
)
async def batch_summarize(
    texts: List[str],
    max_length: int = Query(default=150, ge=20, le=500),
    style: str = Query(default="extractive")
):
    """Batch summarize multiple texts."""
    try:
        if len(texts) > 50:
            raise HTTPException(
                status_code=400,
                detail="Maximum 50 texts per batch"
            )
        
        results = await NLPService.batch_summarize(
            texts=texts,
            max_length=max_length,
            style=style
        )
        
        return {
            "results": results,
            "count": len(results)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Batch summarize error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
