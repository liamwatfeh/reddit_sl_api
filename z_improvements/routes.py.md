# Improvements for routes.py

This document outlines potential production-readiness improvements for the `reddit-build/app/api/routes.py` file, listed in order of priority.

### 1. Handle Long-Running Tasks Asynchronously (Critical)

- **Issue**: The analysis is performed synchronously within the request-response cycle. A large request can easily exceed standard HTTP timeout limits (30-60 seconds), causing the request to fail for the client.
- **Improvement**: Implement a background job queue (e.g., Celery with Redis, or ARQ).
  1. The API endpoint should accept the request and create a job in the queue.
  2. It should immediately return a `202 Accepted` response to the client, along with a unique `job_id`.
  3. A new endpoint (e.g., `/status/{job_id}`) should be created for the client to poll for the job's status and retrieve the results once the analysis is complete.

### 2. Remove or Refactor Legacy Endpoint

- **Issue**: The `/analyze-reddit-comments` endpoint appears to be legacy code. It contains duplicated logic and likely depends on the old `comment_analyzer.py` which is slated for deletion.
- **Improvement**: To reduce code duplication and maintenance overhead, this endpoint should be removed. If it must be kept for backward compatibility, it should be refactored to use the same modern `SubredditDataCollector` and `ModernConcurrentCommentAnalysisOrchestrator` as the other endpoints.

### 3. Externalize Hardcoded Concurrency Limit

- **Issue**: The number of concurrent analysis agents is hardcoded (`max_concurrent_agents=5`) directly in the route handlers for `/analyze-subreddit` and `/analyze-search`.
- **Improvement**: Move this value into the application configuration (`app/core/config.py`). This allows the concurrency limit to be adjusted based on the environment (e.g., lower for development, higher for a powerful production server) without requiring a code change.

### 4. Remove Generic Exception Handling from Routes

- **Issue**: The `try...except Exception as e:` blocks within the route functions are too broad. They catch all exceptions, preventing the more specific, detailed exception handlers defined in `main.py` (e.g., `RedditAPIException`, `AIAnalysisException`) from being triggered.
- **Improvement**: Remove these generic `try...except` blocks from the route handlers. Allowing the custom exceptions to propagate will result in more accurate HTTP status codes, more descriptive error messages for the client, and better-structured logs for debugging.
