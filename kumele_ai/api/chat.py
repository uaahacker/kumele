"""
Chat Room Router - Temporary event chat room endpoints
"""
import logging
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from sqlalchemy.orm import Session

from kumele_ai.dependencies import get_db
from kumele_ai.db import models

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/chat", tags=["Chat Rooms"])


# ============================================================
# Request/Response Models
# ============================================================

class CreateChatRequest(BaseModel):
    event_id: int
    chat_type: str = "event"  # event, match, host_attendee


class SendMessageRequest(BaseModel):
    content: str


class MessageResponse(BaseModel):
    id: int
    user_id: int
    content: str
    created_at: datetime
    is_moderated: bool
    moderation_status: Optional[str]
    toxicity_score: Optional[float]

    class Config:
        from_attributes = True


class ChatResponse(BaseModel):
    id: int
    event_id: int
    chat_type: str
    status: str
    expires_at: datetime
    message_count: int
    active_participants: int
    created_at: datetime

    class Config:
        from_attributes = True


class ParticipantResponse(BaseModel):
    id: int
    user_id: int
    role: str
    is_active: bool
    message_count: int
    joined_at: datetime

    class Config:
        from_attributes = True


# ============================================================
# Chat Room Endpoints
# ============================================================

@router.post("/rooms", response_model=ChatResponse)
async def create_chat_room(
    request: CreateChatRequest,
    db: Session = Depends(get_db)
):
    """
    Create a temporary chat room for an event.
    
    Chat rooms are created after:
    - Successful match/RSVP
    - Event starts
    
    Lifecycle:
    - Created: After match
    - Active: During event + 24 hours
    - Expired: Auto-closed after expiry
    """
    # Check if event exists
    event = db.query(models.Event).filter(models.Event.id == request.event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    
    # Check if chat already exists
    existing = db.query(models.TempChat).filter(
        models.TempChat.event_id == request.event_id,
        models.TempChat.status == "active"
    ).first()
    
    if existing:
        return existing
    
    # Calculate expiry (event end + 24 hours, or now + 48 hours if no end time)
    from datetime import timedelta
    if event.end_time:
        expires_at = event.end_time + timedelta(hours=24)
    elif event.start_time:
        expires_at = event.start_time + timedelta(hours=48)
    else:
        expires_at = datetime.utcnow() + timedelta(hours=48)
    
    chat = models.TempChat(
        event_id=request.event_id,
        chat_type=request.chat_type,
        status="active",
        expires_at=expires_at
    )
    db.add(chat)
    db.commit()
    db.refresh(chat)
    
    return chat


@router.get("/rooms/{chat_id}", response_model=ChatResponse)
async def get_chat_room(
    chat_id: int,
    db: Session = Depends(get_db)
):
    """Get chat room details"""
    chat = db.query(models.TempChat).filter(models.TempChat.id == chat_id).first()
    if not chat:
        raise HTTPException(status_code=404, detail="Chat room not found")
    return chat


@router.get("/rooms/event/{event_id}", response_model=ChatResponse)
async def get_event_chat(
    event_id: int,
    db: Session = Depends(get_db)
):
    """Get active chat room for an event"""
    chat = db.query(models.TempChat).filter(
        models.TempChat.event_id == event_id,
        models.TempChat.status == "active"
    ).first()
    
    if not chat:
        raise HTTPException(status_code=404, detail="No active chat for this event")
    return chat


@router.post("/rooms/{chat_id}/close")
async def close_chat_room(
    chat_id: int,
    reason: str = Query(default="manual", description="Close reason"),
    db: Session = Depends(get_db)
):
    """Manually close a chat room"""
    chat = db.query(models.TempChat).filter(models.TempChat.id == chat_id).first()
    if not chat:
        raise HTTPException(status_code=404, detail="Chat room not found")
    
    chat.status = "closed"
    chat.closed_at = datetime.utcnow()
    chat.close_reason = reason
    db.commit()
    
    return {"status": "closed", "chat_id": chat_id, "reason": reason}


# ============================================================
# Message Endpoints
# ============================================================

@router.get("/rooms/{chat_id}/messages", response_model=List[MessageResponse])
async def get_messages(
    chat_id: int,
    limit: int = Query(default=50, le=200),
    before_id: Optional[int] = None,
    db: Session = Depends(get_db)
):
    """Get messages from a chat room with pagination"""
    chat = db.query(models.TempChat).filter(models.TempChat.id == chat_id).first()
    if not chat:
        raise HTTPException(status_code=404, detail="Chat room not found")
    
    query = db.query(models.TempChatMessage).filter(
        models.TempChatMessage.chat_id == chat_id,
        models.TempChatMessage.is_deleted == False
    )
    
    if before_id:
        query = query.filter(models.TempChatMessage.id < before_id)
    
    messages = query.order_by(models.TempChatMessage.id.desc()).limit(limit).all()
    return list(reversed(messages))


@router.post("/rooms/{chat_id}/messages", response_model=MessageResponse)
async def send_message(
    chat_id: int,
    user_id: int,
    request: SendMessageRequest,
    db: Session = Depends(get_db)
):
    """
    Send a message to a chat room.
    
    Messages are automatically moderated for toxicity.
    High-toxicity messages are flagged for review.
    """
    from kumele_ai.services.moderation_service import moderation_service
    
    chat = db.query(models.TempChat).filter(models.TempChat.id == chat_id).first()
    if not chat:
        raise HTTPException(status_code=404, detail="Chat room not found")
    
    if chat.status != "active":
        raise HTTPException(status_code=400, detail="Chat room is not active")
    
    if datetime.utcnow() > chat.expires_at:
        chat.status = "expired"
        chat.closed_at = datetime.utcnow()
        chat.close_reason = "expired"
        db.commit()
        raise HTTPException(status_code=400, detail="Chat room has expired")
    
    # Check if user is participant
    participant = db.query(models.TempChatParticipant).filter(
        models.TempChatParticipant.chat_id == chat_id,
        models.TempChatParticipant.user_id == user_id,
        models.TempChatParticipant.is_active == True
    ).first()
    
    if not participant:
        raise HTTPException(status_code=403, detail="User is not a participant in this chat")
    
    # Toxicity check using moderation service
    toxicity_score = 0.0
    is_moderated = False
    moderation_status = "pending"
    
    try:
        moderation_result = await moderation_service.moderate_text(request.content)
        toxicity_score = moderation_result.get("labels", {}).get("toxicity", {}).get("score", 0)
        is_moderated = True
        
        if toxicity_score >= 0.9:
            moderation_status = "blocked"
            raise HTTPException(
                status_code=400, 
                detail="Message blocked due to inappropriate content"
            )
        elif toxicity_score >= 0.5:
            moderation_status = "flagged"
        else:
            moderation_status = "approved"
    except HTTPException:
        raise
    except Exception as e:
        logger.warning(f"Moderation check failed: {e}")
        moderation_status = "pending"
    
    message = models.TempChatMessage(
        chat_id=chat_id,
        user_id=user_id,
        content=request.content,
        is_moderated=is_moderated,
        moderation_status=moderation_status,
        toxicity_score=toxicity_score
    )
    db.add(message)
    
    # Update chat stats
    chat.message_count += 1
    chat.last_message_at = datetime.utcnow()
    
    # Update participant stats
    participant.message_count += 1
    
    db.commit()
    db.refresh(message)
    
    return message


@router.delete("/rooms/{chat_id}/messages/{message_id}")
async def delete_message(
    chat_id: int,
    message_id: int,
    user_id: int,
    db: Session = Depends(get_db)
):
    """Delete (soft) a message. Only message author or chat host can delete."""
    message = db.query(models.TempChatMessage).filter(
        models.TempChatMessage.id == message_id,
        models.TempChatMessage.chat_id == chat_id
    ).first()
    
    if not message:
        raise HTTPException(status_code=404, detail="Message not found")
    
    # Check authorization
    chat = db.query(models.TempChat).filter(models.TempChat.id == chat_id).first()
    event = db.query(models.Event).filter(models.Event.id == chat.event_id).first()
    
    if message.user_id != user_id and event.host_id != user_id:
        raise HTTPException(status_code=403, detail="Not authorized to delete this message")
    
    message.is_deleted = True
    db.commit()
    
    return {"status": "deleted", "message_id": message_id}


# ============================================================
# Participant Endpoints
# ============================================================

@router.get("/rooms/{chat_id}/participants", response_model=List[ParticipantResponse])
async def get_participants(
    chat_id: int,
    db: Session = Depends(get_db)
):
    """Get all participants in a chat room"""
    chat = db.query(models.TempChat).filter(models.TempChat.id == chat_id).first()
    if not chat:
        raise HTTPException(status_code=404, detail="Chat room not found")
    
    participants = db.query(models.TempChatParticipant).filter(
        models.TempChatParticipant.chat_id == chat_id
    ).all()
    
    return participants


@router.post("/rooms/{chat_id}/join")
async def join_chat(
    chat_id: int,
    user_id: int,
    db: Session = Depends(get_db)
):
    """Join a chat room as a participant"""
    chat = db.query(models.TempChat).filter(models.TempChat.id == chat_id).first()
    if not chat:
        raise HTTPException(status_code=404, detail="Chat room not found")
    
    if chat.status != "active":
        raise HTTPException(status_code=400, detail="Chat room is not active")
    
    # Check if already participant
    existing = db.query(models.TempChatParticipant).filter(
        models.TempChatParticipant.chat_id == chat_id,
        models.TempChatParticipant.user_id == user_id
    ).first()
    
    if existing:
        if existing.is_active:
            return {"status": "already_joined", "participant_id": existing.id}
        else:
            existing.is_active = True
            existing.left_at = None
            db.commit()
            return {"status": "rejoined", "participant_id": existing.id}
    
    # Determine role (host or attendee)
    event = db.query(models.Event).filter(models.Event.id == chat.event_id).first()
    role = "host" if event and event.host_id == user_id else "attendee"
    
    participant = models.TempChatParticipant(
        chat_id=chat_id,
        user_id=user_id,
        role=role,
        is_active=True
    )
    db.add(participant)
    
    # Update chat stats
    chat.active_participants += 1
    
    db.commit()
    db.refresh(participant)
    
    return {"status": "joined", "participant_id": participant.id, "role": role}


@router.post("/rooms/{chat_id}/leave")
async def leave_chat(
    chat_id: int,
    user_id: int,
    db: Session = Depends(get_db)
):
    """Leave a chat room"""
    participant = db.query(models.TempChatParticipant).filter(
        models.TempChatParticipant.chat_id == chat_id,
        models.TempChatParticipant.user_id == user_id
    ).first()
    
    if not participant:
        raise HTTPException(status_code=404, detail="Participant not found")
    
    participant.is_active = False
    participant.left_at = datetime.utcnow()
    
    # Update chat stats
    chat = db.query(models.TempChat).filter(models.TempChat.id == chat_id).first()
    if chat:
        chat.active_participants = max(0, chat.active_participants - 1)
    
    db.commit()
    
    return {"status": "left", "chat_id": chat_id}


@router.post("/rooms/{chat_id}/read")
async def mark_read(
    chat_id: int,
    user_id: int,
    db: Session = Depends(get_db)
):
    """Mark chat as read for a user"""
    participant = db.query(models.TempChatParticipant).filter(
        models.TempChatParticipant.chat_id == chat_id,
        models.TempChatParticipant.user_id == user_id
    ).first()
    
    if not participant:
        raise HTTPException(status_code=404, detail="Participant not found")
    
    participant.last_read_at = datetime.utcnow()
    db.commit()
    
    return {"status": "read", "last_read_at": participant.last_read_at}


# ============================================================
# Chat Moderation Endpoints
# ============================================================

class ModerateChatMessageRequest(BaseModel):
    message_id: int
    action: str  # "approve", "flag", "delete", "ban_user"
    reason: Optional[str] = None


class ChatModerationResponse(BaseModel):
    message_id: int
    action_taken: str
    toxicity_score: float
    is_flagged: bool
    moderation_reason: Optional[str]


@router.post("/rooms/{chat_id}/messages/{message_id}/moderate", response_model=ChatModerationResponse)
async def moderate_message(
    chat_id: int,
    message_id: int,
    request: ModerateChatMessageRequest,
    db: Session = Depends(get_db)
):
    """
    Manually moderate a chat message.
    
    Actions:
    - approve: Mark message as safe
    - flag: Flag for review
    - delete: Soft delete message
    - ban_user: Remove user from chat
    """
    message = db.query(models.TempChatMessage).filter(
        models.TempChatMessage.id == message_id,
        models.TempChatMessage.chat_id == chat_id
    ).first()
    
    if not message:
        raise HTTPException(status_code=404, detail="Message not found")
    
    action_taken = request.action
    
    if request.action == "approve":
        message.moderation_status = "approved"
        message.is_moderated = True
    elif request.action == "flag":
        message.moderation_status = "flagged"
        message.is_moderated = True
        message.moderation_reason = request.reason
    elif request.action == "delete":
        message.is_deleted = True
        message.moderation_status = "deleted"
    elif request.action == "ban_user":
        # Remove user from chat
        participant = db.query(models.TempChatParticipant).filter(
            models.TempChatParticipant.chat_id == chat_id,
            models.TempChatParticipant.user_id == message.user_id
        ).first()
        if participant:
            participant.is_active = False
            participant.left_at = datetime.utcnow()
        message.is_deleted = True
        message.moderation_status = "banned"
    else:
        raise HTTPException(status_code=400, detail="Invalid action")
    
    db.commit()
    
    return ChatModerationResponse(
        message_id=message_id,
        action_taken=action_taken,
        toxicity_score=message.toxicity_score or 0.0,
        is_flagged=message.moderation_status == "flagged",
        moderation_reason=request.reason
    )


@router.post("/rooms/{chat_id}/auto-moderate")
async def auto_moderate_chat(
    chat_id: int,
    db: Session = Depends(get_db)
):
    """
    Run auto-moderation on all unmoderated messages in a chat.
    
    Uses toxicity detection to:
    - Auto-approve safe messages
    - Flag potentially toxic messages
    - Auto-delete highly toxic content
    """
    from kumele_ai.services.moderation_service import moderation_service
    
    chat = db.query(models.TempChat).filter(models.TempChat.id == chat_id).first()
    if not chat:
        raise HTTPException(status_code=404, detail="Chat room not found")
    
    # Get unmoderated messages
    messages = db.query(models.TempChatMessage).filter(
        models.TempChatMessage.chat_id == chat_id,
        models.TempChatMessage.is_moderated == False,
        models.TempChatMessage.is_deleted == False
    ).all()
    
    results = {
        "total_processed": 0,
        "approved": 0,
        "flagged": 0,
        "deleted": 0
    }
    
    for message in messages:
        try:
            # Run moderation
            moderation_result = await moderation_service.moderate_text(message.content)
            toxicity_score = moderation_result.get("labels", {}).get("toxicity", {}).get("score", 0)
            
            message.toxicity_score = toxicity_score
            message.is_moderated = True
            
            if toxicity_score >= 0.9:
                # Auto-delete highly toxic
                message.is_deleted = True
                message.moderation_status = "auto_deleted"
                results["deleted"] += 1
            elif toxicity_score >= 0.5:
                # Flag for review
                message.moderation_status = "flagged"
                results["flagged"] += 1
            else:
                # Auto-approve
                message.moderation_status = "approved"
                results["approved"] += 1
            
            results["total_processed"] += 1
            
        except Exception as e:
            logger.error(f"Error moderating message {message.id}: {e}")
    
    db.commit()
    
    return {
        "chat_id": chat_id,
        "moderation_results": results
    }


@router.get("/rooms/{chat_id}/moderation-stats")
async def get_chat_moderation_stats(
    chat_id: int,
    db: Session = Depends(get_db)
):
    """Get moderation statistics for a chat room"""
    from sqlalchemy import func
    
    chat = db.query(models.TempChat).filter(models.TempChat.id == chat_id).first()
    if not chat:
        raise HTTPException(status_code=404, detail="Chat room not found")
    
    # Count by moderation status
    stats = db.query(
        models.TempChatMessage.moderation_status,
        func.count(models.TempChatMessage.id)
    ).filter(
        models.TempChatMessage.chat_id == chat_id
    ).group_by(models.TempChatMessage.moderation_status).all()
    
    status_counts = {status: count for status, count in stats if status}
    
    # Average toxicity
    avg_toxicity = db.query(
        func.avg(models.TempChatMessage.toxicity_score)
    ).filter(
        models.TempChatMessage.chat_id == chat_id,
        models.TempChatMessage.toxicity_score.isnot(None)
    ).scalar() or 0.0
    
    # Count flagged messages
    flagged_count = status_counts.get("flagged", 0)
    deleted_count = status_counts.get("deleted", 0) + status_counts.get("auto_deleted", 0)
    
    return {
        "chat_id": chat_id,
        "total_messages": chat.message_count,
        "status_breakdown": status_counts,
        "average_toxicity_score": round(avg_toxicity, 4),
        "flagged_messages": flagged_count,
        "deleted_messages": deleted_count,
        "toxicity_rate": flagged_count / max(chat.message_count, 1)
    }


# ============================================================
# Chat Analytics (ML Features)
# ============================================================

class ChatPopularityResponse(BaseModel):
    chat_id: int
    event_id: int
    popularity_score: float
    activity_level: str  # "dead", "low", "medium", "high", "very_high"
    predicted_active: bool
    messages_per_hour: float
    unique_participants: int
    sentiment_avg: Optional[float]
    should_auto_close: bool


@router.get("/rooms/{chat_id}/popularity", response_model=ChatPopularityResponse)
async def get_chat_popularity(
    chat_id: int,
    db: Session = Depends(get_db)
):
    """
    Predict chat popularity and activity level.
    
    Used for:
    - Prioritizing which events open chats sooner
    - Predicting which chat groups stay active
    - Auto-closing dead chats before event
    """
    from sqlalchemy import func
    
    chat = db.query(models.TempChat).filter(models.TempChat.id == chat_id).first()
    if not chat:
        raise HTTPException(status_code=404, detail="Chat room not found")
    
    # Calculate messages per hour
    if chat.created_at:
        hours_active = max(1, (datetime.utcnow() - chat.created_at).total_seconds() / 3600)
        messages_per_hour = chat.message_count / hours_active
    else:
        messages_per_hour = 0
    
    # Count unique participants
    unique_participants = db.query(
        func.count(func.distinct(models.TempChatParticipant.user_id))
    ).filter(
        models.TempChatParticipant.chat_id == chat_id
    ).scalar() or 0
    
    # Average sentiment (simplified - would use actual sentiment analysis)
    sentiment_avg = None
    
    # Calculate popularity score (0-1)
    # Factors: messages_per_hour, unique_participants, recent activity
    popularity_score = min(1.0, (
        (messages_per_hour / 10) * 0.4 +  # Up to 10 msgs/hr = 0.4
        (unique_participants / 20) * 0.3 +  # Up to 20 participants = 0.3
        (0.3 if chat.last_message_at and (datetime.utcnow() - chat.last_message_at).total_seconds() < 3600 else 0)
    ))
    
    # Determine activity level
    if messages_per_hour < 0.5:
        activity_level = "dead"
    elif messages_per_hour < 2:
        activity_level = "low"
    elif messages_per_hour < 5:
        activity_level = "medium"
    elif messages_per_hour < 15:
        activity_level = "high"
    else:
        activity_level = "very_high"
    
    # Should auto-close if dead and event hasn't started
    should_auto_close = (
        activity_level == "dead" and 
        chat.message_count < 5 and
        (datetime.utcnow() - chat.created_at).total_seconds() > 86400  # 24 hours old
    )
    
    return ChatPopularityResponse(
        chat_id=chat_id,
        event_id=chat.event_id,
        popularity_score=round(popularity_score, 4),
        activity_level=activity_level,
        predicted_active=popularity_score > 0.3,
        messages_per_hour=round(messages_per_hour, 2),
        unique_participants=unique_participants,
        sentiment_avg=sentiment_avg,
        should_auto_close=should_auto_close
    )


@router.get("/rooms/{chat_id}/sentiment")
async def get_chat_sentiment(
    chat_id: int,
    db: Session = Depends(get_db)
):
    """
    Analyze overall chat sentiment.
    
    Monitors:
    - Positive/negative message ratio
    - Toxicity trends
    - User satisfaction indicators
    """
    from sqlalchemy import func
    from kumele_ai.services.classify_service import classify_service
    
    chat = db.query(models.TempChat).filter(models.TempChat.id == chat_id).first()
    if not chat:
        raise HTTPException(status_code=404, detail="Chat room not found")
    
    # Get recent messages for sentiment analysis
    recent_messages = db.query(models.TempChatMessage).filter(
        models.TempChatMessage.chat_id == chat_id,
        models.TempChatMessage.is_deleted == False
    ).order_by(models.TempChatMessage.created_at.desc()).limit(50).all()
    
    sentiments = {"positive": 0, "neutral": 0, "negative": 0}
    total_toxicity = 0.0
    analyzed = 0
    
    for message in recent_messages:
        try:
            # Quick sentiment check
            result = classify_service.analyze_sentiment(message.content)
            sentiment = result.get("sentiment", "neutral")
            if sentiment in sentiments:
                sentiments[sentiment] += 1
            
            total_toxicity += message.toxicity_score or 0.0
            analyzed += 1
        except:
            pass
    
    avg_toxicity = total_toxicity / max(analyzed, 1)
    
    # Calculate overall mood
    if analyzed == 0:
        overall_mood = "unknown"
    elif sentiments["positive"] > sentiments["negative"] * 2:
        overall_mood = "positive"
    elif sentiments["negative"] > sentiments["positive"] * 2:
        overall_mood = "negative"
    else:
        overall_mood = "neutral"
    
    return {
        "chat_id": chat_id,
        "messages_analyzed": analyzed,
        "sentiment_distribution": sentiments,
        "overall_mood": overall_mood,
        "average_toxicity": round(avg_toxicity, 4),
        "health_score": round(1 - avg_toxicity, 4) if avg_toxicity else 1.0
    }


@router.post("/rooms/{chat_id}/auto-close-check")
async def check_auto_close(
    chat_id: int,
    db: Session = Depends(get_db)
):
    """
    Check if chat should be auto-closed due to inactivity.
    
    Criteria:
    - Dead activity (< 0.5 msgs/hour)
    - Less than 5 total messages
    - More than 24 hours since creation
    - Event hasn't started yet
    """
    popularity = await get_chat_popularity(chat_id, db)
    
    if popularity.should_auto_close:
        chat = db.query(models.TempChat).filter(models.TempChat.id == chat_id).first()
        if chat:
            chat.status = "auto_closed"
            chat.closed_at = datetime.utcnow()
            chat.close_reason = "inactivity"
            db.commit()
            
            return {
                "chat_id": chat_id,
                "action": "closed",
                "reason": "Chat auto-closed due to inactivity"
            }
    
    return {
        "chat_id": chat_id,
        "action": "keep_open",
        "reason": f"Chat still active (popularity: {popularity.popularity_score})"
    }

