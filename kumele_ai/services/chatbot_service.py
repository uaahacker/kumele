"""
Chatbot Service - Handles RAG-based chatbot interactions
"""
import logging
import uuid
from typing import Dict, Any, List, Optional
from datetime import datetime
from sqlalchemy.orm import Session
from qdrant_client import QdrantClient
from qdrant_client.models import (
    VectorParams, Distance, PointStruct, 
    Filter, FieldCondition, MatchValue
)

from kumele_ai.config import settings
from kumele_ai.db.models import (
    KnowledgeDocument, KnowledgeEmbedding, ChatbotLog
)
from kumele_ai.services.embed_service import embed_service
from kumele_ai.services.translate_service import translate_service
from kumele_ai.services.llm_service import llm_service

logger = logging.getLogger(__name__)


class ChatbotService:
    """Service for RAG-based chatbot"""
    
    def __init__(self):
        self.qdrant_client: Optional[QdrantClient] = None
        self.collection_name = settings.QDRANT_COLLECTION
        self.chunk_size = 500  # tokens approximately
    
    def _get_qdrant_client(self) -> QdrantClient:
        """Get or create Qdrant client"""
        if self.qdrant_client is None:
            self.qdrant_client = QdrantClient(url=settings.QDRANT_URL)
        return self.qdrant_client
    
    async def _ensure_collection(self):
        """Ensure Qdrant collection exists"""
        client = self._get_qdrant_client()
        collections = client.get_collections().collections
        
        if not any(c.name == self.collection_name for c in collections):
            vector_size = embed_service.get_embedding_dimension()
            client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(
                    size=vector_size,
                    distance=Distance.COSINE
                )
            )
            logger.info(f"Created Qdrant collection: {self.collection_name}")
    
    def _chunk_text(self, text: str, chunk_size: int = 500) -> List[str]:
        """Split text into chunks"""
        words = text.split()
        chunks = []
        current_chunk = []
        current_length = 0
        
        for word in words:
            word_length = len(word.split())
            if current_length + word_length > chunk_size:
                if current_chunk:
                    chunks.append(" ".join(current_chunk))
                current_chunk = [word]
                current_length = word_length
            else:
                current_chunk.append(word)
                current_length += word_length
        
        if current_chunk:
            chunks.append(" ".join(current_chunk))
        
        return chunks
    
    async def sync_documents(
        self,
        db: Session,
        document_ids: Optional[List[int]] = None
    ) -> Dict[str, Any]:
        """Sync knowledge documents to Qdrant"""
        try:
            await self._ensure_collection()
            client = self._get_qdrant_client()
            
            # Get documents to sync
            query = db.query(KnowledgeDocument)
            if document_ids:
                query = query.filter(KnowledgeDocument.id.in_(document_ids))
            
            documents = query.all()
            
            synced_count = 0
            total_chunks = 0
            
            for doc in documents:
                # Delete existing embeddings for this document
                db.query(KnowledgeEmbedding).filter(
                    KnowledgeEmbedding.document_id == doc.id
                ).delete()
                
                # Chunk the document
                chunks = self._chunk_text(doc.content, self.chunk_size)
                
                # Generate embeddings and store in Qdrant
                points = []
                for idx, chunk in enumerate(chunks):
                    embedding = embed_service.embed_text(chunk)
                    vector_id = str(uuid.uuid4())
                    
                    point = PointStruct(
                        id=vector_id,
                        vector=embedding,
                        payload={
                            "document_id": doc.id,
                            "chunk_index": idx,
                            "category": doc.category,
                            "title": doc.title,
                            "language": doc.language,
                            "text": chunk
                        }
                    )
                    points.append(point)
                    
                    # Track in database
                    embedding_record = KnowledgeEmbedding(
                        document_id=doc.id,
                        chunk_index=idx,
                        chunk_text=chunk,
                        embedding_model=settings.EMBEDDING_MODEL,
                        vector_id=vector_id,
                        last_indexed=datetime.utcnow()
                    )
                    db.add(embedding_record)
                
                # Batch upsert to Qdrant
                if points:
                    client.upsert(
                        collection_name=self.collection_name,
                        points=points
                    )
                
                synced_count += 1
                total_chunks += len(chunks)
            
            db.commit()
            
            return {
                "success": True,
                "documents_synced": synced_count,
                "total_chunks": total_chunks,
                "collection": self.collection_name
            }
            
        except Exception as e:
            logger.error(f"Document sync error: {e}")
            db.rollback()
            return {
                "success": False,
                "error": str(e)
            }
    
    async def ask(
        self,
        db: Session,
        query: str,
        user_id: Optional[int] = None,
        top_k: int = 5
    ) -> Dict[str, Any]:
        """Process a chatbot query"""
        try:
            # Detect language
            lang_result = await translate_service.detect_language(query)
            detected_language = lang_result.get("language", "en")
            
            # Translate to English if needed
            english_query = query
            if detected_language != "en":
                translation = await translate_service.translate_to_english(query, detected_language)
                if translation.get("success"):
                    english_query = translation.get("translated_text", query)
            
            # Generate query embedding
            query_embedding = embed_service.embed_text(english_query)
            
            # Search Qdrant for relevant chunks
            await self._ensure_collection()
            client = self._get_qdrant_client()
            
            search_results = client.search(
                collection_name=self.collection_name,
                query_vector=query_embedding,
                limit=top_k
            )
            
            # Extract context from results
            context_chunks = []
            source_docs = []
            
            for result in search_results:
                payload = result.payload
                context_chunks.append(payload.get("text", ""))
                source_docs.append({
                    "document_id": payload.get("document_id"),
                    "title": payload.get("title"),
                    "category": payload.get("category"),
                    "score": result.score
                })
            
            # Generate response using LLM
            llm_response = await llm_service.generate_chat_response(
                query=english_query,
                context=context_chunks,
                language="en"
            )
            
            response_text = llm_response.get("generated_text", "I'm sorry, I couldn't generate a response.")
            confidence = search_results[0].score if search_results else 0.0
            
            # Translate response back if needed
            final_response = response_text
            if detected_language != "en":
                back_translation = await translate_service.translate_from_english(
                    response_text, detected_language
                )
                if back_translation.get("success"):
                    final_response = back_translation.get("translated_text", response_text)
            
            # Log the interaction
            log_entry = ChatbotLog(
                user_id=user_id,
                query=query,
                response=final_response,
                language=detected_language,
                confidence=confidence,
                source_docs=source_docs
            )
            db.add(log_entry)
            db.commit()
            
            return {
                "success": True,
                "response": final_response,
                "language": detected_language,
                "confidence": round(confidence, 4),
                "sources": source_docs[:3],  # Top 3 sources
                "log_id": log_entry.id
            }
            
        except Exception as e:
            logger.error(f"Chatbot ask error: {e}")
            return {
                "success": False,
                "response": "I'm sorry, I encountered an error processing your request.",
                "error": str(e)
            }
    
    async def submit_feedback(
        self,
        db: Session,
        log_id: int,
        feedback: str  # "helpful" or "not_helpful"
    ) -> Dict[str, Any]:
        """Submit feedback for a chatbot response"""
        try:
            log_entry = db.query(ChatbotLog).filter(ChatbotLog.id == log_id).first()
            
            if not log_entry:
                return {
                    "success": False,
                    "error": "Log entry not found"
                }
            
            log_entry.feedback = feedback
            db.commit()
            
            return {
                "success": True,
                "message": "Feedback recorded"
            }
            
        except Exception as e:
            logger.error(f"Feedback submission error: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def health_check(self) -> bool:
        """Check if Qdrant is healthy"""
        try:
            client = self._get_qdrant_client()
            client.get_collections()
            return True
        except Exception as e:
            logger.error(f"Qdrant health check failed: {e}")
            return False


# Singleton instance
chatbot_service = ChatbotService()
