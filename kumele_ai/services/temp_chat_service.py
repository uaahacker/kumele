"""
Temporary Chat Service - Post-Match Communication System

Manages event chat rooms with:
- Automatic lifecycle (creation → expiration)
- Moderation integration
- Activity tracking for ML features

Lifecycle:
1. Created: After successful match/RSVP
2. Active: During event + 24 hours post-event
3. Expired: Auto-closed after 24h post-event
"""
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func

from kumele_ai.db.models import (
    TempChat, TempChatMessage, TempChatParticipant,
    Event, UserEvent, User
)

logger = logging.getLogger(__name__)


# ============================================================
# CONFIGURATION
# ============================================================

CHAT_CONFIG = {
    # Lifecycle settings
    "default_expiry_hours": 24,  # Hours after event ends
    "max_expiry_hours": 72,      # Maximum chat duration
    
    # Activity thresholds
    "inactive_close_hours": 12,  # Close if no messages for X hours
    
    # Moderation thresholds
    "toxic_threshold": 0.7,      # Toxicity score to flag message
    "suspend_after_flags": 3,    # Suspend chat after X flagged messages
    
    # Participants
    "max_participants": 100,     # Maximum participants per chat
}


class TempChatService:
    """
    Service for managing temporary event chat rooms.
    
    Features:
    - Automatic creation on RSVP
    - Expiration management
    - Moderation integration
    - Activity metrics for ML
    """
    
    def __init__(self):
        self.config = CHAT_CONFIG
    
    # ============================================================
    # CHAT LIFECYCLE
    # ============================================================
    
    def create_chat(
        self,
        db: Session,
        event_id: int,
        chat_type: str = "event"
    ) -> TempChat:
        """
        Create a new temporary chat room for an event.
        
        Called when:
        - Event is created (host chat)
        - First RSVP received (attendee chat)
        """
        # Check if chat already exists
        existing = db.query(TempChat).filter(
            and_(
                TempChat.event_id == event_id,
                TempChat.chat_type == chat_type,
                TempChat.status == "active"
            )
        ).first()
        
        if existing:
            logger.info(f"Chat already exists for event {event_id}")
            return existing
        
        # Get event to calculate expiry
        event = db.query(Event).filter(Event.id == event_id).first()
        
        if event and event.event_date:
            # Expire 24 hours after event ends
            event_duration_hours = 3  # Assume 3-hour events
            expires_at = event.event_date + timedelta(
                hours=event_duration_hours + self.config["default_expiry_hours"]
            )
        else:
            # Default: 48 hours from now
            expires_at = datetime.utcnow() + timedelta(hours=48)
        
        # Create chat
        chat = TempChat(
            event_id=event_id,
            chat_type=chat_type,
            status="active",
            expires_at=expires_at,
            message_count=0,
            active_participants=0
        )
        
        db.add(chat)
        db.commit()
        db.refresh(chat)
        
        # Add host as first participant
        if event and event.host_id:
            self.add_participant(db, chat.id, event.host_id, role="host")
        
        logger.info(f"Created chat {chat.id} for event {event_id}")
        return chat
    
    def add_participant(
        self,
        db: Session,
        chat_id: int,
        user_id: int,
        role: str = "attendee"
    ) -> Optional[TempChatParticipant]:
        """Add a participant to the chat"""
        # Check if already a participant
        existing = db.query(TempChatParticipant).filter(
            and_(
                TempChatParticipant.chat_id == chat_id,
                TempChatParticipant.user_id == user_id
            )
        ).first()
        
        if existing:
            if not existing.is_active:
                existing.is_active = True
                existing.left_at = None
                db.commit()
            return existing
        
        # Check participant limit
        chat = db.query(TempChat).filter(TempChat.id == chat_id).first()
        if chat and chat.active_participants >= self.config["max_participants"]:
            logger.warning(f"Chat {chat_id} at max capacity")
            return None
        
        participant = TempChatParticipant(
            chat_id=chat_id,
            user_id=user_id,
            role=role,
            is_active=True,
            message_count=0
        )
        
        db.add(participant)
        
        # Update active count
        if chat:
            chat.active_participants += 1
        
        db.commit()
        db.refresh(participant)
        
        return participant
    
    def remove_participant(
        self,
        db: Session,
        chat_id: int,
        user_id: int
    ) -> bool:
        """Remove a participant from the chat"""
        participant = db.query(TempChatParticipant).filter(
            and_(
                TempChatParticipant.chat_id == chat_id,
                TempChatParticipant.user_id == user_id
            )
        ).first()
        
        if not participant:
            return False
        
        participant.is_active = False
        participant.left_at = datetime.utcnow()
        
        # Update active count
        chat = db.query(TempChat).filter(TempChat.id == chat_id).first()
        if chat and chat.active_participants > 0:
            chat.active_participants -= 1
        
        db.commit()
        return True
    
    def close_chat(
        self,
        db: Session,
        chat_id: int,
        reason: str = "expired"
    ) -> bool:
        """Close a chat room"""
        chat = db.query(TempChat).filter(TempChat.id == chat_id).first()
        
        if not chat:
            return False
        
        chat.status = "expired"
        chat.closed_at = datetime.utcnow()
        chat.close_reason = reason
        
        db.commit()
        
        logger.info(f"Closed chat {chat_id} - reason: {reason}")
        return True
    
    # ============================================================
    # MESSAGING
    # ============================================================
    
    def send_message(
        self,
        db: Session,
        chat_id: int,
        user_id: int,
        content: str
    ) -> Optional[TempChatMessage]:
        """
        Send a message to the chat.
        
        Includes toxicity check via moderation service.
        """
        # Verify chat is active
        chat = db.query(TempChat).filter(
            and_(
                TempChat.id == chat_id,
                TempChat.status == "active"
            )
        ).first()
        
        if not chat:
            logger.warning(f"Cannot send to inactive chat {chat_id}")
            return None
        
        # Check if chat expired
        if chat.expires_at and chat.expires_at < datetime.utcnow():
            self.close_chat(db, chat_id, "expired")
            return None
        
        # Verify user is participant
        participant = db.query(TempChatParticipant).filter(
            and_(
                TempChatParticipant.chat_id == chat_id,
                TempChatParticipant.user_id == user_id,
                TempChatParticipant.is_active == True
            )
        ).first()
        
        if not participant:
            logger.warning(f"User {user_id} not in chat {chat_id}")
            return None
        
        # Check toxicity (mock - integrate with moderation_service)
        toxicity_score = self._check_toxicity(content)
        
        # Create message
        message = TempChatMessage(
            chat_id=chat_id,
            user_id=user_id,
            content=content,
            toxicity_score=toxicity_score,
            is_moderated=toxicity_score >= self.config["toxic_threshold"],
            moderation_status="flagged" if toxicity_score >= self.config["toxic_threshold"] else "approved"
        )
        
        db.add(message)
        
        # Update chat stats
        chat.message_count += 1
        chat.last_message_at = datetime.utcnow()
        
        # Update avg messages per hour
        if chat.created_at:
            hours_active = max((datetime.utcnow() - chat.created_at).total_seconds() / 3600, 1)
            chat.avg_messages_per_hour = chat.message_count / hours_active
        
        # Update participant stats
        participant.message_count += 1
        
        # Check for toxic message threshold
        if toxicity_score >= self.config["toxic_threshold"]:
            chat.toxic_message_count += 1
            if chat.toxic_message_count >= self.config["suspend_after_flags"]:
                chat.is_suspended = True
                chat.status = "suspended"
        
        db.commit()
        db.refresh(message)
        
        return message
    
    def get_messages(
        self,
        db: Session,
        chat_id: int,
        user_id: int,
        limit: int = 50,
        before_id: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Get messages from a chat"""
        # Verify user is participant
        participant = db.query(TempChatParticipant).filter(
            and_(
                TempChatParticipant.chat_id == chat_id,
                TempChatParticipant.user_id == user_id
            )
        ).first()
        
        if not participant:
            return []
        
        query = db.query(TempChatMessage).filter(
            and_(
                TempChatMessage.chat_id == chat_id,
                TempChatMessage.is_deleted == False
            )
        )
        
        # Filter out flagged messages (unless user is moderator)
        query = query.filter(
            or_(
                TempChatMessage.moderation_status == "approved",
                TempChatMessage.user_id == user_id  # User can see their own
            )
        )
        
        if before_id:
            query = query.filter(TempChatMessage.id < before_id)
        
        messages = query.order_by(TempChatMessage.id.desc()).limit(limit).all()
        
        # Update last read
        participant.last_read_at = datetime.utcnow()
        db.commit()
        
        return [
            {
                "id": m.id,
                "user_id": m.user_id,
                "content": m.content,
                "created_at": m.created_at.isoformat() if m.created_at else None,
                "is_mine": m.user_id == user_id,
                "is_flagged": m.moderation_status == "flagged"
            }
            for m in reversed(messages)
        ]
    
    # ============================================================
    # MODERATION
    # ============================================================
    
    def _check_toxicity(self, content: str) -> float:
        """
        Check content toxicity score.
        
        TODO: Integrate with moderation_service for real analysis
        """
        # Simple keyword check (placeholder)
        toxic_keywords = ["spam", "scam", "fake", "hate"]
        content_lower = content.lower()
        
        score = 0.0
        for keyword in toxic_keywords:
            if keyword in content_lower:
                score += 0.3
        
        return min(score, 1.0)
    
    def flag_message(
        self,
        db: Session,
        message_id: int,
        reporter_id: int,
        reason: str
    ) -> bool:
        """Flag a message for moderation review"""
        message = db.query(TempChatMessage).filter(
            TempChatMessage.id == message_id
        ).first()
        
        if not message:
            return False
        
        message.is_moderated = True
        message.moderation_status = "flagged"
        
        # Update chat toxic count
        chat = db.query(TempChat).filter(TempChat.id == message.chat_id).first()
        if chat:
            chat.moderation_flags += 1
        
        db.commit()
        
        logger.info(f"Message {message_id} flagged by user {reporter_id}: {reason}")
        return True
    
    # ============================================================
    # LIFECYCLE MANAGEMENT
    # ============================================================
    
    def process_expired_chats(self, db: Session) -> int:
        """
        Process and close expired chats.
        Called by background worker.
        """
        now = datetime.utcnow()
        
        # Find expired chats
        expired = db.query(TempChat).filter(
            and_(
                TempChat.status == "active",
                TempChat.expires_at <= now
            )
        ).all()
        
        closed_count = 0
        for chat in expired:
            self.close_chat(db, chat.id, "expired")
            closed_count += 1
        
        # Also close inactive chats
        inactive_threshold = now - timedelta(hours=self.config["inactive_close_hours"])
        
        inactive = db.query(TempChat).filter(
            and_(
                TempChat.status == "active",
                or_(
                    TempChat.last_message_at == None,
                    TempChat.last_message_at <= inactive_threshold
                ),
                TempChat.message_count > 0  # Only if had messages before
            )
        ).all()
        
        for chat in inactive:
            self.close_chat(db, chat.id, "inactivity")
            closed_count += 1
        
        logger.info(f"Closed {closed_count} expired/inactive chats")
        return closed_count
    
    def on_event_completed(self, db: Session, event_id: int):
        """
        Handle event completion.
        Start the 24-hour countdown for chat expiration.
        """
        chats = db.query(TempChat).filter(
            and_(
                TempChat.event_id == event_id,
                TempChat.status == "active"
            )
        ).all()
        
        for chat in chats:
            chat.expires_at = datetime.utcnow() + timedelta(
                hours=self.config["default_expiry_hours"]
            )
        
        db.commit()
        logger.info(f"Updated expiry for {len(chats)} chats on event {event_id} completion")
    
    # ============================================================
    # STATISTICS
    # ============================================================
    
    def get_chat_stats(
        self,
        db: Session,
        chat_id: int
    ) -> Dict[str, Any]:
        """Get statistics for a chat"""
        chat = db.query(TempChat).filter(TempChat.id == chat_id).first()
        
        if not chat:
            return {}
        
        # Get participant details
        participants = db.query(TempChatParticipant).filter(
            TempChatParticipant.chat_id == chat_id
        ).all()
        
        active_count = sum(1 for p in participants if p.is_active)
        
        return {
            "chat_id": chat.id,
            "event_id": chat.event_id,
            "status": chat.status,
            "created_at": chat.created_at.isoformat() if chat.created_at else None,
            "expires_at": chat.expires_at.isoformat() if chat.expires_at else None,
            "metrics": {
                "message_count": chat.message_count,
                "active_participants": active_count,
                "total_participants": len(participants),
                "avg_messages_per_hour": round(chat.avg_messages_per_hour or 0, 2),
                "toxic_message_count": chat.toxic_message_count,
                "moderation_flags": chat.moderation_flags
            },
            "is_suspended": chat.is_suspended
        }


# Singleton instance
temp_chat_service = TempChatService()
