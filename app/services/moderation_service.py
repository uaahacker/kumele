"""
Moderation Service for Content Moderation (Text + Image + Video).
Handles toxicity, hate speech, NSFW detection.
"""
from typing import Optional, List, Dict, Any, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime
import logging
import re
import httpx

from app.models.database_models import ModerationJob
from app.config import settings

logger = logging.getLogger(__name__)


class ModerationService:
    """Service for unified content moderation."""
    
    # Text moderation thresholds
    TEXT_THRESHOLDS = {
        "toxicity": settings.TOXICITY_THRESHOLD,
        "hate": settings.HATE_THRESHOLD,
        "spam": settings.SPAM_THRESHOLD,
    }
    
    # Image moderation thresholds
    IMAGE_THRESHOLDS = {
        "nudity": settings.NUDITY_THRESHOLD,
        "violence": settings.VIOLENCE_THRESHOLD,
        "hate_symbols": 0.40,
    }
    
    # Toxic word patterns (basic list for fallback)
    TOXIC_PATTERNS = [
        r'\b(hate|kill|die|stupid|idiot|dumb|ugly|fat|loser)\b',
        r'\b(racist|sexist|homophobic)\b',
        r'\b(scam|fraud|fake)\b',
    ]
    
    # Spam patterns
    SPAM_PATTERNS = [
        r'(click here|free money|you won|congratulations|act now)',
        r'(buy now|limited time|discount|offer expires)',
        r'https?://\S+',  # Multiple URLs
        r'(.)\1{4,}',  # Repeated characters
    ]

    @staticmethod
    async def moderate_text(text: str) -> Dict[str, Any]:
        """
        Moderate text content for toxicity, hate, and spam.
        Returns labels with scores.
        """
        labels = []
        text_lower = text.lower()
        
        try:
            # In production, call Hugging Face toxicity model
            # For now, use pattern-based detection
            
            # Check for toxic content
            toxicity_score = 0.0
            for pattern in ModerationService.TOXIC_PATTERNS:
                matches = re.findall(pattern, text_lower, re.IGNORECASE)
                toxicity_score += len(matches) * 0.2
            toxicity_score = min(toxicity_score, 1.0)
            
            if toxicity_score > 0:
                labels.append({
                    "label": "toxicity",
                    "score": round(toxicity_score, 2)
                })
            
            # Check for spam
            spam_score = 0.0
            for pattern in ModerationService.SPAM_PATTERNS:
                matches = re.findall(pattern, text_lower, re.IGNORECASE)
                spam_score += len(matches) * 0.15
            
            # Check for excessive caps
            caps_ratio = sum(1 for c in text if c.isupper()) / max(len(text), 1)
            if caps_ratio > 0.5:
                spam_score += 0.2
            
            spam_score = min(spam_score, 1.0)
            
            if spam_score > 0:
                labels.append({
                    "label": "spam",
                    "score": round(spam_score, 2)
                })
            
            # Check for potential hate speech (simplified)
            hate_words = ['hate', 'racist', 'sexist', 'homophobic', 'nazi']
            hate_score = sum(0.25 for word in hate_words if word in text_lower)
            hate_score = min(hate_score, 1.0)
            
            if hate_score > 0:
                labels.append({
                    "label": "hate",
                    "score": round(hate_score, 2)
                })
            
            return {
                "labels": labels,
                "max_score": max([l["score"] for l in labels]) if labels else 0.0
            }
            
        except Exception as e:
            logger.error(f"Text moderation error: {e}")
            return {"labels": [], "max_score": 0.0}

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
                    return hf_result
            
            # Fallback: URL-based heuristics
            url_lower = url_to_check.lower()
            
            # Basic URL-based heuristics
            suspicious_terms = ['nsfw', 'adult', 'xxx', 'porn', 'nude']
            for term in suspicious_terms:
                if term in url_lower:
                    labels.append({
                        "label": "nudity",
                        "score": 0.7
                    })
                    break
            
            violence_terms = ['gore', 'blood', 'violence', 'death']
            for term in violence_terms:
                if term in url_lower:
                    labels.append({
                        "label": "violence",
                        "score": 0.6
                    })
                    break
            
            # Default safe scores if no suspicious patterns
            if not labels:
                labels = [
                    {"label": "nudity", "score": 0.05},
                    {"label": "violence", "score": 0.03},
                    {"label": "hate_symbols", "score": 0.02}
                ]
            
            return {
                "labels": labels,
                "max_score": max([l["score"] for l in labels]) if labels else 0.0
            }
            
        except Exception as e:
            logger.error(f"Image moderation error: {e}")
            return {"labels": [], "max_score": 0.0}

    @staticmethod
    async def analyze_image_with_huggingface(image_url: str) -> Optional[Dict[str, Any]]:
        """
        Analyze image using HuggingFace NSFW detection model.
        Your friend's request: "if we give picture to it, it should do work"
        """
        try:
            async with httpx.AsyncClient() as client:
                # Download image first
                img_response = await client.get(image_url, timeout=10.0)
                if img_response.status_code != 200:
                    logger.warning(f"Failed to download image: {img_response.status_code}")
                    return None
                
                image_bytes = img_response.content
                
                # Call HuggingFace Inference API for NSFW detection
                # Model: Falconsai/nsfw_image_detection
                hf_response = await client.post(
                    f"https://api-inference.huggingface.co/models/{settings.IMAGE_MODERATION_MODEL}",
                    headers={
                        "Content-Type": "application/octet-stream"
                    },
                    content=image_bytes,
                    timeout=30.0
                )
                
                if hf_response.status_code == 200:
                    results = hf_response.json()
                    labels = []
                    
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
                        elif label_name == "normal" and score > 0.9:
                            # High confidence safe image
                            labels = [
                                {"label": "nudity", "score": round(1 - score, 2)},
                                {"label": "violence", "score": 0.02},
                                {"label": "hate_symbols", "score": 0.01}
                            ]
                    
                    if labels:
                        return {
                            "labels": labels,
                            "max_score": max([l["score"] for l in labels]),
                            "model": settings.IMAGE_MODERATION_MODEL
                        }
                elif hf_response.status_code == 503:
                    # Model is loading
                    logger.info("HuggingFace model is loading, using fallback")
                else:
                    logger.warning(f"HuggingFace API error: {hf_response.status_code}")
                    
        except httpx.TimeoutException:
            logger.warning("HuggingFace image analysis timeout")
        except Exception as e:
            logger.warning(f"HuggingFace image analysis error: {e}")
        
        return None

    @staticmethod
    async def moderate_video(
        video_url: str,
        thumbnail_url: str,
        text: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Moderate video content by checking thumbnail and associated text.
        For MVP: Only moderate thumbnail + text, not full video.
        """
        all_labels = []
        
        # Moderate thumbnail
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
        Returns: 'approve', 'reject', or 'needs_review'
        """
        if not labels:
            return "approve"
        
        # Get appropriate thresholds
        if content_type == "text":
            thresholds = ModerationService.TEXT_THRESHOLDS
        else:  # image or video
            thresholds = ModerationService.IMAGE_THRESHOLDS
        
        # Check each label against thresholds
        needs_review = False
        
        for label in labels:
            label_name = label["label"]
            score = label["score"]
            
            threshold = thresholds.get(label_name, 0.5)
            
            if score >= threshold:
                # Above threshold = reject
                return "reject"
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
        for label in labels:
            threshold = ModerationService.TEXT_THRESHOLDS.get(
                label["label"], 
                ModerationService.IMAGE_THRESHOLDS.get(label["label"], 0.5)
            )
            flags.append({
                "flag_type": label["label"],
                "score": label["score"],
                "threshold": threshold
            })
            if label["score"] >= threshold:
                reasons.append(f"{label['label']} detected (score: {label['score']:.2f})")
        
        # Make decision
        decision = ModerationService.make_decision(content_type_value, labels)
        confidence = 1.0 - (result.get("max_score", 0) if labels else 0)
        
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
            "job_id": job.content_id if job else None
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
