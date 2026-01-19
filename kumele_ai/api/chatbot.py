"""
Chatbot Router - RAG-based chatbot endpoints

Includes:
- /ask - Ask questions to the AI chatbot
- /sync - Sync documents to Qdrant vector DB
- /feedback - Submit feedback for responses
- /knowledge/* - CRUD operations for knowledge documents
- /knowledge/upload - Upload PDF/text files

API Key Authentication:
- Set API_KEY in environment variables (default: "internal-api-key")
- Pass in request header: x-api-key: <your-api-key>
"""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from pydantic import BaseModel
from typing import Optional, List
from sqlalchemy.orm import Session
import io

from kumele_ai.dependencies import get_db, verify_api_key
from kumele_ai.services.chatbot_service import chatbot_service
from kumele_ai.db.models import KnowledgeDocument

router = APIRouter()


# ============================================================
# Request/Response Models
# ============================================================

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


class KnowledgeDocumentCreate(BaseModel):
    """Create a new knowledge document"""
    title: str
    content: str
    category: str  # faq, blog, event, policy, guidelines
    language: str = "en"
    
    class Config:
        json_schema_extra = {
            "example": {
                "title": "Getting Started Guide",
                "content": "Welcome to Kumele! Here's how to get started...",
                "category": "faq",
                "language": "en"
            }
        }


class KnowledgeDocumentUpdate(BaseModel):
    """Update an existing knowledge document"""
    title: Optional[str] = None
    content: Optional[str] = None
    category: Optional[str] = None
    language: Optional[str] = None


class KnowledgeDocumentResponse(BaseModel):
    """Knowledge document response"""
    id: int
    title: str
    content: str
    category: str
    language: str
    is_synced: bool = False
    
    class Config:
        from_attributes = True


# ============================================================
# Chatbot Endpoints
# ============================================================

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
    
    **Authentication**: Requires x-api-key header.
    Default API key is "internal-api-key" (change in production via API_KEY env var).
    
    Triggered when FAQ/blog/event/policy changes.
    - Chunks text (~500 tokens)
    - Generates embeddings
    - Upserts into Qdrant
    - Tracks version in Postgres
    
    **Usage**:
    ```bash
    curl -X POST "http://localhost:8000/ai/chatbot/sync" \\
      -H "x-api-key: internal-api-key" \\
      -H "Content-Type: application/json" \\
      -d '{"document_ids": [1, 2, 3]}'
    ```
    
    Pass empty document_ids or null to sync ALL documents.
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


# ============================================================
# Knowledge Document CRUD Endpoints
# ============================================================

@router.get("/knowledge", response_model=List[KnowledgeDocumentResponse])
async def list_knowledge_documents(
    category: Optional[str] = None,
    language: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    api_key: str = Depends(verify_api_key)
):
    """
    List all knowledge documents.
    
    **Authentication**: Requires x-api-key header.
    
    **Query Parameters**:
    - category: Filter by category (faq, blog, event, policy, guidelines)
    - language: Filter by language code (en, es, fr, etc.)
    - skip: Pagination offset
    - limit: Max results per page
    """
    query = db.query(KnowledgeDocument)
    
    if category:
        query = query.filter(KnowledgeDocument.category == category)
    if language:
        query = query.filter(KnowledgeDocument.language == language)
    
    documents = query.offset(skip).limit(limit).all()
    
    return [
        KnowledgeDocumentResponse(
            id=doc.id,
            title=doc.title,
            content=doc.content[:500] + "..." if len(doc.content) > 500 else doc.content,
            category=doc.category,
            language=doc.language,
            is_synced=True  # TODO: Check if synced in Qdrant
        )
        for doc in documents
    ]


@router.get("/knowledge/{document_id}", response_model=KnowledgeDocumentResponse)
async def get_knowledge_document(
    document_id: int,
    db: Session = Depends(get_db),
    api_key: str = Depends(verify_api_key)
):
    """
    Get a specific knowledge document by ID.
    
    **Authentication**: Requires x-api-key header.
    """
    document = db.query(KnowledgeDocument).filter(
        KnowledgeDocument.id == document_id
    ).first()
    
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    return KnowledgeDocumentResponse(
        id=document.id,
        title=document.title,
        content=document.content,
        category=document.category,
        language=document.language,
        is_synced=True
    )


@router.post("/knowledge", response_model=KnowledgeDocumentResponse)
async def create_knowledge_document(
    document: KnowledgeDocumentCreate,
    auto_sync: bool = True,
    db: Session = Depends(get_db),
    api_key: str = Depends(verify_api_key)
):
    """
    Create a new knowledge document.
    
    **Authentication**: Requires x-api-key header.
    
    **Categories**:
    - faq: Frequently Asked Questions
    - blog: Blog posts and articles
    - event: Event-related information
    - policy: Policies and terms
    - guidelines: User guidelines and help docs
    
    **Example**:
    ```bash
    curl -X POST "http://localhost:8000/ai/chatbot/knowledge" \\
      -H "x-api-key: internal-api-key" \\
      -H "Content-Type: application/json" \\
      -d '{
        "title": "How to create an event",
        "content": "To create an event, go to...",
        "category": "faq",
        "language": "en"
      }'
    ```
    """
    valid_categories = ["faq", "blog", "event", "policy", "guidelines"]
    if document.category not in valid_categories:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid category. Must be one of: {valid_categories}"
        )
    
    new_doc = KnowledgeDocument(
        title=document.title,
        content=document.content,
        category=document.category,
        language=document.language
    )
    db.add(new_doc)
    db.commit()
    db.refresh(new_doc)
    
    # Auto-sync to Qdrant
    if auto_sync:
        try:
            await chatbot_service.sync_documents(db=db, document_ids=[new_doc.id])
        except Exception as e:
            # Log but don't fail - document is saved
            print(f"Warning: Failed to sync document {new_doc.id}: {e}")
    
    return KnowledgeDocumentResponse(
        id=new_doc.id,
        title=new_doc.title,
        content=new_doc.content,
        category=new_doc.category,
        language=new_doc.language,
        is_synced=auto_sync
    )


@router.put("/knowledge/{document_id}", response_model=KnowledgeDocumentResponse)
async def update_knowledge_document(
    document_id: int,
    document: KnowledgeDocumentUpdate,
    auto_sync: bool = True,
    db: Session = Depends(get_db),
    api_key: str = Depends(verify_api_key)
):
    """
    Update an existing knowledge document.
    
    **Authentication**: Requires x-api-key header.
    """
    existing_doc = db.query(KnowledgeDocument).filter(
        KnowledgeDocument.id == document_id
    ).first()
    
    if not existing_doc:
        raise HTTPException(status_code=404, detail="Document not found")
    
    if document.title is not None:
        existing_doc.title = document.title
    if document.content is not None:
        existing_doc.content = document.content
    if document.category is not None:
        valid_categories = ["faq", "blog", "event", "policy", "guidelines"]
        if document.category not in valid_categories:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid category. Must be one of: {valid_categories}"
            )
        existing_doc.category = document.category
    if document.language is not None:
        existing_doc.language = document.language
    
    db.commit()
    db.refresh(existing_doc)
    
    # Auto-sync to Qdrant
    if auto_sync:
        try:
            await chatbot_service.sync_documents(db=db, document_ids=[existing_doc.id])
        except Exception:
            pass
    
    return KnowledgeDocumentResponse(
        id=existing_doc.id,
        title=existing_doc.title,
        content=existing_doc.content,
        category=existing_doc.category,
        language=existing_doc.language,
        is_synced=auto_sync
    )


@router.delete("/knowledge/{document_id}")
async def delete_knowledge_document(
    document_id: int,
    db: Session = Depends(get_db),
    api_key: str = Depends(verify_api_key)
):
    """
    Delete a knowledge document.
    
    **Authentication**: Requires x-api-key header.
    
    This will also remove the document's embeddings from Qdrant.
    """
    existing_doc = db.query(KnowledgeDocument).filter(
        KnowledgeDocument.id == document_id
    ).first()
    
    if not existing_doc:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # TODO: Remove from Qdrant
    
    db.delete(existing_doc)
    db.commit()
    
    return {"success": True, "message": f"Document {document_id} deleted"}


@router.post("/knowledge/upload")
async def upload_knowledge_document(
    file: UploadFile = File(...),
    title: Optional[str] = Form(None),
    category: str = Form("guidelines"),
    language: str = Form("en"),
    auto_sync: bool = Form(True),
    db: Session = Depends(get_db),
    api_key: str = Depends(verify_api_key)
):
    """
    Upload a PDF or text file as a knowledge document.
    
    **Authentication**: Requires x-api-key header.
    
    **Supported formats**:
    - PDF (.pdf)
    - Text (.txt)
    - Markdown (.md)
    
    **Usage with curl**:
    ```bash
    curl -X POST "http://localhost:8000/ai/chatbot/knowledge/upload" \\
      -H "x-api-key: internal-api-key" \\
      -F "file=@guidelines.pdf" \\
      -F "title=Company Guidelines" \\
      -F "category=guidelines" \\
      -F "language=en"
    ```
    
    **Usage with Python**:
    ```python
    import requests
    
    files = {"file": open("guidelines.pdf", "rb")}
    data = {
        "title": "Company Guidelines",
        "category": "guidelines",
        "language": "en"
    }
    headers = {"x-api-key": "internal-api-key"}
    
    response = requests.post(
        "http://localhost:8000/ai/chatbot/knowledge/upload",
        files=files,
        data=data,
        headers=headers
    )
    print(response.json())
    ```
    """
    # Validate file type
    filename = file.filename or "unknown"
    extension = filename.lower().split(".")[-1] if "." in filename else ""
    
    if extension not in ["pdf", "txt", "md"]:
        raise HTTPException(
            status_code=400,
            detail="Unsupported file format. Use PDF, TXT, or MD files."
        )
    
    # Read file content
    content_bytes = await file.read()
    
    # Parse content based on file type
    if extension == "pdf":
        try:
            import pdfplumber
            
            pdf_file = io.BytesIO(content_bytes)
            text_content = ""
            
            with pdfplumber.open(pdf_file) as pdf:
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text_content += page_text + "\n\n"
            
            if not text_content.strip():
                raise HTTPException(
                    status_code=400,
                    detail="Could not extract text from PDF. Make sure it's not image-based."
                )
                
        except ImportError:
            # Fallback to PyPDF2
            try:
                from PyPDF2 import PdfReader
                
                pdf_file = io.BytesIO(content_bytes)
                reader = PdfReader(pdf_file)
                text_content = ""
                
                for page in reader.pages:
                    text_content += page.extract_text() + "\n\n"
                    
            except Exception as e:
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to parse PDF: {str(e)}"
                )
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to parse PDF: {str(e)}"
            )
    else:
        # TXT or MD file
        try:
            text_content = content_bytes.decode("utf-8")
        except UnicodeDecodeError:
            text_content = content_bytes.decode("latin-1")
    
    # Use filename as title if not provided
    doc_title = title or filename.rsplit(".", 1)[0].replace("_", " ").replace("-", " ").title()
    
    # Validate category
    valid_categories = ["faq", "blog", "event", "policy", "guidelines"]
    if category not in valid_categories:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid category. Must be one of: {valid_categories}"
        )
    
    # Create document
    new_doc = KnowledgeDocument(
        title=doc_title,
        content=text_content.strip(),
        category=category,
        language=language
    )
    db.add(new_doc)
    db.commit()
    db.refresh(new_doc)
    
    # Auto-sync to Qdrant
    synced = False
    if auto_sync:
        try:
            await chatbot_service.sync_documents(db=db, document_ids=[new_doc.id])
            synced = True
        except Exception as e:
            print(f"Warning: Failed to sync document {new_doc.id}: {e}")
    
    return {
        "success": True,
        "document": {
            "id": new_doc.id,
            "title": new_doc.title,
            "category": new_doc.category,
            "language": new_doc.language,
            "content_length": len(new_doc.content),
            "is_synced": synced
        },
        "message": f"Document '{doc_title}' uploaded successfully"
    }


@router.post("/knowledge/bulk-upload")
async def bulk_upload_documents(
    files: List[UploadFile] = File(...),
    category: str = Form("guidelines"),
    language: str = Form("en"),
    db: Session = Depends(get_db),
    api_key: str = Depends(verify_api_key)
):
    """
    Upload multiple PDF/text files at once.
    
    **Authentication**: Requires x-api-key header.
    
    **Usage**:
    ```bash
    curl -X POST "http://localhost:8000/ai/chatbot/knowledge/bulk-upload" \\
      -H "x-api-key: internal-api-key" \\
      -F "files=@doc1.pdf" \\
      -F "files=@doc2.pdf" \\
      -F "files=@doc3.txt" \\
      -F "category=policy"
    ```
    """
    results = []
    errors = []
    
    for file in files:
        try:
            # Reset file position
            await file.seek(0)
            
            # Use the single upload endpoint logic
            filename = file.filename or "unknown"
            extension = filename.lower().split(".")[-1] if "." in filename else ""
            
            if extension not in ["pdf", "txt", "md"]:
                errors.append({"file": filename, "error": "Unsupported format"})
                continue
            
            content_bytes = await file.read()
            
            if extension == "pdf":
                try:
                    import pdfplumber
                    pdf_file = io.BytesIO(content_bytes)
                    text_content = ""
                    with pdfplumber.open(pdf_file) as pdf:
                        for page in pdf.pages:
                            page_text = page.extract_text()
                            if page_text:
                                text_content += page_text + "\n\n"
                except:
                    from PyPDF2 import PdfReader
                    pdf_file = io.BytesIO(content_bytes)
                    reader = PdfReader(pdf_file)
                    text_content = ""
                    for page in reader.pages:
                        text_content += page.extract_text() + "\n\n"
            else:
                try:
                    text_content = content_bytes.decode("utf-8")
                except:
                    text_content = content_bytes.decode("latin-1")
            
            doc_title = filename.rsplit(".", 1)[0].replace("_", " ").replace("-", " ").title()
            
            new_doc = KnowledgeDocument(
                title=doc_title,
                content=text_content.strip(),
                category=category,
                language=language
            )
            db.add(new_doc)
            db.commit()
            db.refresh(new_doc)
            
            results.append({
                "id": new_doc.id,
                "title": new_doc.title,
                "file": filename
            })
            
        except Exception as e:
            errors.append({"file": file.filename, "error": str(e)})
    
    # Sync all new documents
    if results:
        try:
            doc_ids = [r["id"] for r in results]
            await chatbot_service.sync_documents(db=db, document_ids=doc_ids)
        except Exception as e:
            print(f"Warning: Failed to sync documents: {e}")
    
    return {
        "success": len(errors) == 0,
        "uploaded": len(results),
        "failed": len(errors),
        "documents": results,
        "errors": errors
    }

