"""
Chatbot Service for RAG-based Knowledge Base Q&A.
Uses Qdrant for vector search and LLM for answer generation.
Supports both internal TGI and external Mistral API.
"""
from typing import Optional, List, Dict, Any, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from datetime import datetime
import logging
import uuid
import httpx
import hashlib

from app.models.database_models import (
    KnowledgeDocument, EmbeddingsMetadata, ChatbotLog
)
from app.config import settings

logger = logging.getLogger(__name__)


class ChatbotService:
    """Service for RAG-based chatbot operations."""
    
    # Chunk size for document splitting
    CHUNK_SIZE = 500  # tokens approximately
    CHUNK_OVERLAP = 50
    
    # Number of similar chunks to retrieve
    TOP_K = 5

    @staticmethod
    async def generate_embedding(text: str) -> List[float]:
        """
        Generate embedding for text using sentence-transformers.
        In production, this would call the embedding model.
        """
        try:
            # In production, call Hugging Face embedding model
            # For now, generate a placeholder embedding
            
            # Simple hash-based pseudo-embedding for development
            text_hash = hashlib.md5(text.encode()).hexdigest()
            
            # Convert hash to 384-dimensional vector (MiniLM dimension)
            embedding = []
            for i in range(384):
                char_idx = i % len(text_hash)
                value = (int(text_hash[char_idx], 16) - 8) / 8.0
                embedding.append(value)
            
            return embedding
            
        except Exception as e:
            logger.error(f"Embedding generation error: {e}")
            return [0.0] * 384

    @staticmethod
    def chunk_text(text: str, chunk_size: int = 500) -> List[str]:
        """Split text into overlapping chunks."""
        words = text.split()
        chunks = []
        
        if len(words) <= chunk_size:
            return [text]
        
        for i in range(0, len(words), chunk_size - ChatbotService.CHUNK_OVERLAP):
            chunk = ' '.join(words[i:i + chunk_size])
            if chunk:
                chunks.append(chunk)
        
        return chunks

    @staticmethod
    async def search_qdrant(
        query_embedding: List[float],
        collection: str = None,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Search Qdrant for similar documents.
        """
        collection = collection or settings.QDRANT_COLLECTION
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{settings.QDRANT_URL}/collections/{collection}/points/search",
                    json={
                        "vector": query_embedding,
                        "limit": limit,
                        "with_payload": True
                    },
                    timeout=10.0
                )
                
                if response.status_code == 200:
                    data = response.json()
                    return data.get("result", [])
                else:
                    logger.warning(f"Qdrant search failed: {response.status_code}")
                    return []
                    
        except Exception as e:
            logger.error(f"Qdrant search error: {e}")
            return []

    @staticmethod
    async def upsert_to_qdrant(
        vector_id: str,
        embedding: List[float],
        payload: Dict[str, Any],
        collection: str = None
    ) -> bool:
        """
        Upsert vector to Qdrant.
        """
        collection = collection or settings.QDRANT_COLLECTION
        
        try:
            async with httpx.AsyncClient() as client:
                # Ensure collection exists
                await client.put(
                    f"{settings.QDRANT_URL}/collections/{collection}",
                    json={
                        "vectors": {
                            "size": 384,
                            "distance": "Cosine"
                        }
                    },
                    timeout=10.0
                )
                
                # Upsert point
                response = await client.put(
                    f"{settings.QDRANT_URL}/collections/{collection}/points",
                    json={
                        "points": [{
                            "id": vector_id,
                            "vector": embedding,
                            "payload": payload
                        }]
                    },
                    timeout=10.0
                )
                
                return response.status_code in [200, 201]
                
        except Exception as e:
            logger.error(f"Qdrant upsert error: {e}")
            return False

    @staticmethod
    async def call_internal_llm(prompt: str) -> Tuple[str, float]:
        """Call internal TGI server for LLM inference."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{settings.LLM_API_URL}/generate",
                    json={
                        "inputs": prompt,
                        "parameters": {
                            "max_new_tokens": 500,
                            "temperature": 0.7,
                            "do_sample": True
                        }
                    },
                    timeout=30.0
                )
                
                if response.status_code == 200:
                    data = response.json()
                    answer = data.get("generated_text", "")
                    return answer, 0.85
                    
        except httpx.TimeoutException:
            logger.warning("Internal LLM timeout")
        except Exception as e:
            logger.warning(f"Internal LLM error: {e}")
        
        return None, 0.0

    @staticmethod
    async def call_external_mistral(prompt: str) -> Tuple[str, float]:
        """Call external Mistral API for LLM inference."""
        if not settings.MISTRAL_API_KEY:
            logger.warning("MISTRAL_API_KEY not set")
            return None, 0.0
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{settings.MISTRAL_API_URL}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {settings.MISTRAL_API_KEY}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": settings.MISTRAL_MODEL,
                        "messages": [
                            {"role": "user", "content": prompt}
                        ],
                        "max_tokens": 500,
                        "temperature": 0.7
                    },
                    timeout=30.0
                )
                
                if response.status_code == 200:
                    data = response.json()
                    answer = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                    return answer, 0.90  # Higher confidence for external API
                else:
                    logger.warning(f"Mistral API error: {response.status_code} - {response.text}")
                    
        except httpx.TimeoutException:
            logger.warning("Mistral API timeout")
        except Exception as e:
            logger.warning(f"Mistral API error: {e}")
        
        return None, 0.0

    @staticmethod
    async def generate_answer(
        query: str,
        context: List[str],
        language: str = "en"
    ) -> Tuple[str, float]:
        """
        Generate answer using LLM with retrieved context.
        Supports both internal TGI and external Mistral API.
        """
        try:
            # Build prompt
            context_text = "\n\n".join(context)
            
            prompt = f"""Based on the following context, answer the user's question. 
If the answer is not in the context, say "I don't have enough information to answer that."

Context:
{context_text}

Question: {query}

Answer:"""
            
            # Try based on configured mode
            answer = None
            confidence = 0.0
            
            if settings.LLM_MODE == "external" and settings.MISTRAL_API_KEY:
                # Use external Mistral API
                answer, confidence = await ChatbotService.call_external_mistral(prompt)
            
            if not answer:
                # Fall back to internal TGI
                answer, confidence = await ChatbotService.call_internal_llm(prompt)
            
            if answer:
                return answer, confidence
            
            # Final fallback: Return best matching context
            if context:
                return context[0][:500] + "...", 0.5
            else:
                return "I don't have enough information to answer that question.", 0.3
                
        except Exception as e:
            logger.error(f"Answer generation error: {e}")
            return "Sorry, I encountered an error processing your question.", 0.0

    @staticmethod
    async def translate_text(
        text: str,
        source_lang: str,
        target_lang: str
    ) -> str:
        """Translate text using LibreTranslate/Argos."""
        if source_lang == target_lang:
            return text
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{settings.TRANSLATE_URL}/translate",
                    json={
                        "q": text,
                        "source": source_lang,
                        "target": target_lang,
                        "format": "text"
                    },
                    timeout=10.0
                )
                
                if response.status_code == 200:
                    data = response.json()
                    return data.get("translatedText", text)
                    
        except Exception as e:
            logger.warning(f"Translation error: {e}")
        
        return text

    @staticmethod
    async def detect_language(text: str) -> str:
        """Detect language of text."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{settings.TRANSLATE_URL}/detect",
                    json={"q": text},
                    timeout=5.0
                )
                
                if response.status_code == 200:
                    data = response.json()
                    if data:
                        return data[0].get("language", "en")
                        
        except Exception as e:
            logger.warning(f"Language detection error: {e}")
        
        return "en"

    @staticmethod
    async def ask(
        db: AsyncSession,
        query: str,
        user_id: Optional[str] = None,
        language: str = "en"
    ) -> Dict[str, Any]:
        """
        Main chatbot Q&A endpoint.
        1. Detect/translate query to English
        2. Generate query embedding
        3. Search Qdrant for relevant documents
        4. Generate answer with LLM
        5. Translate answer back if needed
        6. Log the interaction
        """
        query_id = str(uuid.uuid4())
        detected_language = await ChatbotService.detect_language(query)
        
        # Translate to English if needed
        query_english = query
        if detected_language != "en":
            query_english = await ChatbotService.translate_text(
                query, detected_language, "en"
            )
        
        # Generate embedding
        query_embedding = await ChatbotService.generate_embedding(query_english)
        
        # Search for relevant documents
        search_results = await ChatbotService.search_qdrant(
            query_embedding,
            limit=ChatbotService.TOP_K
        )
        
        # Extract context from results
        context = []
        source_docs = []
        
        for result in search_results:
            payload = result.get("payload", {})
            text = payload.get("text", "")
            doc_id = payload.get("doc_id", "unknown")
            
            if text:
                context.append(text)
                if doc_id not in source_docs:
                    source_docs.append(doc_id)
        
        # Generate answer
        answer, confidence = await ChatbotService.generate_answer(
            query_english,
            context,
            "en"
        )
        
        # Translate answer back if needed
        if language != "en" and language in settings.SUPPORTED_LANGUAGES:
            answer = await ChatbotService.translate_text(answer, "en", language)
        
        # Log the interaction
        log_entry = ChatbotLog(
            id=uuid.UUID(query_id),
            user_id=uuid.UUID(user_id) if user_id else None,
            query=query,
            response=answer,
            language=language,
            confidence=confidence,
            source_docs=source_docs,
            created_at=datetime.utcnow()
        )
        db.add(log_entry)
        await db.flush()
        
        return {
            "answer": answer,
            "source_docs": source_docs,
            "confidence": confidence,
            "query_id": query_id
        }

    @staticmethod
    async def sync_document(
        db: AsyncSession,
        doc_id: str,
        title: str,
        content: str,
        category: str = "faq",
        language: str = "en"
    ) -> Dict[str, Any]:
        """
        Sync a knowledge document.
        1. Store/update document in PostgreSQL
        2. Chunk the content
        3. Generate embeddings for each chunk
        4. Upsert to Qdrant
        5. Track embedding metadata
        """
        # Translate to English if needed
        content_english = content
        if language != "en":
            content_english = await ChatbotService.translate_text(
                content, language, "en"
            )
        
        # Store/update document
        doc_uuid = uuid.UUID(doc_id) if doc_id else uuid.uuid4()
        
        query = select(KnowledgeDocument).where(
            KnowledgeDocument.id == doc_uuid
        )
        result = await db.execute(query)
        existing = result.scalar_one_or_none()
        
        if existing:
            existing.title = title
            existing.content = content
            existing.category = category
            existing.language = language
            existing.updated_at = datetime.utcnow()
            doc = existing
        else:
            doc = KnowledgeDocument(
                id=doc_uuid,
                title=title,
                content=content,
                category=category,
                language=language,
                updated_at=datetime.utcnow()
            )
            db.add(doc)
        
        await db.flush()
        
        # Delete old embeddings metadata
        delete_query = delete(EmbeddingsMetadata).where(
            EmbeddingsMetadata.document_id == doc_uuid
        )
        await db.execute(delete_query)
        
        # Chunk content
        chunks = ChatbotService.chunk_text(content_english)
        
        # Process each chunk
        chunks_indexed = 0
        
        for i, chunk in enumerate(chunks):
            # Generate embedding
            embedding = await ChatbotService.generate_embedding(chunk)
            
            # Create vector ID
            vector_id = f"{doc_uuid}_{i}"
            
            # Upsert to Qdrant
            payload = {
                "doc_id": str(doc_uuid),
                "title": title,
                "text": chunk,
                "chunk_index": i,
                "category": category,
                "language": language
            }
            
            success = await ChatbotService.upsert_to_qdrant(
                vector_id, embedding, payload
            )
            
            if success:
                # Track embedding metadata
                meta = EmbeddingsMetadata(
                    document_id=doc_uuid,
                    chunk_index=i,
                    vector_id=vector_id,
                    embedding_model=settings.EMBEDDING_MODEL,
                    last_indexed=datetime.utcnow()
                )
                db.add(meta)
                chunks_indexed += 1
        
        await db.flush()
        
        return {
            "success": True,
            "doc_id": str(doc_uuid),
            "chunks_indexed": chunks_indexed,
            "message": f"Document synced with {chunks_indexed} chunks"
        }

    @staticmethod
    async def submit_feedback(
        db: AsyncSession,
        query_id: str,
        user_id: Optional[str],
        feedback: str
    ) -> Dict[str, Any]:
        """Submit feedback for a chatbot response."""
        try:
            query_uuid = uuid.UUID(query_id)
            
            query = select(ChatbotLog).where(
                ChatbotLog.id == query_uuid
            )
            result = await db.execute(query)
            log_entry = result.scalar_one_or_none()
            
            if log_entry:
                log_entry.feedback = feedback
                await db.flush()
                
                return {
                    "success": True,
                    "message": "Feedback recorded"
                }
            else:
                return {
                    "success": False,
                    "message": "Query not found"
                }
                
        except Exception as e:
            logger.error(f"Feedback submission error: {e}")
            return {
                "success": False,
                "message": str(e)
            }
