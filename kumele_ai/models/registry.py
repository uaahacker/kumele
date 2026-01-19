"""
Model Registry - Manages AI/ML model loading and tracking
"""
import logging
from datetime import datetime
from typing import Dict, Any, Optional
from kumele_ai.config import settings

logger = logging.getLogger(__name__)


class ModelRegistry:
    """Registry for managing AI/ML models"""
    
    def __init__(self):
        self._models: Dict[str, Any] = {}
        self._loaded = False
    
    async def load_models(self):
        """Load all required models on startup"""
        if self._loaded:
            return
        
        logger.info("Loading AI/ML models...")
        
        # Register models in database
        try:
            from kumele_ai.db.database import SessionLocal
            from kumele_ai.db.models import AIModelRegistry
            
            db = SessionLocal()
            
            models_to_register = [
                {
                    "name": "sentence-transformers/all-MiniLM-L6-v2",
                    "version": "1.0.0",
                    "type": "embedder"
                },
                {
                    "name": "distilbert-base-uncased-finetuned-sst-2-english",
                    "version": "1.0.0",
                    "type": "classifier"
                },
                {
                    "name": "unitary/toxic-bert",
                    "version": "1.0.0",
                    "type": "classifier"
                },
                {
                    "name": settings.LLM_MODEL,
                    "version": "0.2",
                    "type": "llm"
                },
                {
                    "name": "libretranslate",
                    "version": "1.0.0",
                    "type": "translator"
                }
            ]
            
            for model_info in models_to_register:
                existing = db.query(AIModelRegistry).filter(
                    AIModelRegistry.name == model_info["name"]
                ).first()
                
                if existing:
                    existing.status = "active"
                    existing.loaded_at = datetime.utcnow()
                else:
                    model_record = AIModelRegistry(
                        name=model_info["name"],
                        version=model_info["version"],
                        type=model_info["type"],
                        status="active",
                        loaded_at=datetime.utcnow()
                    )
                    db.add(model_record)
            
            db.commit()
            db.close()
            
            logger.info(f"Registered {len(models_to_register)} models")
            
        except Exception as e:
            logger.error(f"Error registering models: {e}")
        
        self._loaded = True
    
    async def unload_models(self):
        """Unload models and free resources"""
        logger.info("Unloading models...")
        
        # Unload embedding model
        try:
            from kumele_ai.services.embed_service import embed_service
            embed_service.unload()
        except Exception as e:
            logger.error(f"Error unloading embed service: {e}")
        
        # Unload classification models
        try:
            from kumele_ai.services.classify_service import classify_service
            classify_service.unload()
        except Exception as e:
            logger.error(f"Error unloading classify service: {e}")
        
        self._models.clear()
        self._loaded = False
        logger.info("Models unloaded")
    
    def get_model(self, name: str) -> Optional[Any]:
        """Get a loaded model by name"""
        return self._models.get(name)
    
    def is_loaded(self) -> bool:
        """Check if models are loaded"""
        return self._loaded


# Singleton instance
model_registry = ModelRegistry()
