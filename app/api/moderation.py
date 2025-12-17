"""
Moderation API endpoints.
Handles unified content moderation for text, images, and video.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
import logging

from app.database import get_db
from app.services.moderation_service import ModerationService
from app.schemas.schemas import (
    ModerationRequest,
    ModerationResponse,
    ModerationStatus
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/moderation", tags=["Moderation"])


@router.post(
    "",
    response_model=ModerationResponse,
    summary="Moderate Content",
    description="""
    Submit content for moderation.
    
    Supports:
    - **text**: Analyzes for toxicity, hate speech, spam, profanity
    - **image**: Analyzes for nudity, violence, graphic content
    - **video**: Analyzes keyframes for visual content + audio transcription
    
    Moderation thresholds:
    - Toxicity > 0.60 → Flag
    - Hate speech > 0.30 → Reject
    - Spam > 0.70 → Flag
    - Nudity > 0.60 → Reject (images/video)
    - Violence > 0.50 → Flag
    
    Returns:
    - Decision: approve / reject / flag_for_review
    - Confidence score
    - Detailed flags and reasons
    """
)
async def moderate_content(
    request: ModerationRequest,
    db: AsyncSession = Depends(get_db)
):
    """Moderate content."""
    import uuid
    
    # Auto-generate content_id if not provided (for easier testing)
    content_id = request.content_id or str(uuid.uuid4())
    
    try:
        result = await ModerationService.moderate_content(
            db=db,
            content_id=content_id,
            content_type=request.content_type,
            text=request.text,
            image_url=request.image_url,
            video_url=request.video_url,
            user_id=request.user_id
        )
        
        await db.commit()
        return result
        
    except Exception as e:
        await db.rollback()
        logger.error(f"Moderation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/{content_id}",
    response_model=ModerationStatus,
    summary="Get Moderation Status",
    description="""
    Get the moderation status of previously submitted content.
    
    Returns:
    - Current status
    - Decision (if complete)
    - Flags and scores
    - Review notes (if manually reviewed)
    """
)
async def get_moderation_status(
    content_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Get moderation status for content."""
    try:
        result = await ModerationService.get_moderation_status(db, content_id)
        
        if "error" in result:
            raise HTTPException(status_code=404, detail=result["error"])
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get moderation status error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/{content_id}/review",
    summary="Manual Review Decision",
    description="Submit manual review decision for flagged content (admin use)."
)
async def manual_review(
    content_id: str,
    decision: str = Query(..., description="approve / reject"),
    reviewer_id: str = Query(..., description="Reviewer user ID"),
    notes: Optional[str] = Query(None, description="Review notes"),
    db: AsyncSession = Depends(get_db)
):
    """Submit manual review decision."""
    try:
        if decision not in ["approve", "reject"]:
            raise HTTPException(
                status_code=400,
                detail="Decision must be 'approve' or 'reject'"
            )
        
        result = await ModerationService.manual_review(
            db=db,
            content_id=content_id,
            decision=decision,
            reviewer_id=reviewer_id,
            notes=notes
        )
        
        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])
        
        await db.commit()
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Manual review error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/queue/pending",
    summary="Get Pending Reviews",
    description="Get content flagged for manual review."
)
async def get_pending_reviews(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db)
):
    """Get content pending review."""
    try:
        result = await ModerationService.get_pending_reviews(
            db, limit, offset
        )
        
        return result
        
    except Exception as e:
        logger.error(f"Get pending reviews error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/stats",
    summary="Get Moderation Statistics",
    description="Get moderation statistics and metrics."
)
async def get_moderation_stats(
    days: int = Query(7, ge=1, le=90, description="Days to include"),
    db: AsyncSession = Depends(get_db)
):
    """Get moderation statistics."""
    try:
        result = await ModerationService.get_stats(db, days)
        return result
        
    except Exception as e:
        logger.error(f"Get moderation stats error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
