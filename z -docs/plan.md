# 📋 Current State Summary

- ✅ **Complete:** FastAPI infrastructure, data models, configuration, logging, basic endpoints  
- ❌ **Missing:** Reddit data collection, AI analysis, comment processing  
- 🎯 **Goal:** Implement both `/analyze-subreddit` and `/analyze-search` endpoints with full functionality

---

# 🏗️ Implementation Plan (10 Incremental Steps)

## PHASE 1: Foundation Services (Steps 1–3)

### Step 1: Environment Configuration & Dependencies
- **Estimated Time:** 30 minutes  
- **Tasks:**
  - Add missing dependencies for Reddit API integration
  - Create environment configuration for RapidAPI
  - Update `requirements.txt` with new packages
- **Files to Create/Modify:**
  - `requirements.txt` (update)
  - `.env` file in `reddit-build/`
  - `app/core/config.py` (update)
- **Implementation:**
  - Apply to `.env`
  - Run
  - `asyncio`
- **Deliverable:** Environment ready for Reddit API integration

---

### Step 2: Request/Response Schema Updates
- **Estimated Time:** 45 minutes  
- **Tasks:**
  - Add two new request schemas from documentation
  - Update metadata schema to match documentation
  - Ensure proper schema validation
- **Files to Create/Modify:**
  - `app/models/schemas.py` — Add `SubredditAnalysisRequest`, `SearchAnalysisRequest`
  - Update `UnifiedAnalysisResponse` metadata field
- **Implementation:**  
  - Add missing schemas as documented
- **Deliverable:** Complete request/response schemas for both endpoints

---

### Step 3: Reddit Data Extraction Functions
- **Estimated Time:** 1.5 hours  
- **Tasks:**
  - Create cell parsing functions for subreddit/search responses
  - Create flat object processing for posts/search-posts responses
  - Add data validation and error handling
- **Files to Create:**
  - `app/services/cell_extractors.py` — Cell-based data extraction
  - `app/services/search_extractors.py` — Flat object extraction
  - `app/services/data_cleaners.py` — Post and comment cleaning functions
- **Implementation:**  
  - All extraction functions per documentation, including:
    - `extract_posts_from_reddit_response()`
    - `extract_post_from_cells()`
    - `extract_posts_from_search_response()`
    - `clean_reddit_post_updated()`
    - `clean_posts_comments_response()`
- **Deliverable:** Complete data extraction and cleaning pipeline

---

## PHASE 2: Reddit Data Collection (Steps 4–5)

### Step 4: Base Reddit Data Collector
- **Estimated Time:** 2 hours  
- **Tasks:**
  - Implement base collector class with RapidAPI integration
  - Add HTTP client configuration and authentication
  - Implement comment fetching and pagination logic
- **Files to Create/Modify:**
  - `app/services/reddit_collector.py` — Base collector implementation
- **Implementation:**
  - `BaseRedditDataCollector` class with RapidAPI setup
  - `fetch_comment_tree()` method for comment collection
  - `paginate_posts()` for pagination
  - Proper HTTP client management and error handling
- **Deliverable:** Working base collector (auth + pagination)

---

### Step 5: Specialized Data Collectors
- **Estimated Time:** 2.5 hours  
- **Tasks:**
  - Implement `SubredditDataCollector` for cell-based processing
  - Implement `SearchDataCollector` for flat object processing
  - Add endpoint-specific data collection logic
- **Files to Modify:**
  - `app/services/reddit_collector.py` — Add specialized collectors
- **Implementation:**
  - `SubredditDataCollector.collect_subreddit_posts()`
  - `SearchDataCollector.collect_search_posts()`
  - Both collectors using their respective extraction methods
  - Complete post + comment collection for each post
- **Deliverable:** Working Reddit data collection for both endpoints

---

## PHASE 3: AI Analysis Engine (Steps 6–7)

### Step 6: Comment Filtering AI Agent
- **Estimated Time:** 2 hours  
- **Tasks:**
  - Implement Pydantic AI agent for comment analysis
  - Add comment filtering and quote extraction logic
  - Configure multiple AI model support (Gemini, OpenAI)
- **Files to Create/Modify:**
  - `app/agents/comment_analyzer.py` — AI agent implementation
- **Implementation:**
  - `CommentFilteringAgent` class with Pydantic AI
  - `analyze_post_for_comments()` method
  - Prompt building and response processing
  - Quote truncation and metadata assignment
- **Deliverable:** Working AI agent that analyzes individual posts

---

### Step 7: Orchestration and Result Processing
- **Estimated Time:** 1.5 hours  
- **Tasks:**
  - Implement concurrent analysis orchestrator
  - Add results stacking and metadata calculation
  - Create comprehensive response formatting
- **Files to Modify:**
  - `app/agents/comment_analyzer.py` — Add orchestrator and stacker
- **Implementation:**
  - `ConcurrentCommentAnalysisOrchestrator` for parallel processing
  - `ResultsStacker` for combining all analyses
  - Metadata calculation (processing time, API calls, etc.)
  - `UnifiedAnalysisResponse` construction
- **Deliverable:** Complete AI analysis pipeline with result aggregation

---

## PHASE 4: API Endpoints (Steps 8–9)

### Step 8: Implement Subreddit Analysis Endpoint
- **Estimated Time:** 1 hour  
- **Tasks:**
  - Replace placeholder with full subreddit analysis implementation
  - Connect all services: collector → AI → results
  - Add comprehensive error handling and logging
- **Files to Modify:**
  - `app/api/routes.py` — Replace `/analyze-reddit-comments`, add `/analyze-subreddit`
- **Implementation:**
  - Full subreddit analysis workflow
  - Proper request validation
  - Error handling for each phase
  - Detailed logging and timing
- **Deliverable:** Working `/analyze-subreddit` endpoint

---

### Step 9: Implement Search Analysis Endpoint
- **Estimated Time:** 1 hour  
- **Tasks:**
  - Add the new `/analyze-search` endpoint
  - Implement search-based analysis workflow
  - Ensure both endpoints work independently
- **Files to Modify:**
  - `app/api/routes.py` — Add `/analyze-search` endpoint
- **Implementation:**
  - Complete search analysis workflow
  - NSFW filtering support
  - Same error handling patterns as subreddit endpoint
  - Response format consistency
- **Deliverable:** Working `/analyze-search` endpoint

---

## PHASE 5: Production Ready (Step 10)

### Step 10: Testing, Error Handling & Documentation
- **Estimated Time:** 2 hours  
- **Tasks:**
  - Add comprehensive error handling middleware
  - Create test cases for both endpoints
  - Update API documentation and add example requests
  - Performance testing and optimization
- **Files to Create/Modify:**
  - `app/core/exceptions.py` — Custom exception classes
  - `app/main.py` — Error handling middleware
  - `tests/test_endpoints.py` — Endpoint testing
  - `tests/test_data_collection.py` — Data collection testing
  - Documentation updates
- **Implementation:**
  - All custom exceptions as documented
  - Exception handlers for processing phases
  - Integration tests for endpoints
  - Performance benchmarks
  - Updated README with usage examples
- **Deliverable:** Production-ready API with full testing coverage

---

# 📊 Implementation Summary

| Phase   | Steps | Estimated Time | Key Deliverables                        |
|---------|-------|----------------|-----------------------------------------|
| Phase 1 | 1–3   | 2.75 hours     | Environment setup, schemas, extraction  |
| Phase 2 | 4–5   | 4.5 hours      | Reddit data collection services         |
| Phase 3 | 6–7   | 3.5 hours      | AI analysis engine                      |
| Phase 4 | 8–9   | 2 hours        | Working API endpoints                   |
| Phase 5 | 10    | 2 hours        | Production readiness                    |
| **TOTAL** | **10 steps** | **~14.75 hours** | **Complete functional API**           |
