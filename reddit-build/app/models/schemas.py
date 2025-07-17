"""
Core Pydantic models for Reddit comment analysis API.
"""

from pydantic import BaseModel
from typing import List, Dict, Any
from datetime import datetime


class CommentAnalysis(BaseModel):
    """Model for individual comment analysis results."""

    post_id: str
    quote: str
    sentiment: str  # "positive", "negative", "neutral"
    theme: str
    purchase_intent: str  # "high", "medium", "low", "none"
    date: datetime
    source: str = "reddit"

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


class PostWithComments(BaseModel):
    """Model for Reddit post with its comments."""

    post_id: str
    post_title: str
    post_content: str
    post_author: str
    post_score: int
    post_created_utc: datetime
    comments: List[Dict[str, Any]]
    metadata: Dict[str, Any]


class ConfigurableAnalysisRequest(BaseModel):
    """Model for configurable analysis request parameters."""

    keywords: List[str] = ["BMW R 12 GS"]
    subreddits: List[str] = ["motorcycles", "BMW"]
    timeframe: str = "week"
    limit: int = 10
    model: str = "gemini-2.5-pro"
    api_key: str
    system_prompt: str = "You are an expert social media analyst..."
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

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


class UnifiedAnalysisResponse(BaseModel):
    """Model for unified analysis response."""

    comment_analyses: List[CommentAnalysis]
    metadata: AnalysisMetadata
