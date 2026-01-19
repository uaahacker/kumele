"""
Translation Router - Text translation endpoints
"""
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional, List

from kumele_ai.services.translate_service import translate_service, SUPPORTED_LANGUAGES

router = APIRouter()


class TranslateRequest(BaseModel):
    text: str
    source_lang: str
    target_lang: str


class TranslateResponse(BaseModel):
    success: bool
    translated_text: Optional[str] = None
    source_language: Optional[str] = None
    target_language: Optional[str] = None
    error: Optional[str] = None


@router.post("/text", response_model=TranslateResponse)
async def translate_text(request: TranslateRequest):
    """
    Translate text between supported languages.
    
    Uses local Argos/LibreTranslate.
    Stateless - does NOT permanently cache translations.
    
    Supported languages: en, es, fr, de, ar, zh
    """
    result = await translate_service.translate(
        text=request.text,
        source_lang=request.source_lang,
        target_lang=request.target_lang
    )
    
    return TranslateResponse(**result)


@router.get("/languages")
async def get_supported_languages():
    """
    Get list of supported languages.
    """
    return {
        "languages": SUPPORTED_LANGUAGES,
        "count": len(SUPPORTED_LANGUAGES)
    }


@router.post("/detect")
async def detect_language(text: str):
    """
    Detect the language of given text.
    """
    result = await translate_service.detect_language(text)
    return result
