"""
Chatbot Router - RAG-based chatbot endpoints
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional, List
from sqlalchemy.orm import Session

from kumele_ai.dependencies import get_db, verify_api_key
from kumele_ai.services.chatbot_service import chatbot_service

router = APIRouter()


class AskRequest(BaseModel):
    query: str
    user_id: Optional[int] = None


class AskResponse(BaseModel):
    success: bool
    response: str
    language: Optional[str] = None
    confidence: Optional[float] = None
    sources: Optional[List[dict]] = None
    error: Optional[str] = None


class SyncRequest(BaseModel):
    document_ids: Optional[List[int]] = None


class FeedbackRequest(BaseModel):
    log_id: int
    feedback: str  # "helpful" or "not_helpful"


@router.post("/ask", response_model=AskResponse)
async def chatbot_ask(
    request: AskRequest,
    db: Session = Depends(get_db)
):
    """
    Process a chatbot query using RAG.
    
    Flow:
    1. Detect language
    2. Translate to English if needed
    3. Embed query
    4. Retrieve top-K chunks from Qdrant
    5. Generate answer via LLM
    6. Translate back if needed
    7. Log Q&A
    """
    result = await chatbot_service.ask(
        db=db,
        query=request.query,
        user_id=request.user_id
    )
    
    return AskResponse(**result)


@router.post("/sync")
async def chatbot_sync(
    request: SyncRequest,
    db: Session = Depends(get_db),
    api_key: str = Depends(verify_api_key)
):
    """
    Sync knowledge documents to Qdrant (INTERNAL/WEBHOOK).
    
    Triggered when FAQ/blog/event/policy changes.
    - Chunks text (~500 tokens)
    - Generates embeddings
    - Upserts into Qdrant
    - Tracks version in Postgres
    
    Protected by API key.
    """
    result = await chatbot_service.sync_documents(
        db=db,
        document_ids=request.document_ids
    )
    
    return result


@router.post("/feedback")
async def chatbot_feedback(
    request: FeedbackRequest,
    db: Session = Depends(get_db)
):
    """
    Collect user feedback for chatbot responses.
    """
    if request.feedback not in ["helpful", "not_helpful"]:
        raise HTTPException(
            status_code=400,
            detail="Feedback must be 'helpful' or 'not_helpful'"
        )
    
    result = await chatbot_service.submit_feedback(
        db=db,
        log_id=request.log_id,
        feedback=request.feedback
    )
    
    return result
