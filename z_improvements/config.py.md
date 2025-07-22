# Improvements for config.py

This document outlines potential production-readiness improvements for the `reddit-build/app/core/config.py` file, listed in order of priority.

### 1. Remove Insecure Default for `internal_api_key` (High Priority)

- **Issue**: The `internal_api_key` has a default value of `"dev-change-this-key"`. If the application is deployed without this environment variable being set, it will run with a known, insecure key.
- **Improvement**: Make this field mandatory by removing the default value. Change the definition to `internal_api_key: str`. This will cause the application to fail at startup if the key isn't provided, which is a much safer "fail-fast" security posture.

### 2. Enforce Presence of Critical API Keys

- **Issue**: The `rapid_api_key` and `openai_api_key` are defined as `Optional[str]` with a default of `None`. The application cannot function without them, but it will start up successfully and only crash at runtime when an API call is attempted.
- **Improvement**: These fields should be non-optional. Change their definitions to `rapid_api_key: str` and `openai_api_key: str`. This ensures the application verifies that all necessary secrets are present at startup.

### 3. Refine Singleton Implementation

- **Issue**: The current singleton pattern using a global `_settings` variable is functional but can be implemented more elegantly and robustly.
- **Improvement**: Use Python's built-in `lru_cache` decorator from the `functools` module. Applying `@lru_cache(maxsize=1)` or simply `@lru_cache` to the `get_settings` function achieves the same result with less code and is guaranteed to be thread-safe.

### 4. Remove Unused Configuration

- **Issue**: The `gemini_api_key` setting is defined but does not appear to be used anywhere in the current codebase.
- **Improvement**: If this key is a remnant from a past feature or experiment, it should be removed to keep the configuration clean and reduce cognitive overhead for developers. If it is for a planned future feature, it can be kept but should ideally be documented as such.
