"""
Feedback Analysis API - POST /feedback/analyze

Analyzes user feedback for:
- Multi-label theme classification (UX, Bugs/Technical, Feature requests, Host/Event quality, Complaints)
- Sentiment analysis (positive | neutral | negative | mixed)
- Keyword extraction (3-8 keywords)

Request Body:
{
    "text": "The event was great but the app is confusing to navigate",
    "feedback_id": "fb-12345",
    "feedback_source": "event_rating",  // optional
    "user_id": 123  // optional
}

Response:
{
    "feedback_id": "fb-12345",
    "sentiment": {
        "label": "mixed",
        "score": 0.75
    },
    "themes": ["UX", "Host/Event quality"],
    "theme_scores": {
        "UX": 0.82,
        "Host/Event quality": 0.65,
        ...
    },
    "keywords": ["event", "great", "app", "confusing", "navigate"],
    "keyword_scores": {...},
    "confidence_score": 0.78,
    "analysis_id": "uuid"
}
"""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
import logging

from app.database import get_db
from app.services.feedback_service import FeedbackAnalysisService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/feedback", tags=["Feedback Analysis"])


# ============================================================================
# REQUEST/RESPONSE SCHEMAS
# ============================================================================

class FeedbackAnalyzeRequest(BaseModel):
    """Request body for feedback analysis."""
    text: str = Field(..., min_length=3, max_length=10000, description="Feedback text to analyze")
    feedback_id: str = Field(..., min_length=1, max_length=255, description="Unique feedback identifier")
    feedback_source: Optional[str] = Field(
        "general",
        description="Source: event_rating, support_email, app_feedback, general"
    )
    user_id: Optional[int] = Field(None, description="User ID if known")

    class Config:
        json_schema_extra = {
            "example": {
                "text": "The event was fantastic but the app interface is confusing to navigate. Would love better UX!",
                "feedback_id": "fb-12345",
                "feedback_source": "event_rating",
                "user_id": 123
            }
        }


class FeedbackBatchRequest(BaseModel):
    """Request body for batch feedback analysis."""
    feedbacks: List[FeedbackAnalyzeRequest] = Field(
        ...,
        min_length=1,
        max_length=50,
        description="List of feedbacks to analyze (max 50)"
    )


class SentimentResult(BaseModel):
    """Sentiment analysis result."""
    label: str = Field(..., description="positive | neutral | negative | mixed")
    score: float = Field(..., ge=0, le=1, description="Confidence score")


class FeedbackAnalyzeResponse(BaseModel):
    """Response for feedback analysis."""
    feedback_id: str
    feedback_source: Optional[str] = None
    sentiment: SentimentResult
    themes: List[str] = Field(..., description="Detected themes")
    theme_scores: Dict[str, float] = Field(..., description="Score per theme")
    keywords: List[str] = Field(..., description="Extracted keywords (3-8)")
    keyword_scores: Dict[str, float] = Field(..., description="Score per keyword")
    confidence_score: float = Field(..., ge=0, le=1, description="Overall confidence")
    model_version: str = Field(..., description="Model version used")
    processing_time_ms: float = Field(..., description="Processing time in ms")
    analysis_id: Optional[str] = Field(None, description="Database record ID if persisted")

    class Config:
        json_schema_extra = {
            "example": {
                "feedback_id": "fb-12345",
                "feedback_source": "event_rating",
                "sentiment": {
                    "label": "mixed",
                    "score": 0.75
                },
                "themes": ["UX", "Host/Event quality"],
                "theme_scores": {
                    "UX": 0.82,
                    "Bugs/Technical": 0.12,
                    "Feature requests": 0.35,
                    "Host/Event quality": 0.65,
                    "Complaints": 0.08
                },
                "keywords": ["event", "fantastic", "app", "interface", "confusing", "navigate", "ux"],
                "keyword_scores": {
                    "event": 0.92,
                    "fantastic": 0.85,
                    "app": 0.78,
                    "interface": 0.75,
                    "confusing": 0.72,
                    "navigate": 0.68,
                    "ux": 0.65
                },
                "confidence_score": 0.78,
                "model_version": "v1.0",
                "processing_time_ms": 125.5,
                "analysis_id": "550e8400-e29b-41d4-a716-446655440000"
            }
        }


class FeedbackStatsResponse(BaseModel):
    """Response for feedback statistics."""
    period_days: int
    source: str
    total_analyzed: int
    sentiment_distribution: Dict[str, int]
    sentiment_percentages: Dict[str, float]


# ============================================================================
# ENDPOINTS
# ============================================================================

@router.post(
    "/analyze",
    response_model=FeedbackAnalyzeResponse,
    summary="Analyze feedback text",
    description="""
Analyze user feedback to extract:
- **Sentiment**: positive | neutral | negative | mixed with confidence score
- **Themes**: Multi-label classification into UX, Bugs/Technical, Feature requests, Host/Event quality, Complaints
- **Keywords**: 3-8 important keywords extracted using KeyBERT-style algorithm

Uses HuggingFace Transformers for ML inference with fallback to rule-based analysis.
Results are persisted to database for analytics.
    """
)
async def analyze_feedback(
    request: FeedbackAnalyzeRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Analyze a single feedback text.
    
    Returns sentiment, themes, keywords, and confidence scores.
    """
    try:
        result = await FeedbackAnalysisService.analyze_feedback(
            text=request.text,
            feedback_id=request.feedback_id,
            feedback_source=request.feedback_source or "general",
            user_id=request.user_id,
            db=db,
            persist=True
        )
        
        if "error" in result:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result["error"]
            )
        
        # Format response
        return FeedbackAnalyzeResponse(
            feedback_id=result["feedback_id"],
            feedback_source=result.get("feedback_source"),
            sentiment=SentimentResult(
                label=result["sentiment"]["label"],
                score=result["sentiment"]["score"]
            ),
            themes=result["themes"],
            theme_scores=result["theme_scores"],
            keywords=result["keywords"],
            keyword_scores=result["keyword_scores"],
            confidence_score=result["confidence_score"],
            model_version=result["model_version"],
            processing_time_ms=result["processing_time_ms"],
            analysis_id=result.get("analysis_id")
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Feedback analysis error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Analysis failed: {str(e)}"
        )


@router.post(
    "/analyze/batch",
    response_model=List[FeedbackAnalyzeResponse],
    summary="Analyze multiple feedback texts",
    description="Analyze up to 50 feedback items in a single request."
)
async def analyze_feedback_batch(
    request: FeedbackBatchRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Analyze multiple feedback texts in batch.
    
    Returns list of analysis results.
    """
    try:
        feedbacks = [
            {
                "text": fb.text,
                "feedback_id": fb.feedback_id,
                "source": fb.feedback_source or "batch",
                "user_id": fb.user_id
            }
            for fb in request.feedbacks
        ]
        
        results = await FeedbackAnalysisService.analyze_batch(
            feedbacks=feedbacks,
            db=db,
            persist=True
        )
        
        # Format responses
        responses = []
        for result in results:
            if "error" not in result:
                responses.append(FeedbackAnalyzeResponse(
                    feedback_id=result["feedback_id"],
                    feedback_source=result.get("feedback_source"),
                    sentiment=SentimentResult(
                        label=result["sentiment"]["label"],
                        score=result["sentiment"]["score"]
                    ),
                    themes=result["themes"],
                    theme_scores=result["theme_scores"],
                    keywords=result["keywords"],
                    keyword_scores=result["keyword_scores"],
                    confidence_score=result["confidence_score"],
                    model_version=result["model_version"],
                    processing_time_ms=result["processing_time_ms"],
                    analysis_id=result.get("analysis_id")
                ))
        
        return responses
        
    except Exception as e:
        logger.error(f"Batch feedback analysis error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Batch analysis failed: {str(e)}"
        )


@router.get(
    "/stats",
    response_model=FeedbackStatsResponse,
    summary="Get feedback statistics",
    description="Get aggregated sentiment statistics for analyzed feedback."
)
async def get_feedback_stats(
    source: Optional[str] = Query(None, description="Filter by feedback source"),
    days: int = Query(30, ge=1, le=365, description="Period in days"),
    db: AsyncSession = Depends(get_db)
):
    """
    Get aggregated feedback statistics.
    
    Returns sentiment distribution over specified period.
    """
    try:
        stats = await FeedbackAnalysisService.get_feedback_stats(
            db=db,
            source=source,
            days=days
        )
        
        return FeedbackStatsResponse(**stats)
        
    except Exception as e:
        logger.error(f"Feedback stats error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get stats: {str(e)}"
        )


@router.get(
    "/themes",
    summary="Get available themes",
    description="Get list of theme categories used for classification."
)
async def get_themes():
    """
    Get available theme categories.
    """
    return {
        "themes": FeedbackAnalysisService.THEME_LABELS,
        "description": {
            "UX": "User experience, interface, usability issues",
            "Bugs/Technical": "Errors, crashes, technical problems",
            "Feature requests": "Suggestions for new features or improvements",
            "Host/Event quality": "Feedback about hosts, events, venues",
            "Complaints": "General complaints, negative feedback"
        }
    }
