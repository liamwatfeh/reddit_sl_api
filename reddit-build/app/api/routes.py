"""
API routes for Reddit Comment Analysis API.
Enhanced with background job queue for production scalability.
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends, Request
from datetime import datetime, timedelta
from typing import Dict, Any, List

from app.core.logging import get_logger
from app.core.config import get_settings
from app.core.security import verify_internal_api_key
from app.core.exceptions import (
    RedditAPIException,
    DataExtractionException,
    AIAnalysisException,
    ValidationException,
    ConfigurationException,
)
from app.models.schemas import (
    ConfigurableAnalysisRequest,
    UnifiedAnalysisResponse,
    CommentAnalysis,
    SubredditAnalysisRequest,
    SearchAnalysisRequest,
    AnalysisMetadata,
    PostWithComments,
    JobSubmissionResponse,
    JobStatusResponse,
    JobQueueStatsResponse,
)
from app.services.reddit_collector import SubredditDataCollector, SearchDataCollector
from app.agents.modern_comment_analyzer import ModernConcurrentCommentAnalysisOrchestrator
from app.services.job_queue import get_job_queue, update_job_progress

# Initialize router, logger, and settings
router = APIRouter()
logger = get_logger(__name__)
settings = get_settings()


@router.get("/health")
async def health_check() -> Dict[str, Any]:
    """
    Health check endpoint that returns API status.
    """
    logger.info("Health check endpoint accessed")
    return {
        "status": "healthy",
        "version": "v2",
        "analysis_type": "comment_level",
        "service": "reddit-comment-analysis-api",
        "timestamp": datetime.now().isoformat(),
    }


# Background Job Functions

async def _background_subreddit_analysis(job_id: str, request: SubredditAnalysisRequest) -> UnifiedAnalysisResponse:
    """
    Background function for subreddit analysis.
    
    Args:
        job_id: Job identifier for progress tracking
        request: Subreddit analysis configuration
        
    Returns:
        UnifiedAnalysisResponse: Analysis results
        
    Raises:
        RedditAPIException: When Reddit API is unavailable or returns errors
        AIAnalysisException: When AI analysis fails
        DataExtractionException: When data extraction/parsing fails
    """
    logger.info(f"[{job_id}] Starting subreddit analysis: r/{request.subreddit}")
    
    # Phase 1: Data Collection (20% progress)
    await update_job_progress(job_id, 20.0, f"Collecting posts from r/{request.subreddit}")
    
    async with SubredditDataCollector() as collector:
        posts, collection_metadata = await collector.collect_subreddit_posts(request)
        
        logger.info(f"[{job_id}] Collected {len(posts)} posts from r/{request.subreddit}")
        logger.info(f"[{job_id}] Total comments found: {sum(len(post['comments']) for post in posts)}")

    # Phase 2: AI Analysis (20% -> 90% progress)
    await update_job_progress(job_id, 40.0, "Starting AI analysis pipeline")
    
    # Use externalized concurrency configuration (Point 3)
    orchestrator = ModernConcurrentCommentAnalysisOrchestrator(max_concurrent_agents=settings.max_concurrent_agents)
    response = await orchestrator.run_full_analysis(
        posts=posts,
        analysis_request=request,
        collection_metadata=collection_metadata
    )

    # Final progress update
    await update_job_progress(job_id, 95.0, "Finalizing results")
    
    logger.info(
        f"[{job_id}] Subreddit analysis completed: {len(response.comment_analyses)} relevant comments from {response.metadata.total_posts_analyzed} posts"
    )
    
    return response


async def _background_search_analysis(job_id: str, request: SearchAnalysisRequest) -> UnifiedAnalysisResponse:
    """
    Background function for search analysis.
    
    Args:
        job_id: Job identifier for progress tracking
        request: Search analysis configuration
        
    Returns:
        UnifiedAnalysisResponse: Analysis results
        
    Raises:
        RedditAPIException: When Reddit API is unavailable or returns errors
        AIAnalysisException: When AI analysis fails
        DataExtractionException: When data extraction/parsing fails
    """
    logger.info(f"[{job_id}] Starting search analysis: {request.query}")
    
    # Phase 1: Data Collection (20% progress)
    await update_job_progress(job_id, 20.0, f"Searching Reddit for: {request.query}")
    
    async with SearchDataCollector() as collector:
        posts, collection_metadata = await collector.collect_search_posts(request)
        
        logger.info(f"[{job_id}] Found {len(posts)} posts for query: {request.query}")
        logger.info(f"[{job_id}] Total comments found: {sum(len(post['comments']) for post in posts)}")

    # Phase 2: AI Analysis (20% -> 90% progress)
    await update_job_progress(job_id, 40.0, "Starting AI analysis pipeline")
    
    # Use externalized concurrency configuration (Point 3)
    orchestrator = ModernConcurrentCommentAnalysisOrchestrator(max_concurrent_agents=settings.max_concurrent_agents)
    response = await orchestrator.run_full_analysis(
        posts=posts,
        analysis_request=request,
        collection_metadata=collection_metadata
    )

    # Final progress update
    await update_job_progress(job_id, 95.0, "Finalizing results")
    
    logger.info(
        f"[{job_id}] Search analysis completed: {len(response.comment_analyses)} relevant comments from {response.metadata.total_posts_analyzed} posts"
    )
    
    return response


# New Async Endpoints

@router.post("/analyze-subreddit", response_model=JobSubmissionResponse, dependencies=[Depends(verify_internal_api_key)])
async def analyze_subreddit_async(
    request: SubredditAnalysisRequest,
    fastapi_request: Request
) -> JobSubmissionResponse:
    """
    Submit a subreddit analysis job for background processing.

    This endpoint immediately returns a job ID that can be used to track
    the analysis progress and retrieve results when complete.

    Args:
        request: Subreddit analysis configuration
        fastapi_request: FastAPI request object for URL construction

    Returns:
        JobSubmissionResponse: Job submission details with tracking information
        
    Raises:
        ValidationException: When request parameters are invalid
        ConfigurationException: When system configuration is invalid
    """
    logger.info(f"Subreddit analysis job submitted: r/{request.subreddit}")

    # Validate subreddit name
    if not request.subreddit or not request.subreddit.strip():
        raise ValidationException(
            "Subreddit name cannot be empty",
            field="subreddit"
        )

    job_queue = get_job_queue()
    job_id = await job_queue.submit_job(_background_subreddit_analysis, request)
    
    # Estimate completion time (rough estimate: 2-5 minutes for typical requests)
    estimated_time = datetime.now() + timedelta(minutes=3)
    
    # Construct status URL
    base_url = str(fastapi_request.url).replace(str(fastapi_request.url.path), "")
    status_url = f"{base_url}/jobs/{job_id}/status"

    return JobSubmissionResponse(
        job_id=job_id,
        status="pending",
        message=f"Subreddit analysis job for r/{request.subreddit} has been queued for processing",
        estimated_completion_time=estimated_time.isoformat(),
        status_url=status_url,
        created_at=datetime.now().isoformat()
    )


@router.post("/analyze-search", response_model=JobSubmissionResponse, dependencies=[Depends(verify_internal_api_key)])
async def analyze_search_async(
    request: SearchAnalysisRequest,
    fastapi_request: Request
) -> JobSubmissionResponse:
    """
    Submit a search analysis job for background processing.

    This endpoint immediately returns a job ID that can be used to track
    the analysis progress and retrieve results when complete.

    Args:
        request: Search analysis configuration
        fastapi_request: FastAPI request object for URL construction

    Returns:
        JobSubmissionResponse: Job submission details with tracking information
        
    Raises:
        ValidationException: When request parameters are invalid
        ConfigurationException: When system configuration is invalid
    """
    logger.info(f"Search analysis job submitted: {request.query}")

    # Validate search query
    if not request.query or not request.query.strip():
        raise ValidationException(
            "Search query cannot be empty",
            field="query"
        )

    job_queue = get_job_queue()
    job_id = await job_queue.submit_job(_background_search_analysis, request)
    
    # Estimate completion time (rough estimate: 2-5 minutes for typical requests)
    estimated_time = datetime.now() + timedelta(minutes=3)
    
    # Construct status URL
    base_url = str(fastapi_request.url).replace(str(fastapi_request.url.path), "")
    status_url = f"{base_url}/jobs/{job_id}/status"

    return JobSubmissionResponse(
        job_id=job_id,
        status="pending",
        message=f"Search analysis job for '{request.query}' has been queued for processing",
        estimated_completion_time=estimated_time.isoformat(),
        status_url=status_url,
        created_at=datetime.now().isoformat()
    )


# Job Status and Management Endpoints

@router.get("/jobs/{job_id}/status", response_model=JobStatusResponse, dependencies=[Depends(verify_internal_api_key)])
async def get_job_status(job_id: str) -> JobStatusResponse:
    """
    Get the current status and results of a background job.

    Args:
        job_id: Unique job identifier

    Returns:
        JobStatusResponse: Current job status and results (if completed)
        
    Raises:
        ValidationException: When job_id format is invalid
        HTTPException: When job is not found (404)
    """
    # Validate job ID format
    if not job_id or not job_id.strip():
        raise ValidationException(
            "Job ID cannot be empty",
            field="job_id"
        )

    job_queue = get_job_queue()
    job_result = job_queue.get_job_status(job_id)
    
    if not job_result:
        raise HTTPException(
            status_code=404,
            detail=f"Job {job_id} not found. It may have expired or never existed."
        )
    
    # Convert job result to response format
    response_data = job_result.to_dict()
    
    return JobStatusResponse(**response_data)


@router.delete("/jobs/{job_id}", dependencies=[Depends(verify_internal_api_key)])
async def cancel_job(job_id: str) -> Dict[str, Any]:
    """
    Cancel a running job.

    Args:
        job_id: Unique job identifier

    Returns:
        Cancellation status
        
    Raises:
        ValidationException: When job_id format is invalid
        HTTPException: When job is not found (404)
    """
    # Validate job ID format
    if not job_id or not job_id.strip():
        raise ValidationException(
            "Job ID cannot be empty",
            field="job_id"
        )

    job_queue = get_job_queue()
    
    # Check if job exists
    job_result = job_queue.get_job_status(job_id)
    if not job_result:
        raise HTTPException(
            status_code=404,
            detail=f"Job {job_id} not found"
        )
    
    # Attempt to cancel
    cancelled = job_queue.cancel_job(job_id)
    
    if cancelled:
        logger.info(f"Job {job_id} cancellation requested")
        return {
            "job_id": job_id,
            "message": "Job cancellation requested",
            "success": True
        }
    else:
        return {
            "job_id": job_id,
            "message": "Job could not be cancelled (may already be completed)",
            "success": False
        }


@router.get("/jobs/queue/stats", response_model=JobQueueStatsResponse, dependencies=[Depends(verify_internal_api_key)])
async def get_queue_stats() -> JobQueueStatsResponse:
    """
    Get statistics about the job queue.

    Returns:
        JobQueueStatsResponse: Current queue statistics
        
    Raises:
        ConfigurationException: When job queue is not properly configured
    """
    job_queue = get_job_queue()
    stats = job_queue.get_queue_stats()
    
    return JobQueueStatsResponse(**stats)


@router.get("/status", dependencies=[Depends(verify_internal_api_key)])
async def api_status() -> Dict[str, Any]:
    """
    Detailed API status endpoint with configuration information.
    
    Returns:
        Comprehensive API status and configuration details
        
    Raises:
        ConfigurationException: When configuration is invalid or incomplete
    """
    logger.info("Status endpoint accessed")

    # Get job queue stats
    job_queue = get_job_queue()
    queue_stats = job_queue.get_queue_stats()

    return {
        "api_status": "operational",
        "version": settings.app_version,
        "analysis_capabilities": {
            "sentiment_analysis": True,
            "theme_extraction": True,
            "purchase_intent_detection": True,
            "multi_model_support": True,
            "background_job_processing": True,
        },
        "supported_models": [
            settings.openai_model,
            settings.primary_ai_model,
            "gpt-4",
            "claude-3-sonnet"
        ],
        "supported_endpoints": [
            "/analyze-subreddit",     # Async endpoint
            "/analyze-search",        # Async endpoint
            "/jobs/{job_id}/status",  # Job status tracking
            "/jobs/{job_id}",         # Job cancellation
            "/jobs/queue/stats",      # Queue statistics
            "/health",                # Health check
            "/status"                 # API status
        ],
        "configuration": {
            "max_concurrent_agents": settings.max_concurrent_agents,
            "max_analysis_comments": settings.max_analysis_comments,
            "max_thread_depth": settings.max_thread_depth,
            "log_level": settings.log_level,
            "debug_mode": settings.debug,
            "openai_model": settings.openai_model,
            "openai_temperature": settings.openai_temperature,
            "openai_max_tokens": settings.openai_max_tokens,
        },
        "api_keys_configured": {
            "rapid_api": bool(settings.rapid_api_key),
            "openai_api": bool(settings.openai_api_key),
            "internal_api": bool(settings.internal_api_key),
        },
        "job_queue": queue_stats,
        "deprecation_notices": [
            "Legacy synchronous endpoints have been removed. Use async endpoints instead."
        ]
    }
 