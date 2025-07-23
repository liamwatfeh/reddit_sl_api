"""
Custom exception classes for Reddit Comment Analysis API.
Enhanced with granular error handling for better production debugging.
"""

from typing import Optional, Dict, Any
from fastapi import HTTPException


class BaseAPIException(HTTPException):
    """Base exception class for all API errors."""
    
    def __init__(
        self,
        error_code: str,
        message: str,
        status_code: int = 500,
        debug_info: Optional[Dict[str, Any]] = None,
        retry_after: Optional[int] = None,
        **additional_debug_info
    ):
        self.error_code = error_code
        # Centralized debug_info initialization
        self.debug_info = debug_info or {}
        # Add any additional debug info passed as kwargs
        self.debug_info.update(additional_debug_info)
        self.retry_after = retry_after
        
        detail = {
            "error_code": error_code,
            "message": message,
            "debug_info": self.debug_info
        }
        
        headers = {}
        if retry_after:
            headers["Retry-After"] = str(retry_after)
            
        super().__init__(status_code=status_code, detail=detail, headers=headers)


class RedditAPIException(BaseAPIException):
    """Exception for Reddit API related errors."""
    
    def __init__(
        self, 
        message: str, 
        endpoint: str = None,
        status_code: int = 503,
        error_code: str = None,  # Allow granular error codes
        **kwargs
    ):
        # Use granular error code if provided, otherwise default
        if error_code is None:
            error_code = "REDDIT_001"
        
        super().__init__(
            error_code=error_code,
            message=f"Reddit API error: {message}",
            status_code=status_code,
            endpoint=endpoint,
            **kwargs
        )


class DataExtractionException(BaseAPIException):
    """Exception for data extraction and parsing errors."""
    
    def __init__(
        self, 
        message: str, 
        phase: str = None,
        status_code: int = 422,
        error_code: str = None,  # Allow granular error codes
        **kwargs
    ):
        # Use granular error code if provided, otherwise default
        if error_code is None:
            error_code = "DATA_001"
        
        super().__init__(
            error_code=error_code,
            message=f"Data extraction error: {message}",
            status_code=status_code,
            extraction_phase=phase,
            **kwargs
        )


class AIAnalysisException(BaseAPIException):
    """Exception for AI analysis related errors."""
    
    def __init__(
        self, 
        message: str, 
        model: str = None,
        status_code: int = 502,
        error_code: str = None,  # Allow granular error codes
        **kwargs
    ):
        # Use granular error code if provided, otherwise default
        if error_code is None:
            error_code = "AI_001"
        
        super().__init__(
            error_code=error_code,
            message=f"AI analysis error: {message}",
            status_code=status_code,
            model=model,
            **kwargs
        )


class RateLimitException(BaseAPIException):
    """Exception for rate limiting errors."""
    
    def __init__(
        self, 
        message: str, 
        service: str = None,
        retry_after: int = 60,
        error_code: str = None,  # Allow granular error codes
        **kwargs
    ):
        # Use granular error code if provided, otherwise default
        if error_code is None:
            error_code = "RATE_001"
        
        super().__init__(
            error_code=error_code,
            message=f"Rate limit exceeded: {message}",
            status_code=429,
            retry_after=retry_after,
            service=service,
            **kwargs
        )


class ConfigurationException(BaseAPIException):
    """Exception for configuration related errors."""
    
    def __init__(
        self, 
        message: str, 
        config_key: str = None,
        error_code: str = None,  # Allow granular error codes
        **kwargs
    ):
        # Use granular error code if provided, otherwise default
        if error_code is None:
            error_code = "CONFIG_001"
        
        super().__init__(
            error_code=error_code,
            message=f"Configuration error: {message}",
            status_code=503,  # Changed from 500 to 503 (Service Unavailable)
            config_key=config_key,
            **kwargs
        )


class ValidationException(BaseAPIException):
    """Exception for request validation errors."""
    
    def __init__(
        self, 
        message: str, 
        field: str = None,
        error_code: str = None,  # Allow granular error codes
        **kwargs
    ):
        # Use granular error code if provided, otherwise default
        if error_code is None:
            error_code = "VALIDATION_001"
        
        super().__init__(
            error_code=error_code,
            message=f"Validation error: {message}",
            status_code=422,
            field=field,
            **kwargs
        )


# Predefined granular exception subclasses for common error scenarios
class RedditAuthException(RedditAPIException):
    """Specific exception for Reddit authentication errors."""
    
    def __init__(self, message: str, **kwargs):
        super().__init__(
            message=message,
            error_code="REDDIT_AUTH_001",
            **kwargs
        )


class AITimeoutException(AIAnalysisException):
    """Specific exception for AI analysis timeouts."""
    
    def __init__(self, message: str, **kwargs):
        super().__init__(
            message=message,
            error_code="AI_TIMEOUT_001",
            **kwargs
        )


class DataParsingException(DataExtractionException):
    """Specific exception for data parsing errors."""
    
    def __init__(self, message: str, **kwargs):
        super().__init__(
            message=message,
            error_code="DATA_PARSING_001",
            **kwargs
        )


class DataValidationException(DataExtractionException):
    """Specific exception for data validation errors."""
    
    def __init__(self, message: str, **kwargs):
        super().__init__(
            message=message,
            error_code="DATA_VALIDATION_001",
            **kwargs
        )


class ConfigMissingException(ConfigurationException):
    """Specific exception for missing configuration values."""
    
    def __init__(self, message: str, **kwargs):
        super().__init__(
            message=message,
            error_code="CONFIG_MISSING_001",
            **kwargs
        ) 