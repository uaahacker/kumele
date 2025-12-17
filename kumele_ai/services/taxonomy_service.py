"""
Taxonomy Service - Manages the canonical interest/hobby taxonomy (ML-owned)

The taxonomy is the single source of truth for interests across:
- UI (Swift, Flutter, Next.js)
- ML models (recommendations, ads, clustering)
- NLP & embeddings
- Analytics & reporting
"""
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import and_

from kumele_ai.db.models import InterestTaxonomy, InterestTranslation, Hobby
from kumele_ai.services.embed_service import embed_service

logger = logging.getLogger(__name__)


class TaxonomyService:
    """
    Service for managing the canonical interest taxonomy.
    
    Key principles:
    - Interest IDs, not strings, drive the system
    - Frontend displays: label + icon
    - ML consumes: interest_id
    - Translations, grouping, and embeddings are derived, not duplicated
    """
    
    def get_interests(
        self,
        db: Session,
        updated_since: Optional[datetime] = None,
        include_inactive: bool = False,
        language: str = "en"
    ) -> List[Dict[str, Any]]:
        """
        Get interests from taxonomy, optionally filtered by update time.
        
        Args:
            db: Database session
            updated_since: Only return interests updated after this timestamp
            include_inactive: Include deprecated/inactive interests
            language: Language code for translations
            
        Returns:
            List of interests with metadata and translations
        """
        query = db.query(InterestTaxonomy)
        
        if not include_inactive:
            query = query.filter(InterestTaxonomy.is_active == True)
        
        if updated_since:
            query = query.filter(InterestTaxonomy.updated_at > updated_since)
        
        interests = query.order_by(InterestTaxonomy.display_order).all()
        
        result = []
        for interest in interests:
            # Get translation for requested language
            translation = db.query(InterestTranslation).filter(
                and_(
                    InterestTranslation.interest_id == interest.interest_id,
                    InterestTranslation.language == language
                )
            ).first()
            
            # Fall back to English if translation not found
            if not translation and language != "en":
                translation = db.query(InterestTranslation).filter(
                    and_(
                        InterestTranslation.interest_id == interest.interest_id,
                        InterestTranslation.language == "en"
                    )
                ).first()
            
            result.append({
                "interest_id": interest.interest_id,
                "name": interest.name,
                "category": interest.category,
                "parent_id": interest.parent_id,
                "icon_key": interest.icon_key,
                "color_token": interest.color_token,
                "display_order": interest.display_order,
                "is_active": interest.is_active,
                "label": translation.label if translation else interest.name,
                "description": translation.description if translation else None,
                "updated_at": interest.updated_at.isoformat() if interest.updated_at else None
            })
        
        return result
    
    def get_interest_by_id(
        self,
        db: Session,
        interest_id: int,
        language: str = "en"
    ) -> Optional[Dict[str, Any]]:
        """Get single interest by ID"""
        interest = db.query(InterestTaxonomy).filter(
            InterestTaxonomy.interest_id == interest_id
        ).first()
        
        if not interest:
            return None
        
        translation = db.query(InterestTranslation).filter(
            and_(
                InterestTranslation.interest_id == interest_id,
                InterestTranslation.language == language
            )
        ).first()
        
        return {
            "interest_id": interest.interest_id,
            "name": interest.name,
            "category": interest.category,
            "parent_id": interest.parent_id,
            "icon_key": interest.icon_key,
            "color_token": interest.color_token,
            "display_order": interest.display_order,
            "is_active": interest.is_active,
            "label": translation.label if translation else interest.name,
            "description": translation.description if translation else None,
            "updated_at": interest.updated_at.isoformat() if interest.updated_at else None
        }
    
    def create_interest(
        self,
        db: Session,
        name: str,
        category: Optional[str] = None,
        parent_id: Optional[int] = None,
        icon_key: Optional[str] = None,
        color_token: Optional[str] = None,
        display_order: int = 0,
        translations: Optional[Dict[str, Dict[str, str]]] = None
    ) -> Dict[str, Any]:
        """
        Create a new interest in the taxonomy.
        
        Args:
            db: Database session
            name: Interest name (canonical key)
            category: Category grouping
            parent_id: Parent interest ID for hierarchy
            icon_key: Icon reference key
            color_token: Color token for UI
            display_order: Sort order
            translations: Dict of language -> {label, description}
            
        Returns:
            Created interest data
        """
        try:
            # Generate embedding for the interest
            embedding = None
            try:
                embedding = embed_service.embed_text(name)
            except Exception as e:
                logger.warning(f"Could not generate embedding for interest: {e}")
            
            # Create interest
            interest = InterestTaxonomy(
                name=name,
                category=category,
                parent_id=parent_id,
                icon_key=icon_key,
                color_token=color_token,
                display_order=display_order,
                is_active=True,
                embedding_vector=embedding,
                updated_at=datetime.utcnow()
            )
            db.add(interest)
            db.flush()  # Get the ID
            
            # Add translations
            if translations:
                for lang, trans_data in translations.items():
                    translation = InterestTranslation(
                        interest_id=interest.interest_id,
                        language=lang,
                        label=trans_data.get("label", name),
                        description=trans_data.get("description")
                    )
                    db.add(translation)
            
            # Always add English translation if not provided
            if not translations or "en" not in translations:
                en_translation = InterestTranslation(
                    interest_id=interest.interest_id,
                    language="en",
                    label=name,
                    description=None
                )
                db.add(en_translation)
            
            db.commit()
            
            return {
                "success": True,
                "interest_id": interest.interest_id,
                "name": name
            }
            
        except Exception as e:
            db.rollback()
            logger.error(f"Error creating interest: {e}")
            return {"success": False, "error": str(e)}
    
    def update_interest(
        self,
        db: Session,
        interest_id: int,
        updates: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Update an existing interest"""
        interest = db.query(InterestTaxonomy).filter(
            InterestTaxonomy.interest_id == interest_id
        ).first()
        
        if not interest:
            return {"success": False, "error": "Interest not found"}
        
        try:
            # Update allowed fields
            allowed_fields = ["category", "parent_id", "icon_key", "color_token", "display_order", "is_active"]
            for field in allowed_fields:
                if field in updates:
                    setattr(interest, field, updates[field])
            
            interest.updated_at = datetime.utcnow()
            db.commit()
            
            return {"success": True, "interest_id": interest_id}
            
        except Exception as e:
            db.rollback()
            logger.error(f"Error updating interest: {e}")
            return {"success": False, "error": str(e)}
    
    def deprecate_interest(
        self,
        db: Session,
        interest_id: int
    ) -> Dict[str, Any]:
        """
        Deprecate an interest (set is_active = false).
        
        UI hides it, ML keeps historical data, no breaking analytics.
        """
        return self.update_interest(db, interest_id, {"is_active": False})
    
    def sync_from_hobbies(self, db: Session) -> Dict[str, Any]:
        """
        Sync interests from existing hobbies table.
        
        This is a one-time migration helper to populate taxonomy from hobbies.
        """
        hobbies = db.query(Hobby).all()
        
        created = 0
        skipped = 0
        
        for hobby in hobbies:
            # Check if already exists
            existing = db.query(InterestTaxonomy).filter(
                InterestTaxonomy.name == hobby.name
            ).first()
            
            if existing:
                skipped += 1
                continue
            
            result = self.create_interest(
                db=db,
                name=hobby.name,
                category=hobby.category,
                translations={"en": {"label": hobby.name, "description": hobby.description}}
            )
            
            if result.get("success"):
                created += 1
        
        return {
            "created": created,
            "skipped": skipped,
            "total_hobbies": len(hobbies)
        }
    
    def get_categories(self, db: Session) -> List[str]:
        """Get all unique categories"""
        categories = db.query(InterestTaxonomy.category).filter(
            InterestTaxonomy.is_active == True,
            InterestTaxonomy.category.isnot(None)
        ).distinct().all()
        
        return [c[0] for c in categories if c[0]]


# Singleton instance
taxonomy_service = TaxonomyService()
