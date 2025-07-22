# Improvements for schemas.py

This document outlines potential production-readiness improvements for the `reddit-build/app/models/schemas.py` file. The current implementation is well-structured and comprehensive, but these enhancements would make it more robust and maintainable.

### 1. Externalize Hardcoded Default Values

- **Issue**: Both `SubredditAnalysisRequest` and `SearchAnalysisRequest` have hardcoded default values for `model` (`"gpt-4.1-2025-04-14"`) and system prompts. This requires code deployment to change these values.
- **Improvement**: Use Pydantic's `Field(default_factory=...)` with functions that read from configuration settings, or document that these fields should be explicitly provided by clients. This allows for environment-specific defaults and easier updates.

### 2. Standardize System Prompts Across Models

- **Issue**: `ConfigurableAnalysisRequest` has a truncated system prompt (`"You are an expert social media analyst..."`), while `SubredditAnalysisRequest` and `SearchAnalysisRequest` have complete, detailed prompts. This inconsistency could lead to different analysis quality.
- **Improvement**: Standardize all system prompts by referencing a single source of truth, ideally from the configuration file. This ensures consistent analysis behavior across all endpoints.

### 3. Add Validation for Enum-like Fields

- **Issue**: Fields like `sort`, `time`, `sentiment`, `theme`, and `purchase_intent` accept any string value, but only specific values are valid (e.g., `sort` should be one of `["hot", "new", "top", "controversial", "rising"]`).
- **Improvement**: Use Pydantic's `Enum` support or `Literal` types to restrict these fields to valid values:
  ```python
  from typing import Literal
  sort: Literal["hot", "new", "top", "controversial", "rising"] = "hot"
  ```
  This prevents client errors and improves API documentation.

### 4. Define Proper Comment Model Structure

- **Issue**: In `PostWithComments`, the `comments` field is typed as `List[Dict[str, Any]]`, which provides no guidance about the expected comment structure.
- **Improvement**: Create a dedicated `Comment` model that specifies the expected fields (id, text, author, score, children, depth, etc.). This improves type safety and makes the code more self-documenting:
  ```python
  class Comment(BaseModel):
      id: str
      text: str
      author: str
      score: int
      depth: int
      children: List['Comment'] = []
  ```

### 5. Add Limits to Prevent Large Payloads

- **Issue**: There are no size limits on lists like `keywords`, `subreddits`, or response arrays. Malicious or misconfigured clients could send requests with thousands of items, potentially overwhelming the system.
- **Improvement**: Add reasonable limits using Pydantic validation:
  ```python
  keywords: List[str] = Field(..., max_items=50)
  subreddits: List[str] = Field(..., max_items=20)
  ```

### 6. Review Legacy ConfigurableAnalysisRequest

- **Issue**: The `ConfigurableAnalysisRequest` model appears to be a legacy remnant with an incomplete system prompt and may not be actively used.
- **Improvement**: If this model is no longer used, remove it to reduce maintenance overhead. If it's still needed, bring it up to the same standard as the other request models with proper defaults and complete prompts.
