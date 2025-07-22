# Improvements for main.py

This document outlines potential production-readiness improvements for the `reddit-build/app/main.py` file. The current implementation is excellent with sophisticated error handling and logging, but these enhancements would make it even more secure and robust for production deployment.

### 1. Fix CORS Configuration for Production Security (High Priority)

- **Issue**: The CORS middleware allows all origins (`allow_origins=["*"]`), credentials, methods, and headers, which is a significant security risk in production.
- **Improvement**: Make CORS configurable and restrictive:
  ```python
  # In config.py
  allowed_origins: List[str] = Field(default=["http://localhost:3000"], description="Allowed CORS origins")
  allowed_methods: List[str] = Field(default=["GET", "POST"], description="Allowed HTTP methods")

  # In main.py
  app.add_middleware(
      CORSMiddleware,
      allow_origins=settings.allowed_origins,
      allow_credentials=False,  # Only enable if absolutely necessary
      allow_methods=settings.allowed_methods,
      allow_headers=["Content-Type", "Authorization", "X-API-Key"],
  )
  ```

### 2. Implement Robust Request ID Generation

- **Issue**: Request IDs use `int(time.time() * 1000)`, which could have collisions in high-traffic scenarios.
- **Improvement**: Use UUID-based generation for guaranteed uniqueness:
  ```python
  import uuid

  # In exception handlers
  request_id = f"req_{uuid.uuid4().hex[:12]}"
  ```

### 3. Add Request Size Limits

- **Issue**: No limits on request body size, which could allow DoS attacks through massive payloads.
- **Improvement**: Add request size limiting and trusted host middleware:
  ```python
  from fastapi.middleware.trustedhost import TrustedHostMiddleware

  app.add_middleware(
      TrustedHostMiddleware,
      allowed_hosts=settings.allowed_hosts if not settings.debug else ["*"]
  )

  # Also consider adding custom middleware for request size limits
  ```

### 4. Standardize Debug Info Handling

- **Issue**: Debug info is only added to `BaseAPIException` responses but not to other exception types, creating inconsistent behavior.
- **Improvement**: Create a helper function for consistent debug info handling:
  ```python
  def add_debug_info_if_enabled(response_content: dict, debug_info: dict = None) -> dict:
      """Add debug info to response if debug mode is enabled."""
      if settings.debug and debug_info:
          response_content["debug_info"] = debug_info
      return response_content
  ```

### 5. Add Startup Health Checks

- **Issue**: Startup event only logs information but doesn't verify that critical dependencies (APIs, services) are available.
- **Improvement**: Add dependency health checks during startup:
  ```python
  @app.on_event("startup")
  async def startup_event() -> None:
      logger.info("🚀 Reddit Comment Analysis API starting up...")

      # Health check critical dependencies
      health_checks = {
          "reddit_api": await check_reddit_api_health(),
          "openai_api": await check_openai_api_health(),
      }

      for service, is_healthy in health_checks.items():
          if is_healthy:
              logger.info(f"✅ {service} is healthy")
          else:
              logger.error(f"❌ {service} is unhealthy")
              # Consider whether to exit or continue with degraded service
  ```

### 6. Implement Global Rate Limiting

- **Issue**: While API endpoints are protected by keys, there's no global rate limiting to prevent abuse.
- **Improvement**: Add rate limiting middleware using slowapi:
  ```python
  from slowapi import Limiter, _rate_limit_exceeded_handler
  from slowapi.util import get_remote_address
  from slowapi.errors import RateLimitExceeded

  limiter = Limiter(key_func=get_remote_address)
  app.state.limiter = limiter
  app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
  ```

### 7. Add Production Deployment Warning

- **Issue**: The development server block uses `uvicorn.run()` directly, which is not suitable for production.
- **Improvement**: Add clear warnings and production guidance:
  ```python
  if __name__ == "__main__":
      if not settings.debug:
          logger.warning("⚠️  Direct uvicorn.run() detected in production mode!")
          logger.warning("⚠️  Use a production WSGI server like Gunicorn for production deployment")

      # Display startup information
      print("✅ Settings loaded successfully!")
      # ... rest of development startup code
  ```

### 8. Add Metrics Collection Middleware

- **Issue**: While there's excellent logging, there are no hooks for metrics collection (response times, error rates) for monitoring systems.
- **Improvement**: Add metrics middleware for observability:
  ```python
  @app.middleware("http")
  async def metrics_middleware(request: Request, call_next):
      start_time = time.time()
      response = await call_next(request)
      process_time = time.time() - start_time

      # Emit metrics (to Prometheus, StatsD, etc.)
      # This would integrate with your monitoring solution
      logger.info(f"Request metrics", extra={
          "endpoint": request.url.path,
          "method": request.method,
          "status_code": response.status_code,
          "duration_ms": process_time * 1000
      })

      return response
  ```

### 9. Add Security Headers Middleware

- **Issue**: No security headers are set to protect against common web vulnerabilities.
- **Improvement**: Add security headers middleware:
  ```python
  @app.middleware("http")
  async def security_headers_middleware(request: Request, call_next):
      response = await call_next(request)
      response.headers["X-Content-Type-Options"] = "nosniff"
      response.headers["X-Frame-Options"] = "DENY"
      response.headers["X-XSS-Protection"] = "1; mode=block"
      response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
      return response
  ```

### 10. Optimize Exception Handler Order

- **Issue**: Exception handlers could be reordered for better performance by placing more specific handlers first.
- **Improvement**: Reorder handlers from most specific to most general and add documentation comments explaining the hierarchy and reasoning for the order.
