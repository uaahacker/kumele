"""
i18n API Router - Internationalization with lazy loading by scope

Endpoints:
- GET /i18n/{language} - Get all translations for a language (optional scope filter)
"""
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from typing import Optional, List, Dict, Any
from pydantic import BaseModel

from kumele_ai.db.database import get_db
from kumele_ai.services.i18n_service import i18n_service

router = APIRouter(prefix="/i18n", tags=["Internationalization"])


class StringsResponse(BaseModel):
    """Response model for i18n strings"""
    language: str
    scope: str
    strings: Dict[str, str]
    count: int


class MultipleScopesResponse(BaseModel):
    """Response model for multiple scopes"""
    language: str
    scopes: Dict[str, Dict[str, str]]


class SetStringRequest(BaseModel):
    """Request model for setting a string"""
    scope: str
    key: str
    value: str
    is_approved: bool = False


class BulkSetStringsRequest(BaseModel):
    """Request model for bulk setting strings"""
    scope: str
    strings: Dict[str, str]
    is_approved: bool = False


@router.get("/{language}", response_model=StringsResponse)
async def get_translations(
    language: str,
    scope: str = Query(
        "common",
        description="Scope to load (common, events, profile, auth, settings, chat, ads, moderation)"
    ),
    include_unapproved: bool = Query(
        False,
        description="Include unapproved translations (admin only)"
    ),
    db: Session = Depends(get_db)
) -> StringsResponse:
    """
    Get translations for a specific language and scope.
    
    This is the main endpoint for frontend lazy loading. Frontends should:
    1. Load 'common' scope on app startup
    2. Load other scopes as needed when navigating to those features
    
    Path Parameters:
    - **language**: Language code (en, fr, es, de, etc.)
    
    Query Parameters:
    - **scope**: Which strings to load. Default 'common'.
      - common: Shared UI elements, buttons, errors
      - events: Event-related strings
      - profile: User profile strings  
      - auth: Authentication strings
      - settings: Settings/preferences strings
      - chat: Chat/messaging strings
      - ads: Advertisement strings
      - moderation: Content moderation strings
    - **include_unapproved**: Include unapproved translations (for admin preview)
    
    Returns:
    - language: The requested language code
    - scope: The requested scope
    - strings: Key-value pairs of translations
    - count: Number of strings returned
    
    Example Response:
    ```json
    {
      "language": "fr",
      "scope": "common",
      "strings": {
        "button.save": "Enregistrer",
        "button.cancel": "Annuler",
        "error.generic": "Une erreur s'est produite"
      },
      "count": 3
    }
    ```
    """
    strings = i18n_service.get_strings_by_scope(
        db=db,
        language=language,
        scope=scope,
        include_unapproved=include_unapproved
    )
    
    return StringsResponse(
        language=language,
        scope=scope,
        strings=strings,
        count=len(strings)
    )


@router.get("/{language}/multiple")
async def get_multiple_scopes(
    language: str,
    scopes: str = Query(
        "common",
        description="Comma-separated list of scopes to load"
    ),
    include_unapproved: bool = Query(False),
    db: Session = Depends(get_db)
) -> MultipleScopesResponse:
    """
    Get translations for multiple scopes at once.
    
    Useful for initial app load when you need several scopes.
    
    Path Parameters:
    - **language**: Language code
    
    Query Parameters:
    - **scopes**: Comma-separated scope names (e.g., "common,events,profile")
    
    Example: GET /i18n/fr/multiple?scopes=common,events,profile
    """
    scope_list = [s.strip() for s in scopes.split(",")]
    
    results = i18n_service.get_multiple_scopes(
        db=db,
        language=language,
        scopes=scope_list,
        include_unapproved=include_unapproved
    )
    
    return MultipleScopesResponse(
        language=language,
        scopes=results
    )


@router.get("/{language}/{scope}/{key}")
async def get_single_string(
    language: str,
    scope: str,
    key: str,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get a single translation string.
    
    Useful for dynamic content or debugging.
    Falls back to English if the requested language doesn't have this string.
    """
    value = i18n_service.get_string(
        db=db,
        language=language,
        scope=scope,
        key=key,
        fallback_language="en"
    )
    
    if value is None:
        raise HTTPException(status_code=404, detail="String not found")
    
    return {
        "language": language,
        "scope": scope,
        "key": key,
        "value": value
    }


@router.post("/{language}/string")
async def set_string(
    language: str,
    request: SetStringRequest,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Set/update a translation string.
    
    Path Parameters:
    - **language**: Language code
    
    Request Body:
    - **scope**: Scope name
    - **key**: String key
    - **value**: Translated value
    - **is_approved**: Whether approved for production (default false)
    """
    result = i18n_service.set_string(
        db=db,
        scope=request.scope,
        language=language,
        key=request.key,
        value=request.value,
        is_approved=request.is_approved
    )
    
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error"))
    
    return result


@router.post("/{language}/bulk")
async def bulk_set_strings(
    language: str,
    request: BulkSetStringsRequest,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Import multiple translation strings at once.
    
    Path Parameters:
    - **language**: Language code
    
    Request Body:
    - **scope**: Scope name
    - **strings**: Dict of key -> value
    - **is_approved**: Whether to mark all as approved
    
    Example Request:
    ```json
    {
      "scope": "common",
      "strings": {
        "button.save": "Enregistrer",
        "button.cancel": "Annuler"
      },
      "is_approved": false
    }
    ```
    """
    result = i18n_service.bulk_set_strings(
        db=db,
        scope=request.scope,
        language=language,
        strings=request.strings,
        is_approved=request.is_approved
    )
    
    return result


@router.post("/{language}/{scope}/{key}/approve")
async def approve_string(
    language: str,
    scope: str,
    key: str,
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Approve a translation string for production use.
    
    Only approved strings are served to production frontends.
    """
    result = i18n_service.approve_string(
        db=db,
        scope=scope,
        language=language,
        key=key
    )
    
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error"))
    
    return {"success": True, "message": "String approved"}


@router.get("/")
async def get_languages(
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get list of available languages.
    """
    languages = i18n_service.get_available_languages(db)
    return {
        "languages": languages,
        "count": len(languages)
    }


@router.get("/scopes/list")
async def get_scopes(
    db: Session = Depends(get_db)
) -> Dict[str, Any]:
    """
    Get list of all translation scopes.
    """
    scopes = i18n_service.get_scopes(db)
    return {
        "scopes": scopes,
        "count": len(scopes)
    }
