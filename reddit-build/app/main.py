"""
FastAPI application for Reddit Comment Analysis API.
"""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import time
from typing import Callable, Any

from .core.config import get_settings
from .core.logging import get_logger, setup_logging
from .api.routes import router

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


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle unexpected exceptions globally."""
    logger.error(f"Unhandled exception: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal server error",
            "error_type": type(exc).__name__,
            "timestamp": str(time.time()),
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
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
        log_level=settings.log_level.lower(),
    )
