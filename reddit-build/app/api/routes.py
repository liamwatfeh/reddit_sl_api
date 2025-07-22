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
    """
    logger.info(f"[{job_id}] Starting subreddit analysis: r/{request.subreddit}")
    
    try:
        # Phase 1: Data Collection (20% progress)
        await update_job_progress(job_id, 20.0, f"Collecting posts from r/{request.subreddit}")
        
        async with SubredditDataCollector() as collector:
            posts, collection_metadata = await collector.collect_subreddit_posts(request)
            
            logger.info(f"[{job_id}] Collected {len(posts)} posts from r/{request.subreddit}")
            logger.info(f"[{job_id}] Total comments found: {sum(len(post['comments']) for post in posts)}")

        # Phase 2: AI Analysis (20% -> 90% progress)
        await update_job_progress(job_id, 40.0, "Starting AI analysis pipeline")
        
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

    except Exception as e:
        logger.error(f"[{job_id}] Error in subreddit analysis: {str(e)}", exc_info=True)
        raise


async def _background_search_analysis(job_id: str, request: SearchAnalysisRequest) -> UnifiedAnalysisResponse:
    """
    Background function for search analysis.
    
    Args:
        job_id: Job identifier for progress tracking
        request: Search analysis configuration
        
    Returns:
        UnifiedAnalysisResponse: Analysis results
    """
    logger.info(f"[{job_id}] Starting search analysis: {request.query}")
    
    try:
        # Phase 1: Data Collection (20% progress)
        await update_job_progress(job_id, 20.0, f"Searching Reddit for: {request.query}")
        
        async with SearchDataCollector() as collector:
            posts, collection_metadata = await collector.collect_search_posts(request)
            
            logger.info(f"[{job_id}] Found {len(posts)} posts for query: {request.query}")
            logger.info(f"[{job_id}] Total comments found: {sum(len(post['comments']) for post in posts)}")

        # Phase 2: AI Analysis (20% -> 90% progress)
        await update_job_progress(job_id, 40.0, "Starting AI analysis pipeline")
        
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

    except Exception as e:
        logger.error(f"[{job_id}] Error in search analysis: {str(e)}", exc_info=True)
        raise


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
    """
    logger.info(f"Subreddit analysis job submitted: r/{request.subreddit}")

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
    """
    logger.info(f"Search analysis job submitted: {request.query}")

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
    """
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
    """
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
    """
    job_queue = get_job_queue()
    stats = job_queue.get_queue_stats()
    
    return JobQueueStatsResponse(**stats)


# Legacy Synchronous Endpoint (Deprecated)

@router.post("/analyze-reddit-comments", response_model=UnifiedAnalysisResponse, dependencies=[Depends(verify_internal_api_key)])
async def analyze_reddit_comments_legacy(
    request: ConfigurableAnalysisRequest, background_tasks: BackgroundTasks
) -> UnifiedAnalysisResponse:
    """
    DEPRECATED: Legacy synchronous endpoint for analyzing Reddit comments.
    
    WARNING: This endpoint processes requests synchronously and may timeout
    for large requests. Use /analyze-subreddit or /analyze-search instead.

    Args:
        request: Configuration for the analysis including keywords, model, etc.
        background_tasks: FastAPI background tasks for async processing

    Returns:
        UnifiedAnalysisResponse: Structured analysis results
    """
    logger.warning("Legacy synchronous endpoint accessed - consider using async endpoints")
    logger.info(f"Legacy analysis request received: {request.keywords} in {request.subreddits}")

    # Validate request
    if not request.keywords:
        raise HTTPException(
            status_code=400, detail="At least one keyword is required"
        )

    if not request.subreddits:
        raise HTTPException(
            status_code=400, detail="At least one subreddit is required"
        )

    start_time = datetime.now()
    all_comments = []
    total_posts = 0
    total_comments_found = 0
    api_calls_made = 0
    cell_parsing_errors = 0

    # Collect posts from each subreddit using the SubredditDataCollector
    for subreddit in request.subreddits:
        logger.info(f"Processing subreddit r/{subreddit}")
        
        # Create subreddit request
        subreddit_request = SubredditAnalysisRequest(
            subreddit=subreddit,
            sort="hot",
            time=request.timeframe,
            limit=request.limit,
            model=request.model,
            system_prompt=request.system_prompt
        )
        
        async with SubredditDataCollector() as collector:
            posts, metadata = await collector.collect_subreddit_posts(subreddit_request)
            
            api_calls_made += metadata.get("api_calls_made", 0)
            cell_parsing_errors += metadata.get("cell_parsing_errors", 0)
            
            total_posts += len(posts)
            
            # Count total comments
            for post in posts:
                total_comments_found += len(post["comments"])
            
            # Analyze comments using AI
            orchestrator = ModernConcurrentCommentAnalysisOrchestrator(max_concurrent_agents=settings.max_concurrent_agents)
            analysis_results = await orchestrator.analyze_multiple_posts(posts, subreddit_request)
            
            # Collect all analyzed comments
            for result in analysis_results:
                all_comments.extend(result.analyzed_comments)

    processing_time = (datetime.now() - start_time).total_seconds()

    # Create response metadata
    metadata = AnalysisMetadata(
        total_posts_analyzed=total_posts,
        total_comments_found=total_comments_found,
        relevant_comments_extracted=len(all_comments),
        irrelevant_posts=max(0, total_posts - len(all_comments)),
        analysis_timestamp=datetime.now(),
        processing_time_seconds=processing_time,
        model_used=request.model,
        api_calls_made=api_calls_made,
        collection_method="subreddit",
        cell_parsing_errors=cell_parsing_errors
    )

    response = UnifiedAnalysisResponse(
        comment_analyses=all_comments, 
        metadata=metadata
    )

    logger.info(
        f"Legacy analysis completed: {len(all_comments)} comments analyzed from {total_posts} posts"
    )
    return response


@router.get("/status", dependencies=[Depends(verify_internal_api_key)])
async def api_status() -> Dict[str, Any]:
    """
    Detailed API status endpoint with configuration information.
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
        "supported_models": ["gpt-4.1-2025-04-14", "gpt-4", "claude-3-sonnet"],
        "supported_endpoints": [
            "/analyze-subreddit",  # New async endpoint
            "/analyze-search",     # New async endpoint
            "/jobs/{job_id}/status",
            "/jobs/{job_id}",
            "/jobs/queue/stats", 
            "/analyze-reddit-comments",  # Legacy sync endpoint
            "/health",
            "/status"
        ],
        "configuration": {
            "max_concurrent_agents": settings.max_concurrent_agents,
            "log_level": settings.log_level,
            "debug_mode": settings.debug,
        },
        "api_keys_configured": {
            "rapid_api": bool(settings.rapid_api_key),
            "openai_api": bool(settings.openai_api_key),
        },
        "job_queue": queue_stats
    }
 