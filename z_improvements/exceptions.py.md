# Improvements for exceptions.py

This document outlines potential refinements for the `reddit-build/app/core/exceptions.py` file. This file is already in excellent shape and follows best practices; these suggestions are minor enhancements for even better maintainability and error reporting.

### 1. Increase Granularity of Error Codes

- **Issue**: Each exception class currently has a single, static error code (e.g., `REDDIT_001`, `AI_001`). This means different types of errors within the same domain (like a Reddit authentication error vs. a Reddit rate limit error) will produce the same code, offering less detail to the API client.
- **Improvement**: Allow error codes to be more specific. The `__init__` method of each exception could accept an optional, more granular error code. For example, when raising a `RedditAPIException` due to an authentication failure, you could instantiate it with `error_code="REDDIT_AUTH_001"`. This would provide more actionable information to the client for programmatic error handling.

### 2. Centralize `debug_info` Initialization

- **Issue**: Each subclass repeats boilerplate logic to initialize the `debug_info` dictionary and add context-specific keys to it.
  ```python
  if debug_info is None:
      debug_info = {}
  if some_field:
      debug_info["some_key"] = some_field
  ```
- **Improvement**: This logic can be streamlined by handling it in the `BaseAPIException`'s `__init__` method. The base class can be responsible for creating the dictionary, and subclasses can just pass the relevant debug data up in the `super().__init__()` call. This reduces code duplication and centralizes the logic.

### 3. Review Status Code for `ConfigurationException`

- **Issue**: `ConfigurationException` currently defaults to a `500 Internal Server Error`, which is a reasonable choice.
- **Improvement**: For discussion, consider if a `503 Service Unavailable` might be semantically more accurate in some cases. A `503` status implies that the server is temporarily unable to handle the request due to overloading or maintenance. A critical misconfiguration (like a missing API key) could be interpreted as the service being "unavailable" to perform its function. This is a minor semantic point, and the current implementation is perfectly acceptable.
