"""
Moderation Router - Content moderation endpoints
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional, List
from sqlalchemy.orm import Session

from kumele_ai.dependencies import get_db
from kumele_ai.services.moderation_service import moderation_service

router = APIRouter()


class TextModerationRequest(BaseModel):
    content_type: str = "text"
    text: str
    subtype: Optional[str] = None
    content_id: Optional[str] = None


class ImageModerationRequest(BaseModel):
    content_type: str = "image"
    image_url: str
    subtype: Optional[str] = None
    content_id: Optional[str] = None


class VideoModerationRequest(BaseModel):
    content_type: str = "video"
    video_url: str
    thumbnail_url: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    content_id: Optional[str] = None


class ModerationRequest(BaseModel):
    content_type: str  # text, image, video
    text: Optional[str] = None
    image_url: Optional[str] = None
    video_url: Optional[str] = None
    thumbnail_url: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    subtype: Optional[str] = None
    content_id: Optional[str] = None


@router.post("")
async def moderate_content(
    request: ModerationRequest,
    db: Session = Depends(get_db)
):
    """
    Unified moderation endpoint for text/image/video.
    
    Workflow:
    1. Upload content → POST /moderation
    2. Process based on content_type:
       - text: NLP moderation model(s)
       - image: Vision moderation model
       - video: Thumbnail + text moderation ONLY (MVP)
    
    Decision thresholds:
    - Text: Toxicity reject >0.60, Hate reject >0.30, Spam reject >0.70
    - Image: Nudity reject >0.60, Violence reject >0.50, Hate symbols reject >0.40
    
    Outcomes: approve | reject | needs_review
    
    Video MVP limitations:
    - ONLY thumbnail/keyframe + associated text
    - NO frame-by-frame video analysis
    - NO audio transcription
    - NO long-form video moderation
    """
    if request.content_type == "text":
        if not request.text:
            raise HTTPException(status_code=400, detail="Text required for text moderation")
        
        result = moderation_service.moderate_text(
            db=db,
            text=request.text,
            subtype=request.subtype,
            content_id=request.content_id
        )
        
    elif request.content_type == "image":
        if not request.image_url:
            raise HTTPException(status_code=400, detail="Image URL required for image moderation")
        
        result = moderation_service.moderate_image(
            db=db,
            image_url=request.image_url,
            subtype=request.subtype,
            content_id=request.content_id
        )
        
    elif request.content_type == "video":
        if not request.video_url:
            raise HTTPException(status_code=400, detail="Video URL required for video moderation")
        
        # Video moderation requires thumbnail
        if not request.thumbnail_url:
            raise HTTPException(
                status_code=400, 
                detail="Thumbnail URL required for video moderation (MVP limitation)"
            )
        
        result = moderation_service.moderate_video(
            db=db,
            video_url=request.video_url,
            thumbnail_url=request.thumbnail_url,
            title=request.title,
            description=request.description,
            content_id=request.content_id
        )
        
    else:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid content_type: {request.content_type}. Must be text, image, or video"
        )
    
    return result


@router.get("/{content_id}")
async def get_moderation_status(
    content_id: str,
    db: Session = Depends(get_db)
):
    """
    Get moderation status and decision for content.
    
    Returns:
    - status: pending | processing | completed
    - decision: approve | reject | needs_review
    - labels: Detailed moderation labels
    """
    result = moderation_service.get_moderation_status(db, content_id)
    
    if not result:
        raise HTTPException(status_code=404, detail="Content not found")
    
    return result
