"""
Moderation API endpoints.

Handles unified content moderation for text, images, and video.

=============================================================================
CONTENT MODERATION SYSTEM (Section 3G of Requirements)
=============================================================================

Overview:
AI-powered content moderation for community safety.
Supports text, image, and video content.

Text Moderation:
- Toxicity detection (toxic-bert model)
- Hate speech classification
- Profanity filtering
- Spam detection
- PII detection (emails, phones, SSN)

Image Moderation:
- NSFW content detection
- Violence/gore detection
- Face detection (privacy)
- Logo/watermark detection

Video Moderation (Future):
- Frame-by-frame analysis
- Audio transcription + text moderation

Scoring System:
- 0.0 - 0.3: Safe (auto-approve)
- 0.3 - 0.7: Review (manual queue)
- 0.7 - 1.0: Reject (auto-reject)

Job Flow:
pending → processing → completed/failed/needs_review

Endpoints:
- POST /moderation: Submit content for moderation
- GET /moderation/job/{job_id}: Check moderation job status
- POST /moderation/batch: Batch moderation submission
- GET /moderation/queue: Get pending review queue

Async Processing:
- Heavy jobs processed via Celery
- Webhook callback on completion
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


# ==============================================================================
# FILE UPLOAD MODERATION ENDPOINTS
# ==============================================================================

from fastapi import UploadFile, File


@router.post(
    "/upload-image",
    summary="Moderate Uploaded Image",
    description="""
    Moderate an uploaded image file directly.
    
    **Supported formats:** JPEG, PNG, GIF, WebP, BMP
    
    **Max file size:** 10MB
    
    **AI Analysis (when HUGGINGFACE_API_KEY is set):**
    - NSFW content detection
    - Sexual/explicit content
    - Violence detection
    
    **Decision thresholds:**
    - nudity > 0.60 → Reject
    - sexual > 0.30 → Reject
    - violence > 0.40 → Flag for review
    
    This endpoint processes the image immediately and returns results.
    """
)
async def moderate_uploaded_image(
    file: UploadFile = File(..., description="Image file to moderate"),
    user_id: Optional[str] = Query(None, description="User ID for tracking"),
    db: AsyncSession = Depends(get_db)
):
    """Moderate an uploaded image file."""
    import uuid
    
    # Validate file type
    allowed_types = ["image/jpeg", "image/png", "image/gif", "image/webp", "image/bmp"]
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type: {file.content_type}. Allowed: {allowed_types}"
        )
    
    # Read file content
    content = await file.read()
    
    # Check file size (10MB limit)
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(
            status_code=400,
            detail="File too large. Maximum size is 10MB."
        )
    
    content_id = str(uuid.uuid4())
    
    try:
        # Use the image bytes moderation method
        moderation_result = await ModerationService.moderate_image_bytes(
            image_bytes=content,
            filename=file.filename
        )
        
        # Determine decision based on scores
        max_score = moderation_result.get("max_score", 0)
        
        if max_score >= 0.6:
            decision = "reject"
        elif max_score >= 0.3:
            decision = "needs_review"
        else:
            decision = "approve"
        
        result = {
            "content_id": content_id,
            "content_type": "image",
            "filename": file.filename,
            "file_size": len(content),
            "decision": decision,
            "confidence": round(1.0 - max_score, 2),
            "moderation_details": {
                "max_score": round(max_score, 2),
                "labels": moderation_result.get("labels", []),
                "model": moderation_result.get("model", "unknown"),
                "api_status": moderation_result.get("api_status", "unknown")
            },
            "user_id": user_id,
            "error": moderation_result.get("error")
        }
        
        return result
        
    except Exception as e:
        logger.error(f"Image upload moderation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/moderate-base64",
    summary="Moderate Base64 Image",
    description="""
    Moderate an image provided as base64 encoded string.
    
    **Use cases:**
    - Canvas/drawing applications
    - Clipboard images
    - Client-side image processing
    
    **Format:**
    - With data URI: `data:image/jpeg;base64,/9j/4AAQ...`
    - Without prefix: `/9j/4AAQ...`
    
    **AI Analysis:** Same as upload-image endpoint.
    """
)
async def moderate_base64_image(
    base64_data: str = Query(..., description="Base64 encoded image data"),
    user_id: Optional[str] = Query(None, description="User ID for tracking"),
    db: AsyncSession = Depends(get_db)
):
    """Moderate a base64 encoded image."""
    import uuid
    
    content_id = str(uuid.uuid4())
    
    try:
        # Use the base64 moderation method
        moderation_result = await ModerationService.moderate_base64_image(
            base64_data=base64_data,
            filename="base64_image"
        )
        
        # Determine decision based on scores
        max_score = moderation_result.get("max_score", 0)
        
        if max_score >= 0.6:
            decision = "reject"
        elif max_score >= 0.3:
            decision = "needs_review"
        else:
            decision = "approve"
        
        result = {
            "content_id": content_id,
            "content_type": "image",
            "decision": decision,
            "confidence": round(1.0 - max_score, 2),
            "moderation_details": {
                "max_score": round(max_score, 2),
                "labels": moderation_result.get("labels", []),
                "model": moderation_result.get("model", "unknown"),
                "api_status": moderation_result.get("api_status", "unknown")
            },
            "user_id": user_id,
            "error": moderation_result.get("error")
        }
        
        return result
        
    except Exception as e:
        logger.error(f"Base64 image moderation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
