"""
i18n Service - Internationalization with lazy loading by scope

Supports lazy-loaded translations:
- Frontend requests only what it needs (scope-based)
- Only approved translations are served
- Reduces bundle size and improves performance
"""
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import and_

from kumele_ai.db.models import I18nScope, I18nString

logger = logging.getLogger(__name__)


class I18nService:
    """
    Service for managing internationalized strings with lazy loading.
    
    Key concepts:
    - Scopes: Logical groupings (common, events, profile, etc.)
    - Strings: Key-value pairs within scopes
    - Approval: Only reviewed translations are served to production
    """
    
    # Common scopes that align with frontend modules
    COMMON_SCOPES = [
        "common",       # Shared UI elements, buttons, errors
        "events",       # Event-related strings
        "profile",      # User profile strings
        "auth",         # Authentication strings
        "settings",     # Settings/preferences strings
        "chat",         # Chat/messaging strings
        "ads",          # Advertisement strings
        "moderation",   # Content moderation strings
    ]
    
    def get_strings_by_scope(
        self,
        db: Session,
        language: str,
        scope: str,
        include_unapproved: bool = False
    ) -> Dict[str, str]:
        """
        Get all strings for a language and scope.
        
        This is the main endpoint for frontend lazy loading.
        
        Args:
            db: Database session
            language: Language code (en, fr, etc.)
            scope: Scope name (common, events, etc.)
            include_unapproved: Include unapproved translations (for admin/preview)
            
        Returns:
            Dict of string_key -> translated_value
        """
        # Get scope ID
        scope_obj = db.query(I18nScope).filter(I18nScope.name == scope).first()
        
        if not scope_obj:
            logger.warning(f"Scope not found: {scope}")
            return {}
        
        # Build query
        query = db.query(I18nString).filter(
            and_(
                I18nString.scope_id == scope_obj.id,
                I18nString.language == language
            )
        )
        
        if not include_unapproved:
            query = query.filter(I18nString.is_approved == True)
        
        strings = query.all()
        
        return {s.key: s.value for s in strings}
    
    def get_multiple_scopes(
        self,
        db: Session,
        language: str,
        scopes: List[str],
        include_unapproved: bool = False
    ) -> Dict[str, Dict[str, str]]:
        """
        Get strings for multiple scopes at once.
        
        Useful for initial app load.
        
        Args:
            db: Database session
            language: Language code
            scopes: List of scope names
            include_unapproved: Include unapproved translations
            
        Returns:
            Dict of scope_name -> {string_key: translated_value}
        """
        result = {}
        for scope in scopes:
            result[scope] = self.get_strings_by_scope(
                db, language, scope, include_unapproved
            )
        return result
    
    def get_string(
        self,
        db: Session,
        language: str,
        scope: str,
        key: str,
        fallback_language: str = "en"
    ) -> Optional[str]:
        """
        Get a single string by scope and key.
        
        Falls back to fallback_language if not found.
        """
        scope_obj = db.query(I18nScope).filter(I18nScope.name == scope).first()
        
        if not scope_obj:
            return None
        
        # Try requested language
        string = db.query(I18nString).filter(
            and_(
                I18nString.scope_id == scope_obj.id,
                I18nString.language == language,
                I18nString.key == key,
                I18nString.is_approved == True
            )
        ).first()
        
        if string:
            return string.value
        
        # Fallback
        if language != fallback_language:
            string = db.query(I18nString).filter(
                and_(
                    I18nString.scope_id == scope_obj.id,
                    I18nString.language == fallback_language,
                    I18nString.key == key,
                    I18nString.is_approved == True
                )
            ).first()
            
            if string:
                return string.value
        
        return None
    
    def set_string(
        self,
        db: Session,
        scope: str,
        language: str,
        key: str,
        value: str,
        is_approved: bool = False
    ) -> Dict[str, Any]:
        """
        Set/update a translation string.
        
        Args:
            db: Database session
            scope: Scope name
            language: Language code
            key: String key
            value: Translated value
            is_approved: Whether the translation is approved
            
        Returns:
            Result dict with success status
        """
        try:
            # Get or create scope
            scope_obj = db.query(I18nScope).filter(I18nScope.name == scope).first()
            
            if not scope_obj:
                scope_obj = I18nScope(name=scope, description=f"Auto-created scope: {scope}")
                db.add(scope_obj)
                db.flush()
            
            # Check if string exists
            existing = db.query(I18nString).filter(
                and_(
                    I18nString.scope_id == scope_obj.id,
                    I18nString.language == language,
                    I18nString.key == key
                )
            ).first()
            
            if existing:
                existing.value = value
                existing.is_approved = is_approved
                existing.updated_at = datetime.utcnow()
            else:
                new_string = I18nString(
                    scope_id=scope_obj.id,
                    language=language,
                    key=key,
                    value=value,
                    is_approved=is_approved,
                    updated_at=datetime.utcnow()
                )
                db.add(new_string)
            
            db.commit()
            return {"success": True, "key": key, "language": language}
            
        except Exception as e:
            db.rollback()
            logger.error(f"Error setting i18n string: {e}")
            return {"success": False, "error": str(e)}
    
    def bulk_set_strings(
        self,
        db: Session,
        scope: str,
        language: str,
        strings: Dict[str, str],
        is_approved: bool = False
    ) -> Dict[str, Any]:
        """
        Set multiple strings at once.
        
        Useful for importing translations.
        """
        success_count = 0
        error_count = 0
        
        for key, value in strings.items():
            result = self.set_string(db, scope, language, key, value, is_approved)
            if result.get("success"):
                success_count += 1
            else:
                error_count += 1
        
        return {
            "success": error_count == 0,
            "imported": success_count,
            "errors": error_count
        }
    
    def approve_string(
        self,
        db: Session,
        scope: str,
        language: str,
        key: str
    ) -> Dict[str, Any]:
        """Approve a translation string for production use."""
        scope_obj = db.query(I18nScope).filter(I18nScope.name == scope).first()
        
        if not scope_obj:
            return {"success": False, "error": "Scope not found"}
        
        string = db.query(I18nString).filter(
            and_(
                I18nString.scope_id == scope_obj.id,
                I18nString.language == language,
                I18nString.key == key
            )
        ).first()
        
        if not string:
            return {"success": False, "error": "String not found"}
        
        try:
            string.is_approved = True
            string.updated_at = datetime.utcnow()
            db.commit()
            return {"success": True}
        except Exception as e:
            db.rollback()
            return {"success": False, "error": str(e)}
    
    def get_available_languages(self, db: Session) -> List[str]:
        """Get list of all languages with translations."""
        languages = db.query(I18nString.language).distinct().all()
        return [l[0] for l in languages]
    
    def get_scopes(self, db: Session) -> List[Dict[str, Any]]:
        """Get all available scopes."""
        scopes = db.query(I18nScope).all()
        return [
            {
                "id": s.id,
                "name": s.name,
                "description": s.description
            }
            for s in scopes
        ]
    
    def get_translation_stats(
        self,
        db: Session,
        scope: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get translation statistics.
        
        Useful for monitoring translation coverage.
        """
        from sqlalchemy import func
        
        query = db.query(
            I18nString.language,
            func.count(I18nString.id).label("total"),
            func.sum(func.cast(I18nString.is_approved, Integer)).label("approved")
        ).group_by(I18nString.language)
        
        if scope:
            scope_obj = db.query(I18nScope).filter(I18nScope.name == scope).first()
            if scope_obj:
                query = query.filter(I18nString.scope_id == scope_obj.id)
        
        stats = query.all()
        
        return {
            "languages": [
                {
                    "language": s[0],
                    "total": s[1],
                    "approved": s[2] or 0,
                    "coverage": round((s[2] or 0) / s[1] * 100, 1) if s[1] > 0 else 0
                }
                for s in stats
            ]
        }


# Singleton instance
i18n_service = I18nService()


# Import for stats
try:
    from sqlalchemy import Integer
except ImportError:
    pass
