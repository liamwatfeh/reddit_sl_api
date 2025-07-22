"""
Simple shared API key authentication for internal use.
"""

import secrets
from fastapi import HTTPException, Header, status
from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()

async def verify_internal_api_key(x_api_key: str = Header(..., description="Internal API key")):
    """
    Verify the shared internal API key from X-API-Key header.
    All team members use the same key.
    
    Args:
        x_api_key: API key from X-API-Key header
        
    Raises:
        HTTPException: If API key is invalid
    """
    if not x_api_key:
        logger.warning("API request attempted without API key")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API key. Please include X-API-Key header.",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    
    # Use constant-time comparison to prevent timing attacks
    if not secrets.compare_digest(x_api_key, settings.internal_api_key):
        logger.warning("Invalid API key provided")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key. Contact your team admin for the correct key.",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    
    logger.info("Valid API key provided") 