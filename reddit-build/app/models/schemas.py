"""
Core Pydantic models for Reddit comment analysis API.
Enhanced with conversation context and thread analysis support.
"""

from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from datetime import datetime


class CommentAnalysis(BaseModel):
    """Enhanced model for individual comment analysis with conversation context."""

    # Core analysis fields
    post_id: str
    post_url: str = Field(description="URL to original Reddit post for verification")
    quote: str = Field(description="Comment text content", max_length=1000)
    sentiment: str = Field(description="Sentiment: positive, negative, neutral")
    theme: str = Field(description="Main theme or topic discussed")
    purchase_intent: str = Field(description="Purchase intent: high, medium, low, none")
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
    """Post with all its comments after cleaning"""

    post_id: str
    post_title: str
    post_content: str
    post_author: str
    post_score: int
    post_date: datetime
    subreddit: str
    permalink: str
    url: str
    comments: List[Dict[str, Any]]


class ConfigurableAnalysisRequest(BaseModel):
    """Model for configurable analysis request parameters."""

    keywords: List[str] = ["BMW R 12 GS"]
    subreddits: List[str] = ["motorcycles", "BMW"]
    timeframe: str = "week"
    limit: int = 10
    model: str = "gpt-4.1-2025-04-14"
    system_prompt: str = "You are an expert social media analyst..."
    output_format: str = "json"
    max_quote_length: int = 200


class SubredditAnalysisRequest(BaseModel):
    """Request schema for /analyze-subreddit endpoint"""
    # Subreddit browsing parameters
    subreddit: str  # e.g., "motorcycles", "BMW", "advrider"
    sort: str = "hot"  # "hot", "new", "top", "controversial", "rising"
    time: str = "week"  # "all", "year", "month", "week", "day", "hour"
    limit: int = 50  # Number of posts to analyze
    
    # Model configuration
    model: str = "gpt-4.1-2025-04-14"
    
    # Analysis configuration
    system_prompt: str = """You are an expert social media analyst specializing in Reddit comment analysis. Your task is to analyze Reddit discussions to identify insightful comments, understand sentiment patterns, and extract meaningful themes from user conversations."""
    
    # Output configuration
    output_format: str = "json"
    max_quote_length: int = 200


class SearchAnalysisRequest(BaseModel):
    """Request schema for /analyze-search endpoint"""
    # Search parameters
    query: str  # Search query, e.g., "BMW R 12 GS"
    sort: str = "relevance"  # "relevance", "hot", "top", "new", "comments"
    time: str = "week"  # "all", "year", "month", "week", "day", "hour"
    limit: int = 50  # Number of posts to analyze
    nsfw: bool = False  # Include NSFW content
    
    # Model configuration
    model: str = "gpt-4.1-2025-04-14"
    
    # Analysis configuration
    system_prompt: str = """You are an expert social media analyst specializing in Reddit comment analysis. Your task is to analyze Reddit discussions to identify insightful comments, understand sentiment patterns, and extract meaningful themes from user conversations."""
    
    # Output configuration
    output_format: str = "json"
    max_quote_length: int = 200


class AnalysisMetadata(BaseModel):
    """Enhanced model for analysis metadata with thread insights."""

    # Core analysis metrics
    total_posts_analyzed: int
    total_comments_found: int
    relevant_comments_extracted: int
    irrelevant_posts: int
    analysis_timestamp: datetime
    processing_time_seconds: float
    model_used: str
    api_calls_made: int
    collection_method: str = Field(description="subreddit or search")
    cell_parsing_errors: int = Field(default=0, description="Cell parsing issues count")
    
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
 