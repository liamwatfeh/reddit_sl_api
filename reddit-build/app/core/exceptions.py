"""
Custom exception classes for Reddit Comment Analysis API.
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
        retry_after: Optional[int] = None
    ):
        self.error_code = error_code
        self.debug_info = debug_info or {}
        self.retry_after = retry_after
        
        detail = {
            "error_code": error_code,
            "message": message,
            "debug_info": debug_info
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
        debug_info: Optional[Dict[str, Any]] = None
    ):
        error_code = "REDDIT_001"
        if debug_info is None:
            debug_info = {}
        if endpoint:
            debug_info["endpoint"] = endpoint
            
        super().__init__(
            error_code=error_code,
            message=f"Reddit API error: {message}",
            status_code=status_code,
            debug_info=debug_info
        )


class DataExtractionException(BaseAPIException):
    """Exception for data extraction and parsing errors."""
    
    def __init__(
        self, 
        message: str, 
        phase: str = None,
        status_code: int = 422,
        debug_info: Optional[Dict[str, Any]] = None
    ):
        error_code = "DATA_001"
        if debug_info is None:
            debug_info = {}
        if phase:
            debug_info["extraction_phase"] = phase
            
        super().__init__(
            error_code=error_code,
            message=f"Data extraction error: {message}",
            status_code=status_code,
            debug_info=debug_info
        )


class AIAnalysisException(BaseAPIException):
    """Exception for AI analysis related errors."""
    
    def __init__(
        self, 
        message: str, 
        model: str = None,
        status_code: int = 502,
        debug_info: Optional[Dict[str, Any]] = None
    ):
        error_code = "AI_001"
        if debug_info is None:
            debug_info = {}
        if model:
            debug_info["model"] = model
            
        super().__init__(
            error_code=error_code,
            message=f"AI analysis error: {message}",
            status_code=status_code,
            debug_info=debug_info
        )


class RateLimitException(BaseAPIException):
    """Exception for rate limiting errors."""
    
    def __init__(
        self, 
        message: str, 
        service: str = None,
        retry_after: int = 60,
        debug_info: Optional[Dict[str, Any]] = None
    ):
        error_code = "RATE_001"
        if debug_info is None:
            debug_info = {}
        if service:
            debug_info["service"] = service
            
        super().__init__(
            error_code=error_code,
            message=f"Rate limit exceeded: {message}",
            status_code=429,
            debug_info=debug_info,
            retry_after=retry_after
        )


class ConfigurationException(BaseAPIException):
    """Exception for configuration related errors."""
    
    def __init__(
        self, 
        message: str, 
        config_key: str = None,
        debug_info: Optional[Dict[str, Any]] = None
    ):
        error_code = "CONFIG_001"
        if debug_info is None:
            debug_info = {}
        if config_key:
            debug_info["config_key"] = config_key
            
        super().__init__(
            error_code=error_code,
            message=f"Configuration error: {message}",
            status_code=500,
            debug_info=debug_info
        )


class ValidationException(BaseAPIException):
    """Exception for request validation errors."""
    
    def __init__(
        self, 
        message: str, 
        field: str = None,
        debug_info: Optional[Dict[str, Any]] = None
    ):
        error_code = "VALIDATION_001"
        if debug_info is None:
            debug_info = {}
        if field:
            debug_info["field"] = field
            
        super().__init__(
            error_code=error_code,
            message=f"Validation error: {message}",
            status_code=422,
            debug_info=debug_info
        ) 