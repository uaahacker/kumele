"""
Support Email Service.
Handles AI-powered email routing, analysis, and response drafting.
"""
from typing import Optional, List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, desc
from datetime import datetime
import logging
import uuid
import httpx
import re
from email.utils import parseaddr

from app.models.database_models import SupportEmail, SupportEmailAnalysis
from app.config import settings

logger = logging.getLogger(__name__)


class SupportService:
    """Service for AI-powered support email handling."""
    
    # Keywords for category classification
    CATEGORY_KEYWORDS = {
        "billing": [
            "payment", "charge", "refund", "invoice", "subscription",
            "price", "cost", "fee", "credit", "money", "card", "billing"
        ],
        "technical": [
            "bug", "error", "crash", "not working", "broken", "issue",
            "problem", "glitch", "fail", "slow", "loading", "login"
        ],
        "account": [
            "password", "login", "account", "profile", "delete", "verify",
            "email", "phone", "settings", "notification", "privacy"
        ],
        "event": [
            "event", "host", "attend", "cancel", "booking", "ticket",
            "venue", "date", "time", "schedule", "rsvp"
        ],
        "general": [
            "question", "help", "information", "how to", "what is",
            "feature", "suggestion", "feedback"
        ]
    }
    
    # Sentiment indicators
    URGENT_INDICATORS = [
        "urgent", "asap", "immediately", "emergency", "critical",
        "help!", "please help", "frustrated", "angry", "unacceptable"
    ]
    
    POSITIVE_INDICATORS = [
        "thank", "great", "excellent", "love", "wonderful", "amazing",
        "helpful", "appreciate", "satisfied", "happy"
    ]
    
    NEGATIVE_INDICATORS = [
        "terrible", "awful", "horrible", "worst", "disappointed",
        "frustrated", "angry", "unacceptable", "poor", "bad"
    ]

    @staticmethod
    def classify_category(subject: str, body: str) -> str:
        """Classify email into category based on keywords."""
        text = f"{subject} {body}".lower()
        
        scores = {}
        for category, keywords in SupportService.CATEGORY_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw in text)
            scores[category] = score
        
        if max(scores.values()) == 0:
            return "general"
        
        return max(scores, key=scores.get)

    @staticmethod
    def analyze_sentiment(text: str) -> Dict[str, Any]:
        """Analyze sentiment of email text."""
        text_lower = text.lower()
        
        positive_count = sum(1 for ind in SupportService.POSITIVE_INDICATORS if ind in text_lower)
        negative_count = sum(1 for ind in SupportService.NEGATIVE_INDICATORS if ind in text_lower)
        
        total = positive_count + negative_count + 1
        
        if positive_count > negative_count:
            sentiment = "positive"
            score = min(0.9, 0.5 + (positive_count - negative_count) / total)
        elif negative_count > positive_count:
            sentiment = "negative"
            score = min(0.9, 0.5 + (negative_count - positive_count) / total)
        else:
            sentiment = "neutral"
            score = 0.5
        
        return {
            "sentiment": sentiment,
            "score": score,
            "positive_count": positive_count,
            "negative_count": negative_count
        }

    @staticmethod
    def calculate_priority(subject: str, body: str, sentiment: str) -> int:
        """Calculate priority score (1=low, 5=critical)."""
        text = f"{subject} {body}".lower()
        
        # Base priority
        priority = 3
        
        # Check urgency indicators
        urgency_count = sum(1 for ind in SupportService.URGENT_INDICATORS if ind in text)
        
        if urgency_count >= 3:
            priority = 5
        elif urgency_count >= 2:
            priority = 4
        elif urgency_count >= 1:
            priority = max(priority, 4)
        
        # Adjust based on sentiment
        if sentiment == "negative":
            priority = min(5, priority + 1)
        
        return priority

    @staticmethod
    def extract_entities(text: str) -> Dict[str, Any]:
        """Extract entities from email text."""
        entities = {
            "email_addresses": [],
            "phone_numbers": [],
            "dates": [],
            "urls": [],
            "order_ids": [],
            "event_ids": []
        }
        
        # Email addresses
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        entities["email_addresses"] = re.findall(email_pattern, text)
        
        # Phone numbers
        phone_pattern = r'[\+]?[(]?[0-9]{1,3}[)]?[-\s\.]?[(]?[0-9]{1,4}[)]?[-\s\.]?[0-9]{1,4}[-\s\.]?[0-9]{1,9}'
        entities["phone_numbers"] = re.findall(phone_pattern, text)
        
        # URLs
        url_pattern = r'https?://[^\s<>"\']+|www\.[^\s<>"\']+'
        entities["urls"] = re.findall(url_pattern, text)
        
        # Order/Event IDs (common formats)
        id_pattern = r'\b[A-Z]{2,3}-[0-9]{6,}\b|\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b'
        ids = re.findall(id_pattern, text, re.IGNORECASE)
        entities["order_ids"] = ids
        
        return entities

    @staticmethod
    async def generate_reply_draft(
        subject: str,
        body: str,
        category: str,
        sentiment: str
    ) -> str:
        """Generate AI-powered reply draft."""
        # In production, this would call an LLM
        # For now, use template-based responses
        
        templates = {
            "billing": {
                "negative": "I sincerely apologize for any billing concerns you've experienced. I understand how frustrating billing issues can be. Let me look into this immediately and get back to you with a resolution.",
                "neutral": "Thank you for reaching out about your billing inquiry. I'll review your account and provide you with the information you need.",
                "positive": "Thank you for your message regarding billing. I'm happy to assist you with your inquiry."
            },
            "technical": {
                "negative": "I apologize for the technical difficulties you're experiencing. I completely understand how frustrating this must be. Let me investigate this issue and find a solution for you.",
                "neutral": "Thank you for reporting this technical issue. Our team will investigate and work on resolving it.",
                "positive": "Thank you for bringing this to our attention. I'll look into this technical matter for you."
            },
            "account": {
                "negative": "I apologize for any inconvenience with your account. Your security and experience are our top priorities. Let me help resolve this immediately.",
                "neutral": "Thank you for your account-related inquiry. I'll help you with the necessary changes.",
                "positive": "Thank you for reaching out about your account. I'm happy to help with your request."
            },
            "event": {
                "negative": "I sincerely apologize for any issues with your event experience. We take this very seriously and want to make things right.",
                "neutral": "Thank you for your inquiry about our events. I'll provide you with the information you need.",
                "positive": "Thank you for your interest in our events! I'm excited to help you with your inquiry."
            },
            "general": {
                "negative": "I apologize for any frustration you've experienced. We value your feedback and want to help resolve your concerns.",
                "neutral": "Thank you for contacting us. I'm here to help with your inquiry.",
                "positive": "Thank you for reaching out! I'm happy to assist you today."
            }
        }
        
        cat_templates = templates.get(category, templates["general"])
        sentiment_key = sentiment if sentiment in cat_templates else "neutral"
        
        intro = cat_templates[sentiment_key]
        
        return f"""Dear Customer,

{intro}

I'm reviewing your request now and will follow up with more details shortly. In the meantime, please don't hesitate to provide any additional information that might help us assist you better.

Best regards,
Kumele Support Team"""

    @staticmethod
    async def process_incoming_email(
        db: AsyncSession,
        from_email: str,
        subject: str,
        body: str,
        user_id: Optional[str] = None,
        thread_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Process an incoming support email.
        1. Store the email
        2. Analyze category and sentiment
        3. Calculate priority
        4. Extract entities
        5. Generate reply draft
        """
        email_id = uuid.uuid4()
        
        # Parse email
        _, sender_email = parseaddr(from_email)
        
        # Analyze
        category = SupportService.classify_category(subject, body)
        sentiment_data = SupportService.analyze_sentiment(body)
        priority = SupportService.calculate_priority(subject, body, sentiment_data["sentiment"])
        entities = SupportService.extract_entities(body)
        
        # Generate draft reply
        draft_reply = await SupportService.generate_reply_draft(
            subject, body, category, sentiment_data["sentiment"]
        )
        
        # Determine if escalation needed
        needs_escalation = priority >= 4 or sentiment_data["sentiment"] == "negative"
        
        # Create email record
        email = SupportEmail(
            id=email_id,
            user_id=uuid.UUID(user_id) if user_id else None,
            from_email=sender_email,
            subject=subject,
            body=body,
            thread_id=uuid.UUID(thread_id) if thread_id else email_id,
            status="new",
            priority=priority,
            created_at=datetime.utcnow()
        )
        db.add(email)
        
        # Create analysis record
        analysis = SupportEmailAnalysis(
            email_id=email_id,
            category=category,
            sentiment=sentiment_data["sentiment"],
            sentiment_score=sentiment_data["score"],
            priority_score=priority,
            entities=entities,
            suggested_reply=draft_reply,
            needs_escalation=needs_escalation,
            analyzed_at=datetime.utcnow()
        )
        db.add(analysis)
        
        await db.flush()
        
        return {
            "email_id": str(email_id),
            "category": category,
            "sentiment": sentiment_data["sentiment"],
            "priority": priority,
            "needs_escalation": needs_escalation,
            "draft_reply": draft_reply,
            "entities": entities,
            "status": "new"
        }

    @staticmethod
    async def reply_to_email(
        db: AsyncSession,
        email_id: str,
        reply_body: str,
        agent_id: str
    ) -> Dict[str, Any]:
        """Send a reply to a support email."""
        try:
            email_uuid = uuid.UUID(email_id)
            agent_uuid = uuid.UUID(agent_id)
            
            # Get original email
            query = select(SupportEmail).where(SupportEmail.id == email_uuid)
            result = await db.execute(query)
            original = result.scalar_one_or_none()
            
            if not original:
                return {
                    "success": False,
                    "message": "Email not found"
                }
            
            # Create reply record
            reply_id = uuid.uuid4()
            reply = SupportEmail(
                id=reply_id,
                user_id=original.user_id,
                from_email=settings.SMTP_USER,
                to_email=original.from_email,
                subject=f"Re: {original.subject}",
                body=reply_body,
                thread_id=original.thread_id,
                parent_id=original.id,
                status="sent",
                priority=original.priority,
                assigned_to=agent_uuid,
                replied_at=datetime.utcnow(),
                created_at=datetime.utcnow()
            )
            db.add(reply)
            
            # Update original email status
            original.status = "replied"
            original.assigned_to = agent_uuid
            original.replied_at = datetime.utcnow()
            
            await db.flush()
            
            # In production, actually send email via SMTP
            # For now, just log
            logger.info(f"Reply sent to {original.from_email}")
            
            return {
                "success": True,
                "reply_id": str(reply_id),
                "message": "Reply sent successfully"
            }
            
        except Exception as e:
            logger.error(f"Reply error: {e}")
            return {
                "success": False,
                "message": str(e)
            }

    @staticmethod
    async def escalate_email(
        db: AsyncSession,
        email_id: str,
        reason: str,
        escalated_by: str
    ) -> Dict[str, Any]:
        """Escalate a support email to higher tier."""
        try:
            email_uuid = uuid.UUID(email_id)
            
            query = select(SupportEmail).where(SupportEmail.id == email_uuid)
            result = await db.execute(query)
            email = result.scalar_one_or_none()
            
            if not email:
                return {
                    "success": False,
                    "message": "Email not found"
                }
            
            email.status = "escalated"
            email.priority = min(5, email.priority + 1)
            
            # Update analysis
            analysis_query = select(SupportEmailAnalysis).where(
                SupportEmailAnalysis.email_id == email_uuid
            )
            analysis_result = await db.execute(analysis_query)
            analysis = analysis_result.scalar_one_or_none()
            
            if analysis:
                analysis.needs_escalation = True
                analysis.escalation_reason = reason
                analysis.escalated_by = uuid.UUID(escalated_by)
            
            await db.flush()
            
            return {
                "success": True,
                "email_id": email_id,
                "new_priority": email.priority,
                "message": "Email escalated successfully"
            }
            
        except Exception as e:
            logger.error(f"Escalation error: {e}")
            return {
                "success": False,
                "message": str(e)
            }

    @staticmethod
    async def get_email_details(
        db: AsyncSession,
        email_id: str
    ) -> Dict[str, Any]:
        """Get full email details with analysis."""
        try:
            email_uuid = uuid.UUID(email_id)
            
            # Get email
            email_query = select(SupportEmail).where(SupportEmail.id == email_uuid)
            email_result = await db.execute(email_query)
            email = email_result.scalar_one_or_none()
            
            if not email:
                return {"error": "Email not found"}
            
            # Get analysis
            analysis_query = select(SupportEmailAnalysis).where(
                SupportEmailAnalysis.email_id == email_uuid
            )
            analysis_result = await db.execute(analysis_query)
            analysis = analysis_result.scalar_one_or_none()
            
            # Get thread if exists
            thread_emails = []
            if email.thread_id:
                thread_query = select(SupportEmail).where(
                    and_(
                        SupportEmail.thread_id == email.thread_id,
                        SupportEmail.id != email_uuid
                    )
                ).order_by(SupportEmail.created_at)
                thread_result = await db.execute(thread_query)
                thread_emails = [
                    {
                        "id": str(e.id),
                        "from_email": e.from_email,
                        "subject": e.subject,
                        "body": e.body[:200] + "..." if len(e.body) > 200 else e.body,
                        "created_at": e.created_at.isoformat()
                    }
                    for e in thread_result.scalars().all()
                ]
            
            result = {
                "id": str(email.id),
                "from_email": email.from_email,
                "to_email": email.to_email,
                "subject": email.subject,
                "body": email.body,
                "status": email.status,
                "priority": email.priority,
                "created_at": email.created_at.isoformat(),
                "replied_at": email.replied_at.isoformat() if email.replied_at else None,
                "thread": thread_emails
            }
            
            if analysis:
                result["analysis"] = {
                    "category": analysis.category,
                    "sentiment": analysis.sentiment,
                    "sentiment_score": analysis.sentiment_score,
                    "entities": analysis.entities,
                    "suggested_reply": analysis.suggested_reply,
                    "needs_escalation": analysis.needs_escalation
                }
            
            return result
            
        except Exception as e:
            logger.error(f"Get email error: {e}")
            return {"error": str(e)}

    @staticmethod
    async def get_email_queue(
        db: AsyncSession,
        status: Optional[str] = None,
        category: Optional[str] = None,
        priority_min: Optional[int] = None,
        limit: int = 50,
        offset: int = 0
    ) -> Dict[str, Any]:
        """Get support email queue with filters."""
        query = select(SupportEmail).order_by(desc(SupportEmail.priority), SupportEmail.created_at)
        
        if status:
            query = query.where(SupportEmail.status == status)
        
        if priority_min:
            query = query.where(SupportEmail.priority >= priority_min)
        
        query = query.limit(limit).offset(offset)
        
        result = await db.execute(query)
        emails = result.scalars().all()
        
        email_list = []
        for email in emails:
            # Get analysis
            analysis_query = select(SupportEmailAnalysis).where(
                SupportEmailAnalysis.email_id == email.id
            )
            analysis_result = await db.execute(analysis_query)
            analysis = analysis_result.scalar_one_or_none()
            
            email_data = {
                "id": str(email.id),
                "from_email": email.from_email,
                "subject": email.subject,
                "status": email.status,
                "priority": email.priority,
                "created_at": email.created_at.isoformat()
            }
            
            if analysis:
                if category and analysis.category != category:
                    continue
                email_data["category"] = analysis.category
                email_data["sentiment"] = analysis.sentiment
            
            email_list.append(email_data)
        
        return {
            "emails": email_list,
            "count": len(email_list),
            "offset": offset,
            "limit": limit
        }
