"""
Taxonomy API endpoints.
Handles interest/hobby taxonomy management.
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
    
    Returns:
    - Top-level categories
    - Nested subcategories
    - Interest items with IDs
    
    Use for:
    - User profile interest selection
    - Event categorization
    - Content tagging
    """
)
async def get_interests(
    parent_id: Optional[str] = Query(None, description="Parent category ID"),
    include_children: bool = Query(True, description="Include child categories"),
    db: AsyncSession = Depends(get_db)
):
    """Get interest taxonomy."""
    try:
        from app.models.database_models import InterestTaxonomy
        
        if parent_id:
            parent_uuid = uuid.UUID(parent_id)
            query = select(InterestTaxonomy).where(
                InterestTaxonomy.parent_id == parent_uuid
            ).order_by(InterestTaxonomy.sort_order)
        else:
            # Get top-level categories
            query = select(InterestTaxonomy).where(
                InterestTaxonomy.parent_id.is_(None)
            ).order_by(InterestTaxonomy.sort_order)
        
        result = await db.execute(query)
        items = result.scalars().all()
        
        async def build_tree(item):
            """Recursively build category tree."""
            node = {
                "id": str(item.id),
                "name": item.name,
                "slug": item.slug,
                "icon": item.icon,
                "level": item.level
            }
            
            if include_children:
                children_query = select(InterestTaxonomy).where(
                    InterestTaxonomy.parent_id == item.id
                ).order_by(InterestTaxonomy.sort_order)
                
                children_result = await db.execute(children_query)
                children = children_result.scalars().all()
                
                if children:
                    node["children"] = [
                        await build_tree(child) for child in children
                    ]
            
            return node
        
        categories = [await build_tree(item) for item in items]
        
        return {
            "categories": categories
        }
        
    except Exception as e:
        logger.error(f"Get interests error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


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
        from app.models.database_models import InterestTaxonomy
        
        query = select(InterestTaxonomy)
        
        if level is not None:
            query = query.where(InterestTaxonomy.level == level)
        
        if search:
            query = query.where(
                InterestTaxonomy.name.ilike(f"%{search}%")
            )
        
        query = query.order_by(InterestTaxonomy.level, InterestTaxonomy.name)
        
        result = await db.execute(query)
        items = result.scalars().all()
        
        return {
            "interests": [
                {
                    "id": str(item.id),
                    "name": item.name,
                    "slug": item.slug,
                    "icon": item.icon,
                    "level": item.level,
                    "parent_id": str(item.parent_id) if item.parent_id else None
                }
                for item in items
            ]
        }
        
    except Exception as e:
        logger.error(f"Get interests flat error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


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
        from app.models.database_models import InterestTaxonomy
        
        interest_uuid = uuid.UUID(interest_id)
        
        query = select(InterestTaxonomy).where(
            InterestTaxonomy.id == interest_uuid
        )
        
        result = await db.execute(query)
        interest = result.scalar_one_or_none()
        
        if not interest:
            raise HTTPException(status_code=404, detail="Interest not found")
        
        # Get parent
        parent = None
        if interest.parent_id:
            parent_query = select(InterestTaxonomy).where(
                InterestTaxonomy.id == interest.parent_id
            )
            parent_result = await db.execute(parent_query)
            parent_item = parent_result.scalar_one_or_none()
            if parent_item:
                parent = {
                    "id": str(parent_item.id),
                    "name": parent_item.name
                }
        
        # Get children
        children_query = select(InterestTaxonomy).where(
            InterestTaxonomy.parent_id == interest_uuid
        ).order_by(InterestTaxonomy.sort_order)
        
        children_result = await db.execute(children_query)
        children = [
            {
                "id": str(c.id),
                "name": c.name,
                "slug": c.slug
            }
            for c in children_result.scalars().all()
        ]
        
        return {
            "id": str(interest.id),
            "name": interest.name,
            "slug": interest.slug,
            "icon": interest.icon,
            "level": interest.level,
            "parent": parent,
            "children": children
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get interest error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


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
