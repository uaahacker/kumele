"""
Translation and i18n API endpoints.
Handles text translation and UI string management.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List
import logging

from app.database import get_db
from app.services.translation_service import TranslationService
from app.schemas.schemas import (
    TranslateRequest,
    TranslateResponse,
    I18nStringsResponse,
    TranslationApprovalRequest,
    TranslationApprovalResponse
)
from app.config import settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/translate", tags=["Translation"])


@router.post(
    "/text",
    response_model=TranslateResponse,
    summary="Translate Text",
    description="""
    Translate text between languages.
    
    Supported languages:
    - English (en)
    - French (fr)
    - Spanish (es)
    - Chinese (zh)
    - Arabic (ar)
    - German (de)
    
    Uses LibreTranslate/Argos Translate for translations.
    
    Returns:
    - Translated text
    - Source language
    - Target language
    - Confidence score
    """
)
async def translate_text(
    request: TranslateRequest,
    db: AsyncSession = Depends(get_db)
):
    """Translate text."""
    try:
        result = await TranslationService.translate_text(
            text=request.text,
            source_lang=request.source_language,
            target_lang=request.target_language
        )
        
        return result
        
    except Exception as e:
        logger.error(f"Translation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/detect",
    summary="Detect Language",
    description="Detect the language of input text."
)
async def detect_language(
    text: str = Query(..., min_length=1, description="Text to analyze"),
    db: AsyncSession = Depends(get_db)
):
    """Detect language of text."""
    try:
        result = await TranslationService.detect_language(text)
        return result
        
    except Exception as e:
        logger.error(f"Language detection error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/languages",
    summary="Get Supported Languages",
    description="Get list of supported languages."
)
async def get_languages():
    """Get supported languages."""
    return {
        "languages": [
            {"code": "en", "name": "English"},
            {"code": "fr", "name": "French"},
            {"code": "es", "name": "Spanish"},
            {"code": "zh", "name": "Chinese"},
            {"code": "ar", "name": "Arabic"},
            {"code": "de", "name": "German"}
        ]
    }


# I18n Router
i18n_router = APIRouter(prefix="/i18n", tags=["Internationalization"])


@i18n_router.get(
    "/{language}",
    response_model=I18nStringsResponse,
    summary="Get UI Strings",
    description="""
    Get all UI strings for a language.
    
    Returns approved translations for the language, 
    falling back to English for untranslated strings.
    
    Use for client-side internationalization.
    
    **Lazy Loading with Scope:**
    Use the `scope` parameter to load only specific sections:
    - `common` - Loaded at startup (buttons, labels, errors)
    - `events` - Event-related strings
    - `profile` - User profile strings
    - `settings` - Settings screen strings
    - `chat` - Chat/messaging strings
    - `support` - Support/help strings
    
    Example: `/i18n/fr?scope=events`
    """
)
async def get_i18n_strings(
    language: str,
    scope: Optional[str] = Query(None, description="Scope: common, events, profile, settings, chat, support"),
    db: AsyncSession = Depends(get_db)
):
    """Get UI strings for language."""
    try:
        if language not in settings.SUPPORTED_LANGUAGES:
            language = "en"
        
        strings = await TranslationService.get_i18n_strings(db, language, scope)
        
        return {
            "language": language,
            "strings": strings
        }
        
    except Exception as e:
        logger.error(f"Get i18n strings error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Admin Translation Router
admin_i18n_router = APIRouter(prefix="/admin/i18n", tags=["Admin - Translation"])


@admin_i18n_router.post(
    "/approve",
    response_model=TranslationApprovalResponse,
    summary="Approve Translation",
    description="Approve a pending translation (admin use)."
)
async def approve_translation(
    request: TranslationApprovalRequest,
    db: AsyncSession = Depends(get_db)
):
    """Approve a translation."""
    try:
        result = await TranslationService.approve_translation(
            db=db,
            translation_id=request.translation_id,
            approved_by=request.approved_by
        )
        
        if not result.get("success"):
            raise HTTPException(status_code=400, detail=result.get("message"))
        
        await db.commit()
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Approve translation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@admin_i18n_router.get(
    "/pending",
    summary="Get Pending Translations",
    description="Get translations pending approval."
)
async def get_pending_translations(
    language: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db)
):
    """Get pending translations."""
    try:
        result = await TranslationService.get_pending_translations(db, language)
        return {"pending": result}
        
    except Exception as e:
        logger.error(f"Get pending translations error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@admin_i18n_router.post(
    "/strings",
    summary="Add UI String",
    description="Add or update a UI string (admin use)."
)
async def add_ui_string(
    string_key: str = Query(..., description="String key"),
    english_value: str = Query(..., description="English value"),
    context: Optional[str] = Query(None, description="Context/usage notes"),
    db: AsyncSession = Depends(get_db)
):
    """Add or update UI string."""
    try:
        result = await TranslationService.add_ui_string(
            db=db,
            string_key=string_key,
            english_value=english_value,
            context=context
        )
        
        await db.commit()
        return result
        
    except Exception as e:
        await db.rollback()
        logger.error(f"Add UI string error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@admin_i18n_router.post(
    "/submit",
    summary="Submit Translation",
    description="Submit a translation for review."
)
async def submit_translation(
    string_id: str = Query(..., description="UI String ID"),
    language: str = Query(..., description="Target language"),
    translated_value: str = Query(..., description="Translated text"),
    translator_id: Optional[str] = Query(None, description="Translator user ID"),
    db: AsyncSession = Depends(get_db)
):
    """Submit a translation."""
    try:
        result = await TranslationService.submit_translation(
            db=db,
            string_id=string_id,
            language=language,
            translated_value=translated_value,
            translator_id=translator_id
        )
        
        await db.commit()
        return result
        
    except Exception as e:
        await db.rollback()
        logger.error(f"Submit translation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
