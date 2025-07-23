"""
Core Pydantic models for Reddit comment analysis API.
Enhanced with conversation context and thread analysis support.
"""

from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional, Literal
from datetime import datetime

from app.core.config import get_settings


def get_default_system_prompt() -> str:
    """Get default system prompt from settings."""
    return get_settings().default_system_prompt


def get_default_analysis_model() -> str:
    """Get default analysis model from settings."""
    return get_settings().default_analysis_model


def get_default_subreddit_sort() -> str:
    """Get default subreddit sort method from settings."""
    return get_settings().default_subreddit_sort


def get_default_subreddit_time() -> str:
    """Get default subreddit time filter from settings."""
    return get_settings().default_subreddit_time


def get_default_search_sort() -> str:
    """Get default search sort method from settings."""
    return get_settings().default_search_sort


def get_default_search_time() -> str:
    """Get default search time filter from settings."""
    return get_settings().default_search_time


def get_default_request_limit() -> int:
    """Get default request limit from settings."""
    return get_settings().default_request_limit


# Enum-like type definitions for validation (Improvement #3)
SortMethod = Literal["hot", "new", "top", "controversial", "rising"]
TimeFilter = Literal["hour", "day", "week", "month", "year", "all"]
SearchSortMethod = Literal["relevance", "hot", "top", "new", "comments"]
SentimentType = Literal["positive", "negative", "neutral"]
ThemeType = str  # Keep as string for flexibility since themes are dynamic
PurchaseIntentType = Literal["high", "medium", "low", "none"]


class CommentAnalysis(BaseModel):
    """Enhanced model for individual comment analysis with conversation context."""

    # Core analysis fields
    post_id: str
    post_url: str = Field(description="URL to original Reddit post for verification")
    quote: str = Field(description="Comment text content", max_length=1000)
    sentiment: SentimentType = Field(description="Sentiment: positive, negative, neutral")
    theme: ThemeType = Field(description="Main theme or topic discussed")
    purchase_intent: PurchaseIntentType = Field(description="Purchase intent: high, medium, low, none")
    date: datetime
    source: str = Field(default="reddit", description="Data source platform")
    
    # Enhanced context fields (optional for backward compatibility)
    parent_comment_id: Optional[str] = Field(
        default=None, 
        description="ID of parent comment this responds to"
    )
    thread_depth: Optional[int] = Field(
        default=None, 
        description="Depth level in conversation thread (0=top-level)"
    )
    thread_position: Optional[int] = Field(
        default=None,
        description="Position within thread siblings"
    )
    children_count: Optional[int] = Field(
        default=None,
        description="Number of direct replies to this comment"
    )
    conversation_context: Optional[str] = Field(
        default=None,
        description="What this comment is responding to (parent context)",
        max_length=200
    )
    thread_context: Optional[str] = Field(
        default=None,
        description="Summary of conversation flow leading to this comment",
        max_length=300
    )
    confidence_score: Optional[float] = Field(
        default=None,
        description="AI analysis confidence (0.0-1.0)",
        ge=0.0,
        le=1.0
    )
    conversation_quality: Optional[float] = Field(
        default=None,
        description="Thread conversation quality score (0.0-1.0)",
        ge=0.0,
        le=1.0
    )

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


class PostWithComments(BaseModel):
    """Model for Reddit post with its comments."""

    post_id: str = Field(description="Unique identifier for the post")
    post_title: str = Field(description="Title of the Reddit post")
    post_content: str = Field(description="Post content/description")
    post_url: str = Field(description="URL to the original Reddit post")
    post_date: datetime = Field(description="When the post was created")
    subreddit: str = Field(description="Subreddit where the post is located")
    comments: List[Dict[str, Any]] = Field(description="List of comments on the post")


class AnalysisContext(BaseModel):
    """Context configuration for AI analysis."""
    
    system_prompt: str = Field(
        default_factory=get_default_system_prompt,
        description="System prompt for AI analysis"
    )
    max_comments_per_post: int = Field(
        default=50, 
        description="Maximum number of comments to analyze per post"
    )


class SubredditAnalysisRequest(BaseModel):
    """Request model for subreddit analysis."""

    subreddit: str = Field(description="Target subreddit name (without r/)")
    sort: SortMethod = Field(default_factory=get_default_subreddit_sort, description="Sort method: hot, new, top, controversial, rising")
    time: TimeFilter = Field(default_factory=get_default_subreddit_time, description="Time filter: hour, day, week, month, year")
    limit: int = Field(default_factory=get_default_request_limit, description="Number of posts to collect", ge=1, le=100)
    model: str = Field(
        default_factory=get_default_analysis_model,
        description="AI model to use for analysis"
    )
    system_prompt: str = Field(
        default_factory=get_default_system_prompt,
        description="Custom system prompt for AI analysis"
    )


class SearchAnalysisRequest(BaseModel):
    """Request model for search analysis."""

    query: str = Field(description="Search query for Reddit posts")
    sort: SearchSortMethod = Field(default_factory=get_default_search_sort, description="Sort method: relevance, hot, top, new, comments")
    time: TimeFilter = Field(default_factory=get_default_search_time, description="Time filter: hour, day, week, month, year, all")
    limit: int = Field(default_factory=get_default_request_limit, description="Number of posts to collect", ge=1, le=100)
    nsfw: bool = Field(default=False, description="Include NSFW content")
    model: str = Field(
        default_factory=get_default_analysis_model,
        description="AI model to use for analysis"
    )
    system_prompt: str = Field(
        default_factory=get_default_system_prompt,
        description="Custom system prompt for AI analysis"
    )


class ConfigurableAnalysisRequest(BaseModel):
    """Legacy model for configurable analysis requests."""

    keywords: List[str] = Field(description="Keywords to search for")
    subreddits: List[str] = Field(description="List of subreddits to search")
    timeframe: TimeFilter = Field(default_factory=get_default_subreddit_time, description="Time period: hour, day, week, month, year")
    limit: int = Field(default_factory=get_default_request_limit, description="Number of posts per subreddit", ge=1, le=100)
    model: str = Field(
        default_factory=get_default_analysis_model,
        description="AI model for analysis"
    )
    system_prompt: str = Field(
        default_factory=get_default_system_prompt,
        description="System prompt for AI model"
    )


class AnalysisMetadata(BaseModel):
    """Enhanced metadata for analysis results with conversation insights."""

    total_posts_analyzed: int = Field(description="Number of posts processed")
    total_comments_found: int = Field(description="Total comments discovered")
    relevant_comments_extracted: int = Field(description="Comments selected for analysis")
    irrelevant_posts: int = Field(description="Posts without relevant comments")
    analysis_timestamp: datetime = Field(description="When analysis was completed")
    processing_time_seconds: float = Field(description="Total processing time")
    model_used: str = Field(description="AI model used for analysis")
    api_calls_made: int = Field(description="Number of API calls executed")
    collection_method: str = Field(description="Data collection method used")
    
    # Error tracking
    cell_parsing_errors: Optional[int] = Field(
        default=None,
        description="Number of cell parsing errors encountered"
    )
    data_extraction_errors: Optional[int] = Field(
        default=None,
        description="Number of data extraction errors"
    )
    ai_analysis_errors: Optional[int] = Field(
        default=None,
        description="Number of AI analysis errors"
    )

    # Enhanced thread analysis metrics (optional)
    max_thread_depth: Optional[int] = Field(
        default=None,
        description="Maximum conversation thread depth found"
    )
    total_threaded_comments: Optional[int] = Field(
        default=None,
        description="Total comments including all thread levels"
    )
    average_thread_depth: Optional[float] = Field(
        default=None,
        description="Average depth of comment threads"
    )
    conversation_threads_analyzed: Optional[int] = Field(
        default=None,
        description="Number of conversation threads processed"
    )
    thread_insights_generated: Optional[int] = Field(
        default=None,
        description="Number of conversation flow insights generated"
    )
    average_conversation_quality: Optional[float] = Field(
        default=None,
        description="Average conversation quality score (0.0-1.0)",
        ge=0.0,
        le=1.0
    )
    json_context_analysis_used: Optional[bool] = Field(
        default=None,
        description="Whether enhanced JSON context analysis was used"
    )

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


class UnifiedAnalysisResponse(BaseModel):
    """Model for unified analysis response."""

    comment_analyses: List[CommentAnalysis]
    metadata: AnalysisMetadata


# Background Job Models

class JobSubmissionResponse(BaseModel):
    """Response model for job submission."""
    
    job_id: str = Field(description="Unique identifier for the submitted job")
    status: str = Field(description="Current job status")
    message: str = Field(description="Human-readable status message")
    estimated_completion_time: Optional[str] = Field(
        default=None,
        description="Estimated completion time (ISO format)"
    )
    status_url: str = Field(description="URL to check job status")
    created_at: str = Field(description="Job creation timestamp (ISO format)")


class JobStatusResponse(BaseModel):
    """Response model for job status queries."""
    
    job_id: str = Field(description="Job identifier")
    status: str = Field(description="Current job status: pending, running, completed, failed, cancelled")
    created_at: str = Field(description="Job creation timestamp (ISO format)")
    started_at: Optional[str] = Field(default=None, description="Job start timestamp (ISO format)")
    completed_at: Optional[str] = Field(default=None, description="Job completion timestamp (ISO format)")
    processing_time: Optional[float] = Field(default=None, description="Processing time in seconds")
    progress: float = Field(description="Progress percentage (0-100)")
    progress_message: str = Field(description="Current progress description")
    result: Optional[UnifiedAnalysisResponse] = Field(default=None, description="Analysis results (if completed)")
    error: Optional[str] = Field(default=None, description="Error message (if failed)")
    error_details: Optional[Dict[str, Any]] = Field(default=None, description="Detailed error information")


class JobQueueStatsResponse(BaseModel):
    """Response model for job queue statistics."""
    
    total_jobs: int = Field(description="Total jobs in the system")
    running_jobs: int = Field(description="Currently running jobs")
    available_slots: int = Field(description="Available job execution slots")
    max_concurrent_jobs: int = Field(description="Maximum concurrent jobs allowed")
    status_breakdown: Dict[str, int] = Field(description="Count of jobs by status")
    result_ttl_hours: float = Field(description="Hours that job results are retained")
 