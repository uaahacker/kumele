"""
Taxonomy API endpoints.

Handles interest/hobby taxonomy management.

Core Principle (per requirements):
- Use interest_id EVERYWHERE (never hardcode labels in frontend)

DB Tables (owned by ML):
- interest_taxonomy: Hierarchical structure
- interest_metadata: icon_key, display_order, color_token
- interest_translations: Labels per language

API Pattern:
- GET /taxonomy/interests?updated_since=...
- Frontends sync taxonomy, cache locally, display translated labels

This is the SOURCE OF TRUTH for all hobby/interest IDs across the platform.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List
import logging
import uuid

from app.database import get_db
from app.schemas.schemas import TaxonomyResponse
from sqlalchemy import select, and_

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/taxonomy", tags=["Taxonomy"])


@router.get(
    "/interests",
    response_model=TaxonomyResponse,
    summary="Get Interest Taxonomy",
    description="""
    Get hierarchical interest/hobby taxonomy.
    
    Supports incremental sync with `updated_since` parameter.
    
    Returns:
    - Top-level categories
    - Nested subcategories
    - Interest items with IDs
    
    Use for:
    - User profile interest selection
    - Event categorization
    - Content tagging
    
    **Sync Pattern:**
    - First load: GET /taxonomy/interests (full)
    - Incremental: GET /taxonomy/interests?updated_since=2025-01-01T00:00:00
    
    **Cache Headers:**
    Response includes version info for caching.
    """
)
async def get_interests(
    parent_id: Optional[str] = Query(None, description="Parent category ID"),
    include_children: bool = Query(True, description="Include child categories"),
    updated_since: Optional[str] = Query(None, description="ISO timestamp for incremental sync"),
    language: str = Query("en", description="Language for labels"),
    db: AsyncSession = Depends(get_db)
):
    """Get interest taxonomy."""
    try:
        from app.models.database_models import InterestTaxonomy, InterestMetadata, InterestTranslation
        from datetime import datetime as dt
        
        # Parse updated_since if provided
        since_date = None
        if updated_since:
            try:
                since_date = dt.fromisoformat(updated_since.replace("Z", "+00:00"))
            except ValueError:
                pass
        
        # Build query based on parent_id
        # Model uses: interest_id (string), parent_id (string), level, is_active
        if parent_id:
            query = select(InterestTaxonomy).where(
                and_(
                    InterestTaxonomy.parent_id == parent_id,
                    InterestTaxonomy.is_active == True
                )
            )
        else:
            # Get top-level categories (where parent_id is None)
            query = select(InterestTaxonomy).where(
                and_(
                    InterestTaxonomy.parent_id.is_(None),
                    InterestTaxonomy.is_active == True
                )
            )
        
        # Filter by updated_since for incremental sync
        if since_date:
            query = query.where(InterestTaxonomy.updated_at >= since_date)
        
        result = await db.execute(query)
        items = result.scalars().all()
        
        # If no data in DB, return sample taxonomy
        if not items:
            return _get_sample_taxonomy(parent_id, include_children)
        
        async def build_tree(item):
            """Recursively build category tree."""
            # Get metadata for icon
            meta_query = select(InterestMetadata).where(
                InterestMetadata.interest_id == item.interest_id
            )
            meta_result = await db.execute(meta_query)
            metadata = meta_result.scalar_one_or_none()
            
            # Get translation for name (use requested language with fallback to en)
            trans_query = select(InterestTranslation).where(
                and_(
                    InterestTranslation.interest_id == item.interest_id,
                    InterestTranslation.language_code == language
                )
            )
            trans_result = await db.execute(trans_query)
            translation = trans_result.scalar_one_or_none()
            
            # Fallback to English if translation not found
            if not translation and language != "en":
                fallback_query = select(InterestTranslation).where(
                    and_(
                        InterestTranslation.interest_id == item.interest_id,
                        InterestTranslation.language_code == "en"
                    )
                )
                fallback_result = await db.execute(fallback_query)
                translation = fallback_result.scalar_one_or_none()
            
            node = {
                "id": item.interest_id,
                "name": translation.label if translation else item.interest_id.replace("_", " ").title(),
                "slug": item.interest_id,
                "icon": metadata.icon_key if metadata else "🎯",
                "level": item.level or 0,
                "updated_at": item.updated_at.isoformat() if item.updated_at else None
            }
            
            if include_children:
                children_query = select(InterestTaxonomy).where(
                    and_(
                        InterestTaxonomy.parent_id == item.interest_id,
                        InterestTaxonomy.is_active == True
                    )
                )
                
                children_result = await db.execute(children_query)
                children = children_result.scalars().all()
                
                if children:
                    node["children"] = [
                        await build_tree(child) for child in children
                    ]
            
            return node
        
        categories = [await build_tree(item) for item in items]
        
        # Calculate version hash for caching
        from datetime import datetime as dt
        latest_update = max(
            (item.updated_at for item in items if item.updated_at),
            default=dt.utcnow()
        )
        
        return {
            "categories": categories,
            "version": latest_update.isoformat() if latest_update else None,
            "language": language,
            "count": len(categories)
        }
        
    except Exception as e:
        logger.error(f"Get interests error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def _get_sample_taxonomy(parent_id: Optional[str], include_children: bool) -> dict:
    """Return sample taxonomy when DB is empty."""
    sample_categories = [
        {
            "id": "sports_fitness",
            "name": "Sports & Fitness",
            "slug": "sports-fitness",
            "icon": "🏃",
            "level": 0,
            "children": [
                {"id": "running", "name": "Running", "slug": "running", "icon": "🏃", "level": 1},
                {"id": "yoga", "name": "Yoga", "slug": "yoga", "icon": "🧘", "level": 1},
                {"id": "gym", "name": "Gym & Weights", "slug": "gym", "icon": "🏋️", "level": 1},
                {"id": "swimming", "name": "Swimming", "slug": "swimming", "icon": "🏊", "level": 1},
            ] if include_children else None
        },
        {
            "id": "arts_crafts",
            "name": "Arts & Crafts",
            "slug": "arts-crafts",
            "icon": "🎨",
            "level": 0,
            "children": [
                {"id": "painting", "name": "Painting", "slug": "painting", "icon": "🖌️", "level": 1},
                {"id": "pottery", "name": "Pottery", "slug": "pottery", "icon": "🏺", "level": 1},
                {"id": "photography", "name": "Photography", "slug": "photography", "icon": "📷", "level": 1},
            ] if include_children else None
        },
        {
            "id": "food_drink",
            "name": "Food & Drink",
            "slug": "food-drink",
            "icon": "🍳",
            "level": 0,
            "children": [
                {"id": "cooking", "name": "Cooking", "slug": "cooking", "icon": "👨‍🍳", "level": 1},
                {"id": "baking", "name": "Baking", "slug": "baking", "icon": "🧁", "level": 1},
                {"id": "wine_tasting", "name": "Wine Tasting", "slug": "wine-tasting", "icon": "🍷", "level": 1},
            ] if include_children else None
        },
        {
            "id": "music",
            "name": "Music",
            "slug": "music",
            "icon": "🎵",
            "level": 0,
            "children": [
                {"id": "guitar", "name": "Guitar", "slug": "guitar", "icon": "🎸", "level": 1},
                {"id": "piano", "name": "Piano", "slug": "piano", "icon": "🎹", "level": 1},
                {"id": "singing", "name": "Singing", "slug": "singing", "icon": "🎤", "level": 1},
            ] if include_children else None
        },
        {
            "id": "tech",
            "name": "Technology",
            "slug": "tech",
            "icon": "💻",
            "level": 0,
            "children": [
                {"id": "coding", "name": "Coding", "slug": "coding", "icon": "👨‍💻", "level": 1},
                {"id": "gaming", "name": "Gaming", "slug": "gaming", "icon": "🎮", "level": 1},
                {"id": "ai_ml", "name": "AI & Machine Learning", "slug": "ai-ml", "icon": "🤖", "level": 1},
            ] if include_children else None
        },
        {
            "id": "outdoor",
            "name": "Outdoor Activities",
            "slug": "outdoor",
            "icon": "🏕️",
            "level": 0,
            "children": [
                {"id": "hiking", "name": "Hiking", "slug": "hiking", "icon": "🥾", "level": 1},
                {"id": "camping", "name": "Camping", "slug": "camping", "icon": "⛺", "level": 1},
                {"id": "cycling", "name": "Cycling", "slug": "cycling", "icon": "🚴", "level": 1},
            ] if include_children else None
        },
    ]
    
    # Filter by parent_id if provided
    if parent_id:
        for cat in sample_categories:
            if cat["id"] == parent_id:
                return {"categories": cat.get("children", [])}
        return {"categories": []}
    
    # Clean up None children
    for cat in sample_categories:
        if cat.get("children") is None:
            del cat["children"]
    
    return {"categories": sample_categories}


@router.get(
    "/interests/flat",
    summary="Get Flat Interest List",
    description="Get all interests as a flat list (no hierarchy)."
)
async def get_interests_flat(
    level: Optional[int] = Query(None, description="Filter by level"),
    search: Optional[str] = Query(None, description="Search by name"),
    db: AsyncSession = Depends(get_db)
):
    """Get flat interest list."""
    try:
        from app.models.database_models import InterestTaxonomy, InterestTranslation
        
        query = select(InterestTaxonomy).where(InterestTaxonomy.is_active == True)
        
        if level is not None:
            query = query.where(InterestTaxonomy.level == level)
        
        # Note: search by interest_id since name is in translations table
        if search:
            query = query.where(
                InterestTaxonomy.interest_id.ilike(f"%{search}%")
            )
        
        query = query.order_by(InterestTaxonomy.level, InterestTaxonomy.interest_id)
        
        result = await db.execute(query)
        items = result.scalars().all()
        
        # If no data, return sample flat list
        if not items:
            return _get_sample_flat_interests(level, search)
        
        interests = []
        for item in items:
            # Get translation for display name
            trans_query = select(InterestTranslation).where(
                and_(
                    InterestTranslation.interest_id == item.interest_id,
                    InterestTranslation.language_code == "en"
                )
            )
            trans_result = await db.execute(trans_query)
            translation = trans_result.scalar_one_or_none()
            
            interests.append({
                "id": item.interest_id,
                "name": translation.label if translation else item.interest_id.replace("_", " ").title(),
                "slug": item.interest_id,
                "icon": "🎯",  # Default icon
                "level": item.level or 0,
                "parent_id": item.parent_id
            })
        
        return {"interests": interests}
        
    except Exception as e:
        logger.error(f"Get interests flat error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def _get_sample_flat_interests(level: Optional[int], search: Optional[str]) -> dict:
    """Return sample flat interests when DB is empty."""
    all_interests = [
        {"id": "sports_fitness", "name": "Sports & Fitness", "slug": "sports-fitness", "icon": "🏃", "level": 0, "parent_id": None},
        {"id": "running", "name": "Running", "slug": "running", "icon": "🏃", "level": 1, "parent_id": "sports_fitness"},
        {"id": "yoga", "name": "Yoga", "slug": "yoga", "icon": "🧘", "level": 1, "parent_id": "sports_fitness"},
        {"id": "gym", "name": "Gym & Weights", "slug": "gym", "icon": "🏋️", "level": 1, "parent_id": "sports_fitness"},
        {"id": "arts_crafts", "name": "Arts & Crafts", "slug": "arts-crafts", "icon": "🎨", "level": 0, "parent_id": None},
        {"id": "painting", "name": "Painting", "slug": "painting", "icon": "🖌️", "level": 1, "parent_id": "arts_crafts"},
        {"id": "photography", "name": "Photography", "slug": "photography", "icon": "📷", "level": 1, "parent_id": "arts_crafts"},
        {"id": "food_drink", "name": "Food & Drink", "slug": "food-drink", "icon": "🍳", "level": 0, "parent_id": None},
        {"id": "cooking", "name": "Cooking", "slug": "cooking", "icon": "👨‍🍳", "level": 1, "parent_id": "food_drink"},
        {"id": "baking", "name": "Baking", "slug": "baking", "icon": "🧁", "level": 1, "parent_id": "food_drink"},
        {"id": "music", "name": "Music", "slug": "music", "icon": "🎵", "level": 0, "parent_id": None},
        {"id": "guitar", "name": "Guitar", "slug": "guitar", "icon": "🎸", "level": 1, "parent_id": "music"},
        {"id": "tech", "name": "Technology", "slug": "tech", "icon": "💻", "level": 0, "parent_id": None},
        {"id": "coding", "name": "Coding", "slug": "coding", "icon": "👨‍💻", "level": 1, "parent_id": "tech"},
        {"id": "outdoor", "name": "Outdoor Activities", "slug": "outdoor", "icon": "🏕️", "level": 0, "parent_id": None},
        {"id": "hiking", "name": "Hiking", "slug": "hiking", "icon": "🥾", "level": 1, "parent_id": "outdoor"},
    ]
    
    filtered = all_interests
    
    if level is not None:
        filtered = [i for i in filtered if i["level"] == level]
    
    if search:
        search_lower = search.lower()
        filtered = [i for i in filtered if search_lower in i["name"].lower() or search_lower in i["id"].lower()]
    
    return {"interests": filtered}


@router.get(
    "/interests/{interest_id}",
    summary="Get Interest Details",
    description="Get details of a specific interest."
)
async def get_interest(
    interest_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Get interest details."""
    try:
        from app.models.database_models import InterestTaxonomy, InterestTranslation, InterestMetadata
        
        query = select(InterestTaxonomy).where(
            InterestTaxonomy.interest_id == interest_id
        )
        
        result = await db.execute(query)
        interest = result.scalar_one_or_none()
        
        if not interest:
            # Return sample interest if not found
            return _get_sample_interest_details(interest_id)
        
        # Get translation for name
        trans_query = select(InterestTranslation).where(
            and_(
                InterestTranslation.interest_id == interest_id,
                InterestTranslation.language_code == "en"
            )
        )
        trans_result = await db.execute(trans_query)
        translation = trans_result.scalar_one_or_none()
        
        # Get metadata for icon
        meta_query = select(InterestMetadata).where(
            InterestMetadata.interest_id == interest_id
        )
        meta_result = await db.execute(meta_query)
        metadata = meta_result.scalar_one_or_none()
        
        # Get parent
        parent = None
        if interest.parent_id:
            parent_query = select(InterestTaxonomy).where(
                InterestTaxonomy.interest_id == interest.parent_id
            )
            parent_result = await db.execute(parent_query)
            parent_item = parent_result.scalar_one_or_none()
            if parent_item:
                parent = {
                    "id": parent_item.interest_id,
                    "name": parent_item.interest_id.replace("_", " ").title()
                }
        
        # Get children
        children_query = select(InterestTaxonomy).where(
            InterestTaxonomy.parent_id == interest_id
        )
        
        children_result = await db.execute(children_query)
        children = [
            {
                "id": c.interest_id,
                "name": c.interest_id.replace("_", " ").title(),
                "slug": c.interest_id
            }
            for c in children_result.scalars().all()
        ]
        
        return {
            "id": interest.interest_id,
            "name": translation.label if translation else interest.interest_id.replace("_", " ").title(),
            "slug": interest.interest_id,
            "icon": metadata.icon_key if metadata else "🎯",
            "level": interest.level or 0,
            "parent": parent,
            "children": children
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get interest error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def _get_sample_interest_details(interest_id: str) -> dict:
    """Return sample interest details."""
    sample_map = {
        "sports_fitness": {"name": "Sports & Fitness", "icon": "🏃", "level": 0, "parent": None, "children": ["running", "yoga", "gym"]},
        "running": {"name": "Running", "icon": "🏃", "level": 1, "parent": "sports_fitness", "children": []},
        "yoga": {"name": "Yoga", "icon": "🧘", "level": 1, "parent": "sports_fitness", "children": []},
        "cooking": {"name": "Cooking", "icon": "👨‍🍳", "level": 1, "parent": "food_drink", "children": []},
        "food_drink": {"name": "Food & Drink", "icon": "🍳", "level": 0, "parent": None, "children": ["cooking", "baking"]},
    }
    
    if interest_id in sample_map:
        data = sample_map[interest_id]
        return {
            "id": interest_id,
            "name": data["name"],
            "slug": interest_id,
            "icon": data["icon"],
            "level": data["level"],
            "parent": {"id": data["parent"], "name": sample_map.get(data["parent"], {}).get("name", "")} if data["parent"] else None,
            "children": [{"id": c, "name": sample_map.get(c, {}).get("name", c), "slug": c} for c in data["children"]]
        }
    
    raise HTTPException(status_code=404, detail=f"Interest '{interest_id}' not found")


@router.post(
    "/interests",
    summary="Create Interest",
    description="Create a new interest category (admin use)."
)
async def create_interest(
    name: str = Query(..., description="Interest name"),
    slug: str = Query(..., description="URL-friendly slug"),
    parent_id: Optional[str] = Query(None, description="Parent category ID"),
    icon: Optional[str] = Query(None, description="Icon name/URL"),
    sort_order: int = Query(0, description="Sort order"),
    db: AsyncSession = Depends(get_db)
):
    """Create interest."""
    try:
        from app.models.database_models import InterestTaxonomy
        
        # Determine level
        level = 0
        parent_uuid = None
        
        if parent_id:
            parent_uuid = uuid.UUID(parent_id)
            parent_query = select(InterestTaxonomy).where(
                InterestTaxonomy.id == parent_uuid
            )
            parent_result = await db.execute(parent_query)
            parent = parent_result.scalar_one_or_none()
            
            if parent:
                level = parent.level + 1
            else:
                raise HTTPException(status_code=404, detail="Parent not found")
        
        interest = InterestTaxonomy(
            name=name,
            slug=slug,
            parent_id=parent_uuid,
            icon=icon,
            level=level,
            sort_order=sort_order
        )
        
        db.add(interest)
        await db.commit()
        
        return {
            "success": True,
            "id": str(interest.id),
            "name": interest.name
        }
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Create interest error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
