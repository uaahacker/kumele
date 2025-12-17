"""
Translation and Internationalization Service.
Handles UI string translations and dynamic text translation.
"""
from typing import Optional, List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from datetime import datetime
import logging
import uuid
import httpx

from app.models.database_models import UIString, UITranslation
from app.config import settings

logger = logging.getLogger(__name__)


class TranslationService:
    """Service for translation and i18n operations."""
    
    # Cache for translations (in production, use Redis)
    _cache: Dict[str, Dict[str, str]] = {}
    _cache_ttl: Dict[str, datetime] = {}

    @staticmethod
    async def translate_text(
        text: str,
        source_lang: str,
        target_lang: str
    ) -> Dict[str, Any]:
        """
        Translate text using LibreTranslate/Argos.
        """
        if source_lang == target_lang:
            return {
                "translated_text": text,
                "source_language": source_lang,
                "target_language": target_lang,
                "confidence": 1.0
            }
        
        if target_lang not in settings.SUPPORTED_LANGUAGES:
            return {
                "error": f"Unsupported target language: {target_lang}",
                "supported_languages": settings.SUPPORTED_LANGUAGES
            }
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{settings.TRANSLATE_URL}/translate",
                    json={
                        "q": text,
                        "source": source_lang,
                        "target": target_lang,
                        "format": "text"
                    },
                    timeout=10.0
                )
                
                if response.status_code == 200:
                    data = response.json()
                    return {
                        "translated_text": data.get("translatedText", text),
                        "source_language": source_lang,
                        "target_language": target_lang,
                        "confidence": 0.95
                    }
                else:
                    # Fallback: return original
                    return {
                        "translated_text": text,
                        "source_language": source_lang,
                        "target_language": target_lang,
                        "confidence": 0.0,
                        "error": f"Translation service returned {response.status_code}"
                    }
                    
        except Exception as e:
            logger.error(f"Translation error: {e}")
            return {
                "translated_text": text,
                "source_language": source_lang,
                "target_language": target_lang,
                "confidence": 0.0,
                "error": str(e)
            }

    @staticmethod
    async def detect_language(text: str) -> Dict[str, Any]:
        """Detect language of text."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{settings.TRANSLATE_URL}/detect",
                    json={"q": text},
                    timeout=5.0
                )
                
                if response.status_code == 200:
                    data = response.json()
                    if data:
                        return {
                            "language": data[0].get("language", "en"),
                            "confidence": data[0].get("confidence", 0.0)
                        }
                        
        except Exception as e:
            logger.warning(f"Language detection error: {e}")
        
        # Fallback: try pattern matching
        return TranslationService._detect_language_fallback(text)

    @staticmethod
    def _detect_language_fallback(text: str) -> Dict[str, Any]:
        """Simple fallback language detection."""
        # Common patterns for supported languages
        patterns = {
            "zh": ["的", "是", "在", "了", "和"],  # Chinese
            "ar": ["ال", "من", "في", "إلى", "على"],  # Arabic
            "fr": ["le", "la", "les", "de", "est"],  # French
            "es": ["el", "la", "de", "que", "es"],  # Spanish
            "de": ["der", "die", "das", "und", "ist"],  # German
        }
        
        text_lower = text.lower()
        
        for lang, words in patterns.items():
            matches = sum(1 for w in words if w in text_lower)
            if matches >= 2:
                return {"language": lang, "confidence": 0.6}
        
        return {"language": "en", "confidence": 0.5}

    @staticmethod
    async def get_i18n_strings(
        db: AsyncSession,
        language: str,
        scope: Optional[str] = None
    ) -> Dict[str, str]:
        """
        Get all UI strings for a language.
        Returns approved translations or falls back to English.
        
        Supports lazy loading with scope parameter:
        - common: Basic UI elements (loaded at startup)
        - events: Event-related strings
        - profile: User profile strings
        - settings: Settings screen strings
        - chat: Chat/messaging strings
        - support: Support/help strings
        """
        # Check cache
        cache_key = f"i18n_{language}_{scope or 'all'}"
        if cache_key in TranslationService._cache:
            cached_time = TranslationService._cache_ttl.get(cache_key)
            if cached_time and (datetime.utcnow() - cached_time).seconds < 300:
                return TranslationService._cache[cache_key]
        
        result = {}
        
        # Get UI strings - filter by scope if provided
        query = select(UIString)
        
        # Apply scope filter - strings are expected to have key prefixes like:
        # common.*, events.*, profile.*, settings.*, chat.*, support.*
        if scope:
            # Filter by key prefix matching the scope
            query = query.where(UIString.string_key.like(f"{scope}.%"))
        
        db_result = await db.execute(query)
        ui_strings = db_result.scalars().all()
        
        for ui_string in ui_strings:
            if language == "en":
                # Return English (source)
                result[ui_string.string_key] = ui_string.english_value
            else:
                # Look for approved translation
                trans_query = select(UITranslation).where(
                    and_(
                        UITranslation.string_id == ui_string.id,
                        UITranslation.language == language,
                        UITranslation.status == "approved"
                    )
                )
                trans_result = await db.execute(trans_query)
                translation = trans_result.scalar_one_or_none()
                
                if translation:
                    result[ui_string.string_key] = translation.translated_value
                else:
                    # Fallback to English
                    result[ui_string.string_key] = ui_string.english_value
        
        # Cache result
        TranslationService._cache[cache_key] = result
        TranslationService._cache_ttl[cache_key] = datetime.utcnow()
        
        return result

    @staticmethod
    async def approve_translation(
        db: AsyncSession,
        translation_id: str,
        approved_by: str
    ) -> Dict[str, Any]:
        """Approve a pending translation."""
        try:
            trans_uuid = uuid.UUID(translation_id)
            
            query = select(UITranslation).where(
                UITranslation.id == trans_uuid
            )
            result = await db.execute(query)
            translation = result.scalar_one_or_none()
            
            if not translation:
                return {
                    "success": False,
                    "message": "Translation not found"
                }
            
            translation.status = "approved"
            translation.approved_by = uuid.UUID(approved_by)
            translation.approved_at = datetime.utcnow()
            
            await db.flush()
            
            # Invalidate cache
            cache_key = f"i18n_{translation.language}"
            if cache_key in TranslationService._cache:
                del TranslationService._cache[cache_key]
            
            return {
                "success": True,
                "message": "Translation approved",
                "translation_id": translation_id
            }
            
        except Exception as e:
            logger.error(f"Approval error: {e}")
            return {
                "success": False,
                "message": str(e)
            }

    @staticmethod
    async def add_ui_string(
        db: AsyncSession,
        string_key: str,
        english_value: str,
        context: Optional[str] = None
    ) -> Dict[str, Any]:
        """Add a new UI string."""
        try:
            # Check if exists
            query = select(UIString).where(
                UIString.string_key == string_key
            )
            result = await db.execute(query)
            existing = result.scalar_one_or_none()
            
            if existing:
                existing.english_value = english_value
                existing.context = context
                existing.updated_at = datetime.utcnow()
                string_id = str(existing.id)
            else:
                ui_string = UIString(
                    string_key=string_key,
                    english_value=english_value,
                    context=context,
                    updated_at=datetime.utcnow()
                )
                db.add(ui_string)
                await db.flush()
                string_id = str(ui_string.id)
            
            return {
                "success": True,
                "string_id": string_id,
                "string_key": string_key
            }
            
        except Exception as e:
            logger.error(f"Add UI string error: {e}")
            return {
                "success": False,
                "message": str(e)
            }

    @staticmethod
    async def submit_translation(
        db: AsyncSession,
        string_id: str,
        language: str,
        translated_value: str,
        translator_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Submit a translation for review."""
        try:
            string_uuid = uuid.UUID(string_id)
            
            # Check if string exists
            query = select(UIString).where(UIString.id == string_uuid)
            result = await db.execute(query)
            ui_string = result.scalar_one_or_none()
            
            if not ui_string:
                return {
                    "success": False,
                    "message": "UI string not found"
                }
            
            # Check for existing translation
            trans_query = select(UITranslation).where(
                and_(
                    UITranslation.string_id == string_uuid,
                    UITranslation.language == language
                )
            )
            trans_result = await db.execute(trans_query)
            existing_trans = trans_result.scalar_one_or_none()
            
            if existing_trans:
                existing_trans.translated_value = translated_value
                existing_trans.status = "pending"
                existing_trans.submitted_by = uuid.UUID(translator_id) if translator_id else None
                existing_trans.submitted_at = datetime.utcnow()
                translation_id = str(existing_trans.id)
            else:
                translation = UITranslation(
                    string_id=string_uuid,
                    language=language,
                    translated_value=translated_value,
                    status="pending",
                    submitted_by=uuid.UUID(translator_id) if translator_id else None,
                    submitted_at=datetime.utcnow()
                )
                db.add(translation)
                await db.flush()
                translation_id = str(translation.id)
            
            return {
                "success": True,
                "translation_id": translation_id,
                "status": "pending"
            }
            
        except Exception as e:
            logger.error(f"Submit translation error: {e}")
            return {
                "success": False,
                "message": str(e)
            }

    @staticmethod
    async def get_pending_translations(
        db: AsyncSession,
        language: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get all pending translations for review."""
        query = select(UITranslation).where(
            UITranslation.status == "pending"
        )
        
        if language:
            query = query.where(UITranslation.language == language)
        
        result = await db.execute(query)
        translations = result.scalars().all()
        
        pending = []
        for trans in translations:
            # Get source string
            string_query = select(UIString).where(
                UIString.id == trans.string_id
            )
            string_result = await db.execute(string_query)
            ui_string = string_result.scalar_one_or_none()
            
            pending.append({
                "translation_id": str(trans.id),
                "string_key": ui_string.string_key if ui_string else None,
                "english_value": ui_string.english_value if ui_string else None,
                "language": trans.language,
                "translated_value": trans.translated_value,
                "submitted_at": trans.submitted_at.isoformat() if trans.submitted_at else None
            })
        
        return pending

    @staticmethod
    async def bulk_translate(
        db: AsyncSession,
        texts: List[str],
        source_lang: str,
        target_lang: str
    ) -> List[Dict[str, Any]]:
        """Translate multiple texts."""
        results = []
        
        for text in texts:
            result = await TranslationService.translate_text(
                text, source_lang, target_lang
            )
            results.append(result)
        
        return results
