"""
Chatbot API endpoints.
Handles RAG-based Q&A and knowledge base management.
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
import logging

from app.database import get_db
from app.services.chatbot_service import ChatbotService
from app.schemas.schemas import (
    ChatbotAskRequest,
    ChatbotAskResponse,
    KnowledgeSyncRequest,
    KnowledgeSyncResponse,
    ChatbotFeedbackRequest,
    ChatbotFeedbackResponse
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/chatbot", tags=["Chatbot"])


@router.post(
    "/ask",
    response_model=ChatbotAskResponse,
    summary="Ask Question",
    description="""
    Ask a question to the chatbot.
    
    Uses RAG (Retrieval-Augmented Generation):
    1. Query is embedded and matched against knowledge base in Qdrant
    2. Relevant documents are retrieved
    3. LLM generates answer using retrieved context
    4. Answer is translated if needed
    
    Supports multiple languages:
    - English (en)
    - French (fr)
    - Spanish (es)
    - Chinese (zh)
    - Arabic (ar)
    - German (de)
    
    Returns:
    - Answer text
    - Source documents used
    - Confidence score
    - Query ID for feedback
    """
)
async def ask_question(
    request: ChatbotAskRequest,
    db: AsyncSession = Depends(get_db)
):
    """Ask the chatbot a question."""
    try:
        result = await ChatbotService.ask(
            db=db,
            query=request.query,
            user_id=request.user_id,
            language=request.language or "en"
        )
        
        await db.commit()
        return result
        
    except Exception as e:
        await db.rollback()
        logger.error(f"Chatbot ask error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/sync",
    response_model=KnowledgeSyncResponse,
    summary="Sync Knowledge Document",
    description="""
    Sync a document to the knowledge base.
    
    Process:
    1. Document is stored in PostgreSQL
    2. Content is chunked into segments
    3. Each chunk is embedded using sentence-transformers
    4. Embeddings are stored in Qdrant vector database
    
    Categories:
    - faq: Frequently asked questions
    - policy: Terms and policies
    - help: Help articles
    - guide: User guides and tutorials
    
    Returns:
    - Document ID
    - Number of chunks indexed
    - Success status
    """
)
async def sync_document(
    request: KnowledgeSyncRequest,
    db: AsyncSession = Depends(get_db)
):
    """Sync knowledge document."""
    try:
        result = await ChatbotService.sync_document(
            db=db,
            doc_id=request.doc_id,
            title=request.title,
            content=request.content,
            category=request.category or "faq",
            language=request.language or "en"
        )
        
        await db.commit()
        return result
        
    except Exception as e:
        await db.rollback()
        logger.error(f"Knowledge sync error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/feedback",
    response_model=ChatbotFeedbackResponse,
    summary="Submit Feedback",
    description="""
    Submit feedback for a chatbot response.
    
    Feedback types:
    - helpful: Response was helpful
    - not_helpful: Response wasn't helpful
    - incorrect: Response was incorrect
    - incomplete: Response was incomplete
    
    Used to improve chatbot quality over time.
    """
)
async def submit_feedback(
    request: ChatbotFeedbackRequest,
    db: AsyncSession = Depends(get_db)
):
    """Submit feedback for a response."""
    try:
        result = await ChatbotService.submit_feedback(
            db=db,
            query_id=request.query_id,
            user_id=request.user_id,
            feedback=request.feedback
        )
        
        await db.commit()
        return result
        
    except Exception as e:
        await db.rollback()
        logger.error(f"Feedback submission error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/history/{user_id}",
    summary="Get Chat History",
    description="Get recent chat history for a user."
)
async def get_chat_history(
    user_id: str,
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db)
):
    """Get user's chat history."""
    try:
        from sqlalchemy import select, desc
        from app.models.database_models import ChatbotLog
        import uuid
        
        user_uuid = uuid.UUID(user_id)
        
        query = select(ChatbotLog).where(
            ChatbotLog.user_id == user_uuid
        ).order_by(desc(ChatbotLog.created_at)).limit(limit)
        
        result = await db.execute(query)
        logs = result.scalars().all()
        
        return {
            "user_id": user_id,
            "history": [
                {
                    "query_id": str(log.id),
                    "query": log.query,
                    "response": log.response,
                    "confidence": log.confidence,
                    "feedback": log.feedback,
                    "created_at": log.created_at.isoformat()
                }
                for log in logs
            ]
        }
        
    except Exception as e:
        logger.error(f"Get chat history error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get(
    "/documents",
    summary="List Knowledge Documents",
    description="List all knowledge base documents."
)
async def list_documents(
    category: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db)
):
    """List knowledge documents."""
    try:
        from sqlalchemy import select
        from app.models.database_models import KnowledgeDocument
        
        query = select(KnowledgeDocument)
        
        if category:
            query = query.where(KnowledgeDocument.category == category)
        
        query = query.limit(limit).offset(offset)
        
        result = await db.execute(query)
        docs = result.scalars().all()
        
        return {
            "documents": [
                {
                    "id": str(doc.id),
                    "title": doc.title,
                    "category": doc.category,
                    "language": doc.language,
                    "updated_at": doc.updated_at.isoformat() if doc.updated_at else None
                }
                for doc in docs
            ],
            "count": len(docs)
        }
        
    except Exception as e:
        logger.error(f"List documents error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
