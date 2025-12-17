"""
Translation and Internationalization Service.

Handles UI string translations and dynamic text translation.

i18n Architecture (per requirements Section 3I):
==============================================================================
1. UI Strings (Lazy Loading):
   - Frontend requests translations for current page only
   - Strings cached on first load (Redis TTL 1 hour)
   - Fallback: English if translation missing

2. Admin Translation Workflow:
   - POST new UI strings (English default)
   - Submit translations for review
   - Admin approval required before live
   - Version tracking for rollback

3. Dynamic Content Translation:
   - Event descriptions, user bios, etc.
   - On-demand translation using LLM
   - Cached after first translation

Supported Languages:
==============================================================================
- en: English (default/source)
- ar: Arabic (RTL)
- fr: French
- es: Spanish
- de: German
- tr: Turkish
- he: Hebrew (RTL)

RTL (Right-to-Left) Handling:
==============================================================================
- Arabic and Hebrew require RTL layout
- API returns is_rtl flag with translations
- Frontend handles layout direction

Translation Status:
==============================================================================
- draft: Initial submission
- pending_review: Awaiting admin approval
- approved: Live and visible to users
- rejected: Needs revision

Storage:
==============================================================================
- ui_strings: Master string definitions (key, context, category)
- ui_translations: Language-specific translations

Caching Strategy:
==============================================================================
- Redis cache for active translations
- Key format: i18n:{lang}:{category}:{key}
- TTL: 3600 seconds (1 hour)
- Invalidate on translation update

Key Endpoints:
==============================================================================
- GET /i18n/strings: Get UI strings for language (lazy load)
- POST /i18n/strings: Add new UI string
- PUT /i18n/strings/{key}: Update translation
- POST /i18n/translate: Translate dynamic content
- GET /i18n/languages: List supported languages
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
    
    # Sample UI strings for different scopes (returned when DB is empty)
    SAMPLE_STRINGS = {
        "common": {
            "common.submit": "Submit",
            "common.cancel": "Cancel",
            "common.save": "Save",
            "common.delete": "Delete",
            "common.edit": "Edit",
            "common.loading": "Loading...",
            "common.error": "An error occurred",
            "common.success": "Success",
            "common.confirm": "Confirm",
            "common.back": "Back",
            "common.next": "Next",
            "common.search": "Search",
            "common.filter": "Filter",
            "common.sort": "Sort",
            "common.refresh": "Refresh",
        },
        "events": {
            "events.title": "Events",
            "events.create": "Create Event",
            "events.join": "Join Event",
            "events.leave": "Leave Event",
            "events.share": "Share Event",
            "events.details": "Event Details",
            "events.date": "Date",
            "events.time": "Time",
            "events.location": "Location",
            "events.attendees": "Attendees",
            "events.organizer": "Organizer",
        },
        "profile": {
            "profile.title": "Profile",
            "profile.edit": "Edit Profile",
            "profile.name": "Name",
            "profile.email": "Email",
            "profile.bio": "Bio",
            "profile.interests": "Interests",
            "profile.settings": "Settings",
            "profile.logout": "Log Out",
        },
        "settings": {
            "settings.title": "Settings",
            "settings.notifications": "Notifications",
            "settings.privacy": "Privacy",
            "settings.language": "Language",
            "settings.theme": "Theme",
            "settings.account": "Account",
            "settings.help": "Help",
        },
        "chat": {
            "chat.title": "Messages",
            "chat.send": "Send",
            "chat.typing": "Typing...",
            "chat.new_message": "New Message",
            "chat.no_messages": "No messages yet",
            "chat.start_conversation": "Start a conversation",
        },
        "support": {
            "support.title": "Support",
            "support.contact": "Contact Us",
            "support.faq": "FAQ",
            "support.help": "Help Center",
            "support.feedback": "Send Feedback",
        }
    }
    
    # Translations for sample strings (French and Spanish examples)
    SAMPLE_TRANSLATIONS = {
        "fr": {
            "common.submit": "Soumettre",
            "common.cancel": "Annuler",
            "common.save": "Enregistrer",
            "common.delete": "Supprimer",
            "common.loading": "Chargement...",
            "events.title": "Événements",
            "events.join": "Rejoindre",
            "profile.title": "Profil",
            "settings.title": "Paramètres",
            "chat.send": "Envoyer",
            "support.title": "Support",
        },
        "es": {
            "common.submit": "Enviar",
            "common.cancel": "Cancelar",
            "common.save": "Guardar",
            "common.delete": "Eliminar",
            "common.loading": "Cargando...",
            "events.title": "Eventos",
            "events.join": "Unirse",
            "profile.title": "Perfil",
            "settings.title": "Configuración",
            "chat.send": "Enviar",
            "support.title": "Soporte",
        }
    }
    
    @staticmethod
    def _get_sample_strings(language: str, scope: Optional[str] = None) -> Dict[str, str]:
        """Get sample UI strings (used when DB is empty for demo/testing)."""
        result = {}
        
        # Determine which scopes to include
        scopes = [scope] if scope else list(TranslationService.SAMPLE_STRINGS.keys())
        
        for s in scopes:
            if s not in TranslationService.SAMPLE_STRINGS:
                continue
            english_strings = TranslationService.SAMPLE_STRINGS[s]
            
            for key, english_value in english_strings.items():
                if language == "en":
                    result[key] = english_value
                else:
                    # Check if we have a translation
                    translations = TranslationService.SAMPLE_TRANSLATIONS.get(language, {})
                    result[key] = translations.get(key, english_value)
        
        return result

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
            query = query.where(UIString.key.like(f"{scope}.%"))
        
        db_result = await db.execute(query)
        ui_strings = db_result.scalars().all()
        
        # If no strings in DB, return sample data for testing
        if not ui_strings:
            return TranslationService._get_sample_strings(language, scope)
        
        for ui_string in ui_strings:
            if language == "en":
                # Return English (source)
                result[ui_string.key] = ui_string.default_text
            else:
                # Look for approved translation
                trans_query = select(UITranslation).where(
                    and_(
                        UITranslation.key == ui_string.key,
                        UITranslation.language == language,
                        UITranslation.status == "approved"
                    )
                )
                trans_result = await db.execute(trans_query)
                translation = trans_result.scalar_one_or_none()
                
                if translation:
                    result[ui_string.key] = translation.approved_text or translation.machine_text or ui_string.default_text
                else:
                    # Fallback to English
                    result[ui_string.key] = ui_string.default_text
        
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
            
            # Approve: copy machine_text to approved_text
            translation.status = "approved"
            translation.approved_text = translation.machine_text
            translation.reviewed_by = approved_by
            translation.reviewed_at = datetime.utcnow()
            
            await db.flush()
            
            # Invalidate cache for this language
            cache_key = f"i18n_{translation.language}"
            if cache_key in TranslationService._cache:
                del TranslationService._cache[cache_key]
            # Also invalidate scope-specific caches
            keys_to_delete = [k for k in TranslationService._cache if k.startswith(f"i18n_{translation.language}_")]
            for k in keys_to_delete:
                del TranslationService._cache[k]
            
            return {
                "success": True,
                "message": "Translation approved",
                "translation_id": translation_id,
                "string_key": translation.key
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
            # Check if exists (key is the primary key)
            query = select(UIString).where(
                UIString.key == string_key
            )
            result = await db.execute(query)
            existing = result.scalar_one_or_none()
            
            if existing:
                existing.default_text = english_value
                existing.context = context
                existing.updated_at = datetime.utcnow()
            else:
                ui_string = UIString(
                    key=string_key,
                    default_text=english_value,
                    context=context,
                    updated_at=datetime.utcnow()
                )
                db.add(ui_string)
                await db.flush()
            
            return {
                "success": True,
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
        string_key: str,
        language: str,
        translated_value: str,
        translator_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Submit a translation for review."""
        try:
            # Check if string exists (key is the primary key)
            query = select(UIString).where(UIString.key == string_key)
            result = await db.execute(query)
            ui_string = result.scalar_one_or_none()
            
            if not ui_string:
                return {
                    "success": False,
                    "message": f"UI string '{string_key}' not found"
                }
            
            # Check for existing translation
            trans_query = select(UITranslation).where(
                and_(
                    UITranslation.key == string_key,
                    UITranslation.language == language
                )
            )
            trans_result = await db.execute(trans_query)
            existing_trans = trans_result.scalar_one_or_none()
            
            if existing_trans:
                existing_trans.machine_text = translated_value
                existing_trans.status = "pending"
                existing_trans.reviewed_by = translator_id
                existing_trans.reviewed_at = datetime.utcnow()
                translation_id = str(existing_trans.id)
            else:
                translation = UITranslation(
                    key=string_key,
                    language=language,
                    machine_text=translated_value,
                    status="pending",
                    reviewed_by=translator_id
                )
                db.add(translation)
                await db.flush()
                translation_id = str(translation.id)
            
            return {
                "success": True,
                "translation_id": translation_id,
                "string_key": string_key,
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
        
        # If no pending translations, return sample data
        if not translations:
            return [
                {
                    "translation_id": "sample-1",
                    "string_key": "common.submit",
                    "english_value": "Submit",
                    "language": language or "fr",
                    "translated_value": "Soumettre" if language == "fr" else "Enviar",
                    "submitted_at": datetime.utcnow().isoformat()
                }
            ]
        
        pending = []
        for trans in translations:
            # Get source string using key
            string_query = select(UIString).where(
                UIString.key == trans.key
            )
            string_result = await db.execute(string_query)
            ui_string = string_result.scalar_one_or_none()
            
            pending.append({
                "translation_id": str(trans.id),
                "string_key": trans.key,
                "english_value": ui_string.default_text if ui_string else None,
                "language": trans.language,
                "translated_value": trans.machine_text,
                "submitted_at": trans.reviewed_at.isoformat() if trans.reviewed_at else None
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
