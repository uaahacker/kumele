"""
Embedding Service for User and Event Vector Storage in Qdrant.

Replaces any FAISS usage with Qdrant for hobby/event/user embeddings.

Collections:
==============================================================================
- user_embeddings: User preference vectors (hobbies, interactions, history)
- event_embeddings: Event vectors (category, tags, description)
- hobby_embeddings: Hobby taxonomy vectors

Pipeline (per requirements):
==============================================================================
1. Generate embeddings using sentence-transformers (all-MiniLM-L6-v2)
2. Store in Qdrant with metadata
3. Search using cosine similarity
4. Hybrid scoring: ML relevance + trust + engagement + business

Key Features:
==============================================================================
- Async Qdrant operations
- Automatic collection creation
- Batch upsert support
- Similar user/event search

Storage: Qdrant (NOT FAISS)
"""
from typing import Optional, List, Dict, Any, Union
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from datetime import datetime
import logging
import uuid
import httpx
import hashlib
import numpy as np

from app.models.database_models import (
    User, Event, UserHobby, InterestTaxonomy, UserInteraction
)
from app.config import settings

logger = logging.getLogger(__name__)


# ============================================
# QDRANT COLLECTION NAMES
# ============================================
USER_EMBEDDINGS_COLLECTION = "kumele_user_embeddings"
EVENT_EMBEDDINGS_COLLECTION = "kumele_event_embeddings"
HOBBY_EMBEDDINGS_COLLECTION = "kumele_hobby_embeddings"


class EmbeddingService:
    """
    Service for managing user/event/hobby embeddings in Qdrant.
    
    This replaces FAISS with Qdrant for vector storage.
    All embedding vectors are stored in Qdrant collections.
    """
    
    # Embedding dimension (MiniLM-L6-v2)
    EMBEDDING_DIM = 384
    
    # Category keyword mappings for content-based embeddings
    CATEGORY_KEYWORDS = {
        "fitness": ["gym", "workout", "exercise", "yoga", "running", "cycling", "swimming", "crossfit", "health"],
        "music": ["singing", "guitar", "piano", "drums", "djing", "concerts", "karaoke", "orchestra", "band"],
        "outdoor": ["hiking", "camping", "climbing", "surfing", "skiing", "kayaking", "fishing", "nature"],
        "food": ["cooking", "baking", "wine", "coffee", "restaurants", "culinary", "chef", "recipes"],
        "tech": ["coding", "programming", "ai", "startups", "gaming", "robotics", "blockchain", "apps"],
        "arts": ["painting", "photography", "dance", "theater", "crafts", "sculpture", "design", "film"],
        "social": ["networking", "dating", "community", "volunteering", "meetups", "clubs", "groups"],
        "education": ["workshop", "seminar", "course", "learning", "training", "lecture", "tutorial"],
        "sports": ["football", "basketball", "tennis", "golf", "volleyball", "baseball", "soccer"],
        "wellness": ["meditation", "spa", "mindfulness", "therapy", "healing", "relaxation"],
    }

    @staticmethod
    async def generate_embedding(text: str) -> List[float]:
        """
        Generate embedding for text using sentence-transformers.
        
        In production, this calls the HuggingFace Inference API.
        Falls back to hash-based pseudo-embedding for development.
        """
        try:
            # Try calling HuggingFace Inference API if key is set
            if settings.HUGGINGFACE_API_KEY:
                try:
                    async with httpx.AsyncClient() as client:
                        response = await client.post(
                            f"https://api-inference.huggingface.co/pipeline/feature-extraction/{settings.EMBEDDING_MODEL}",
                            headers={"Authorization": f"Bearer {settings.HUGGINGFACE_API_KEY}"},
                            json={"inputs": text, "options": {"wait_for_model": True}},
                            timeout=30.0
                        )
                        if response.status_code == 200:
                            embedding = response.json()
                            if isinstance(embedding, list) and len(embedding) > 0:
                                # Handle nested list from API
                                if isinstance(embedding[0], list):
                                    return embedding[0]
                                return embedding
                except Exception as e:
                    logger.warning(f"HuggingFace embedding failed, using fallback: {e}")
            
            # Fallback: Hash-based pseudo-embedding for development
            text_hash = hashlib.sha256(text.encode()).hexdigest()
            
            # Convert hash to 384-dimensional vector
            embedding = []
            for i in range(EmbeddingService.EMBEDDING_DIM):
                char_idx = i % len(text_hash)
                value = (int(text_hash[char_idx], 16) - 8) / 8.0
                embedding.append(value)
            
            # Normalize vector
            norm = np.linalg.norm(embedding)
            if norm > 0:
                embedding = [v / norm for v in embedding]
            
            return embedding
            
        except Exception as e:
            logger.error(f"Embedding generation error: {e}")
            return [0.0] * EmbeddingService.EMBEDDING_DIM

    @staticmethod
    async def ensure_collection_exists(collection_name: str) -> bool:
        """Create Qdrant collection if it doesn't exist."""
        try:
            async with httpx.AsyncClient() as client:
                # Check if collection exists
                check_response = await client.get(
                    f"{settings.QDRANT_URL}/collections/{collection_name}",
                    timeout=10.0
                )
                
                if check_response.status_code == 200:
                    return True
                
                # Create collection
                response = await client.put(
                    f"{settings.QDRANT_URL}/collections/{collection_name}",
                    json={
                        "vectors": {
                            "size": EmbeddingService.EMBEDDING_DIM,
                            "distance": "Cosine"
                        }
                    },
                    timeout=10.0
                )
                
                return response.status_code in [200, 201]
                
        except Exception as e:
            logger.error(f"Collection creation error: {e}")
            return False

    @staticmethod
    async def upsert_embedding(
        collection_name: str,
        vector_id: str,
        embedding: List[float],
        payload: Dict[str, Any]
    ) -> bool:
        """Upsert a single embedding to Qdrant."""
        try:
            await EmbeddingService.ensure_collection_exists(collection_name)
            
            # Convert string ID to numeric ID for Qdrant
            numeric_id = abs(hash(vector_id)) % (2**63)
            
            async with httpx.AsyncClient() as client:
                response = await client.put(
                    f"{settings.QDRANT_URL}/collections/{collection_name}/points",
                    json={
                        "points": [{
                            "id": numeric_id,
                            "vector": embedding,
                            "payload": {**payload, "original_id": vector_id}
                        }]
                    },
                    timeout=10.0
                )
                
                return response.status_code in [200, 201]
                
        except Exception as e:
            logger.error(f"Qdrant upsert error: {e}")
            return False

    @staticmethod
    async def batch_upsert_embeddings(
        collection_name: str,
        embeddings: List[Dict[str, Any]]
    ) -> bool:
        """Batch upsert multiple embeddings to Qdrant."""
        try:
            await EmbeddingService.ensure_collection_exists(collection_name)
            
            points = []
            for item in embeddings:
                numeric_id = abs(hash(item["id"])) % (2**63)
                points.append({
                    "id": numeric_id,
                    "vector": item["embedding"],
                    "payload": {**item.get("payload", {}), "original_id": item["id"]}
                })
            
            async with httpx.AsyncClient() as client:
                response = await client.put(
                    f"{settings.QDRANT_URL}/collections/{collection_name}/points",
                    json={"points": points},
                    timeout=30.0
                )
                
                return response.status_code in [200, 201]
                
        except Exception as e:
            logger.error(f"Batch upsert error: {e}")
            return False

    @staticmethod
    async def search_similar(
        collection_name: str,
        query_embedding: List[float],
        limit: int = 10,
        filter_conditions: Dict[str, Any] = None
    ) -> List[Dict[str, Any]]:
        """Search for similar vectors in Qdrant collection."""
        try:
            async with httpx.AsyncClient() as client:
                body = {
                    "vector": query_embedding,
                    "limit": limit,
                    "with_payload": True
                }
                
                if filter_conditions:
                    body["filter"] = filter_conditions
                
                response = await client.post(
                    f"{settings.QDRANT_URL}/collections/{collection_name}/points/search",
                    json=body,
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
    async def get_embedding(
        collection_name: str,
        vector_id: str
    ) -> Optional[List[float]]:
        """Retrieve embedding by ID from Qdrant."""
        try:
            numeric_id = abs(hash(vector_id)) % (2**63)
            
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{settings.QDRANT_URL}/collections/{collection_name}/points/{numeric_id}",
                    timeout=10.0
                )
                
                if response.status_code == 200:
                    data = response.json()
                    result = data.get("result", {})
                    return result.get("vector")
                    
                return None
                
        except Exception as e:
            logger.error(f"Get embedding error: {e}")
            return None

    # ============================================
    # USER EMBEDDINGS
    # ============================================
    
    @staticmethod
    async def generate_user_embedding(
        db: AsyncSession,
        user_id: Union[int, str]
    ) -> List[float]:
        """
        Generate embedding for user based on their hobbies and interactions.
        
        Combines:
        - Hobby preferences (weighted by preference_score)
        - Interaction history (weighted by interaction type)
        - Category preferences
        """
        try:
            # Convert user_id to int
            try:
                user_id_int = int(user_id)
            except (ValueError, TypeError):
                user_id_int = abs(hash(user_id)) % 1000000
            
            # Get user's hobbies
            hobbies_query = select(UserHobby, InterestTaxonomy).join(
                InterestTaxonomy,
                UserHobby.hobby_id == InterestTaxonomy.interest_id
            ).where(UserHobby.user_id == user_id_int)
            
            hobbies_result = await db.execute(hobbies_query)
            hobby_rows = hobbies_result.fetchall()
            
            # Build text representation
            hobby_texts = []
            for row in hobby_rows:
                hobby_name = row.InterestTaxonomy.interest_name
                score = row.UserHobby.preference_score or 1.0
                # Repeat hobby name based on preference score
                hobby_texts.extend([hobby_name] * max(1, int(score * 3)))
            
            # Get recent interactions
            interactions_query = select(UserInteraction).where(
                UserInteraction.user_id == user_id_int
            ).order_by(UserInteraction.created_at.desc()).limit(50)
            
            interactions_result = await db.execute(interactions_query)
            interactions = interactions_result.scalars().all()
            
            # Add interaction categories
            for interaction in interactions:
                if interaction.item_type in hobby_texts:
                    hobby_texts.append(interaction.item_type)
            
            # If no data, use default text
            if not hobby_texts:
                hobby_texts = ["general", "social", "community"]
            
            # Generate embedding
            user_text = " ".join(hobby_texts)
            embedding = await EmbeddingService.generate_embedding(user_text)
            
            return embedding
            
        except Exception as e:
            logger.error(f"User embedding generation error: {e}")
            return [0.0] * EmbeddingService.EMBEDDING_DIM

    @staticmethod
    async def store_user_embedding(
        db: AsyncSession,
        user_id: Union[int, str]
    ) -> bool:
        """Generate and store user embedding in Qdrant."""
        try:
            embedding = await EmbeddingService.generate_user_embedding(db, user_id)
            
            payload = {
                "user_id": str(user_id),
                "type": "user",
                "updated_at": datetime.utcnow().isoformat()
            }
            
            return await EmbeddingService.upsert_embedding(
                USER_EMBEDDINGS_COLLECTION,
                f"user_{user_id}",
                embedding,
                payload
            )
            
        except Exception as e:
            logger.error(f"Store user embedding error: {e}")
            return False

    @staticmethod
    async def get_user_embedding(
        db: AsyncSession,
        user_id: Union[int, str]
    ) -> Optional[List[float]]:
        """Get user embedding from Qdrant, generating if needed."""
        # Try to get existing embedding
        embedding = await EmbeddingService.get_embedding(
            USER_EMBEDDINGS_COLLECTION,
            f"user_{user_id}"
        )
        
        if embedding:
            return embedding
        
        # Generate and store new embedding
        await EmbeddingService.store_user_embedding(db, user_id)
        return await EmbeddingService.get_embedding(
            USER_EMBEDDINGS_COLLECTION,
            f"user_{user_id}"
        )

    # ============================================
    # EVENT EMBEDDINGS
    # ============================================
    
    @staticmethod
    async def generate_event_embedding(event: Event) -> List[float]:
        """
        Generate embedding for event based on its attributes.
        
        Combines:
        - Category
        - Title
        - Description (if available)
        - Location
        - Tags
        """
        try:
            text_parts = []
            
            # Add category (weighted high)
            if event.category:
                text_parts.extend([event.category] * 3)
            
            # Add title
            if event.title:
                text_parts.append(event.title)
            
            # Add description
            if hasattr(event, 'description') and event.description:
                text_parts.append(event.description[:200])
            
            # Add location keywords
            if event.location:
                text_parts.append(event.location)
            
            # Add tags if available
            if hasattr(event, 'tags') and event.tags:
                if isinstance(event.tags, list):
                    text_parts.extend(event.tags)
                elif isinstance(event.tags, str):
                    text_parts.extend(event.tags.split(','))
            
            # Default text if nothing
            if not text_parts:
                text_parts = ["event", "community"]
            
            event_text = " ".join(text_parts)
            embedding = await EmbeddingService.generate_embedding(event_text)
            
            return embedding
            
        except Exception as e:
            logger.error(f"Event embedding generation error: {e}")
            return [0.0] * EmbeddingService.EMBEDDING_DIM

    @staticmethod
    async def store_event_embedding(event: Event) -> bool:
        """Generate and store event embedding in Qdrant."""
        try:
            embedding = await EmbeddingService.generate_event_embedding(event)
            
            payload = {
                "event_id": str(event.event_id),
                "title": event.title,
                "category": event.category,
                "location": event.location,
                "type": "event",
                "updated_at": datetime.utcnow().isoformat()
            }
            
            return await EmbeddingService.upsert_embedding(
                EVENT_EMBEDDINGS_COLLECTION,
                f"event_{event.event_id}",
                embedding,
                payload
            )
            
        except Exception as e:
            logger.error(f"Store event embedding error: {e}")
            return False

    @staticmethod
    async def get_event_embedding(event_id: Union[int, str]) -> Optional[List[float]]:
        """Get event embedding from Qdrant."""
        return await EmbeddingService.get_embedding(
            EVENT_EMBEDDINGS_COLLECTION,
            f"event_{event_id}"
        )

    # ============================================
    # HOBBY EMBEDDINGS
    # ============================================
    
    @staticmethod
    async def store_hobby_embedding(
        hobby_id: str,
        hobby_name: str,
        category: str = None
    ) -> bool:
        """Generate and store hobby embedding in Qdrant."""
        try:
            # Build hobby text
            text_parts = [hobby_name]
            
            if category:
                text_parts.append(category)
            
            # Add related keywords
            for cat, keywords in EmbeddingService.CATEGORY_KEYWORDS.items():
                if hobby_name.lower() in keywords or (category and category.lower() == cat):
                    text_parts.extend(keywords[:5])
                    break
            
            hobby_text = " ".join(text_parts)
            embedding = await EmbeddingService.generate_embedding(hobby_text)
            
            payload = {
                "hobby_id": hobby_id,
                "hobby_name": hobby_name,
                "category": category,
                "type": "hobby",
                "updated_at": datetime.utcnow().isoformat()
            }
            
            return await EmbeddingService.upsert_embedding(
                HOBBY_EMBEDDINGS_COLLECTION,
                f"hobby_{hobby_id}",
                embedding,
                payload
            )
            
        except Exception as e:
            logger.error(f"Store hobby embedding error: {e}")
            return False

    @staticmethod
    async def sync_all_hobbies(db: AsyncSession) -> Dict[str, Any]:
        """Sync all hobbies from taxonomy to Qdrant."""
        try:
            query = select(InterestTaxonomy).where(InterestTaxonomy.is_active == True)
            result = await db.execute(query)
            hobbies = result.scalars().all()
            
            success_count = 0
            for hobby in hobbies:
                if await EmbeddingService.store_hobby_embedding(
                    str(hobby.interest_id),
                    hobby.interest_name,
                    hobby.parent_id
                ):
                    success_count += 1
            
            return {
                "total": len(hobbies),
                "synced": success_count,
                "collection": HOBBY_EMBEDDINGS_COLLECTION
            }
            
        except Exception as e:
            logger.error(f"Hobby sync error: {e}")
            return {"error": str(e)}

    # ============================================
    # SIMILARITY SEARCH
    # ============================================
    
    @staticmethod
    async def find_similar_events(
        user_embedding: List[float],
        limit: int = 20,
        category_filter: str = None
    ) -> List[Dict[str, Any]]:
        """Find events similar to user's preferences."""
        filter_conditions = None
        
        if category_filter:
            filter_conditions = {
                "must": [{
                    "key": "category",
                    "match": {"value": category_filter}
                }]
            }
        
        return await EmbeddingService.search_similar(
            EVENT_EMBEDDINGS_COLLECTION,
            user_embedding,
            limit,
            filter_conditions
        )

    @staticmethod
    async def find_similar_users(
        user_embedding: List[float],
        exclude_user_id: str = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Find users with similar preferences (for collaborative filtering)."""
        filter_conditions = None
        
        if exclude_user_id:
            filter_conditions = {
                "must_not": [{
                    "key": "user_id",
                    "match": {"value": exclude_user_id}
                }]
            }
        
        return await EmbeddingService.search_similar(
            USER_EMBEDDINGS_COLLECTION,
            user_embedding,
            limit,
            filter_conditions
        )

    @staticmethod
    async def compute_relevance_score(
        user_embedding: List[float],
        event_embedding: List[float]
    ) -> float:
        """Compute cosine similarity between user and event embeddings."""
        try:
            # Convert to numpy arrays
            user_vec = np.array(user_embedding)
            event_vec = np.array(event_embedding)
            
            # Compute cosine similarity
            dot_product = np.dot(user_vec, event_vec)
            norm_product = np.linalg.norm(user_vec) * np.linalg.norm(event_vec)
            
            if norm_product == 0:
                return 0.0
            
            similarity = dot_product / norm_product
            
            # Normalize to 0-1 range
            return float(max(0.0, min(1.0, (similarity + 1) / 2)))
            
        except Exception as e:
            logger.error(f"Relevance score error: {e}")
            return 0.5  # Default neutral score
