"""
Embedding Service - Handles text embeddings using Hugging Face models
"""
import logging
from typing import List, Optional, Dict, Any
import numpy as np
from sentence_transformers import SentenceTransformer
from kumele_ai.config import settings

logger = logging.getLogger(__name__)


class EmbedService:
    """Service for generating text embeddings"""
    
    def __init__(self):
        self.model_name = settings.EMBEDDING_MODEL
        self._model: Optional[SentenceTransformer] = None
    
    @property
    def model(self) -> SentenceTransformer:
        """Lazy load the embedding model"""
        if self._model is None:
            logger.info(f"Loading embedding model: {self.model_name}")
            self._model = SentenceTransformer(self.model_name)
            logger.info("Embedding model loaded successfully")
        return self._model
    
    def embed_text(self, text: str) -> List[float]:
        """Generate embedding for a single text"""
        try:
            embedding = self.model.encode(text, convert_to_numpy=True)
            return embedding.tolist()
        except Exception as e:
            logger.error(f"Error embedding text: {e}")
            raise
    
    def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple texts"""
        try:
            embeddings = self.model.encode(texts, convert_to_numpy=True)
            return embeddings.tolist()
        except Exception as e:
            logger.error(f"Error embedding texts: {e}")
            raise
    
    def compute_similarity(self, embedding1: List[float], embedding2: List[float]) -> float:
        """Compute cosine similarity between two embeddings"""
        vec1 = np.array(embedding1)
        vec2 = np.array(embedding2)
        
        dot_product = np.dot(vec1, vec2)
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        return float(dot_product / (norm1 * norm2))
    
    def find_most_similar(
        self,
        query_embedding: List[float],
        candidate_embeddings: List[List[float]],
        top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """Find most similar embeddings to a query"""
        similarities = []
        
        for idx, candidate in enumerate(candidate_embeddings):
            sim = self.compute_similarity(query_embedding, candidate)
            similarities.append({
                "index": idx,
                "similarity": sim
            })
        
        # Sort by similarity descending
        similarities.sort(key=lambda x: x["similarity"], reverse=True)
        
        return similarities[:top_k]
    
    def embed_hobby(self, hobby_name: str, description: Optional[str] = None) -> List[float]:
        """Generate embedding for a hobby"""
        text = hobby_name
        if description:
            text = f"{hobby_name}: {description}"
        return self.embed_text(text)
    
    def embed_event(self, title: str, description: Optional[str] = None, tags: Optional[List[str]] = None) -> List[float]:
        """Generate embedding for an event"""
        parts = [title]
        if description:
            parts.append(description)
        if tags:
            parts.append(", ".join(tags))
        text = " | ".join(parts)
        return self.embed_text(text)
    
    def get_embedding_dimension(self) -> int:
        """Get the dimension of embeddings"""
        return self.model.get_sentence_embedding_dimension()
    
    def unload(self):
        """Unload the model to free memory"""
        self._model = None
        logger.info("Embedding model unloaded")


# Singleton instance
embed_service = EmbedService()
