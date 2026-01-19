"""
FastAPI dependencies for Kumele AI/ML Service
"""
from typing import Generator, Optional
from fastapi import Depends, HTTPException, Header, status
from sqlalchemy.orm import Session
from kumele_ai.db.database import SessionLocal
from kumele_ai.config import settings


def get_db() -> Generator[Session, None, None]:
    """Get database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


async def verify_api_key(x_api_key: Optional[str] = Header(None)) -> str:
    """Verify API key for internal endpoints"""
    if not x_api_key or x_api_key != settings.API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key"
        )
    return x_api_key


async def optional_api_key(x_api_key: Optional[str] = Header(None)) -> Optional[str]:
    """Optional API key verification"""
    return x_api_key
