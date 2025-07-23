"""
Custom exception classes for Reddit Comment Analysis API.
"""

from typing import Optional, Dict, Any, Union
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
        
        # Centralized debug_info initialization (Improvement #2)
        self.debug_info = debug_info or {}
        # Merge any additional debug info passed as kwargs
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
        endpoint: Optional[str] = None,
        status_code: int = 503,
        error_code: str = "REDDIT_001",  # Improvement #1: Allow granular error codes
        debug_info: Optional[Dict[str, Any]] = None
    ):
        # Pass endpoint as additional debug info to base class (Improvement #2)
        super().__init__(
            error_code=error_code,
            message=f"Reddit API error: {message}",
            status_code=status_code,
            debug_info=debug_info,
            endpoint=endpoint  # Automatically added to debug_info if not None
        )


class DataExtractionException(BaseAPIException):
    """Exception for data extraction and parsing errors."""
    
    def __init__(
        self, 
        message: str, 
        phase: Optional[str] = None,
        status_code: int = 422,
        error_code: str = "DATA_001",  # Improvement #1: Allow granular error codes
        debug_info: Optional[Dict[str, Any]] = None
    ):
        # Pass phase as additional debug info to base class (Improvement #2)
        super().__init__(
            error_code=error_code,
            message=f"Data extraction error: {message}",
            status_code=status_code,
            debug_info=debug_info,
            extraction_phase=phase  # Automatically added to debug_info if not None
        )


class AIAnalysisException(BaseAPIException):
    """Exception for AI analysis related errors."""
    
    def __init__(
        self, 
        message: str, 
        model: Optional[str] = None,
        status_code: int = 502,
        error_code: str = "AI_001",  # Improvement #1: Allow granular error codes
        debug_info: Optional[Dict[str, Any]] = None
    ):
        # Pass model as additional debug info to base class (Improvement #2)
        super().__init__(
            error_code=error_code,
            message=f"AI analysis error: {message}",
            status_code=status_code,
            debug_info=debug_info,
            model=model  # Automatically added to debug_info if not None
        )


class RateLimitException(BaseAPIException):
    """Exception for rate limiting errors."""
    
    def __init__(
        self, 
        message: str, 
        service: Optional[str] = None,
        retry_after: int = 60,
        error_code: str = "RATE_001",  # Improvement #1: Allow granular error codes
        debug_info: Optional[Dict[str, Any]] = None
    ):
        # Pass service as additional debug info to base class (Improvement #2)
        super().__init__(
            error_code=error_code,
            message=f"Rate limit exceeded: {message}",
            status_code=429,
            debug_info=debug_info,
            retry_after=retry_after,
            service=service  # Automatically added to debug_info if not None
        )


class ConfigurationException(BaseAPIException):
    """Exception for configuration related errors."""
    
    def __init__(
        self, 
        message: str, 
        config_key: Optional[str] = None,
        error_code: str = "CONFIG_001",  # Improvement #1: Allow granular error codes
        debug_info: Optional[Dict[str, Any]] = None,
        service_unavailable: bool = False  # Improvement #3: Allow semantic status code choice
    ):
        # Choose appropriate status code based on context (Improvement #3)
        status_code = 503 if service_unavailable else 500
        
        # Pass config_key as additional debug info to base class (Improvement #2)
        super().__init__(
            error_code=error_code,
            message=f"Configuration error: {message}",
            status_code=status_code,
            debug_info=debug_info,
            config_key=config_key  # Automatically added to debug_info if not None
        )


class ValidationException(BaseAPIException):
    """Exception for request validation errors."""
    
    def __init__(
        self, 
        message: str, 
        field: Optional[str] = None,
        error_code: str = "VALIDATION_001",  # Improvement #1: Allow granular error codes
        debug_info: Optional[Dict[str, Any]] = None
    ):
        # Pass field as additional debug info to base class (Improvement #2)
        super().__init__(
            error_code=error_code,
            message=f"Validation error: {message}",
            status_code=422,
            debug_info=debug_info,
            field=field  # Automatically added to debug_info if not None
        )


# Common granular error codes for better client-side error handling
class RedditErrorCodes:
    """Predefined granular error codes for Reddit API errors."""
    AUTH_FAILED = "REDDIT_AUTH_001"
    RATE_LIMITED = "REDDIT_RATE_002"
    SUBREDDIT_NOT_FOUND = "REDDIT_NOTFOUND_003"
    FORBIDDEN = "REDDIT_FORBIDDEN_004"
    TIMEOUT = "REDDIT_TIMEOUT_005"
    MALFORMED_RESPONSE = "REDDIT_RESPONSE_006"


class AIErrorCodes:
    """Predefined granular error codes for AI analysis errors."""
    API_KEY_INVALID = "AI_AUTH_001"
    MODEL_UNAVAILABLE = "AI_MODEL_002"
    CONTEXT_TOO_LONG = "AI_CONTEXT_003"
    RATE_LIMITED = "AI_RATE_004"
    PARSING_FAILED = "AI_PARSE_005"
    TIMEOUT = "AI_TIMEOUT_006"


class DataErrorCodes:
    """Predefined granular error codes for data processing errors."""
    EXTRACTION_FAILED = "DATA_EXTRACT_001"
    CLEANING_FAILED = "DATA_CLEAN_002"
    VALIDATION_FAILED = "DATA_VALIDATE_003"
    TRANSFORMATION_FAILED = "DATA_TRANSFORM_004"


class ConfigErrorCodes:
    """Predefined granular error codes for configuration errors."""
    MISSING_KEY = "CONFIG_MISSING_001"
    INVALID_VALUE = "CONFIG_INVALID_002"
    SERVICE_UNAVAILABLE = "CONFIG_SERVICE_003" 