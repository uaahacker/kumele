"""
Support Email API endpoints.

Handles AI-powered email support system.

IMPORTANT: Support is EMAIL-ONLY (per requirements).
- Uses Acelle SMTP or IMAP webhook
- NO in-app support chat

Support APIs (4 per spec):
1. POST /support/email/incoming - Process incoming email
2. POST /support/email/reply/:id - Send reply
3. POST /support/email/escalate/:id - Escalate to tier 2
4. GET /support/email/queue - View email queue

AI Features:
- Category classification (billing, technical, account, event, general)
- Sentiment analysis (positive, neutral, negative)
- Priority calculation (1-5 scale)
- Auto-generated reply draft
- Entity extraction (emails, phones, IDs)

Escalation Triggers:
- Priority >= 4
- Negative sentiment
- Specific keywords (urgent, legal, etc.)
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
import logging

from app.database import get_db
from app.services.support_service import SupportService
from app.schemas.schemas import (
    SupportEmailIncomingRequest,
    SupportEmailResponse,
    SupportEmailReplyRequest,
    SupportEmailReplyResponse,
    SupportEmailEscalateRequest,
    SupportEmailEscalateResponse,
    SupportEmailDetailsResponse
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/support", tags=["Support"])


@router.post(
    "/email/incoming",
    response_model=SupportEmailResponse,
    summary="Process Incoming Email",
    description="""
    Process an incoming support email.
    
    AI Analysis:
    - Category classification (billing, technical, account, event, general)
    - Sentiment analysis (positive, neutral, negative)
    - Priority calculation (1-5 scale)
    - Entity extraction (emails, phones, IDs)
    - Auto-generated reply draft
    
    Escalation triggers:
    - Priority >= 4
    - Negative sentiment
    - Specific keywords (urgent, legal, etc.)
    
    Returns:
    - Email ID
    - Analysis results
    - Suggested reply draft
    - Escalation flag
    """
)
async def process_incoming_email(
    request: SupportEmailIncomingRequest,
    db: AsyncSession = Depends(get_db)
):
    """Process incoming support email."""
    try:
        result = await SupportService.process_incoming_email(
            db=db,
            from_email=request.from_email,
            subject=request.subject,
            body=request.body,
            user_id=request.user_id,
            thread_id=request.thread_id
        )
        
        await db.commit()
        return result
        
    except Exception as e:
        await db.rollback()
        logger.error(f"Process email error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/email/reply/{email_id}",
    response_model=SupportEmailReplyResponse,
    summary="Reply to Email",
    description="""
    Send a reply to a support email.
    
    - Creates reply record
    - Updates original email status
    - Sends email via configured SMTP
    
    Tracks agent who responded.
    """
)
async def reply_to_email(
    email_id: str,
    request: SupportEmailReplyRequest,
    db: AsyncSession = Depends(get_db)
):
    """Reply to support email."""
    try:
        result = await SupportService.reply_to_email(
            db=db,
            email_id=email_id,
            reply_body=request.reply_body,
            agent_id=request.agent_id
        )
        
        if not result.get("success"):
            raise HTTPException(status_code=400, detail=result.get("message"))
        
        await db.commit()
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Reply error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/email/escalate/{email_id}",
    response_model=SupportEmailEscalateResponse,
    summary="Escalate Email",
    description="""
    Escalate a support email to higher tier.
    
    - Increases priority
    - Marks as escalated
    - Records escalation reason
    
    Used when:
    - Complex issues
    - VIP customers
    - Legal matters
    - Technical expertise needed
    """
)
async def escalate_email(
    email_id: str,
    request: SupportEmailEscalateRequest,
    db: AsyncSession = Depends(get_db)
):
    """Escalate support email."""
    try:
        result = await SupportService.escalate_email(
            db=db,
            email_id=email_id,
            reason=request.reason,
            escalated_by=request.escalated_by
        )
        
        if not result.get("success"):
            raise HTTPException(status_code=400, detail=result.get("message"))
        
        await db.commit()
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.error(f"Escalate error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================
# GET ENDPOINTS - STATIC PATHS FIRST!
# (Must come before /email/{email_id})
# ============================================

@router.get(
    "/email/list",
    summary="List Support Emails",
    description="""
    List all support emails with filters.
    
    Returns paginated list of emails with status, category, and priority.
    Used by admin/support UI.
    """
)
async def list_emails(
    status: Optional[str] = Query(None, description="Filter by status: received, processing, awaiting_human, replied, closed"),
    category: Optional[str] = Query(None, description="Filter by category: support, billing, partnership, feedback, abuse, other"),
    priority_min: Optional[int] = Query(None, ge=1, le=5, description="Minimum priority"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db)
):
    """List support emails (alias for queue endpoint)."""
    try:
        result = await SupportService.get_email_queue(
            db=db,
            status=status,
            category=category,
            priority_min=priority_min,
            limit=limit,
            offset=offset
        )
        
        return result
        
    except Exception as e:
        logger.error(f"List emails error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/email/queue",
    summary="Get Email Queue",
    description="Get support email queue with filters."
)
async def get_email_queue(
    status: Optional[str] = Query(None, description="Filter by status: received, processing, awaiting_human, replied, closed"),
    category: Optional[str] = Query(None, description="Filter by category: support, billing, partnership, feedback, abuse, other"),
    priority_min: Optional[int] = Query(None, ge=1, le=5, description="Minimum priority"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db)
):
    """Get email queue."""
    try:
        result = await SupportService.get_email_queue(
            db=db,
            status=status,
            category=category,
            priority_min=priority_min,
            limit=limit,
            offset=offset
        )
        
        return result
        
    except Exception as e:
        logger.error(f"Get queue error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/email/stats",
    summary="Get Support Stats",
    description="Get support email statistics."
)
async def get_support_stats(
    days: int = Query(7, ge=1, le=90, description="Statistics for last N days"),
    db: AsyncSession = Depends(get_db)
):
    """Get support statistics."""
    try:
        from sqlalchemy import select, func, and_
        from app.models.database_models import SupportEmail, SupportEmailAnalysis
        from datetime import datetime, timedelta
        
        since = datetime.utcnow() - timedelta(days=days)
        
        # Total emails
        total_query = select(func.count(SupportEmail.id)).where(
            SupportEmail.created_at >= since
        )
        total_result = await db.execute(total_query)
        total = total_result.scalar() or 0
        
        # By status
        status_query = select(
            SupportEmail.status,
            func.count(SupportEmail.id)
        ).where(
            SupportEmail.created_at >= since
        ).group_by(SupportEmail.status)
        
        status_result = await db.execute(status_query)
        by_status = dict(status_result.all())
        
        # By category
        cat_query = select(
            SupportEmailAnalysis.category,
            func.count(SupportEmailAnalysis.email_id)
        ).group_by(SupportEmailAnalysis.category)
        
        cat_result = await db.execute(cat_query)
        by_category = dict(cat_result.all())
        
        return {
            "period_days": days,
            "total_emails": total,
            "by_status": by_status,
            "by_category": by_category
        }
        
    except Exception as e:
        logger.error(f"Get stats error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================
# GET ENDPOINT WITH DYNAMIC PATH - MUST BE LAST!
# ============================================

@router.get(
    "/email/{email_id}",
    response_model=SupportEmailDetailsResponse,
    summary="Get Email Details",
    description="""
    Get full details of a support email.
    
    Returns:
    - Email content
    - AI analysis
    - Thread history
    - Status and priority
    - Agent assignments
    """
)
async def get_email_details(
    email_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Get email details."""
    try:
        result = await SupportService.get_email_details(db, email_id)
        
        if "error" in result:
            raise HTTPException(status_code=404, detail=result["error"])
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get email details error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
