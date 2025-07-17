"""
FastAPI application for Reddit Comment Analysis API.
"""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import time
from datetime import datetime
from typing import Callable, Any

from app.core.config import get_settings
from app.core.logging import get_logger, setup_logging
from app.api.routes import router
from app.core.exceptions import (
    BaseAPIException,
    RedditAPIException,
    DataExtractionException,
    AIAnalysisException,
    RateLimitException,
    ConfigurationException,
    ValidationException,
)

# Initialize settings and logging
settings = get_settings()
setup_logging()
logger = get_logger(__name__)

# Create FastAPI app
app = FastAPI(
    title="Reddit Comment Analysis API",
    description="AI-powered analysis of Reddit comments with sentiment analysis, theme extraction, and purchase intent detection",
    version=settings.app_version,
    docs_url="/docs",
    redoc_url="/redoc",
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request/response logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next: Callable[[Request], Any]) -> Any:
    """Log all HTTP requests and responses."""
    start_time = time.time()

    # Log request
    logger.info(
        f"Request: {request.method} {request.url.path} - "
        f"Client: {request.client.host if request.client else 'unknown'}"
    )

    # Process request
    response = await call_next(request)

    # Log response
    process_time = time.time() - start_time
    logger.info(
        f"Response: {response.status_code} - " f"Processing time: {process_time:.3f}s"
    )

    return response


# Enhanced Exception Handlers
@app.exception_handler(BaseAPIException)
async def api_exception_handler(request: Request, exc: BaseAPIException) -> JSONResponse:
    """Handle custom API exceptions with detailed logging."""
    request_id = f"req_{int(time.time() * 1000)}"
    
    logger.error(
        f"API Exception [{request_id}]: {exc.error_code} - {exc.detail['message']}",
        extra={
            "request_id": request_id,
            "error_code": exc.error_code,
            "endpoint": str(request.url.path),
            "method": request.method,
            "debug_info": exc.debug_info,
        }
    )
    
    response_content = {
        "error_code": exc.error_code,
        "message": exc.detail["message"],
        "request_id": request_id,
        "timestamp": datetime.now().isoformat(),
    }
    
    # Add debug info in development mode only
    if settings.debug and exc.debug_info:
        response_content["debug_info"] = exc.debug_info
    
    return JSONResponse(
        status_code=exc.status_code,
        content=response_content,
        headers=exc.headers or {}
    )


@app.exception_handler(RedditAPIException)
async def reddit_api_exception_handler(request: Request, exc: RedditAPIException) -> JSONResponse:
    """Handle Reddit API specific exceptions."""
    request_id = f"req_{int(time.time() * 1000)}"
    
    logger.error(
        f"Reddit API Error [{request_id}]: {exc.error_code}",
        extra={
            "request_id": request_id,
            "error_code": exc.error_code,
            "endpoint": exc.debug_info.get("endpoint", "unknown"),
            "reddit_response": exc.debug_info.get("response_code"),
        }
    )
    
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error_code": exc.error_code,
            "message": "Reddit service temporarily unavailable. Please try again later.",
            "request_id": request_id,
            "timestamp": datetime.now().isoformat(),
            "retry_after": 60,
        },
        headers={"Retry-After": "60"}
    )


@app.exception_handler(AIAnalysisException)
async def ai_analysis_exception_handler(request: Request, exc: AIAnalysisException) -> JSONResponse:
    """Handle AI analysis specific exceptions."""
    request_id = f"req_{int(time.time() * 1000)}"
    
    logger.error(
        f"AI Analysis Error [{request_id}]: {exc.error_code}",
        extra={
            "request_id": request_id,
            "error_code": exc.error_code,
            "model": exc.debug_info.get("model", "unknown"),
            "analysis_phase": exc.debug_info.get("phase"),
        }
    )
    
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error_code": exc.error_code,
            "message": "AI analysis service temporarily unavailable. Please try again later.",
            "request_id": request_id,
            "timestamp": datetime.now().isoformat(),
        }
    )


@app.exception_handler(DataExtractionException)
async def data_extraction_exception_handler(request: Request, exc: DataExtractionException) -> JSONResponse:
    """Handle data extraction specific exceptions."""
    request_id = f"req_{int(time.time() * 1000)}"
    
    logger.error(
        f"Data Extraction Error [{request_id}]: {exc.error_code}",
        extra={
            "request_id": request_id,
            "error_code": exc.error_code,
            "extraction_phase": exc.debug_info.get("extraction_phase"),
            "data_source": exc.debug_info.get("source"),
        }
    )
    
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error_code": exc.error_code,
            "message": "Unable to process the requested data. Please check your parameters and try again.",
            "request_id": request_id,
            "timestamp": datetime.now().isoformat(),
        }
    )


@app.exception_handler(RateLimitException)
async def rate_limit_exception_handler(request: Request, exc: RateLimitException) -> JSONResponse:
    """Handle rate limiting exceptions."""
    request_id = f"req_{int(time.time() * 1000)}"
    
    logger.warning(
        f"Rate Limit Exceeded [{request_id}]: {exc.error_code}",
        extra={
            "request_id": request_id,
            "error_code": exc.error_code,
            "service": exc.debug_info.get("service"),
            "retry_after": exc.retry_after,
        }
    )
    
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error_code": exc.error_code,
            "message": f"Rate limit exceeded. Please try again in {exc.retry_after} seconds.",
            "request_id": request_id,
            "timestamp": datetime.now().isoformat(),
            "retry_after": exc.retry_after,
        },
        headers={"Retry-After": str(exc.retry_after)}
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle unexpected exceptions globally with enhanced logging."""
    request_id = f"req_{int(time.time() * 1000)}"
    
    logger.error(
        f"Unhandled Exception [{request_id}]: {type(exc).__name__} - {str(exc)}",
        exc_info=True,
        extra={
            "request_id": request_id,
            "endpoint": str(request.url.path),
            "method": request.method,
            "exception_type": type(exc).__name__,
        }
    )
    
    return JSONResponse(
        status_code=500,
        content={
            "error_code": "INTERNAL_001",
            "message": "An unexpected error occurred. Please try again later.",
            "request_id": request_id,
            "timestamp": datetime.now().isoformat(),
        },
    )


# Include API routes
app.include_router(router)


# Startup event
@app.on_event("startup")
async def startup_event() -> None:
    """Log startup information."""
    logger.info("🚀 Reddit Comment Analysis API starting up...")
    logger.info(f"📍 Version: {settings.app_version}")
    logger.info(f"🔧 Debug mode: {settings.debug}")
    logger.info(f"📊 Log level: {settings.log_level}")
    logger.info(f"🤖 Max concurrent agents: {settings.max_concurrent_agents}")


# Shutdown event
@app.on_event("shutdown")
async def shutdown_event() -> None:
    """Log shutdown information."""
    logger.info("🛑 Reddit Comment Analysis API shutting down...")


# Development mode startup check
if __name__ == "__main__":
    import uvicorn

    # Display startup information
    print("✅ Settings loaded successfully!")
    print("🔑 API Keys configured:")
    print(f"   - RapidAPI: {'✓' if settings.rapid_api_key else '✗'}")
    print(f"   - Gemini: {'✓' if settings.gemini_api_key else '✗'}")
    print(f"   - OpenAI: {'✓' if settings.openai_api_key else '✗'}")

    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_level=settings.log_level.lower(),
    )
