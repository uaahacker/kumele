"""
Moderation Service - Handles content moderation for text, images, and video
"""
import logging
import hashlib
from typing import Dict, Any, List, Optional
from datetime import datetime
from sqlalchemy.orm import Session
from kumele_ai.config import settings
from kumele_ai.db.models import ModerationJob
from kumele_ai.services.classify_service import classify_service

logger = logging.getLogger(__name__)


class ModerationService:
    """Service for content moderation"""
    
    def __init__(self):
        self._image_model = None
    
    def _generate_content_id(self, content: str, content_type: str) -> str:
        """Generate a unique content ID based on content hash"""
        content_hash = hashlib.sha256(f"{content_type}:{content}".encode()).hexdigest()[:16]
        return f"{content_type}_{content_hash}"
    
    def moderate_text(
        self,
        db: Session,
        text: str,
        subtype: Optional[str] = None,
        content_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Moderate text content"""
        try:
            # Generate content ID if not provided
            if not content_id:
                content_id = self._generate_content_id(text, "text")
            
            # Check if already moderated
            existing = db.query(ModerationJob).filter(
                ModerationJob.content_id == content_id,
                ModerationJob.status == "completed"
            ).first()
            
            if existing:
                return {
                    "content_id": content_id,
                    "content_type": "text",
                    "status": existing.status,
                    "decision": existing.decision,
                    "labels": existing.labels,
                    "cached": True
                }
            
            # Create moderation job
            job = ModerationJob(
                content_id=content_id,
                content_type="text",
                subtype=subtype,
                content_data=text[:5000],  # Limit stored content
                status="processing"
            )
            db.add(job)
            db.commit()
            
            # Run moderation checks
            labels = {}
            decision = "approve"
            
            # Toxicity check
            toxicity = classify_service.detect_toxicity(text)
            labels["toxicity"] = {
                "score": toxicity.get("toxicity_score", 0),
                "is_toxic": toxicity.get("is_toxic", False)
            }
            
            if toxicity.get("toxicity_score", 0) > settings.MODERATION_TEXT_TOXICITY_THRESHOLD:
                decision = "reject"
            
            # Spam check
            spam = classify_service.detect_spam(text)
            labels["spam"] = {
                "score": spam.get("spam_score", 0),
                "is_spam": spam.get("is_spam", False)
            }
            
            if spam.get("spam_score", 0) > settings.MODERATION_TEXT_SPAM_THRESHOLD:
                decision = "reject"
            
            # Sentiment (for context)
            sentiment = classify_service.analyze_sentiment(text)
            labels["sentiment"] = {
                "value": sentiment.get("sentiment"),
                "confidence": sentiment.get("confidence")
            }
            
            # Check for needs_review (borderline cases)
            if decision == "approve":
                if (toxicity.get("toxicity_score", 0) > settings.MODERATION_TEXT_TOXICITY_THRESHOLD * 0.7 or
                    spam.get("spam_score", 0) > settings.MODERATION_TEXT_SPAM_THRESHOLD * 0.7):
                    decision = "needs_review"
            
            # Update job
            job.status = "completed"
            job.decision = decision
            job.labels = labels
            job.reviewed_at = datetime.utcnow()
            db.commit()
            
            return {
                "content_id": content_id,
                "content_type": "text",
                "status": "completed",
                "decision": decision,
                "labels": labels,
                "cached": False
            }
            
        except Exception as e:
            logger.error(f"Text moderation error: {e}")
            return {
                "content_id": content_id,
                "content_type": "text",
                "status": "error",
                "decision": "needs_review",
                "error": str(e)
            }
    
    def moderate_image(
        self,
        db: Session,
        image_url: str,
        subtype: Optional[str] = None,
        content_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Moderate image content"""
        try:
            if not content_id:
                content_id = self._generate_content_id(image_url, "image")
            
            # Check if already moderated
            existing = db.query(ModerationJob).filter(
                ModerationJob.content_id == content_id,
                ModerationJob.status == "completed"
            ).first()
            
            if existing:
                return {
                    "content_id": content_id,
                    "content_type": "image",
                    "status": existing.status,
                    "decision": existing.decision,
                    "labels": existing.labels,
                    "cached": True
                }
            
            # Create moderation job
            job = ModerationJob(
                content_id=content_id,
                content_type="image",
                subtype=subtype,
                content_data=image_url,
                status="processing"
            )
            db.add(job)
            db.commit()
            
            # Image moderation using simple heuristics
            # In production, this would use a proper image moderation model
            labels = {
                "nudity": {"score": 0.0, "detected": False},
                "violence": {"score": 0.0, "detected": False},
                "hate_symbols": {"score": 0.0, "detected": False}
            }
            
            decision = "approve"
            
            # Placeholder for actual image analysis
            # In production: load image, run through NSFW detector, violence detector, etc.
            
            # Update job
            job.status = "completed"
            job.decision = decision
            job.labels = labels
            job.reviewed_at = datetime.utcnow()
            db.commit()
            
            return {
                "content_id": content_id,
                "content_type": "image",
                "status": "completed",
                "decision": decision,
                "labels": labels,
                "cached": False,
                "note": "Image moderation uses placeholder analysis"
            }
            
        except Exception as e:
            logger.error(f"Image moderation error: {e}")
            return {
                "content_id": content_id,
                "content_type": "image",
                "status": "error",
                "decision": "needs_review",
                "error": str(e)
            }
    
    def moderate_video(
        self,
        db: Session,
        video_url: str,
        thumbnail_url: Optional[str] = None,
        title: Optional[str] = None,
        description: Optional[str] = None,
        content_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Moderate video content (MVP: thumbnail + text only)"""
        try:
            if not content_id:
                content_id = self._generate_content_id(video_url, "video")
            
            # Check if already moderated
            existing = db.query(ModerationJob).filter(
                ModerationJob.content_id == content_id,
                ModerationJob.status == "completed"
            ).first()
            
            if existing:
                return {
                    "content_id": content_id,
                    "content_type": "video",
                    "status": existing.status,
                    "decision": existing.decision,
                    "labels": existing.labels,
                    "cached": True
                }
            
            # Create moderation job
            job = ModerationJob(
                content_id=content_id,
                content_type="video",
                subtype="thumbnail_text",
                content_data=video_url,
                status="processing"
            )
            db.add(job)
            db.commit()
            
            labels = {
                "thumbnail": {"decision": "approve", "labels": {}},
                "text": {"decision": "approve", "labels": {}}
            }
            decision = "approve"
            
            # Moderate thumbnail if provided
            if thumbnail_url:
                thumbnail_result = self.moderate_image(
                    db, thumbnail_url, subtype="video_thumbnail"
                )
                labels["thumbnail"] = {
                    "decision": thumbnail_result.get("decision"),
                    "labels": thumbnail_result.get("labels", {})
                }
                if thumbnail_result.get("decision") == "reject":
                    decision = "reject"
            
            # Moderate title and description
            if title or description:
                text_content = f"{title or ''} {description or ''}".strip()
                if text_content:
                    text_result = self.moderate_text(
                        db, text_content, subtype="video_metadata"
                    )
                    labels["text"] = {
                        "decision": text_result.get("decision"),
                        "labels": text_result.get("labels", {})
                    }
                    if text_result.get("decision") == "reject":
                        decision = "reject"
            
            # Update job
            job.status = "completed"
            job.decision = decision
            job.labels = labels
            job.reviewed_at = datetime.utcnow()
            db.commit()
            
            return {
                "content_id": content_id,
                "content_type": "video",
                "status": "completed",
                "decision": decision,
                "labels": labels,
                "cached": False,
                "note": "Video moderation limited to thumbnail and metadata only"
            }
            
        except Exception as e:
            logger.error(f"Video moderation error: {e}")
            return {
                "content_id": content_id,
                "content_type": "video",
                "status": "error",
                "decision": "needs_review",
                "error": str(e)
            }
    
    def get_moderation_status(
        self,
        db: Session,
        content_id: str
    ) -> Optional[Dict[str, Any]]:
        """Get moderation status for content"""
        job = db.query(ModerationJob).filter(
            ModerationJob.content_id == content_id
        ).order_by(ModerationJob.created_at.desc()).first()
        
        if not job:
            return None
        
        return {
            "content_id": job.content_id,
            "content_type": job.content_type,
            "subtype": job.subtype,
            "status": job.status,
            "decision": job.decision,
            "labels": job.labels,
            "created_at": job.created_at.isoformat() if job.created_at else None,
            "reviewed_at": job.reviewed_at.isoformat() if job.reviewed_at else None
        }


# Singleton instance
moderation_service = ModerationService()
