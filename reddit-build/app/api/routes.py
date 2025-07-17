"""
API routes for Reddit Comment Analysis API.
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks
import asyncio
from datetime import datetime
from typing import Dict, Any, List

from ..core.logging import get_logger
from ..core.config import get_settings
from ..models.schemas import (
    ConfigurableAnalysisRequest,
    UnifiedAnalysisResponse,
    CommentAnalysis,
    SubredditAnalysisRequest,
    SearchAnalysisRequest,
    AnalysisMetadata,
    PostWithComments,
)
from ..services.reddit_collector import SubredditDataCollector, SearchDataCollector
from ..agents.comment_analyzer import get_comment_analyzer, AnalysisContext

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


@router.post("/analyze-reddit-comments", response_model=UnifiedAnalysisResponse)
async def analyze_reddit_comments(
    request: ConfigurableAnalysisRequest, background_tasks: BackgroundTasks
) -> UnifiedAnalysisResponse:
    """
    Legacy endpoint for analyzing Reddit comments based on configurable parameters.
    This endpoint collects posts from multiple subreddits and analyzes comments.

    Args:
        request: Configuration for the analysis including keywords, model, etc.
        background_tasks: FastAPI background tasks for async processing

    Returns:
        UnifiedAnalysisResponse: Structured analysis results
    """
    logger.info(
        f"Legacy analysis request received: {request.keywords} in {request.subreddits}"
    )

    try:
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

        # Initialize services
        analyzer = get_comment_analyzer()
        
        # Collect posts from each subreddit using the SubredditDataCollector
        for subreddit in request.subreddits:
            try:
                logger.info(f"Collecting posts from r/{subreddit}")
                
                # Create subreddit request
                subreddit_request = SubredditAnalysisRequest(
                    subreddit=subreddit,
                    sort="hot",
                    time=request.timeframe,
                    limit=request.limit,
                    model=request.model,
                    api_key=request.api_key,  # Will be ignored in processing
                    system_prompt=request.system_prompt
                )
                
                async with SubredditDataCollector() as collector:
                    posts, metadata = await collector.collect_subreddit_posts(subreddit_request)
                    
                    api_calls_made += metadata.get("api_calls_made", 0)
                    cell_parsing_errors += metadata.get("cell_parsing_errors", 0)
                    
                    total_posts += len(posts)
                    
                    # Count total comments
                    for post in posts:
                        total_comments_found += len(post.comments)
                    
                    # Analyze comments using AI
                    # Note: We ignore the api_key from the request and use environment variables
                    context = AnalysisContext(
                        keywords=request.keywords,
                        system_prompt=request.system_prompt,
                        max_comments_per_post=50
                    )
                    
                    analysis_results = await analyzer.analyze_multiple_posts(posts, context)
                    
                    # Collect all analyzed comments
                    for result in analysis_results:
                        all_comments.extend(result.analyzed_comments)
                        
            except Exception as e:
                logger.error(f"Error processing subreddit {subreddit}: {e}")
                continue

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

    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"Error processing legacy analysis request: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Analysis processing failed: {str(e)}"
        )


@router.post("/analyze-subreddit", response_model=UnifiedAnalysisResponse)
async def analyze_subreddit(
    request: SubredditAnalysisRequest, background_tasks: BackgroundTasks
) -> UnifiedAnalysisResponse:
    """
    Analyze Reddit comments from a specific subreddit with AI-powered insights.

    This endpoint:
    1. Collects posts from the specified subreddit
    2. Extracts and cleans comments from those posts
    3. Uses AI to analyze each comment for sentiment, theme, and purchase intent
    4. Returns structured analysis results

    Args:
        request: Subreddit analysis configuration
        background_tasks: FastAPI background tasks for async processing

    Returns:
        UnifiedAnalysisResponse: Comprehensive analysis results with metadata
    """
    logger.info(f"Subreddit analysis request: r/{request.subreddit}")

    try:
        start_time = datetime.now()
        
        # Initialize services
        analyzer = get_comment_analyzer()
        
        async with SubredditDataCollector() as collector:
            # Collect posts from subreddit
            logger.info(f"Collecting posts from r/{request.subreddit}")
            
            posts, metadata = await collector.collect_subreddit_posts(request)
            
            api_calls_made = metadata.get("api_calls_made", 0)
            cell_parsing_errors = metadata.get("cell_parsing_errors", 0)
            
            logger.info(f"Collected {len(posts)} posts from r/{request.subreddit}")
            
            # Count total comments
            total_comments_found = sum(len(post.comments) for post in posts)
            
            # Analyze comments using AI
            # Note: We ignore the api_key from the request and use environment variables
            context = AnalysisContext(
                keywords=[request.subreddit],  # Use subreddit name as context
                system_prompt=request.system_prompt,
                max_comments_per_post=50
            )
            
            analysis_results = await analyzer.analyze_multiple_posts(posts, context)
            
            # Collect all analyzed comments
            all_comments = []
            for result in analysis_results:
                all_comments.extend(result.analyzed_comments)

        processing_time = (datetime.now() - start_time).total_seconds()

        # Create response metadata
        response_metadata = AnalysisMetadata(
            total_posts_analyzed=len(posts),
            total_comments_found=total_comments_found,
            relevant_comments_extracted=len(all_comments),
            irrelevant_posts=max(0, len(posts) - len([r for r in analysis_results if r.analyzed_comments])),
            analysis_timestamp=datetime.now(),
            processing_time_seconds=processing_time,
            model_used=request.model,
            api_calls_made=api_calls_made,
            collection_method="subreddit",
            cell_parsing_errors=cell_parsing_errors
        )

        response = UnifiedAnalysisResponse(
            comment_analyses=all_comments, 
            metadata=response_metadata
        )

        logger.info(
            f"Subreddit analysis completed: {len(all_comments)} comments analyzed from {len(posts)} posts"
        )
        return response

    except Exception as e:
        logger.error(f"Error processing subreddit analysis: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Subreddit analysis failed: {str(e)}"
        )


@router.post("/analyze-search", response_model=UnifiedAnalysisResponse)
async def analyze_search(
    request: SearchAnalysisRequest, background_tasks: BackgroundTasks
) -> UnifiedAnalysisResponse:
    """
    Analyze Reddit comments from search results with AI-powered insights.

    This endpoint:
    1. Searches Reddit for posts matching the query
    2. Extracts and cleans comments from those posts
    3. Uses AI to analyze each comment for sentiment, theme, and purchase intent
    4. Returns structured analysis results

    Args:
        request: Search analysis configuration
        background_tasks: FastAPI background tasks for async processing

    Returns:
        UnifiedAnalysisResponse: Comprehensive analysis results with metadata
    """
    logger.info(f"Search analysis request: {request.query}")

    try:
        start_time = datetime.now()
        
        # Initialize services
        analyzer = get_comment_analyzer()
        
        async with SearchDataCollector() as collector:
            # Search for posts
            logger.info(f"Searching Reddit for: {request.query}")
            
            posts, metadata = await collector.collect_search_posts(request)
            
            api_calls_made = metadata.get("api_calls_made", 0)
            
            logger.info(f"Found {len(posts)} posts for query: {request.query}")
            
            # Count total comments
            total_comments_found = sum(len(post.comments) for post in posts)
            
            # Analyze comments using AI
            # Note: We ignore the api_key from the request and use environment variables
            context = AnalysisContext(
                keywords=[request.query],
                system_prompt=request.system_prompt,
                max_comments_per_post=50
            )
            
            analysis_results = await analyzer.analyze_multiple_posts(posts, context)
            
            # Collect all analyzed comments
            all_comments = []
            for result in analysis_results:
                all_comments.extend(result.analyzed_comments)

        processing_time = (datetime.now() - start_time).total_seconds()

        # Create response metadata
        response_metadata = AnalysisMetadata(
            total_posts_analyzed=len(posts),
            total_comments_found=total_comments_found,
            relevant_comments_extracted=len(all_comments),
            irrelevant_posts=max(0, len(posts) - len([r for r in analysis_results if r.analyzed_comments])),
            analysis_timestamp=datetime.now(),
            processing_time_seconds=processing_time,
            model_used=request.model,
            api_calls_made=api_calls_made,
            collection_method="search",
            cell_parsing_errors=0  # Search endpoint doesn't use cell structure
        )

        response = UnifiedAnalysisResponse(
            comment_analyses=all_comments, 
            metadata=response_metadata
        )

        logger.info(
            f"Search analysis completed: {len(all_comments)} comments analyzed from {len(posts)} posts"
        )
        return response

    except Exception as e:
        logger.error(f"Error processing search analysis: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Search analysis failed: {str(e)}"
        )


@router.get("/status")
async def api_status() -> Dict[str, Any]:
    """
    Detailed API status endpoint with configuration information.
    """
    logger.info("Status endpoint accessed")

    return {
        "api_status": "operational",
        "version": settings.app_version,
        "analysis_capabilities": {
            "sentiment_analysis": True,
            "theme_extraction": True,
            "purchase_intent_detection": True,
            "multi_model_support": True,
        },
        "supported_models": ["gpt-4.1-2025-04-14", "gpt-4", "claude-3-sonnet"],
        "supported_endpoints": [
            "/analyze-reddit-comments",
            "/analyze-subreddit", 
            "/analyze-search",
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
            "gemini_api": bool(settings.gemini_api_key),
            "openai_api": bool(settings.openai_api_key),
        },
    }
