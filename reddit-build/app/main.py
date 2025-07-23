"""
FastAPI application for Reddit Comment Analysis API.
"""

from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
import time
import uuid
import asyncio
import httpx
from datetime import datetime
from typing import Callable, Any, Dict

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


# Helper function for standardized debug info handling (Point 4)
def add_debug_info_if_enabled(response_content: Dict[str, Any], debug_info: Dict[str, Any] = None) -> Dict[str, Any]:
    """Add debug info to response if debug mode is enabled."""
    if settings.debug and debug_info:
        response_content["debug_info"] = debug_info
    return response_content


# Security headers middleware (Point 9)
@app.middleware("http")
async def security_headers_middleware(request: Request, call_next: Callable[[Request], Any]) -> Any:
    """Add security headers to all responses."""
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["X-API-Version"] = settings.app_version
    return response


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


# Metrics collection middleware (Point 8)
@app.middleware("http")
async def metrics_middleware(request: Request, call_next: Callable[[Request], Any]) -> Any:
    """Collect request metrics for monitoring and observability."""
    start_time = time.time()
    request_id = f"req_{uuid.uuid4().hex[:12]}"
    
    # Add request ID to request state for use in other handlers
    request.state.request_id = request_id

    try:
        response = await call_next(request)
        process_time = time.time() - start_time
        
        # Emit metrics for monitoring systems
        logger.info(
            f"Request metrics [{request_id}]",
            extra={
                "request_id": request_id,
                "endpoint": request.url.path,
                "method": request.method,
                "status_code": response.status_code,
                "duration_ms": round(process_time * 1000, 2),
                "content_length": request.headers.get("content-length", 0),
                "user_agent": request.headers.get("user-agent", "unknown"),
                "client_ip": request.client.host if request.client else "unknown",
                "query_params": str(request.query_params) if request.query_params else None,
            }
        )
        
        # Add performance headers
        response.headers["X-Process-Time"] = str(round(process_time, 3))
        response.headers["X-Request-ID"] = request_id
        
        return response
        
    except Exception as e:
        process_time = time.time() - start_time
        logger.error(
            f"Request failed [{request_id}]: {type(e).__name__}",
            extra={
                "request_id": request_id,
                "endpoint": request.url.path,
                "method": request.method,
                "duration_ms": round(process_time * 1000, 2),
                "error_type": type(e).__name__,
                "error_message": str(e),
            }
        )
        raise


# Request/response logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next: Callable[[Request], Any]) -> Any:
    """Log all HTTP requests and responses."""
    start_time = time.time()
    request_id = getattr(request.state, 'request_id', f"req_{uuid.uuid4().hex[:12]}")

    # Log request
    logger.info(
        f"Request [{request_id}]: {request.method} {request.url.path} - "
        f"Client: {request.client.host if request.client else 'unknown'}"
    )

    # Process request
    response = await call_next(request)

    # Log response
    process_time = time.time() - start_time
    logger.info(
        f"Response [{request_id}]: {response.status_code} - " 
        f"Processing time: {process_time:.3f}s"
    )

    return response


# Health check functions (Point 5)
async def check_reddit_api_health() -> bool:
    """Check if Reddit API is accessible and responding."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            # Simple health check to Reddit's API
            response = await client.get(
                "https://reddit-api25.p.rapidapi.com/health",
                headers={"X-RapidAPI-Key": settings.rapid_api_key}
            )
            return response.status_code == 200
    except Exception as e:
        logger.warning(f"Reddit API health check failed: {e}")
        return False


async def check_openai_api_health() -> bool:
    """Check if OpenAI API is accessible and responding."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            # Simple health check to OpenAI's API
            response = await client.get(
                "https://api.openai.com/v1/models",
                headers={"Authorization": f"Bearer {settings.openai_api_key}"}
            )
            return response.status_code == 200
    except Exception as e:
        logger.warning(f"OpenAI API health check failed: {e}")
        return False


# Exception Handlers - Optimized order (Point 10: Most specific to most general)

# 1. Most specific: Rate limiting exceptions
@app.exception_handler(RateLimitException)
async def rate_limit_exception_handler(request: Request, exc: RateLimitException) -> JSONResponse:
    """Handle rate limiting exceptions."""
    request_id = getattr(request.state, 'request_id', f"req_{uuid.uuid4().hex[:12]}")
    
    logger.warning(
        f"Rate Limit Exceeded [{request_id}]: {exc.error_code}",
        extra={
            "request_id": request_id,
            "error_code": exc.error_code,
            "service": exc.debug_info.get("service"),
            "retry_after": exc.retry_after,
        }
    )
    
    response_content = {
        "error_code": exc.error_code,
        "message": f"Rate limit exceeded. Please try again in {exc.retry_after} seconds.",
        "request_id": request_id,
        "timestamp": datetime.now().isoformat(),
        "retry_after": exc.retry_after,
    }
    
    # Apply standardized debug info handling (Point 4)
    response_content = add_debug_info_if_enabled(response_content, exc.debug_info)
    
    return JSONResponse(
        status_code=exc.status_code,
        content=response_content,
        headers={"Retry-After": str(exc.retry_after)}
    )


# 2. Service-specific exceptions
@app.exception_handler(RedditAPIException)
async def reddit_api_exception_handler(request: Request, exc: RedditAPIException) -> JSONResponse:
    """Handle Reddit API specific exceptions."""
    request_id = getattr(request.state, 'request_id', f"req_{uuid.uuid4().hex[:12]}")
    
    logger.error(
        f"Reddit API Error [{request_id}]: {exc.error_code}",
        extra={
            "request_id": request_id,
            "error_code": exc.error_code,
            "endpoint": exc.debug_info.get("endpoint", "unknown"),
            "reddit_response": exc.debug_info.get("response_code"),
        }
    )
    
    response_content = {
        "error_code": exc.error_code,
        "message": "Reddit service temporarily unavailable. Please try again later.",
        "request_id": request_id,
        "timestamp": datetime.now().isoformat(),
        "retry_after": 60,
    }
    
    # Apply standardized debug info handling (Point 4)
    response_content = add_debug_info_if_enabled(response_content, exc.debug_info)
    
    return JSONResponse(
        status_code=exc.status_code,
        content=response_content,
        headers={"Retry-After": "60"}
    )


@app.exception_handler(AIAnalysisException)
async def ai_analysis_exception_handler(request: Request, exc: AIAnalysisException) -> JSONResponse:
    """Handle AI analysis specific exceptions."""
    request_id = getattr(request.state, 'request_id', f"req_{uuid.uuid4().hex[:12]}")
    
    logger.error(
        f"AI Analysis Error [{request_id}]: {exc.error_code}",
        extra={
            "request_id": request_id,
            "error_code": exc.error_code,
            "model": exc.debug_info.get("model", "unknown"),
            "analysis_phase": exc.debug_info.get("phase"),
        }
    )
    
    response_content = {
        "error_code": exc.error_code,
        "message": "AI analysis service temporarily unavailable. Please try again later.",
        "request_id": request_id,
        "timestamp": datetime.now().isoformat(),
    }
    
    # Apply standardized debug info handling (Point 4)
    response_content = add_debug_info_if_enabled(response_content, exc.debug_info)
    
    return JSONResponse(
        status_code=exc.status_code,
        content=response_content
    )


@app.exception_handler(DataExtractionException)
async def data_extraction_exception_handler(request: Request, exc: DataExtractionException) -> JSONResponse:
    """Handle data extraction specific exceptions."""
    request_id = getattr(request.state, 'request_id', f"req_{uuid.uuid4().hex[:12]}")
    
    logger.error(
        f"Data Extraction Error [{request_id}]: {exc.error_code}",
        extra={
            "request_id": request_id,
            "error_code": exc.error_code,
            "extraction_phase": exc.debug_info.get("extraction_phase"),
            "data_source": exc.debug_info.get("source"),
        }
    )
    
    response_content = {
        "error_code": exc.error_code,
        "message": "Unable to process the requested data. Please check your parameters and try again.",
        "request_id": request_id,
        "timestamp": datetime.now().isoformat(),
    }
    
    # Apply standardized debug info handling (Point 4)
    response_content = add_debug_info_if_enabled(response_content, exc.debug_info)
    
    return JSONResponse(
        status_code=exc.status_code,
        content=response_content
    )


@app.exception_handler(ValidationException)
async def validation_exception_handler(request: Request, exc: ValidationException) -> JSONResponse:
    """Handle validation specific exceptions."""
    request_id = getattr(request.state, 'request_id', f"req_{uuid.uuid4().hex[:12]}")
    
    logger.warning(
        f"Validation Error [{request_id}]: {exc.error_code}",
        extra={
            "request_id": request_id,
            "error_code": exc.error_code,
            "field": exc.debug_info.get("field"),
            "validation_issue": exc.debug_info.get("issue"),
        }
    )
    
    response_content = {
        "error_code": exc.error_code,
        "message": exc.detail["message"],
        "request_id": request_id,
        "timestamp": datetime.now().isoformat(),
    }
    
    # Apply standardized debug info handling (Point 4)
    response_content = add_debug_info_if_enabled(response_content, exc.debug_info)
    
    return JSONResponse(
        status_code=exc.status_code,
        content=response_content
    )


@app.exception_handler(ConfigurationException)
async def configuration_exception_handler(request: Request, exc: ConfigurationException) -> JSONResponse:
    """Handle configuration specific exceptions."""
    request_id = getattr(request.state, 'request_id', f"req_{uuid.uuid4().hex[:12]}")
    
    logger.critical(
        f"Configuration Error [{request_id}]: {exc.error_code}",
        extra={
            "request_id": request_id,
            "error_code": exc.error_code,
            "config_key": exc.debug_info.get("config_key"),
        }
    )
    
    response_content = {
        "error_code": exc.error_code,
        "message": "Service temporarily unavailable due to configuration issues.",
        "request_id": request_id,
        "timestamp": datetime.now().isoformat(),
    }
    
    # Apply standardized debug info handling (Point 4)
    response_content = add_debug_info_if_enabled(response_content, exc.debug_info)
    
    return JSONResponse(
        status_code=exc.status_code,
        content=response_content
    )


# 3. General custom API exceptions
@app.exception_handler(BaseAPIException)
async def api_exception_handler(request: Request, exc: BaseAPIException) -> JSONResponse:
    """Handle custom API exceptions with detailed logging."""
    request_id = getattr(request.state, 'request_id', f"req_{uuid.uuid4().hex[:12]}")
    
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
    
    # Apply standardized debug info handling (Point 4)
    response_content = add_debug_info_if_enabled(response_content, exc.debug_info)
    
    return JSONResponse(
        status_code=exc.status_code,
        content=response_content,
        headers=exc.headers or {}
    )


# 4. Most general: Catch-all exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle unexpected exceptions globally with enhanced logging."""
    request_id = getattr(request.state, 'request_id', f"req_{uuid.uuid4().hex[:12]}")
    
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


# Startup event with health checks (Point 5)
@app.on_event("startup")
async def startup_event() -> None:
    """Initialize application services and perform health checks."""
    logger.info("🚀 Reddit Comment Analysis API starting up...")
    logger.info(f"📍 Version: {settings.app_version}")
    logger.info(f"🔧 Debug mode: {settings.debug}")
    logger.info(f"📊 Log level: {settings.log_level}")
    logger.info(f"🤖 Max concurrent agents: {settings.max_concurrent_agents}")
    
    # Initialize job queue
    from app.services.job_queue import get_job_queue
    job_queue = get_job_queue()
    logger.info(f"📋 Background job queue initialized with {job_queue.max_concurrent_jobs} max concurrent jobs")
    
    # Health check critical dependencies (Point 5)
    logger.info("🔍 Performing startup health checks...")
    
    health_checks = {
        "reddit_api": await check_reddit_api_health(),
        "openai_api": await check_openai_api_health(),
    }
    
    for service, is_healthy in health_checks.items():
        if is_healthy:
            logger.info(f"✅ {service} is healthy")
        else:
            logger.error(f"❌ {service} is unhealthy")
            # In production, you might want to fail fast here
            if not settings.debug:
                logger.warning(f"⚠️  Service {service} is unhealthy but continuing startup")
    
    # Log health check summary
    healthy_services = sum(health_checks.values())
    total_services = len(health_checks)
    logger.info(f"🏥 Health check summary: {healthy_services}/{total_services} services healthy")


# Shutdown event
@app.on_event("shutdown")
async def shutdown_event() -> None:
    """Gracefully shutdown application services."""
    logger.info("🛑 Reddit Comment Analysis API shutting down...")
    
    # Shutdown job queue
    from app.services.job_queue import get_job_queue
    job_queue = get_job_queue()
    await job_queue.shutdown()
    logger.info("📋 Background job queue shutdown completed")


# Development mode startup check with production warning (Point 7)
if __name__ == "__main__":
    import uvicorn

    # Production deployment warning (Point 7)
    if not settings.debug:
        logger.warning("⚠️  Direct uvicorn.run() detected in production mode!")
        logger.warning("⚠️  Use a production WSGI server like Gunicorn for production deployment")
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
    print(f"   - Security Headers: ✓")
    print("📝 Logging configuration:")
    print(f"   - Level: {settings.log_level}")
    print(f"   - File Logging: {'✓' if settings.enable_file_logging else '✗'}")
    print(f"   - JSON Format: {'✓' if settings.enable_json_logging else '✗'}")
    print(f"   - Log Path: {settings.log_file_path}/{settings.log_file_name}")
    print(f"   - Rotation: {settings.log_rotation_size / (1024*1024):.1f}MB, {settings.log_retention_count} files")
    print("📊 Monitoring features:")
    print(f"   - Request Metrics: ✓")
    print(f"   - Health Checks: ✓")
    print(f"   - Performance Headers: ✓")

    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_level=settings.log_level.lower(),
    )
 