"""
Support Service - Handles support email processing
"""
import logging
import re
import hashlib
from typing import Dict, Any, Optional
from datetime import datetime
from sqlalchemy.orm import Session

from kumele_ai.db.models import (
    SupportEmail, SupportEmailAnalysis, SupportEmailReply, SupportEmailEscalation
)
from kumele_ai.services.classify_service import classify_service
from kumele_ai.services.llm_service import llm_service
from kumele_ai.services.email_service import email_service

logger = logging.getLogger(__name__)


class SupportService:
    """Service for support email processing"""
    
    def __init__(self):
        pass
    
    def _clean_email_text(self, raw_body: str) -> str:
        """Clean email body text"""
        if not raw_body:
            return ""
        
        # Remove HTML tags
        clean = re.sub(r'<[^>]+>', '', raw_body)
        
        # Remove excessive whitespace
        clean = re.sub(r'\s+', ' ', clean)
        
        # Remove email signatures (simple pattern)
        clean = re.sub(r'--\s*\n.*$', '', clean, flags=re.DOTALL)
        
        # Remove quoted replies
        clean = re.sub(r'>.*$', '', clean, flags=re.MULTILINE)
        
        return clean.strip()
    
    def _generate_thread_id(self, from_email: str, subject: str) -> str:
        """Generate or extract thread ID"""
        # Remove Re:, Fwd: etc. from subject
        clean_subject = re.sub(r'^(Re:|Fwd:|FW:)\s*', '', subject, flags=re.IGNORECASE)
        
        # Generate hash
        hash_input = f"{from_email}:{clean_subject}".lower()
        return hashlib.sha256(hash_input.encode()).hexdigest()[:16]
    
    async def process_incoming_email(
        self,
        db: Session,
        from_email: str,
        to_email: str,
        subject: str,
        raw_body: str
    ) -> Dict[str, Any]:
        """Process an incoming support email"""
        try:
            # Clean text
            cleaned_text = self._clean_email_text(raw_body)
            
            # Generate thread ID
            thread_id = self._generate_thread_id(from_email, subject)
            
            # Store email
            email_record = SupportEmail(
                thread_id=thread_id,
                from_email=from_email,
                to_email=to_email,
                subject=subject,
                raw_body=raw_body,
                cleaned_text=cleaned_text,
                status="new"
            )
            db.add(email_record)
            db.commit()
            db.refresh(email_record)
            
            # Analyze email
            analysis = await self._analyze_email(db, email_record)
            
            # Queue AI response generation (would be done by worker in production)
            
            return {
                "success": True,
                "email_id": email_record.id,
                "thread_id": thread_id,
                "analysis": analysis
            }
            
        except Exception as e:
            logger.error(f"Email processing error: {e}")
            db.rollback()
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _analyze_email(
        self,
        db: Session,
        email: SupportEmail
    ) -> Dict[str, Any]:
        """Analyze email content"""
        try:
            text = email.cleaned_text or email.raw_body or ""
            
            # Sentiment analysis
            sentiment = classify_service.analyze_sentiment(text)
            
            # Category classification
            classification = classify_service.classify_support_email(text)
            
            # Generate suggested response
            llm_response = await llm_service.generate_email_response(
                email_content=text,
                category=classification.get("category", "general"),
                sentiment=sentiment.get("sentiment", "neutral")
            )
            
            # Store analysis
            analysis = SupportEmailAnalysis(
                email_id=email.id,
                category=classification.get("category"),
                sentiment=sentiment.get("sentiment"),
                sentiment_score=sentiment.get("confidence"),
                urgency=classification.get("urgency"),
                keywords={},  # Could extract keywords here
                suggested_response=llm_response.get("generated_text"),
                confidence=classification.get("confidence")
            )
            db.add(analysis)
            
            # Update email status
            email.status = "analyzed"
            db.commit()
            
            return {
                "category": classification.get("category"),
                "sentiment": sentiment.get("sentiment"),
                "urgency": classification.get("urgency"),
                "suggested_response_available": bool(llm_response.get("generated_text"))
            }
            
        except Exception as e:
            logger.error(f"Email analysis error: {e}")
            return {"error": str(e)}
    
    async def send_reply(
        self,
        db: Session,
        email_id: int,
        response_text: str,
        response_type: str = "ai_generated"
    ) -> Dict[str, Any]:
        """Send reply to a support email"""
        try:
            # Get original email
            email = db.query(SupportEmail).filter(SupportEmail.id == email_id).first()
            if not email:
                return {"success": False, "error": "Email not found"}
            
            # Create reply record
            reply = SupportEmailReply(
                email_id=email_id,
                draft_response=response_text,
                final_response=response_text,
                response_type=response_type,
                sent_status="draft"
            )
            db.add(reply)
            db.commit()
            
            # Send email
            send_result = await email_service.send_support_reply(
                to_email=email.from_email,
                subject=email.subject or "Support Response",
                reply_body=response_text,
                thread_id=email.thread_id
            )
            
            if send_result.get("success"):
                reply.sent_status = "sent"
                reply.sent_at = datetime.utcnow()
                email.status = "replied"
            else:
                reply.sent_status = "failed"
            
            db.commit()
            
            return {
                "success": send_result.get("success"),
                "reply_id": reply.id,
                "message": send_result.get("message") or send_result.get("error")
            }
            
        except Exception as e:
            logger.error(f"Reply send error: {e}")
            db.rollback()
            return {"success": False, "error": str(e)}
    
    async def escalate_email(
        self,
        db: Session,
        email_id: int,
        reason: str,
        escalation_level: str = "tier2",
        assigned_to: Optional[str] = None
    ) -> Dict[str, Any]:
        """Escalate a support email"""
        try:
            # Get email
            email = db.query(SupportEmail).filter(SupportEmail.id == email_id).first()
            if not email:
                return {"success": False, "error": "Email not found"}
            
            # Create escalation record
            escalation = SupportEmailEscalation(
                email_id=email_id,
                escalation_reason=reason,
                escalation_level=escalation_level,
                assigned_to=assigned_to
            )
            db.add(escalation)
            
            # Update email status
            email.status = "escalated"
            db.commit()
            
            return {
                "success": True,
                "escalation_id": escalation.id,
                "level": escalation_level
            }
            
        except Exception as e:
            logger.error(f"Escalation error: {e}")
            db.rollback()
            return {"success": False, "error": str(e)}
    
    def get_email_details(
        self,
        db: Session,
        email_id: int
    ) -> Optional[Dict[str, Any]]:
        """Get email with analysis and replies"""
        email = db.query(SupportEmail).filter(SupportEmail.id == email_id).first()
        if not email:
            return None
        
        analysis = db.query(SupportEmailAnalysis).filter(
            SupportEmailAnalysis.email_id == email_id
        ).first()
        
        replies = db.query(SupportEmailReply).filter(
            SupportEmailReply.email_id == email_id
        ).all()
        
        escalations = db.query(SupportEmailEscalation).filter(
            SupportEmailEscalation.email_id == email_id
        ).all()
        
        return {
            "email": {
                "id": email.id,
                "thread_id": email.thread_id,
                "from_email": email.from_email,
                "subject": email.subject,
                "cleaned_text": email.cleaned_text,
                "status": email.status,
                "received_at": email.received_at.isoformat() if email.received_at else None
            },
            "analysis": {
                "category": analysis.category if analysis else None,
                "sentiment": analysis.sentiment if analysis else None,
                "urgency": analysis.urgency if analysis else None,
                "suggested_response": analysis.suggested_response if analysis else None
            } if analysis else None,
            "replies": [
                {
                    "id": r.id,
                    "response_type": r.response_type,
                    "sent_status": r.sent_status,
                    "sent_at": r.sent_at.isoformat() if r.sent_at else None
                }
                for r in replies
            ],
            "escalations": [
                {
                    "id": e.id,
                    "reason": e.escalation_reason,
                    "level": e.escalation_level,
                    "escalated_at": e.escalated_at.isoformat() if e.escalated_at else None
                }
                for e in escalations
            ]
        }


# Singleton instance
support_service = SupportService()
