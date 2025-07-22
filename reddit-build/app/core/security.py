"""
Simple shared API key authentication for internal use.
"""

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
        
    Returns:
        True if valid
        
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
    
    if x_api_key != settings.internal_api_key:
        logger.warning(f"Invalid API key attempted: {x_api_key[:10]}...")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key. Contact your team admin for the correct key.",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    
    logger.info(f"Valid API key used: {x_api_key[:10]}...")
    return True 