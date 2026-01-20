"""
Taxonomy API Router - Manages canonical interest/hobby taxonomy

Endpoints:
- GET /taxonomy/interests - Fetch interests, optionally filtered by updated_since
"""
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from typing import Optional, List, Dict, Any
from datetime import datetime
from pydantic import BaseModel

from kumele_ai.db.database import get_db
from kumele_ai.services.taxonomy_service import taxonomy_service

router = APIRouter(prefix="/taxonomy", tags=["Taxonomy"])


class InterestResponse(BaseModel):
    """Response model for interest data"""
    interest_id: int
    name: str
    category: Optional[str] = None
    parent_id: Optional[int] = None
    icon_key: Optional[str] = None
    color_token: Optional[str] = None
    display_order: int = 0
    is_active: bool = True
    label: str
    description: Optional[str] = None
    updated_at: Optional[str] = None


class InterestsListResponse(BaseModel):
    """Response model for interests list"""
    interests: List[InterestResponse]
    count: int
    updated_since: Optional[str] = None


class CreateInterestRequest(BaseModel):
    """Request model for creating an interest"""
    name: str
    category: Optional[str] = None
    parent_id: Optional[int] = None
    icon_key: Optional[str] = None
    color_token: Optional[str] = None
    display_order: int = 0
    translations: Optional[Dict[str, Dict[str, str]]] = None


class UpdateInterestRequest(BaseModel):
    """Request model for updating an interest"""
    category: Optional[str] = None
    parent_id: Optional[int] = None
    icon_key: Optional[str] = None
    color_token: Optional[str] = None
    display_order: Optional[int] = None
    is_active: Optional[bool] = None


@router.get("/interests", response_model=InterestsListResponse)
async def get_interests(
    updated_since: Optional[str] = Query(
        None,
        description="ISO 8601 timestamp - only return interests updated after this time"
    ),
    include_inactive: bool = Query(
        False,
        description="Include deprecated/inactive interests"
    ),
    language: str = Query(
        "en",
        description="Language code for translations"
    ),
    db: Session = Depends(get_db)
) -> InterestsListResponse:
    """
    Get interests from the canonical taxonomy.
    
    This endpoint is the single source of truth for interests across all UIs
    (Swift, Flutter, Next.js) and ML systems.
    
    Query Parameters:
    - **updated_since**: ISO 8601 timestamp to filter for recently updated interests.
      Use this for incremental syncs.
    - **include_inactive**: Set to true to include deprecated interests
    - **language**: Language code (en, fr, etc.) for translated labels
    
    Returns:
    - interest_id: Unique identifier (use this in ML, not names)
    - name: Canonical name (internal key)
    - label: Translated display name for UI
    - category: Grouping category
    - icon_key: Reference to icon asset
    - color_token: Design system color token
    - updated_at: Last modification timestamp
    """
    # Parse updated_since if provided
    updated_since_dt = None
    if updated_since:
        try:
            updated_since_dt = datetime.fromisoformat(updated_since.replace("Z", "+00:00"))
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="Invalid timestamp format. Use ISO 8601 (e.g., 2024-01-15T10:30:00Z)"
            )
    
    interests = taxonomy_service.get_interests(
        db=db,
        updated_since=updated_since_dt,
        include_inactive=include_inactive,
        language=language
    )
    
    return InterestsListResponse(
        interests=interests,
        count=len(interests),
        updated_since=updated_since
    )


@router.get("/interests/{interest_id}", response_model=InterestResponse)
async def get_interest(
    interest_id: int,
    language: str = Query("en", description="Language code for translations"),
    db: Session = Depends(get_db)
) -> InterestResponse:
    """
    Get a single interest by ID.
    
    Path Parameters:
    - **interest_id**: The unique interest identifier
    
    Query Parameters:
    - **language**: Language code for translated label
    """
    interest = taxonomy_service.get_interest_by_id(
        db=db,
        interest_id=interest_id,
        language=language
    )
    
    if not interest:
        raise HTTPException(status_code=404, detail="Interest not found")
    
    return interest


@router.post("/interests")
async def create_interest(
    request: CreateInterestRequest,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Create a new interest in the taxonomy.
    
    Request Body:
    - **name**: Canonical name (unique key)
    - **category**: Optional grouping category
    - **parent_id**: Optional parent interest for hierarchy
    - **icon_key**: Optional icon reference
    - **color_token**: Optional color token
    - **display_order**: Sort order (default 0)
    - **translations**: Optional dict of language -> {label, description}
    
    Example translations:
    ```json
    {
      "en": {"label": "Photography", "description": "The art of taking photos"},
      "fr": {"label": "Photographie", "description": "L'art de prendre des photos"}
    }
    ```
    """
    result = taxonomy_service.create_interest(
        db=db,
        name=request.name,
        category=request.category,
        parent_id=request.parent_id,
        icon_key=request.icon_key,
        color_token=request.color_token,
        display_order=request.display_order,
        translations=request.translations
    )
    
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "Failed to create interest"))
    
    return result


@router.patch("/interests/{interest_id}")
async def update_interest(
    interest_id: int,
    request: UpdateInterestRequest,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Update an existing interest.
    
    Path Parameters:
    - **interest_id**: The interest to update
    
    Request Body (all optional):
    - **category**: New category
    - **icon_key**: New icon reference
    - **color_token**: New color token
    - **display_order**: New sort order
    - **is_active**: Set to false to deprecate
    """
    updates = request.dict(exclude_none=True)
    
    result = taxonomy_service.update_interest(
        db=db,
        interest_id=interest_id,
        updates=updates
    )
    
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "Failed to update interest"))
    
    return result


@router.delete("/interests/{interest_id}")
async def deprecate_interest(
    interest_id: int,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Deprecate an interest (soft delete).
    
    This sets is_active = false, which:
    - Hides the interest from UI
    - Keeps historical data intact for ML
    - Preserves analytics continuity
    
    Path Parameters:
    - **interest_id**: The interest to deprecate
    """
    result = taxonomy_service.deprecate_interest(db, interest_id)
    
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "Failed to deprecate interest"))
    
    return {"success": True, "message": "Interest deprecated"}


@router.get("/categories")
async def get_categories(
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get all unique interest categories.
    
    Returns a list of category names for filtering/grouping.
    """
    categories = taxonomy_service.get_categories(db)
    return {
        "categories": categories,
        "count": len(categories)
    }


@router.post("/sync-from-hobbies")
async def sync_from_hobbies(
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    One-time migration: sync interests from existing hobbies table.
    
    This populates the interest_taxonomy table from the legacy hobbies table.
    Safe to run multiple times - skips existing entries.
    """
    result = taxonomy_service.sync_from_hobbies(db)
    return result
