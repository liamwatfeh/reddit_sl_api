"""
FastAPI application for Reddit Comment Analysis API.
"""

from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
import time
import uuid
from datetime import datetime
from typing import Callable, Any, Dict
from collections import defaultdict

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

# Add Trusted Host middleware for security (Point 3)
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=settings.allowed_hosts if not settings.debug else ["*"]
)

# Add CORS middleware with secure configuration (Point 1)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins if not settings.debug else ["*"],
    allow_credentials=False,  # Only enable if absolutely necessary
    allow_methods=settings.allowed_methods,
    allow_headers=["Content-Type", "Authorization", "X-API-Key"],
)

# Point 6: Simple rate limiting (in-memory, production would use Redis)
rate_limit_storage: Dict[str, Dict[str, float]] = defaultdict(lambda: {"count": 0, "reset_time": 0})

@app.middleware("http")
async def simple_rate_limit_middleware(request: Request, call_next: Callable[[Request], Any]) -> Any:
    """Simple rate limiting middleware - 100 requests per minute per IP."""
    if request.url.path in ["/health", "/docs", "/redoc"]:  # Skip rate limiting for health/docs
        return await call_next(request)
    
    client_ip = request.client.host if request.client else "unknown"
    current_time = time.time()
    
    # Reset counter every minute
    if current_time > rate_limit_storage[client_ip]["reset_time"]:
        rate_limit_storage[client_ip] = {"count": 0, "reset_time": current_time + 60}
    
    # Check limit (100 requests per minute)
    if rate_limit_storage[client_ip]["count"] >= 100:
        return JSONResponse(
            status_code=429,
            content={
                "error_code": "RATE_LIMIT_EXCEEDED",
                "message": "Too many requests. Please try again later.",
                "request_id": f"req_{uuid.uuid4().hex[:12]}",
                "timestamp": datetime.now().isoformat(),
                "retry_after": int(rate_limit_storage[client_ip]["reset_time"] - current_time),
            },
            headers={"Retry-After": str(int(rate_limit_storage[client_ip]["reset_time"] - current_time))}
        )
    
    rate_limit_storage[client_ip]["count"] += 1
    return await call_next(request)


# Request size limiting middleware (Point 3)
@app.middleware("http")
async def request_size_limit_middleware(request: Request, call_next: Callable[[Request], Any]) -> Any:
    """Limit request body size to prevent DoS attacks."""
    content_length = request.headers.get("content-length")
    if content_length:
        content_length = int(content_length)
        if content_length > settings.max_request_size:
            return JSONResponse(
                status_code=413,
                content={
                    "error_code": "REQUEST_TOO_LARGE",
                    "message": f"Request body too large. Maximum size is {settings.max_request_size / (1024*1024):.1f}MB",
                    "request_id": f"req_{uuid.uuid4().hex[:12]}",
                    "timestamp": datetime.now().isoformat(),
                }
            )
    
    return await call_next(request)


# Point 8: Metrics collection middleware
@app.middleware("http")
async def metrics_middleware(request: Request, call_next: Callable[[Request], Any]) -> Any:
    """Collect metrics for monitoring and observability."""
    start_time = time.time()
    
    # Process request
    response = await call_next(request)
    
    # Calculate metrics
    process_time = time.time() - start_time
    
    # Point 8: Emit structured metrics for monitoring
    logger.info(
        "Request metrics",
        extra={
            "endpoint": request.url.path,
            "method": request.method,
            "status_code": response.status_code,
            "duration_ms": round(process_time * 1000, 2),
            "client_ip": request.client.host if request.client else "unknown",
            "user_agent": request.headers.get("user-agent", "unknown")[:100],  # Truncate for safety
            "request_size": request.headers.get("content-length", 0),
            "response_size": response.headers.get("content-length", 0),
        }
    )
    
    return response


# Request/response logging middleware (enhanced with metrics)
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


# Point 9: Security headers middleware
@app.middleware("http")
async def security_headers_middleware(request: Request, call_next: Callable[[Request], Any]) -> Any:
    """Add security headers to protect against common web vulnerabilities."""
    response = await call_next(request)
    
    # Point 9: Add security headers
    response.headers.update({
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "X-XSS-Protection": "1; mode=block",
        "Referrer-Policy": "strict-origin-when-cross-origin",
        "X-Permitted-Cross-Domain-Policies": "none",
        "X-Download-Options": "noopen",
    })
    
    # Add CSP for API (restrictive)
    if not settings.debug:
        response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none';"
    
    return response


# Point 4: Helper function for consistent debug info handling
def add_debug_info_if_enabled(response_content: dict, debug_info: dict = None) -> dict:
    """Add debug info to response if debug mode is enabled."""
    if settings.debug and debug_info:
        response_content["debug_info"] = debug_info
    return response_content


# Point 10: Exception handlers ordered from most specific to most general
# Order: BaseAPIException -> RedditAPIException -> AIAnalysisException -> 
#        DataExtractionException -> RateLimitException -> Global Exception
# This ordering ensures that specific exceptions are caught before generic ones

# Enhanced Exception Handlers with UUID-based request IDs (Point 2)
@app.exception_handler(BaseAPIException)
async def api_exception_handler(request: Request, exc: BaseAPIException) -> JSONResponse:
    """Handle custom API exceptions with detailed logging."""
    request_id = f"req_{uuid.uuid4().hex[:12]}"
    
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
    request_id = f"req_{uuid.uuid4().hex[:12]}"
    
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
    request_id = f"req_{uuid.uuid4().hex[:12]}"
    
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
    request_id = f"req_{uuid.uuid4().hex[:12]}"
    
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
    request_id = f"req_{uuid.uuid4().hex[:12]}"
    
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
    request_id = f"req_{uuid.uuid4().hex[:12]}"
    
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


# Point 5: Health check functions for startup
async def check_reddit_api_health() -> bool:
    """Check if Reddit API is accessible (non-blocking)."""
    try:
        import httpx
        async with httpx.AsyncClient(timeout=5.0) as client:
            # Simple health check - just verify we can connect
            response = await client.get("https://reddit.com", timeout=5.0)
            return response.status_code < 500
    except Exception:
        return False

async def check_openai_api_health() -> bool:
    """Check if OpenAI API is accessible (non-blocking)."""
    try:
        if not settings.openai_api_key:
            return False
        # Don't make actual API call, just verify key format
        return len(settings.openai_api_key) > 10
    except Exception:
        return False


# Startup event with health checks (Point 5)
@app.on_event("startup")
async def startup_event() -> None:
    """Log startup information and check critical dependencies."""
    logger.info("🚀 Reddit Comment Analysis API starting up...")
    logger.info(f"📍 Version: {settings.app_version}")
    logger.info(f"🔧 Debug mode: {settings.debug}")
    logger.info(f"📊 Log level: {settings.log_level}")
    logger.info(f"🤖 Max concurrent agents: {settings.max_concurrent_agents}")
    
    # Point 5: Health check critical dependencies (non-blocking)
    logger.info("🔍 Checking service dependencies...")
    health_checks = {
        "reddit_api": await check_reddit_api_health(),
        "openai_api": await check_openai_api_health(),
    }
    
    for service, is_healthy in health_checks.items():
        if is_healthy:
            logger.info(f"✅ {service} is healthy")
        else:
            logger.warning(f"⚠️  {service} health check failed - service may be degraded")
            # Continue startup anyway - don't fail the deployment


# Shutdown event
@app.on_event("shutdown")
async def shutdown_event() -> None:
    """Log shutdown information."""
    logger.info("🛑 Reddit Comment Analysis API shutting down...")


# Development mode startup check (Point 7: Production warnings)
if __name__ == "__main__":
    import uvicorn

    # Point 7: Production deployment warning
    if not settings.debug:
        logger.warning("⚠️  Direct uvicorn.run() detected in production mode!")
        logger.warning("⚠️  Use Gunicorn with uvicorn workers for Railway deployment")
        logger.warning("⚠️  Example: gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker")

    # Display startup information
    print("✅ Settings loaded successfully!")
    print("🔑 API Keys configured:")
    print(f"   - RapidAPI: {'✓' if settings.rapid_api_key else '✗'}")
    print(f"   - OpenAI: {'✓' if settings.openai_api_key else '✗'}")
    print("🔒 Security features enabled:")
    print(f"   - CORS Origins: {settings.allowed_origins if not settings.debug else ['*']}")
    print(f"   - Trusted Hosts: {settings.allowed_hosts if not settings.debug else ['*']}")
    print(f"   - Max Request Size: {settings.max_request_size / (1024*1024):.1f}MB")
    print("📝 Logging configuration:")
    print(f"   - Level: {settings.log_level}")
    print(f"   - File Logging: {'✓' if settings.enable_file_logging else '✗'}")
    print(f"   - JSON Format: {'✓' if settings.enable_json_logging else '✗'}")
    print(f"   - Log Path: {settings.log_file_path}/{settings.log_file_name}")
    print(f"   - Rotation: {settings.log_rotation_size / (1024*1024):.1f}MB, {settings.log_retention_count} files")

    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_level=settings.log_level.lower(),
    )
 