"""
Ads Router - Ad intelligence endpoints
"""
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from typing import Optional, List
from sqlalchemy.orm import Session

from kumele_ai.dependencies import get_db
from kumele_ai.services.ads_service import ads_service

router = APIRouter()


class AudienceMatchRequest(BaseModel):
    title: str
    description: str
    image_tags: Optional[List[str]] = None
    target_hobby: Optional[str] = None
    target_location: Optional[str] = None


class PerformancePredictRequest(BaseModel):
    title: str
    description: str
    image_tags: Optional[List[str]] = None
    target_hobby: Optional[str] = None
    budget: float = 100.0


@router.get("/audience-match")
async def match_audience(
    title: str = Query(..., description="Ad title"),
    description: str = Query(..., description="Ad description"),
    image_tags: Optional[str] = Query(None, description="Comma-separated image tags"),
    target_hobby: Optional[str] = Query(None, description="Target hobby"),
    target_location: Optional[str] = Query(None, description="Target location"),
    db: Session = Depends(get_db)
):
    """
    Match ad to relevant audience segments.
    
    Logic:
    - HF embeddings extract hobbies/themes from text/images
    - Cluster users by hobbies/location/age/engagement
    - Rank segments by similarity score
    
    Returns:
    - extracted_themes: Detected themes from ad content
    - matched_hobbies: Relevant hobbies by similarity
    - audience_segments: Ranked user segments with reach estimates
    """
    tags = image_tags.split(",") if image_tags else None
    
    result = ads_service.match_audience(
        db=db,
        title=title,
        description=description,
        image_tags=tags,
        target_hobby=target_hobby,
        target_location=target_location
    )
    
    return result


@router.get("/performance-predict")
async def predict_performance(
    title: str = Query(..., description="Ad title"),
    description: str = Query(..., description="Ad description"),
    image_tags: Optional[str] = Query(None, description="Comma-separated image tags"),
    target_hobby: Optional[str] = Query(None, description="Target hobby"),
    budget: float = Query(100.0, description="Ad budget"),
    db: Session = Depends(get_db)
):
    """
    Predict CTR and engagement before ad goes live.
    
    Analysis includes:
    - Text clarity and sentiment (HF)
    - Image embeddings relevance
    - Historical ad/event performance regression
    
    Returns:
    - predicted_ctr: Expected click-through rate
    - optimization_tips: Suggestions for improvement
    """
    tags = image_tags.split(",") if image_tags else None
    
    result = ads_service.predict_performance(
        db=db,
        title=title,
        description=description,
        image_tags=tags,
        target_hobby=target_hobby,
        budget=budget
    )
    
    return result
