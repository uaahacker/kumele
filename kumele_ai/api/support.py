"""
Support Router - Support email handling endpoints
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr
from typing import Optional
from sqlalchemy.orm import Session

from kumele_ai.dependencies import get_db
from kumele_ai.services.support_service import support_service

router = APIRouter()


class IncomingEmailRequest(BaseModel):
    from_email: EmailStr
    to_email: Optional[EmailStr] = None
    subject: Optional[str] = ""
    body: str


class ReplyRequest(BaseModel):
    response_text: str
    response_type: str = "ai_generated"  # ai_generated, human_edited, human_written


class EscalateRequest(BaseModel):
    reason: str
    escalation_level: str = "tier2"
    assigned_to: Optional[str] = None


@router.post("/email/incoming")
async def receive_incoming_email(
    request: IncomingEmailRequest,
    db: Session = Depends(get_db)
):
    """
    Receive incoming support email from Acelle SMTP or IMAP webhook.
    
    - Stores raw email and cleaned text
    - Classifies category and sentiment
    - Stores thread_id
    - Queues AI or human response flow
    """
    result = await support_service.process_incoming_email(
        db=db,
        from_email=request.from_email,
        to_email=request.to_email or "",
        subject=request.subject or "",
        raw_body=request.body
    )
    
    return result


@router.post("/email/reply/{email_id}")
async def send_email_reply(
    email_id: int,
    request: ReplyRequest,
    db: Session = Depends(get_db)
):
    """
    Send reply to a support email (AI or human approved).
    
    - Sends via Acelle SMTP integration
    - Stores drafted and final reply
    - Tracks sent status
    """
    result = await support_service.send_reply(
        db=db,
        email_id=email_id,
        response_text=request.response_text,
        response_type=request.response_type
    )
    
    return result


@router.post("/email/escalate/{email_id}")
async def escalate_email(
    email_id: int,
    request: EscalateRequest,
    db: Session = Depends(get_db)
):
    """
    Escalate support email based on sentiment or confidence.
    
    - Logs escalation reason
    - Assigns to appropriate tier
    """
    result = await support_service.escalate_email(
        db=db,
        email_id=email_id,
        reason=request.reason,
        escalation_level=request.escalation_level,
        assigned_to=request.assigned_to
    )
    
    return result


@router.get("/email/{email_id}")
async def get_email_details(
    email_id: int,
    db: Session = Depends(get_db)
):
    """
    Get email details including analysis and replies.
    """
    result = support_service.get_email_details(db, email_id)
    
    if not result:
        raise HTTPException(status_code=404, detail="Email not found")
    
    return result
