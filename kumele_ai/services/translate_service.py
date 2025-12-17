"""
Translation Service - Handles text translation using LibreTranslate/Argos
"""
import httpx
import logging
from typing import Dict, Any, List, Optional
from kumele_ai.config import settings

logger = logging.getLogger(__name__)

# Supported languages
SUPPORTED_LANGUAGES = {
    "en": "English",
    "es": "Spanish",
    "fr": "French",
    "de": "German",
    "ar": "Arabic",
    "zh": "Chinese"
}


class TranslateService:
    """Service for text translation using LibreTranslate/Argos"""
    
    def __init__(self):
        self.base_url = settings.TRANSLATE_URL
        self.timeout = 30.0
    
    async def translate(
        self,
        text: str,
        source_lang: str,
        target_lang: str
    ) -> Dict[str, Any]:
        """Translate text from source to target language"""
        try:
            # Validate languages
            if source_lang not in SUPPORTED_LANGUAGES:
                return {
                    "success": False,
                    "error": f"Source language '{source_lang}' not supported",
                    "supported_languages": list(SUPPORTED_LANGUAGES.keys())
                }
            
            if target_lang not in SUPPORTED_LANGUAGES:
                return {
                    "success": False,
                    "error": f"Target language '{target_lang}' not supported",
                    "supported_languages": list(SUPPORTED_LANGUAGES.keys())
                }
            
            # Same language - return as is
            if source_lang == target_lang:
                return {
                    "success": True,
                    "translated_text": text,
                    "source_language": source_lang,
                    "target_language": target_lang
                }
            
            payload = {
                "q": text,
                "source": source_lang,
                "target": target_lang,
                "format": "text"
            }
            
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/translate",
                    json=payload
                )
                response.raise_for_status()
                result = response.json()
                
                return {
                    "success": True,
                    "translated_text": result.get("translatedText", ""),
                    "source_language": source_lang,
                    "target_language": target_lang
                }
                
        except httpx.TimeoutException:
            logger.error("Translation request timed out")
            return {
                "success": False,
                "error": "Translation request timed out"
            }
        except Exception as e:
            logger.error(f"Translation error: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def detect_language(self, text: str) -> Dict[str, Any]:
        """Detect the language of text"""
        try:
            payload = {
                "q": text
            }
            
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/detect",
                    json=payload
                )
                response.raise_for_status()
                result = response.json()
                
                if result and len(result) > 0:
                    detected = result[0]
                    return {
                        "success": True,
                        "language": detected.get("language", "en"),
                        "confidence": detected.get("confidence", 0.0)
                    }
                
                return {
                    "success": True,
                    "language": "en",
                    "confidence": 0.0
                }
                
        except Exception as e:
            logger.error(f"Language detection error: {e}")
            return {
                "success": False,
                "language": "en",
                "confidence": 0.0,
                "error": str(e)
            }
    
    async def translate_to_english(self, text: str, source_lang: Optional[str] = None) -> Dict[str, Any]:
        """Translate text to English, auto-detecting source if not provided"""
        if source_lang is None:
            detection = await self.detect_language(text)
            source_lang = detection.get("language", "en")
        
        if source_lang == "en":
            return {
                "success": True,
                "translated_text": text,
                "source_language": "en",
                "target_language": "en"
            }
        
        return await self.translate(text, source_lang, "en")
    
    async def translate_from_english(self, text: str, target_lang: str) -> Dict[str, Any]:
        """Translate text from English to target language"""
        return await self.translate(text, "en", target_lang)
    
    async def get_supported_languages(self) -> Dict[str, Any]:
        """Get list of supported languages"""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(f"{self.base_url}/languages")
                response.raise_for_status()
                return {
                    "success": True,
                    "languages": response.json()
                }
        except Exception as e:
            logger.error(f"Error getting languages: {e}")
            return {
                "success": True,
                "languages": SUPPORTED_LANGUAGES
            }
    
    async def health_check(self) -> bool:
        """Check if translation service is healthy"""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(f"{self.base_url}/languages")
                return response.status_code == 200
        except Exception as e:
            logger.error(f"Translation health check failed: {e}")
            return False


# Singleton instance
translate_service = TranslateService()
