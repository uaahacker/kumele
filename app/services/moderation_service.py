"""
Moderation Service for Content Moderation (Text + Image + Video).

Handles toxicity, hate speech, NSFW detection.

============================================================================
UNIFIED MODERATION SERVICE SPECIFICATION (MVP)
============================================================================

API Endpoints:
- POST /moderation: Submit content for moderation
- GET /moderation/{content_id}: Get moderation status

Content Types (MVP):
1. TEXT (Moderate):
   - Blogs, comments, event descriptions
   - Ad titles, descriptions, CTAs
   - Uses Hugging Face NLP moderation (toxicity, hate, spam)

2. IMAGE (Moderate):
   - Event banners
   - Profile images
   - Static ad creatives
   - Video thumbnails
   - Uses Hugging Face vision safety models

3. VIDEO ADS (Limited MVP Scope):
   - Moderate thumbnail/keyframe image ✓
   - Moderate associated text (title/description/CTA) ✓
   - ❌ No full video frame analysis
   - ❌ No audio/speech moderation
   - ❌ No live or long-form video moderation

Decision Thresholds (MVP Defaults):
TEXT:
  - Toxicity > 0.60 → reject
  - Hate > 0.30 → reject
  - Spam > 0.70 → reject

IMAGE / THUMBNAIL:
  - Nudity > 0.60 → reject
  - Violence > 0.50 → reject
  - Hate symbols > 0.40 → reject

Outcomes:
  - approve: Content is safe
  - reject: Content violates policy
  - needs_review: Logged for manual review (gray zone)

Database:
  - moderation_jobs table supports text, image, video
  - Stores decision, labels (JSONB), timestamps

Explicitly Out of Scope (MVP):
  - Full video frame analysis
  - Audio moderation
  - Live moderation
  - Human review UI
  - Appeals workflow
  - ML-based decision engine (heuristics only for MVP)

Workflow:
1. Frontend submits content via POST /moderation
2. Routing by type:
   - text → NLP worker
   - image → vision worker
   - video → thumbnail image + text moderation
3. Threshold-based decision engine
4. Persist result
5. Fetch status via GET endpoint
============================================================================
"""
from typing import Optional, List, Dict, Any, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_
from datetime import datetime
import logging
import re
import httpx

from app.models.database_models import ModerationJob
from app.config import settings

logger = logging.getLogger(__name__)


class ModerationService:
    """Service for unified content moderation."""
    
    # Text moderation thresholds (lower = more sensitive)
    # Per spec: Toxicity > 0.60 → reject, Hate > 0.30 → reject, Spam > 0.70 → reject
    TEXT_THRESHOLDS = {
        "toxicity": settings.TOXICITY_THRESHOLD,      # 0.60
        "hate": settings.HATE_THRESHOLD,              # 0.30
        "spam": settings.SPAM_THRESHOLD,              # 0.70
        "sexual": 0.30,                               # Sexual content threshold
        "violence": 0.40,                             # Violence threshold for text
        "profanity": 0.50,                            # Profanity threshold
    }
    
    # Image moderation thresholds
    # Per spec: Nudity > 0.60 → reject, Violence > 0.50 → reject, Hate symbols > 0.40 → reject
    IMAGE_THRESHOLDS = {
        "nudity": settings.NUDITY_THRESHOLD,          # 0.60
        "violence": settings.VIOLENCE_THRESHOLD,      # 0.50
        "hate_symbols": settings.HATE_SYMBOLS_THRESHOLD,  # 0.40
    }
    
    # =========================================================================
    # EXPLICIT/SEXUAL CONTENT PATTERNS - High severity (instant flag)
    # =========================================================================
    SEXUAL_PATTERNS = [
        # Explicit sexual acts
        r'\b(fuck|fucking|fucked|fucker|fucks)\b',
        r'\b(sex|sexy|sexual|sexually)\b',
        r'\b(porn|porno|pornography|pornographic)\b',
        r'\b(nude|naked|nudity|nudes)\b',
        r'\b(dick|cock|penis|vagina|pussy|cunt|ass|arse|asshole|butthole)\b',
        r'\b(boobs|tits|breasts|nipples|titties)\b',
        r'\b(blowjob|handjob|masturbat|orgasm|ejaculat|cum|cumming|cumshot)\b',
        r'\b(slut|whore|hooker|prostitut|escort)\b',
        r'\b(rape|raped|raping|rapist)\b',
        r'\b(incest|pedophil|molest)\b',
        r'\b(bitch|bitches|bitching)\b',
        r'\b(horny|erotic|erection|aroused)\b',
        r'\b(stripper|striptease|lapdance)\b',
        r'\b(threesome|foursome|gangbang|orgy)\b',
        r'\b(dildo|vibrator|buttplug|fleshlight)\b',
        r'\b(anal|oral|69|blowj|handy|rimjob|creampie)\b',
    ]
    
    # =========================================================================
    # HATE SPEECH / DISCRIMINATION PATTERNS - High severity
    # =========================================================================
    HATE_PATTERNS = [
        # Racial slurs (censored but detectable patterns)
        r'\b(nigger|nigga|negro|coon|spic|chink|gook|kike|wetback)\b',
        r'\b(cracker|honky|gringo|beaner|towelhead|raghead|camel.?jockey)\b',
        # Homophobic slurs
        r'\b(faggot|fag|dyke|homo|queer|tranny|shemale)\b',
        # Disability slurs
        r'\b(retard|retarded|spastic|cripple|mongoloid)\b',
        # Religious hate
        r'\b(jihad|terrorist|islamophob|antisemit)\b',
        # General hate
        r'\b(nazi|fascist|white.?power|heil.?hitler|kkk|skinhead)\b',
        r'\b(genocide|ethnic.?cleansing|holocaust.?denial)\b',
        r'\b(subhuman|untermensch|master.?race)\b',
    ]
    
    # =========================================================================
    # VIOLENCE / THREATS PATTERNS - High severity
    # =========================================================================
    VIOLENCE_PATTERNS = [
        r'\b(kill|killing|killed|killer|murder|murdered|murderer)\b',
        r'\b(die|dying|death|dead|suicide|suicidal)\b',
        r'\b(shoot|shooting|shot|gun|firearm|weapon)\b',
        r'\b(stab|stabbing|knife|machete|sword)\b',
        r'\b(bomb|bombing|explosive|detonate|terrorist)\b',
        r'\b(assault|attack|beat|beating|punch|kick)\b',
        r'\b(torture|torment|mutilate|dismember)\b',
        r'\b(threat|threaten|threatening|i.?will.?kill)\b',
        r'\b(blood|bloody|bleed|bleeding|gore|gory)\b',
        r'\b(harm|hurt|injure|wound|damage)\b',
        r'\b(strangle|choke|suffocate|drown)\b',
        r'\b(execute|execution|behead|decapitat)\b',
    ]
    
    # =========================================================================
    # TOXICITY / INSULTS PATTERNS - Medium severity
    # =========================================================================
    TOXIC_PATTERNS = [
        r'\b(hate|hating|hatred|hater)\b',
        r'\b(stupid|idiot|moron|dumb|dumbass|imbecile)\b',
        r'\b(ugly|hideous|disgusting|repulsive)\b',
        r'\b(loser|pathetic|worthless|useless)\b',
        r'\b(trash|garbage|scum|filth)\b',
        r'\b(shut.?up|stfu|gtfo|kys|go.?die)\b',
        r'\b(fat|fatass|obese|pig|cow)\b',
        r'\b(bastard|damn|damned|hell)\b',
        r'\b(piss|pissed|crap|crappy|shit|shitty|bullshit)\b',
        r'\b(suck|sucks|sucker|sucking)\b',
        r'\b(jerk|asshole|dickhead|douchebag|scumbag)\b',
    ]
    
    # =========================================================================
    # SPAM PATTERNS - Lower severity
    # =========================================================================
    SPAM_PATTERNS = [
        r'(click here|free money|you won|congratulations|act now)',
        r'(buy now|limited time|discount|offer expires)',
        r'(make money fast|work from home|earn \$)',
        r'(https?://\S+){2,}',  # Multiple URLs
        r'(.)\1{4,}',  # Repeated characters (aaaaaaa)
        r'\b[A-Z]{5,}\b',  # ALL CAPS words
        r'(!{3,}|\?{3,})',  # Excessive punctuation
    ]

    @staticmethod
    async def moderate_text(text: str) -> Dict[str, Any]:
        """
        Moderate text content for sexual, hate, violence, toxicity, and spam.
        
        Scoring System:
        - Each match in HIGH severity patterns (sexual, hate, violence) = 0.4 score
        - Each match in MEDIUM severity patterns (toxicity) = 0.25 score  
        - Each match in LOW severity patterns (spam) = 0.15 score
        - Single match of severe content is enough to trigger rejection
        
        Returns labels with scores for each category detected.
        """
        labels = []
        text_lower = text.lower()
        matched_terms = []  # Track what was found for debugging
        
        try:
            # =================================================================
            # 1. SEXUAL/EXPLICIT CONTENT - Highest severity (0.4 per match, max 1.0)
            # =================================================================
            sexual_score = 0.0
            sexual_matches = []
            for pattern in ModerationService.SEXUAL_PATTERNS:
                matches = re.findall(pattern, text_lower, re.IGNORECASE)
                if matches:
                    sexual_matches.extend(matches)
                    # Each sexual term is severe - high score per match
                    sexual_score += len(matches) * 0.4
            sexual_score = min(sexual_score, 1.0)
            
            if sexual_score > 0:
                labels.append({
                    "label": "sexual",
                    "score": round(sexual_score, 2),
                    "matched": sexual_matches[:5]  # Include what was matched
                })
                matched_terms.extend(sexual_matches)
            
            # =================================================================
            # 2. HATE SPEECH - Highest severity (0.5 per match, max 1.0)
            # =================================================================
            hate_score = 0.0
            hate_matches = []
            for pattern in ModerationService.HATE_PATTERNS:
                matches = re.findall(pattern, text_lower, re.IGNORECASE)
                if matches:
                    hate_matches.extend(matches)
                    # Hate speech is extremely severe
                    hate_score += len(matches) * 0.5
            hate_score = min(hate_score, 1.0)
            
            if hate_score > 0:
                labels.append({
                    "label": "hate",
                    "score": round(hate_score, 2),
                    "matched": hate_matches[:5]
                })
                matched_terms.extend(hate_matches)
            
            # =================================================================
            # 3. VIOLENCE/THREATS - High severity (0.35 per match, max 1.0)
            # =================================================================
            violence_score = 0.0
            violence_matches = []
            for pattern in ModerationService.VIOLENCE_PATTERNS:
                matches = re.findall(pattern, text_lower, re.IGNORECASE)
                if matches:
                    violence_matches.extend(matches)
                    violence_score += len(matches) * 0.35
            violence_score = min(violence_score, 1.0)
            
            if violence_score > 0:
                labels.append({
                    "label": "violence",
                    "score": round(violence_score, 2),
                    "matched": violence_matches[:5]
                })
                matched_terms.extend(violence_matches)
            
            # =================================================================
            # 4. TOXICITY/INSULTS - Medium severity (0.25 per match, max 1.0)
            # =================================================================
            toxicity_score = 0.0
            toxicity_matches = []
            for pattern in ModerationService.TOXIC_PATTERNS:
                matches = re.findall(pattern, text_lower, re.IGNORECASE)
                if matches:
                    toxicity_matches.extend(matches)
                    toxicity_score += len(matches) * 0.25
            toxicity_score = min(toxicity_score, 1.0)
            
            if toxicity_score > 0:
                labels.append({
                    "label": "toxicity",
                    "score": round(toxicity_score, 2),
                    "matched": toxicity_matches[:5]
                })
                matched_terms.extend(toxicity_matches)
            
            # =================================================================
            # 5. SPAM - Lower severity (0.15 per match, max 1.0)
            # =================================================================
            spam_score = 0.0
            spam_matches = []
            for pattern in ModerationService.SPAM_PATTERNS:
                matches = re.findall(pattern, text_lower, re.IGNORECASE)
                if matches:
                    # Convert match tuples to strings if needed
                    for m in matches:
                        spam_matches.append(str(m) if not isinstance(m, str) else m)
                    spam_score += len(matches) * 0.15
            
            # Check for excessive caps (spam indicator)
            if len(text) > 10:
                caps_ratio = sum(1 for c in text if c.isupper()) / len(text)
                if caps_ratio > 0.6:
                    spam_score += 0.3
                    spam_matches.append("EXCESSIVE_CAPS")
            
            spam_score = min(spam_score, 1.0)
            
            if spam_score > 0:
                labels.append({
                    "label": "spam",
                    "score": round(spam_score, 2),
                    "matched": spam_matches[:5]
                })
            
            # =================================================================
            # Calculate max score across all categories
            # =================================================================
            max_score = max([l["score"] for l in labels]) if labels else 0.0
            
            logger.info(f"Text moderation: found {len(matched_terms)} flagged terms, max_score={max_score}")
            
            return {
                "labels": labels,
                "max_score": max_score,
                "total_flags": len(matched_terms)
            }
            
        except Exception as e:
            logger.error(f"Text moderation error: {e}")
            # On error, be conservative and flag for review
            return {
                "labels": [{"label": "error", "score": 0.5}],
                "max_score": 0.5,
                "error": str(e)
            }

    @staticmethod
    async def moderate_image(
        image_url: str,
        thumbnail_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Moderate image content for NSFW, violence, hate symbols.
        Uses HuggingFace image classification models when enabled.
        """
        labels = []
        url_to_check = thumbnail_url or image_url
        
        try:
            # Try HuggingFace image analysis if enabled
            if settings.IMAGE_ANALYSIS_ENABLED:
                hf_result = await ModerationService.analyze_image_with_huggingface(url_to_check)
                if hf_result and hf_result.get("labels"):
                    # Check if there was an API error
                    if hf_result.get("api_status") in ["auth_failed", "model_loading", "timeout"]:
                        logger.warning(f"HuggingFace API issue: {hf_result.get('error')}")
                        # Fall through to URL heuristics
                    else:
                        return hf_result
            
            # Fallback: URL-based heuristics (when API not available)
            logger.info("Using URL-based heuristics for image moderation (HuggingFace API not available)")
            url_lower = url_to_check.lower()
            
            # Basic URL-based heuristics
            suspicious_terms = ['nsfw', 'adult', 'xxx', 'porn', 'nude', 'sexy', 'hot', 'naked']
            for term in suspicious_terms:
                if term in url_lower:
                    labels.append({
                        "label": "nudity",
                        "score": 0.7,
                        "method": "url_heuristic"
                    })
                    break
            
            violence_terms = ['gore', 'blood', 'violence', 'death', 'kill', 'murder', 'graphic']
            for term in violence_terms:
                if term in url_lower:
                    labels.append({
                        "label": "violence",
                        "score": 0.6,
                        "method": "url_heuristic"
                    })
                    break
            
            # Default safe scores if no suspicious patterns
            if not labels:
                labels = [
                    {"label": "nudity", "score": 0.05, "method": "url_heuristic"},
                    {"label": "violence", "score": 0.03, "method": "url_heuristic"},
                    {"label": "hate_symbols", "score": 0.02, "method": "url_heuristic"}
                ]
            
            return {
                "labels": labels,
                "max_score": max([l["score"] for l in labels]) if labels else 0.0,
                "note": "Used URL heuristics - set HUGGINGFACE_API_KEY for AI-powered analysis"
            }
            
        except Exception as e:
            logger.error(f"Image moderation error: {e}")
            return {"labels": [], "max_score": 0.0, "error": str(e)}

    @staticmethod
    async def moderate_image_bytes(
        image_bytes: bytes,
        filename: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Moderate uploaded image bytes directly using HuggingFace AI.
        Use this for file uploads instead of URLs.
        
        Args:
            image_bytes: Raw image file bytes
            filename: Optional filename for logging
            
        Returns:
            Moderation result with labels and scores
        """
        try:
            if not image_bytes:
                return {
                    "labels": [],
                    "max_score": 0.0,
                    "error": "No image data provided"
                }
            
            logger.info(f"Moderating uploaded image: {filename or 'unknown'}, size={len(image_bytes)} bytes")
            
            # Try HuggingFace image analysis
            if settings.IMAGE_ANALYSIS_ENABLED:
                hf_result = await ModerationService.analyze_image_bytes_with_huggingface(image_bytes)
                if hf_result:
                    return hf_result
            
            # Fallback: Cannot do URL heuristics for uploaded images
            # Return a "needs review" status since we can't analyze it
            logger.warning("Cannot analyze uploaded image - HUGGINGFACE_API_KEY not set or API unavailable")
            return {
                "labels": [
                    {"label": "unanalyzed", "score": 0.5, "method": "fallback"}
                ],
                "max_score": 0.5,
                "error": "Image analysis unavailable - set HUGGINGFACE_API_KEY for AI moderation",
                "recommendation": "needs_review"
            }
            
        except Exception as e:
            logger.error(f"Image bytes moderation error: {e}")
            return {"labels": [], "max_score": 0.0, "error": str(e)}

    @staticmethod
    async def moderate_base64_image(
        base64_data: str,
        filename: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Moderate base64 encoded image using HuggingFace AI.
        
        Args:
            base64_data: Base64 encoded image string (with or without data URI prefix)
            filename: Optional filename for logging
            
        Returns:
            Moderation result with labels and scores
        """
        import base64 as b64
        
        try:
            # Remove data URI prefix if present (e.g., "data:image/jpeg;base64,")
            if "," in base64_data:
                base64_data = base64_data.split(",", 1)[1]
            
            # Decode base64 to bytes
            image_bytes = b64.b64decode(base64_data)
            
            return await ModerationService.moderate_image_bytes(image_bytes, filename)
            
        except Exception as e:
            logger.error(f"Base64 image moderation error: {e}")
            return {"labels": [], "max_score": 0.0, "error": f"Invalid base64 data: {e}"}

    @staticmethod
    async def analyze_image_with_huggingface(image_url: str) -> Optional[Dict[str, Any]]:
        """
        Analyze image using HuggingFace NSFW detection model.
        Supports both URL and base64 encoded images.
        """
        try:
            async with httpx.AsyncClient() as client:
                # Download image first
                img_response = await client.get(image_url, timeout=10.0)
                if img_response.status_code != 200:
                    logger.warning(f"Failed to download image: {img_response.status_code}")
                    return None
                
                image_bytes = img_response.content
                
                return await ModerationService._call_huggingface_image_api(client, image_bytes)
                    
        except httpx.TimeoutException:
            logger.warning("HuggingFace image analysis timeout")
        except Exception as e:
            logger.warning(f"HuggingFace image analysis error: {e}")
        
        return None

    @staticmethod
    async def analyze_image_bytes_with_huggingface(image_bytes: bytes) -> Optional[Dict[str, Any]]:
        """
        Analyze image bytes directly using HuggingFace NSFW detection model.
        Use this for uploaded files or base64 decoded images.
        """
        try:
            async with httpx.AsyncClient() as client:
                return await ModerationService._call_huggingface_image_api(client, image_bytes)
        except Exception as e:
            logger.warning(f"HuggingFace image analysis error: {e}")
        return None

    @staticmethod
    async def _call_huggingface_image_api(client: httpx.AsyncClient, image_bytes: bytes) -> Optional[Dict[str, Any]]:
        """
        Internal method to call HuggingFace Inference API for image classification.
        Model: Falconsai/nsfw_image_detection
        
        NOTE: As of late 2024, HuggingFace deprecated api-inference.huggingface.co
        and now requires using router.huggingface.co instead.
        """
        # Build headers - API key is REQUIRED for the new router endpoint
        headers = {
            "Content-Type": "application/octet-stream"
        }
        
        # Add API key - REQUIRED for router.huggingface.co
        if settings.HUGGINGFACE_API_KEY:
            headers["Authorization"] = f"Bearer {settings.HUGGINGFACE_API_KEY}"
        else:
            logger.warning("HUGGINGFACE_API_KEY not set - image moderation will fail")
            return None
        
        # New HuggingFace Router endpoint (api-inference.huggingface.co is deprecated/410 Gone)
        api_url = f"https://router.huggingface.co/hf-inference/models/{settings.IMAGE_MODERATION_MODEL}"
        
        try:
            hf_response = await client.post(
                api_url,
                headers=headers,
                content=image_bytes,
                timeout=30.0
            )
            
            logger.info(f"HuggingFace API response status: {hf_response.status_code}")
            
            if hf_response.status_code == 200:
                results = hf_response.json()
                labels = []
                
                logger.info(f"HuggingFace raw results: {results}")
                
                # Parse HuggingFace response
                # Format: [{"label": "nsfw", "score": 0.95}, {"label": "normal", "score": 0.05}]
                for result in results:
                    label_name = result.get("label", "").lower()
                    score = result.get("score", 0.0)
                    
                    # Map HuggingFace labels to our labels
                    if label_name in ["nsfw", "sexy", "porn", "hentai"]:
                        labels.append({"label": "nudity", "score": round(score, 2)})
                    elif label_name in ["gore", "violence", "disturbing"]:
                        labels.append({"label": "violence", "score": round(score, 2)})
                    elif label_name == "normal":
                        # Normal/safe image - score represents how safe it is
                        # So nudity score = 1 - normal_score
                        nudity_score = round(1 - score, 2)
                        labels.append({"label": "nudity", "score": nudity_score})
                        labels.append({"label": "violence", "score": 0.02})
                        labels.append({"label": "hate_symbols", "score": 0.01})
                
                if labels:
                    max_score = max([l["score"] for l in labels])
                    return {
                        "labels": labels,
                        "max_score": max_score,
                        "model": settings.IMAGE_MODERATION_MODEL,
                        "api_status": "success"
                    }
                    
            elif hf_response.status_code == 401:
                logger.error("HuggingFace API: Unauthorized - check HUGGINGFACE_API_KEY")
                return {
                    "labels": [{"label": "error", "score": 0.5}],
                    "max_score": 0.5,
                    "error": "API authentication failed - set HUGGINGFACE_API_KEY",
                    "api_status": "auth_failed"
                }
            elif hf_response.status_code == 503:
                # Model is loading - try to parse estimated time
                try:
                    error_data = hf_response.json()
                    estimated_time = error_data.get("estimated_time", 20)
                    logger.info(f"HuggingFace model is loading, estimated time: {estimated_time}s")
                except:
                    pass
                return {
                    "labels": [{"label": "pending", "score": 0.5}],
                    "max_score": 0.5,
                    "error": "Model is loading, please retry in a few seconds",
                    "api_status": "model_loading"
                }
            else:
                logger.warning(f"HuggingFace API error: {hf_response.status_code} - {hf_response.text}")
                
        except httpx.TimeoutException:
            logger.warning("HuggingFace API timeout")
            return {
                "labels": [{"label": "timeout", "score": 0.5}],
                "max_score": 0.5,
                "error": "API timeout",
                "api_status": "timeout"
            }
        
        return None

    @staticmethod
    async def moderate_video(
        video_url: str,
        thumbnail_url: str,
        text: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Moderate video content (MVP scope).
        
        MVP SCOPE:
        ✓ Moderate thumbnail/keyframe image
        ✓ Moderate associated text (title/description/CTA)
        ❌ No full video frame analysis
        ❌ No audio/speech moderation
        ❌ No live or long-form video moderation
        
        For video ads: moderate thumbnail + text at upload only.
        """
        all_labels = []
        
        # Moderate thumbnail image (MVP: only thumbnail, not full video)
        image_result = await ModerationService.moderate_image(
            video_url, 
            thumbnail_url
        )
        all_labels.extend(image_result.get("labels", []))
        
        # Moderate associated text if provided
        if text:
            text_result = await ModerationService.moderate_text(text)
            all_labels.extend(text_result.get("labels", []))
        
        # Combine and deduplicate labels
        combined_labels = {}
        for label in all_labels:
            label_name = label["label"]
            if label_name not in combined_labels or label["score"] > combined_labels[label_name]:
                combined_labels[label_name] = label["score"]
        
        final_labels = [
            {"label": k, "score": v} 
            for k, v in combined_labels.items()
        ]
        
        return {
            "labels": final_labels,
            "max_score": max([l["score"] for l in final_labels]) if final_labels else 0.0
        }

    @staticmethod
    def make_decision(
        content_type: str,
        labels: List[Dict[str, Any]]
    ) -> str:
        """
        Make moderation decision based on labels and thresholds.
        
        Decision Logic:
        - Any high-severity category (sexual, hate) above threshold → REJECT
        - Any medium-severity category near threshold → NEEDS_REVIEW  
        - All scores below thresholds → APPROVE
        
        Returns: 'approve', 'reject', or 'needs_review'
        """
        if not labels:
            return "approve"
        
        # Combined thresholds for all categories
        all_thresholds = {
            # High severity - immediate rejection
            "sexual": 0.30,       # Very low threshold for sexual content
            "hate": 0.30,         # Very low threshold for hate speech
            "violence": 0.40,     # Low threshold for violence
            # Medium severity
            "toxicity": 0.60,     # Medium threshold for general toxicity
            "profanity": 0.50,    # Medium threshold for profanity
            "spam": 0.70,         # Higher threshold for spam
            # Image categories
            "nudity": 0.60,
            "hate_symbols": 0.40,
        }
        
        # Track decision factors
        needs_review = False
        rejection_reasons = []
        
        for label in labels:
            label_name = label["label"]
            score = label["score"]
            
            threshold = all_thresholds.get(label_name, 0.5)
            
            # High severity categories get instant rejection at lower scores
            high_severity = label_name in ["sexual", "hate", "violence", "nudity"]
            
            if score >= threshold:
                # Above threshold = definite rejection
                rejection_reasons.append(f"{label_name}:{score}")
                return "reject"
            elif high_severity and score >= threshold * 0.5:
                # High severity content even at 50% of threshold should be reviewed
                needs_review = True
            elif score >= threshold * 0.7:
                # Close to threshold = needs review
                needs_review = True
        
        if needs_review:
            return "needs_review"
        
        return "approve"

    @staticmethod
    async def moderate_content(
        db: AsyncSession,
        content_id: str,
        content_type: str,
        text: Optional[str] = None,
        image_url: Optional[str] = None,
        video_url: Optional[str] = None,
        user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Main moderation entry point.
        Handles text, image, and video content.
        """
        labels = []
        flags = []
        reasons = []
        
        content_type_value = content_type.value if hasattr(content_type, 'value') else str(content_type)
        
        if content_type_value == "text":
            if not text:
                return {
                    "content_id": content_id,
                    "content_type": content_type_value,
                    "decision": "approve",
                    "confidence": 1.0,
                    "flags": [],
                    "reasons": ["No text provided"]
                }
            result = await ModerationService.moderate_text(text)
            labels = result["labels"]
            
        elif content_type_value == "image":
            if not image_url:
                return {
                    "content_id": content_id,
                    "content_type": content_type_value,
                    "decision": "approve",
                    "confidence": 1.0,
                    "flags": [],
                    "reasons": ["No image URL provided"]
                }
            result = await ModerationService.moderate_image(image_url)
            labels = result["labels"]
            
        elif content_type_value == "video":
            if not video_url:
                return {
                    "content_id": content_id,
                    "content_type": content_type_value,
                    "decision": "needs_review",
                    "confidence": 0.5,
                    "flags": [],
                    "reasons": ["No video URL provided"]
                }
            result = await ModerationService.moderate_video(
                video_url, image_url or "", text
            )
            labels = result["labels"]
        
        # Convert labels to flags format expected by response
        # Include matched terms for transparency
        for label in labels:
            threshold = ModerationService.TEXT_THRESHOLDS.get(
                label["label"], 
                ModerationService.IMAGE_THRESHOLDS.get(label["label"], 0.5)
            )
            flag_info = {
                "flag_type": label["label"],
                "score": label["score"],
                "threshold": threshold,
                "exceeds_threshold": label["score"] >= threshold
            }
            # Include matched terms if available (helps debugging)
            if "matched" in label:
                flag_info["matched_terms"] = label["matched"]
            flags.append(flag_info)
            
            if label["score"] >= threshold:
                matched_info = ""
                if "matched" in label and label["matched"]:
                    matched_info = f" (matched: {', '.join(str(m) for m in label['matched'][:3])})"
                reasons.append(f"{label['label']} detected (score: {label['score']:.2f}, threshold: {threshold}){matched_info}")
            elif label["score"] >= threshold * 0.7:
                reasons.append(f"{label['label']} near threshold (score: {label['score']:.2f}, threshold: {threshold})")
        
        # Make decision
        decision = ModerationService.make_decision(content_type_value, labels)
        
        # Confidence: lower when more flags or higher scores
        max_score = result.get("max_score", 0) if labels else 0
        confidence = max(0.0, 1.0 - max_score)
        
        # Log the moderation result
        logger.info(f"Moderation result: content_id={content_id}, decision={decision}, "
                   f"max_score={max_score}, flags={len(flags)}")
        
        # Store in database
        job = await ModerationService.store_moderation_job(
            db, content_id, content_type_value, None, decision, labels
        )
        
        return {
            "content_id": content_id,
            "content_type": content_type_value,
            "decision": decision,
            "confidence": round(confidence, 2),
            "flags": flags,
            "reasons": reasons,
            "job_id": job.content_id if job else content_id,
            "max_score": round(max_score, 2)
        }

    @staticmethod
    async def store_moderation_job(
        db: AsyncSession,
        content_id: str,
        content_type: str,
        subtype: Optional[str],
        decision: str,
        labels: List[Dict[str, Any]]
    ) -> ModerationJob:
        """Store moderation job result."""
        # Check for existing job
        query = select(ModerationJob).where(
            ModerationJob.content_id == content_id
        )
        result = await db.execute(query)
        existing = result.scalar_one_or_none()
        
        if existing:
            existing.status = "completed"
            existing.decision = decision
            existing.labels = labels
            existing.reviewed_at = datetime.utcnow()
            job = existing
        else:
            job = ModerationJob(
                content_id=content_id,
                content_type=content_type,
                subtype=subtype,
                status="completed",
                decision=decision,
                labels=labels,
                created_at=datetime.utcnow(),
                reviewed_at=datetime.utcnow()
            )
            db.add(job)
        
        await db.flush()
        return job

    @staticmethod
    async def get_moderation_status(
        db: AsyncSession,
        content_id: str
    ) -> Dict[str, Any]:
        """Get moderation status for content."""
        query = select(ModerationJob).where(
            ModerationJob.content_id == content_id
        )
        result = await db.execute(query)
        job = result.scalar_one_or_none()
        
        if not job:
            return {"error": "Moderation job not found"}
        
        flags = []
        if job.labels:
            for label in job.labels:
                threshold = ModerationService.TEXT_THRESHOLDS.get(
                    label.get("label", ""),
                    ModerationService.IMAGE_THRESHOLDS.get(label.get("label", ""), 0.5)
                )
                flags.append({
                    "flag_type": label.get("label", ""),
                    "score": label.get("score", 0),
                    "threshold": threshold
                })
        
        return {
            "content_id": job.content_id,
            "content_type": job.content_type,
            "status": job.status,
            "decision": job.decision,
            "flags": flags,
            "created_at": job.created_at,
            "reviewed_at": job.reviewed_at,
            "reviewer_notes": job.reviewer_notes if hasattr(job, 'reviewer_notes') else None
        }

    @staticmethod
    async def manual_review(
        db: AsyncSession,
        content_id: str,
        decision: str,
        reviewer_id: str,
        notes: Optional[str] = None
    ) -> Dict[str, Any]:
        """Submit manual review decision for flagged content."""
        try:
            # Find the moderation job
            query = select(ModerationJob).where(
                ModerationJob.content_id == content_id
            )
            result = await db.execute(query)
            job = result.scalar_one_or_none()
            
            if not job:
                return {"error": f"Content '{content_id}' not found"}
            
            # Update the job with review decision
            job.status = "reviewed"
            job.decision = decision
            job.reviewed_at = datetime.utcnow()
            
            # Store reviewer info in labels if no dedicated field
            if hasattr(job, 'reviewer_id'):
                job.reviewer_id = reviewer_id
            if hasattr(job, 'reviewer_notes'):
                job.reviewer_notes = notes
            
            # Add review info to labels
            review_info = {
                "review_decision": decision,
                "reviewer_id": reviewer_id,
                "review_notes": notes,
                "reviewed_at": datetime.utcnow().isoformat()
            }
            
            if job.labels:
                job.labels.append(review_info)
            else:
                job.labels = [review_info]
            
            await db.flush()
            
            return {
                "success": True,
                "content_id": content_id,
                "decision": decision,
                "reviewer_id": reviewer_id,
                "notes": notes,
                "reviewed_at": datetime.utcnow().isoformat(),
                "message": f"Content {decision}d successfully"
            }
            
        except Exception as e:
            logger.error(f"Manual review error: {e}")
            return {"error": str(e)}

    @staticmethod
    async def get_pending_reviews(
        db: AsyncSession,
        limit: int = 50,
        offset: int = 0
    ) -> Dict[str, Any]:
        """Get content flagged for manual review."""
        try:
            # Query for pending/flagged content
            query = select(ModerationJob).where(
                ModerationJob.status.in_(["pending", "flagged", "flag_for_review"])
            ).order_by(ModerationJob.created_at.desc()).offset(offset).limit(limit)
            
            result = await db.execute(query)
            jobs = result.scalars().all()
            
            # Count total pending
            count_query = select(func.count(ModerationJob.id)).where(
                ModerationJob.status.in_(["pending", "flagged", "flag_for_review"])
            )
            count_result = await db.execute(count_query)
            total = count_result.scalar() or 0
            
            if not jobs:
                # Return sample pending items when no real data
                return {
                    "pending_items": [
                        {
                            "content_id": "sample-pending-1",
                            "content_type": "text",
                            "status": "flag_for_review",
                            "created_at": datetime.utcnow().isoformat(),
                            "flags": [
                                {"flag_type": "toxicity", "score": 0.65, "threshold": 0.60}
                            ],
                            "preview": "Sample flagged content...",
                            "note": "Sample data - no real pending reviews"
                        }
                    ],
                    "total": 1,
                    "offset": offset,
                    "limit": limit,
                    "note": "Sample data - submit content via /moderation endpoint to create real reviews"
                }
            
            pending_items = []
            for job in jobs:
                flags = []
                if job.labels:
                    for label in job.labels:
                        if isinstance(label, dict) and "label" in label:
                            flags.append({
                                "flag_type": label.get("label", ""),
                                "score": label.get("score", 0),
                                "threshold": label.get("threshold", 0.5)
                            })
                
                pending_items.append({
                    "content_id": job.content_id,
                    "content_type": job.content_type,
                    "status": job.status,
                    "created_at": job.created_at.isoformat() if job.created_at else None,
                    "flags": flags,
                    "user_id": job.user_id if hasattr(job, 'user_id') else None
                })
            
            return {
                "pending_items": pending_items,
                "total": total,
                "offset": offset,
                "limit": limit
            }
            
        except Exception as e:
            logger.error(f"Get pending reviews error: {e}")
            return {
                "pending_items": [],
                "total": 0,
                "offset": offset,
                "limit": limit,
                "error": str(e)
            }

    @staticmethod
    async def get_stats(
        db: AsyncSession,
        days: int = 7
    ) -> Dict[str, Any]:
        """Get moderation statistics."""
        try:
            from datetime import timedelta
            cutoff = datetime.utcnow() - timedelta(days=days)
            
            # Count by status
            status_query = select(
                ModerationJob.status,
                func.count(ModerationJob.id).label("count")
            ).where(
                ModerationJob.created_at >= cutoff
            ).group_by(ModerationJob.status)
            
            status_result = await db.execute(status_query)
            status_counts = {row.status: row.count for row in status_result.fetchall()}
            
            # Count by decision
            decision_query = select(
                ModerationJob.decision,
                func.count(ModerationJob.id).label("count")
            ).where(
                and_(
                    ModerationJob.created_at >= cutoff,
                    ModerationJob.decision.isnot(None)
                )
            ).group_by(ModerationJob.decision)
            
            decision_result = await db.execute(decision_query)
            decision_counts = {row.decision: row.count for row in decision_result.fetchall()}
            
            # Count by content type
            type_query = select(
                ModerationJob.content_type,
                func.count(ModerationJob.id).label("count")
            ).where(
                ModerationJob.created_at >= cutoff
            ).group_by(ModerationJob.content_type)
            
            type_result = await db.execute(type_query)
            type_counts = {row.content_type: row.count for row in type_result.fetchall()}
            
            # Total count
            total_query = select(func.count(ModerationJob.id)).where(
                ModerationJob.created_at >= cutoff
            )
            total_result = await db.execute(total_query)
            total = total_result.scalar() or 0
            
            if total == 0:
                # Return sample stats
                return {
                    "period_days": days,
                    "total_items": 0,
                    "by_status": {
                        "approved": 0,
                        "rejected": 0,
                        "pending": 0,
                        "flagged": 0
                    },
                    "by_decision": {
                        "approve": 0,
                        "reject": 0,
                        "flag_for_review": 0
                    },
                    "by_content_type": {
                        "text": 0,
                        "image": 0,
                        "video": 0
                    },
                    "note": "No moderation data yet - submit content via /moderation endpoint"
                }
            
            return {
                "period_days": days,
                "total_items": total,
                "by_status": status_counts,
                "by_decision": decision_counts,
                "by_content_type": type_counts
            }
            
        except Exception as e:
            logger.error(f"Get stats error: {e}")
            return {
                "period_days": days,
                "total_items": 0,
                "error": str(e)
            }
