"""
Testing API endpoints.
Provides helper endpoints for testing from FastAPI Swagger UI.
These endpoints generate test data so you can test other APIs without external data.
"""
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List
import logging
import uuid
from datetime import datetime, timedelta
import random
import base64

from app.database import get_db

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/testing", tags=["Testing Helpers"])


# ============================================
# TEST DATA GENERATORS
# ============================================

@router.get(
    "/generate-uuid",
    summary="Generate Test UUID",
    description="""
    Generate a random UUID for testing.
    
    Use this UUID for:
    - user_id
    - content_id
    - event_id
    - host_id
    - ad_id
    - any other ID fields
    
    **TIP**: Copy the generated UUID and paste it into other API endpoints!
    """
)
async def generate_uuid():
    """Generate a random UUID for testing."""
    new_uuid = str(uuid.uuid4())
    return {
        "uuid": new_uuid,
        "usage_examples": {
            "user_id": new_uuid,
            "content_id": new_uuid,
            "event_id": new_uuid,
            "host_id": new_uuid,
            "ad_id": new_uuid
        },
        "tip": "Copy this UUID and use it in other endpoints!"
    }


@router.get(
    "/generate-test-user",
    summary="Generate Test User Data",
    description="""
    Generate a complete test user profile with all fields.
    
    Returns user data you can use across all APIs:
    - User ID (UUID)
    - Sample hobbies
    - Location with lat/lon
    - Other profile data
    """
)
async def generate_test_user():
    """Generate test user data."""
    user_id = str(uuid.uuid4())
    
    # Sample hobbies
    all_hobbies = [
        "photography", "hiking", "cooking", "gaming", "music",
        "reading", "yoga", "painting", "dancing", "gardening",
        "cycling", "swimming", "running", "chess", "crafts"
    ]
    
    # Sample locations with lat/lon
    locations = [
        {"city": "New York", "lat": 40.7128, "lon": -74.0060},
        {"city": "Los Angeles", "lat": 34.0522, "lon": -118.2437},
        {"city": "Chicago", "lat": 41.8781, "lon": -87.6298},
        {"city": "Houston", "lat": 29.7604, "lon": -95.3698},
        {"city": "Phoenix", "lat": 33.4484, "lon": -112.0740},
        {"city": "London", "lat": 51.5074, "lon": -0.1278},
        {"city": "Paris", "lat": 48.8566, "lon": 2.3522},
        {"city": "Tokyo", "lat": 35.6762, "lon": 139.6503},
    ]
    
    location = random.choice(locations)
    user_hobbies = random.sample(all_hobbies, k=random.randint(2, 5))
    
    return {
        "user_id": user_id,
        "hobbies": user_hobbies,
        "location": location,
        "age": random.randint(18, 65),
        "reward_tier": random.choice(["none", "bronze", "silver", "gold"]),
        "usage_in_apis": {
            "/recommendations/hobbies": f"?user_id={user_id}",
            "/recommendations/events": f"?user_id={user_id}",
            "/rewards/suggestion": f"?user_id={user_id}",
            "/match/events": f"?user_id={user_id}&lat={location['lat']}&lon={location['lon']}"
        }
    }


@router.get(
    "/generate-test-event",
    summary="Generate Test Event Data",
    description="""
    Generate test event data for prediction and matching APIs.
    
    Returns event data including:
    - Event ID
    - Date/time
    - Category
    - Location
    - Capacity
    """
)
async def generate_test_event():
    """Generate test event data."""
    event_id = str(uuid.uuid4())
    host_id = str(uuid.uuid4())
    
    categories = [
        "photography", "hiking", "cooking", "gaming", "music",
        "yoga", "painting", "dancing", "fitness", "outdoor"
    ]
    
    locations = [
        {"city": "New York", "address": "Central Park, NYC"},
        {"city": "Los Angeles", "address": "Santa Monica Beach"},
        {"city": "Chicago", "address": "Millennium Park"},
        {"city": "London", "address": "Hyde Park"},
    ]
    
    category = random.choice(categories)
    location = random.choice(locations)
    event_date = datetime.utcnow() + timedelta(days=random.randint(1, 30))
    
    return {
        "event_id": event_id,
        "host_id": host_id,
        "category": category,
        "location": location["city"],
        "address": location["address"],
        "event_date": event_date.isoformat(),
        "capacity": random.randint(10, 100),
        "is_free": random.choice([True, False]),
        "usage_in_apis": {
            "/predict/attendance": {
                "event_id": event_id,
                "event_date": event_date.isoformat(),
                "category": category,
                "location": location["city"],
                "capacity": 50,
                "host_id": host_id
            },
            "/predict/no-show-rate": f"?category={category}&is_free=true&days_until_event=7",
            "/predict/trends": f"?category={category}&location={location['city']}"
        }
    }


@router.get(
    "/generate-test-content",
    summary="Generate Test Content for Moderation",
    description="""
    Generate test content for moderation API.
    
    Returns content data including:
    - content_id
    - Sample text (positive/negative/toxic variations)
    - Sample image URLs for testing
    """
)
async def generate_test_content():
    """Generate test content for moderation."""
    content_id = str(uuid.uuid4())
    user_id = str(uuid.uuid4())
    
    # Sample texts
    sample_texts = {
        "positive": "This was an amazing event! The host was so friendly and I learned a lot. Can't wait for the next one!",
        "neutral": "The event was okay. It started on time and covered the topics mentioned.",
        "negative": "Not what I expected. The venue was hard to find and there weren't enough materials.",
        "test_toxic": "This is a test string for toxicity detection.",
    }
    
    # Sample image URLs (public test images)
    sample_images = {
        "safe_image": "https://upload.wikimedia.org/wikipedia/commons/thumb/4/47/PNG_transparency_demonstration_1.png/280px-PNG_transparency_demonstration_1.png",
        "nature_image": "https://upload.wikimedia.org/wikipedia/commons/thumb/b/b6/Image_created_with_a_mobile_phone.png/1200px-Image_created_with_a_mobile_phone.png",
        "note": "Use any public image URL for testing"
    }
    
    return {
        "content_id": content_id,
        "user_id": user_id,
        "sample_texts": sample_texts,
        "sample_images": sample_images,
        "moderation_request_example": {
            "content_id": content_id,
            "content_type": "text",
            "text": sample_texts["positive"],
            "user_id": user_id
        },
        "moderation_with_image_example": {
            "content_id": content_id,
            "content_type": "image",
            "image_url": sample_images["safe_image"],
            "user_id": user_id
        }
    }


@router.get(
    "/generate-test-ad",
    summary="Generate Test Ad Data",
    description="""
    Generate test ad data for advertising APIs.
    
    Returns ad data including:
    - ad_id
    - Sample ad content
    - Target interests
    - Budget info
    """
)
async def generate_test_ad():
    """Generate test ad data."""
    ad_id = str(uuid.uuid4())
    
    interests = [
        "photography", "hiking", "cooking", "gaming", "music",
        "fitness", "travel", "technology", "art", "sports"
    ]
    
    locations = ["New York", "Los Angeles", "Chicago", "Miami", "Seattle"]
    
    target_interests = random.sample(interests, k=random.randint(2, 4))
    target_locations = random.sample(locations, k=random.randint(1, 3))
    
    return {
        "ad_id": ad_id,
        "ad_content": f"Join our amazing {target_interests[0]} community! Special offer for new members.",
        "target_interests": target_interests,
        "target_locations": target_locations,
        "target_age_min": 18,
        "target_age_max": 45,
        "budget": random.randint(100, 1000),
        "duration_days": random.randint(7, 30),
        "audience_match_request": {
            "ad_id": ad_id,
            "ad_content": f"Join our amazing {target_interests[0]} community!",
            "target_interests": target_interests,
            "target_locations": target_locations,
            "target_age_min": 18,
            "target_age_max": 45
        },
        "performance_predict_request": {
            "ad_id": ad_id,
            "budget": 500.0,
            "duration_days": 14,
            "audience_segment_ids": []
        }
    }


# ============================================
# FILE UPLOAD FOR TESTING
# ============================================

@router.post(
    "/upload-image-moderation",
    summary="Upload & Moderate Image (AI-Powered)",
    description="""
    Upload an image file and get **instant AI moderation results**.
    
    Uses HuggingFace NSFW detection model to analyze:
    - **NSFW/Nudity**: Sexual or explicit content
    - **Violence**: Gore, blood, disturbing content
    - **Hate Symbols**: Offensive imagery
    
    **Requirements:**
    - HUGGINGFACE_API_KEY must be set in environment
    - Supported formats: JPEG, PNG, GIF, WebP
    - Max file size: 5MB
    
    **Decision thresholds:**
    - score < 0.3: APPROVE (safe)
    - score 0.3-0.6: NEEDS_REVIEW
    - score > 0.6: REJECT (unsafe)
    """
)
async def upload_and_moderate_image(
    file: UploadFile = File(..., description="Image file to moderate (JPG, PNG, GIF, WebP)"),
    db: AsyncSession = Depends(get_db)
):
    """Upload an image and get AI moderation results."""
    from app.services.moderation_service import ModerationService
    
    # Validate file type
    allowed_types = ["image/jpeg", "image/png", "image/gif", "image/webp"]
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail=f"File type not allowed. Allowed: {allowed_types}"
        )
    
    # Read file content
    content = await file.read()
    
    # Check file size (max 5MB)
    if len(content) > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File too large. Max 5MB.")
    
    content_id = str(uuid.uuid4())
    
    try:
        # Moderate the image bytes directly
        moderation_result = await ModerationService.moderate_image_bytes(
            image_bytes=content,
            filename=file.filename
        )
        
        # Make decision based on scores
        labels = moderation_result.get("labels", [])
        max_score = moderation_result.get("max_score", 0)
        
        # Determine decision
        if max_score >= 0.6:
            decision = "reject"
            is_safe = False
        elif max_score >= 0.3:
            decision = "needs_review"
            is_safe = False
        else:
            decision = "approve"
            is_safe = True
        
        return {
            "content_id": content_id,
            "filename": file.filename,
            "content_type": file.content_type,
            "size_bytes": len(content),
            "is_safe": is_safe,  # TRUE = safe, FALSE = unsafe/rejected
            "moderation_result": {
                "decision": decision,  # "approve", "reject", or "needs_review"
                "nsfw_score": round(max_score, 2),  # 0.0 = safe, 1.0 = explicit
                "confidence": round(max_score * 100, 1),  # Percentage confidence it's NSFW
                "labels": labels,
                "model": moderation_result.get("model", "fallback"),
                "api_status": moderation_result.get("api_status", "unknown")
            },
            "message": f"Image {'REJECTED - NSFW content detected' if decision == 'reject' else 'FLAGGED for review' if decision == 'needs_review' else 'APPROVED - Safe content'}",
            "error": moderation_result.get("error")
        }
        
    except Exception as e:
        logger.error(f"Image upload moderation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/upload-image",
    summary="Upload Image (No Moderation)",
    description="""
    Upload an image file and get a base64 encoded version.
    
    **This does NOT moderate the image** - use `/upload-image-moderation` for that.
    
    The response includes:
    - Base64 encoded image data
    - A content_id you can use
    """
)
async def upload_image_for_testing(
    file: UploadFile = File(..., description="Image file to upload (JPG, PNG)")
):
    """Upload an image for testing (no moderation)."""
    # Validate file type
    allowed_types = ["image/jpeg", "image/png", "image/gif", "image/webp"]
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail=f"File type not allowed. Allowed: {allowed_types}"
        )
    
    # Read file content
    content = await file.read()
    
    # Check file size (max 5MB)
    if len(content) > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File too large. Max 5MB.")
    
    # Encode to base64
    base64_content = base64.b64encode(content).decode("utf-8")
    content_id = str(uuid.uuid4())
    
    return {
        "success": True,
        "content_id": content_id,
        "filename": file.filename,
        "content_type": file.content_type,
        "size_bytes": len(content),
        "base64_preview": base64_content[:100] + "..." if len(base64_content) > 100 else base64_content,
        "tip": "Use POST /testing/upload-image-moderation for AI-powered image moderation"
    }


@router.post(
    "/test-image-moderation",
    summary="Test Image Moderation by URL",
    description="""
    Test image moderation using a public image URL.
    
    The image will be analyzed for:
    - **NSFW/Nudity**: Sexual or explicit content
    - **Violence**: Gore, blood, disturbing content  
    - **Hate Symbols**: Offensive symbols or imagery
    
    **Requirements:**
    - HUGGINGFACE_API_KEY must be set for AI analysis
    - Image must be publicly accessible URL
    
    **Example URLs to test:**
    - Safe image: `https://upload.wikimedia.org/wikipedia/commons/thumb/4/47/PNG_transparency_demonstration_1.png/300px-PNG_transparency_demonstration_1.png`
    
    **Note**: The system uses HuggingFace's NSFW detection model when available.
    """
)
async def quick_test_image_moderation(
    image_url: str = Form(..., description="Public URL of image to moderate"),
    db: AsyncSession = Depends(get_db)
):
    """Quick test for image moderation by URL."""
    from app.services.moderation_service import ModerationService
    
    content_id = str(uuid.uuid4())
    
    try:
        result = await ModerationService.moderate_content(
            db=db,
            content_id=content_id,
            content_type="image",
            text=None,
            image_url=image_url,
            video_url=None,
            user_id=None
        )
        
        return {
            "input_url": image_url,
            "content_id": content_id,
            "result": result
        }
        
    except Exception as e:
        logger.error(f"Quick image moderation test error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/test-base64-image-moderation",
    summary="Test Base64 Image Moderation",
    description="""
    Moderate an image provided as base64 encoded string.
    
    **Use this when you have base64 image data** (e.g., from canvas, clipboard, etc.)
    
    **Format:**
    - Can include data URI prefix: `data:image/jpeg;base64,/9j/4AAQ...`
    - Or just the base64 string: `/9j/4AAQ...`
    
    **Requirements:**
    - HUGGINGFACE_API_KEY must be set for AI analysis
    """
)
async def test_base64_image_moderation(
    base64_image: str = Form(..., description="Base64 encoded image data"),
    db: AsyncSession = Depends(get_db)
):
    """Test image moderation with base64 encoded image."""
    from app.services.moderation_service import ModerationService
    
    content_id = str(uuid.uuid4())
    
    try:
        # Moderate the base64 image
        moderation_result = await ModerationService.moderate_base64_image(
            base64_data=base64_image,
            filename="base64_upload"
        )
        
        # Make decision based on scores
        labels = moderation_result.get("labels", [])
        max_score = moderation_result.get("max_score", 0)
        
        # Determine decision
        if max_score >= 0.6:
            decision = "reject"
        elif max_score >= 0.3:
            decision = "needs_review"
        else:
            decision = "approve"
        
        return {
            "content_id": content_id,
            "moderation": {
                "decision": decision,
                "confidence": round(1.0 - max_score, 2),
                "max_score": round(max_score, 2),
                "labels": labels,
                "model": moderation_result.get("model", "fallback"),
                "api_status": moderation_result.get("api_status", "unknown")
            },
            "error": moderation_result.get("error")
        }
        
    except Exception as e:
        logger.error(f"Base64 image moderation test error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/test-text-moderation",
    summary="Quick Test Text Moderation",
    description="""
    Quickly test text moderation without needing to construct the full request.
    
    Just provide the text you want to moderate!
    
    **Categories detected:**
    - **Sexual**: Explicit sexual content, profanity
    - **Hate**: Hate speech, slurs, discrimination
    - **Violence**: Threats, violent content
    - **Toxicity**: Insults, harassment
    - **Spam**: Promotional content, excessive caps
    
    **Decision thresholds:**
    - Sexual/Hate: 0.30 (very sensitive)
    - Violence: 0.40
    - Toxicity: 0.60
    - Spam: 0.70
    """
)
async def quick_test_moderation(
    text: str = Form(..., description="Text to moderate"),
    db: AsyncSession = Depends(get_db)
):
    """Quick test for text moderation."""
    from app.services.moderation_service import ModerationService
    
    content_id = str(uuid.uuid4())
    
    try:
        result = await ModerationService.moderate_content(
            db=db,
            content_id=content_id,
            content_type="text",
            text=text,
            image_url=None,
            video_url=None,
            user_id=None
        )
        
        return {
            "input_text": text,
            "content_id": content_id,
            "result": result
        }
        
    except Exception as e:
        logger.error(f"Quick moderation test error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/test-sentiment",
    summary="Quick Test Sentiment Analysis",
    description="""
    Quickly test sentiment analysis on any text.
    
    Just provide the text - no other fields needed!
    """
)
async def quick_test_sentiment(
    text: str = Form(..., description="Text to analyze"),
    db: AsyncSession = Depends(get_db)
):
    """Quick test for sentiment analysis."""
    from app.services.nlp_service import NLPService
    
    try:
        result = await NLPService.analyze_sentiment(text)
        
        return {
            "input_text": text,
            "result": result
        }
        
    except Exception as e:
        logger.error(f"Quick sentiment test error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/test-keywords",
    summary="Quick Test Keyword Extraction",
    description="""
    Quickly test keyword extraction on any text.
    """
)
async def quick_test_keywords(
    text: str = Form(..., description="Text to extract keywords from"),
    max_keywords: int = Form(10, description="Max keywords to extract")
):
    """Quick test for keyword extraction."""
    from app.services.nlp_service import NLPService
    
    try:
        result = await NLPService.extract_keywords(text, max_keywords)
        
        return {
            "input_text": text,
            "result": result
        }
        
    except Exception as e:
        logger.error(f"Quick keyword test error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/test-chatbot",
    summary="Quick Test Chatbot",
    description="""
    Quickly test the chatbot with a question.
    
    Just type your question - no user_id needed!
    """
)
async def quick_test_chatbot(
    question: str = Form(..., description="Your question"),
    language: str = Form("en", description="Language code (en, fr, es, zh, ar, de)"),
    db: AsyncSession = Depends(get_db)
):
    """Quick test for chatbot."""
    from app.services.chatbot_service import ChatbotService
    
    user_id = str(uuid.uuid4())
    
    try:
        result = await ChatbotService.ask(
            db=db,
            query=question,
            user_id=user_id,
            language=language
        )
        
        return {
            "question": question,
            "language": language,
            "user_id": user_id,
            "result": result
        }
        
    except Exception as e:
        logger.error(f"Quick chatbot test error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/test-translation",
    summary="Quick Test Translation",
    description="""
    Quickly test translation between languages.
    """
)
async def quick_test_translation(
    text: str = Form(..., description="Text to translate"),
    source_lang: str = Form("en", description="Source language (en, fr, es, de, zh, ar)"),
    target_lang: str = Form("fr", description="Target language (en, fr, es, de, zh, ar)")
):
    """Quick test for translation."""
    from app.services.translation_service import TranslationService
    
    try:
        result = await TranslationService.translate_text(
            text=text,
            source_lang=source_lang,
            target_lang=target_lang
        )
        
        return {
            "input_text": text,
            "source_lang": source_lang,
            "target_lang": target_lang,
            "result": result
        }
        
    except Exception as e:
        logger.error(f"Quick translation test error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================
# SAMPLE API CALLS
# ============================================

@router.get(
    "/sample-api-calls",
    summary="Get Sample API Calls",
    description="""
    Get sample request bodies for all APIs.
    
    Copy-paste these into Swagger UI to test endpoints!
    """
)
async def get_sample_api_calls():
    """Get sample API calls for all endpoints."""
    user_id = str(uuid.uuid4())
    event_id = str(uuid.uuid4())
    content_id = str(uuid.uuid4())
    host_id = str(uuid.uuid4())
    ad_id = str(uuid.uuid4())
    
    return {
        "generated_ids": {
            "user_id": user_id,
            "event_id": event_id,
            "content_id": content_id,
            "host_id": host_id,
            "ad_id": ad_id
        },
        "sample_calls": {
            "moderation": {
                "POST /moderation": {
                    "content_id": content_id,
                    "content_type": "text",
                    "text": "This is a great event! I really enjoyed it.",
                    "user_id": user_id
                }
            },
            "chatbot": {
                "POST /chatbot/ask": {
                    "query": "How do I create an event?",
                    "user_id": user_id,
                    "language": "en"
                }
            },
            "nlp": {
                "POST /nlp/sentiment": {
                    "text": "I absolutely loved this hiking trip! The views were breathtaking.",
                    "content_id": content_id,
                    "content_type": "event_review"
                },
                "POST /nlp/keywords": {
                    "text": "Looking for photography workshops in downtown Chicago near the Art Institute.",
                    "max_keywords": 10
                }
            },
            "rating": {
                "POST /rating/event/{event_id}": {
                    "user_id": user_id,
                    "rating": 5,
                    "feedback": "Excellent event, very well organized!"
                }
            },
            "recommendations": {
                "GET /recommendations/hobbies": f"?user_id={user_id}&limit=10",
                "GET /recommendations/events": f"?user_id={user_id}&limit=10"
            },
            "ads": {
                "POST /ads/audience-match": {
                    "ad_id": ad_id,
                    "ad_content": "Join our photography community!",
                    "target_interests": ["photography", "art"],
                    "target_locations": ["New York", "Los Angeles"],
                    "target_age_min": 18,
                    "target_age_max": 45
                },
                "POST /ads/performance-predict": {
                    "ad_id": ad_id,
                    "budget": 500.0,
                    "duration_days": 14,
                    "audience_segment_ids": []
                }
            },
            "rewards": {
                "GET /rewards/suggestion": f"?user_id={user_id}",
                "GET /rewards/progress/{user_id}": f"/{user_id}"
            },
            "matching": {
                "GET /match/events": f"?user_id={user_id}&lat=40.7128&lon=-74.0060&max_distance_km=50"
            },
            "predictions": {
                "POST /predict/attendance": {
                    "event_id": event_id,
                    "event_date": (datetime.utcnow() + timedelta(days=7)).isoformat(),
                    "category": "photography",
                    "location": "New York",
                    "capacity": 50,
                    "host_id": host_id
                },
                "GET /predict/trends": "?category=photography&location=New York",
                "GET /predict/no-show-rate": "?category=photography&is_free=true&days_until_event=7"
            },
            "translation": {
                "POST /translate": {
                    "text": "Hello, how are you?",
                    "source_language": "en",
                    "target_language": "fr"
                }
            }
        }
    }


# ==============================================================================
# HUGGINGFACE API STATUS CHECK
# ==============================================================================

@router.get(
    "/huggingface-status",
    summary="Check HuggingFace API Status",
    description="""
    Check if HuggingFace API is properly configured and accessible.
    
    **This helps diagnose image moderation issues:**
    - Is HUGGINGFACE_API_KEY set?
    - Is the API accessible?
    - Is the model loaded?
    
    **Common issues:**
    - Missing API key → Set HUGGINGFACE_API_KEY in .env
    - Model loading → Wait 20-30 seconds and retry
    - Rate limited → Wait or upgrade HuggingFace plan
    """
)
async def check_huggingface_status():
    """Check HuggingFace API configuration and status."""
    import httpx
    from app.config import settings
    
    status = {
        "api_key_configured": bool(settings.HUGGINGFACE_API_KEY),
        "image_analysis_enabled": settings.IMAGE_ANALYSIS_ENABLED,
        "model": "Falconsai/nsfw_image_detection",
        "api_status": "unknown",
        "api_message": None,
        "recommendation": None
    }
    
    if not settings.HUGGINGFACE_API_KEY:
        status["api_status"] = "not_configured"
        status["api_message"] = "HUGGINGFACE_API_KEY not set"
        status["recommendation"] = "Add HUGGINGFACE_API_KEY to your .env file. Get a free key at https://huggingface.co/settings/tokens"
        return status
    
    if not settings.IMAGE_ANALYSIS_ENABLED:
        status["api_status"] = "disabled"
        status["api_message"] = "IMAGE_ANALYSIS_ENABLED is False"
        status["recommendation"] = "Set IMAGE_ANALYSIS_ENABLED=true in your .env file"
        return status
    
    # Try to check model status using new HuggingFace Router endpoint
    # NOTE: api-inference.huggingface.co is deprecated (returns 410 Gone)
    try:
        api_url = "https://router.huggingface.co/hf-inference/models/Falconsai/nsfw_image_detection"
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            # Check the model via POST with empty/minimal request
            response = await client.post(
                api_url,
                headers={
                    "Authorization": f"Bearer {settings.HUGGINGFACE_API_KEY}",
                    "Content-Type": "application/octet-stream"
                },
                content=b""  # Empty content to check if API is accessible
            )
            
            # Note: Empty content may return 400 (bad request) but that means API is reachable
            if response.status_code == 200:
                status["api_status"] = "ready"
                status["api_message"] = "Model is loaded and ready"
            elif response.status_code == 400:
                # 400 with empty content means API is working, just needs valid image
                status["api_status"] = "ready"
                status["api_message"] = "API is accessible (empty test request rejected as expected)"
            elif response.status_code == 401:
                status["api_status"] = "auth_failed"
                status["api_message"] = "Invalid API key"
                status["recommendation"] = "Check your HUGGINGFACE_API_KEY is correct"
            elif response.status_code == 410:
                status["api_status"] = "deprecated"
                status["api_message"] = "API endpoint is deprecated"
                status["recommendation"] = "Update to router.huggingface.co (contact developer)"
            elif response.status_code == 503:
                status["api_status"] = "loading"
                status["api_message"] = "Model is loading, please wait 20-30 seconds"
                status["recommendation"] = "Retry in 30 seconds, model needs to cold-start"
            else:
                status["api_status"] = f"error_{response.status_code}"
                status["api_message"] = response.text[:200]
                
    except httpx.TimeoutException:
        status["api_status"] = "timeout"
        status["api_message"] = "Request timed out"
        status["recommendation"] = "Network issue or HuggingFace is slow, retry"
    except Exception as e:
        status["api_status"] = "error"
        status["api_message"] = str(e)
    
    return status

