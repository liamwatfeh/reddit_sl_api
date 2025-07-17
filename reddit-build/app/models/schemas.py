"""
Core Pydantic models for Reddit comment analysis API.
"""

from pydantic import BaseModel
from typing import List, Dict, Any
from datetime import datetime


class CommentAnalysis(BaseModel):
    """Model for individual comment analysis results."""

    post_id: str
    post_url: str  # URL to original Reddit post for verification
    quote: str
    sentiment: str  # "positive", "negative", "neutral"
    theme: str
    purchase_intent: str  # "high", "medium", "low", "none"
    date: datetime
    source: str = "reddit"

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
    """Model for analysis metadata."""

    total_posts_analyzed: int
    total_comments_found: int
    relevant_comments_extracted: int
    irrelevant_posts: int
    analysis_timestamp: datetime
    processing_time_seconds: float
    model_used: str
    api_calls_made: int
    collection_method: str  # "subreddit" or "search"
    cell_parsing_errors: int = 0  # New field for cell parsing issues

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


class UnifiedAnalysisResponse(BaseModel):
    """Model for unified analysis response."""

    comment_analyses: List[CommentAnalysis]
    metadata: AnalysisMetadata
