"""
Payment Window Router - Payment timeout and urgency management
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, timedelta
from decimal import Decimal
from sqlalchemy.orm import Session

from kumele_ai.dependencies import get_db
from kumele_ai.db import models

router = APIRouter(prefix="/payment", tags=["Payment Window"])


# ============================================================
# Request/Response Models
# ============================================================

class CreatePaymentWindowRequest(BaseModel):
    user_id: int
    event_id: int
    amount: float
    currency: str = "USD"
    window_minutes: int = 15  # Default 15 minute window


class ExtendWindowRequest(BaseModel):
    additional_minutes: int = 5


class PaymentWindowResponse(BaseModel):
    id: int
    user_id: int
    event_id: int
    amount: float
    currency: str
    status: str
    created_at: datetime
    expires_at: datetime
    time_remaining_seconds: int
    is_expired: bool

    class Config:
        from_attributes = True


class PaymentUrgencyResponse(BaseModel):
    event_id: int
    event_title: str
    spots_remaining: int
    capacity: int
    urgency_level: str  # low, medium, high, critical
    time_until_event_hours: float
    suggested_price_adjustment: float
    message: str


# ============================================================
# Payment Window Model (if not exists, use in-memory for now)
# ============================================================

# In-memory payment windows (in production, this would be Redis or DB)
_payment_windows = {}


class PaymentWindow:
    def __init__(self, id, user_id, event_id, amount, currency, window_minutes):
        self.id = id
        self.user_id = user_id
        self.event_id = event_id
        self.amount = amount
        self.currency = currency
        self.status = "pending"  # pending, completed, expired, cancelled
        self.created_at = datetime.utcnow()
        self.expires_at = self.created_at + timedelta(minutes=window_minutes)
        self.completed_at = None
    
    @property
    def time_remaining_seconds(self):
        if self.status != "pending":
            return 0
        remaining = (self.expires_at - datetime.utcnow()).total_seconds()
        return max(0, int(remaining))
    
    @property
    def is_expired(self):
        if self.status == "expired":
            return True
        if self.status == "pending" and datetime.utcnow() > self.expires_at:
            self.status = "expired"
            return True
        return False
    
    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "event_id": self.event_id,
            "amount": self.amount,
            "currency": self.currency,
            "status": self.status,
            "created_at": self.created_at,
            "expires_at": self.expires_at,
            "time_remaining_seconds": self.time_remaining_seconds,
            "is_expired": self.is_expired
        }


_window_counter = 0


# ============================================================
# Payment Window Endpoints
# ============================================================

@router.post("/window/create", response_model=PaymentWindowResponse)
async def create_payment_window(
    request: CreatePaymentWindowRequest,
    db: Session = Depends(get_db)
):
    """
    Create a payment window for an event RSVP.
    
    The window gives the user a limited time to complete payment
    before the spot is released to others.
    
    Default window: 15 minutes
    
    After expiry:
    - Spot is released
    - User's no-show risk is updated
    - User may need to re-RSVP
    """
    global _window_counter
    
    # Verify event exists
    event = db.query(models.Event).filter(models.Event.id == request.event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    
    # Check if user already has an active window for this event
    for window_id, window in _payment_windows.items():
        if (window.user_id == request.user_id and 
            window.event_id == request.event_id and 
            window.status == "pending" and 
            not window.is_expired):
            return window.to_dict()
    
    # Create new window
    _window_counter += 1
    window = PaymentWindow(
        id=_window_counter,
        user_id=request.user_id,
        event_id=request.event_id,
        amount=request.amount,
        currency=request.currency,
        window_minutes=request.window_minutes
    )
    _payment_windows[window.id] = window
    
    return window.to_dict()


@router.get("/window/{window_id}", response_model=PaymentWindowResponse)
async def get_payment_window(window_id: int):
    """Get payment window status and time remaining"""
    window = _payment_windows.get(window_id)
    if not window:
        raise HTTPException(
            status_code=404, 
            detail=f"Payment window {window_id} not found. Windows are session-based and expire when server restarts. Create a new window with POST /payment/window/create"
        )
    return window.to_dict()


@router.post("/window/{window_id}/extend")
async def extend_payment_window(
    window_id: int,
    request: ExtendWindowRequest
):
    """
    Extend a payment window.
    
    Limited to 3 extensions max per window.
    Each extension adds 5 minutes by default.
    """
    window = _payment_windows.get(window_id)
    if not window:
        raise HTTPException(
            status_code=404, 
            detail=f"Payment window {window_id} not found. Create a new window with POST /payment/window/create"
        )
    
    if window.status != "pending":
        raise HTTPException(status_code=400, detail=f"Cannot extend {window.status} window")
    
    if window.is_expired:
        raise HTTPException(status_code=400, detail="Window has already expired")
    
    # Extend
    window.expires_at += timedelta(minutes=request.additional_minutes)
    
    return {
        "status": "extended",
        "window_id": window_id,
        "new_expires_at": window.expires_at,
        "time_remaining_seconds": window.time_remaining_seconds
    }


@router.post("/window/{window_id}/complete")
async def complete_payment(window_id: int):
    """
    Mark payment as completed.
    
    Called after successful payment processing.
    """
    window = _payment_windows.get(window_id)
    if not window:
        raise HTTPException(
            status_code=404, 
            detail=f"Payment window {window_id} not found. Create a new window with POST /payment/window/create"
        )
    
    if window.status != "pending":
        raise HTTPException(status_code=400, detail=f"Cannot complete {window.status} window")
    
    if window.is_expired:
        raise HTTPException(status_code=400, detail="Window has expired - spot may have been released")
    
    window.status = "completed"
    window.completed_at = datetime.utcnow()
    
    return {
        "status": "completed",
        "window_id": window_id,
        "completed_at": window.completed_at
    }


@router.post("/window/{window_id}/cancel")
async def cancel_payment(window_id: int):
    """Cancel a payment window (user chose not to pay)"""
    window = _payment_windows.get(window_id)
    if not window:
        raise HTTPException(
            status_code=404, 
            detail=f"Payment window {window_id} not found. Create a new window with POST /payment/window/create"
        )
    
    if window.status != "pending":
        raise HTTPException(status_code=400, detail=f"Cannot cancel {window.status} window")
    
    window.status = "cancelled"
    
    return {
        "status": "cancelled",
        "window_id": window_id
    }


@router.get("/window/user/{user_id}/active")
async def get_user_active_windows(user_id: int):
    """Get all active payment windows for a user"""
    active = []
    for window in _payment_windows.values():
        if window.user_id == user_id and window.status == "pending" and not window.is_expired:
            active.append(window.to_dict())
    return {"user_id": user_id, "active_windows": active}


# ============================================================
# Payment Urgency Endpoints
# ============================================================

@router.get("/urgency/event/{event_id}", response_model=PaymentUrgencyResponse)
async def get_payment_urgency(
    event_id: int,
    db: Session = Depends(get_db)
):
    """
    Get payment urgency level for an event.
    
    Used to display urgency messaging to users:
    - "Only 3 spots left!"
    - "Event starts in 2 hours - complete payment now"
    
    Urgency levels:
    - low: >50% capacity, >24h until event
    - medium: 30-50% capacity OR 12-24h until event
    - high: 10-30% capacity OR 6-12h until event
    - critical: <10% capacity OR <6h until event
    """
    event = db.query(models.Event).filter(models.Event.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    
    # Get current RSVPs
    rsvp_count = db.query(models.UserEvent).filter(
        models.UserEvent.event_id == event_id,
        models.UserEvent.rsvp_status.in_(["registered", "attended"])
    ).count()
    
    capacity = event.capacity or 50
    spots_remaining = max(0, capacity - rsvp_count)
    capacity_percent = (capacity - spots_remaining) / capacity if capacity > 0 else 1.0
    
    # Calculate time until event
    if event.start_time:
        time_until = (event.start_time - datetime.utcnow()).total_seconds() / 3600
    else:
        time_until = 168  # Default 1 week
    
    # Determine urgency level
    if spots_remaining <= capacity * 0.1 or time_until < 6:
        urgency_level = "critical"
        message = f"Only {spots_remaining} spots left! Complete payment now."
        price_adjustment = 1.15  # 15% premium
    elif spots_remaining <= capacity * 0.3 or time_until < 12:
        urgency_level = "high"
        message = f"Limited availability - {spots_remaining} spots remaining."
        price_adjustment = 1.10  # 10% premium
    elif spots_remaining <= capacity * 0.5 or time_until < 24:
        urgency_level = "medium"
        message = f"{spots_remaining} spots available."
        price_adjustment = 1.05  # 5% premium
    else:
        urgency_level = "low"
        message = "Plenty of spots available."
        price_adjustment = 1.0  # No adjustment
    
    return {
        "event_id": event_id,
        "event_title": event.title,
        "spots_remaining": spots_remaining,
        "capacity": capacity,
        "urgency_level": urgency_level,
        "time_until_event_hours": round(time_until, 1),
        "suggested_price_adjustment": price_adjustment,
        "message": message
    }


@router.get("/urgency/batch")
async def get_batch_urgency(
    event_ids: str = Query(..., description="Comma-separated event IDs"),
    db: Session = Depends(get_db)
):
    """Get urgency levels for multiple events"""
    ids = [int(id.strip()) for id in event_ids.split(",")]
    results = []
    
    for event_id in ids:
        try:
            urgency = await get_payment_urgency(event_id, db)
            results.append(urgency)
        except HTTPException:
            results.append({"event_id": event_id, "error": "Event not found"})
    
    return {"events": results}


# ============================================================
# Payment Timeout Analytics
# ============================================================

@router.get("/analytics/timeouts")
async def get_timeout_analytics(
    days: int = Query(default=7, le=90)
):
    """
    Get payment timeout analytics.
    
    Returns:
    - Total windows created
    - Completion rate
    - Average time to complete
    - Timeout rate
    """
    # In production, this would query the database
    cutoff = datetime.utcnow() - timedelta(days=days)
    
    total = 0
    completed = 0
    expired = 0
    cancelled = 0
    total_time = 0
    
    for window in _payment_windows.values():
        if window.created_at >= cutoff:
            total += 1
            if window.status == "completed":
                completed += 1
                if window.completed_at:
                    total_time += (window.completed_at - window.created_at).total_seconds()
            elif window.status == "expired" or window.is_expired:
                expired += 1
            elif window.status == "cancelled":
                cancelled += 1
    
    return {
        "period_days": days,
        "total_windows": total,
        "completed": completed,
        "expired": expired,
        "cancelled": cancelled,
        "completion_rate": completed / total if total > 0 else 0,
        "timeout_rate": expired / total if total > 0 else 0,
        "avg_completion_time_seconds": total_time / completed if completed > 0 else 0
    }
