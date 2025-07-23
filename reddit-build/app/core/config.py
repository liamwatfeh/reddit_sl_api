"""
Configuration management using Pydantic Settings.
"""

from functools import lru_cache
from typing import Optional, List, Dict
from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # API Keys - Critical keys are required, no defaults
    rapid_api_key: str = Field(
        description="RapidAPI key for Reddit access (REQUIRED)"
    )
    openai_api_key: str = Field(
        description="OpenAI API key (REQUIRED)"
    )
    
    # Internal API Security - No insecure default
    internal_api_key: str = Field(
        description="Shared API key for internal team access (REQUIRED)"
    )

    # Reddit API Configuration  
    rapidapi_reddit_host: str = Field(
        default="reddit-com.p.rapidapi.com", 
        description="RapidAPI Reddit host"
    )
    reddit_api_timeout: int = Field(
        default=30, 
        description="Reddit API request timeout in seconds"
    )
    reddit_api_rate_limit_delay: float = Field(
        default=0.1, 
        description="Delay between Reddit API requests in seconds"
    )

    # CORS Configuration
    allowed_origins: List[str] = Field(
        default=["http://localhost:3000", "http://localhost:8000"], 
        description="Allowed CORS origins"
    )
    allowed_methods: List[str] = Field(
        default=["GET", "POST"], 
        description="Allowed HTTP methods"
    )
    allowed_hosts: List[str] = Field(
        default=["localhost", "127.0.0.1"], 
        description="Allowed trusted hosts"
    )

    # Security Configuration
    max_request_size: int = Field(
        default=10 * 1024 * 1024,  # 10MB
        description="Maximum request body size in bytes"
    )

    # Logging Configuration
    log_level: str = Field(default="INFO", description="Global logging level")
    log_file_path: str = Field(
        default="./logs", 
        description="Directory path for log files"
    )
    log_file_name: str = Field(
        default="reddit_api.log", 
        description="Base name for log files"
    )
    enable_file_logging: bool = Field(
        default=True, 
        description="Enable logging to files"
    )
    enable_json_logging: bool = Field(
        default=False, 
        description="Use structured JSON logging format"
    )
    log_rotation_size: int = Field(
        default=10 * 1024 * 1024,  # 10MB
        description="Log file size before rotation (bytes)"
    )
    log_retention_count: int = Field(
        default=5, 
        description="Number of rotated log files to keep"
    )
    module_log_levels: Dict[str, str] = Field(
        default={
            "uvicorn.access": "WARNING",
            "httpx": "WARNING", 
            "httpcore": "WARNING",
            "app.services.reddit_collector": "INFO",
            "app.agents.modern_comment_analyzer": "INFO"
        },
        description="Module-specific log levels"
    )

    # Application Configuration
    debug: bool = Field(default=False, description="Enable debug mode")

    # AI Model Configuration
    primary_ai_model: str = Field(
        default="gpt-4.1-2025-04-14", 
        description="Primary AI model for comment analysis"
    )
    openai_model: str = Field(default="gpt-4.1-2025-04-14", description="OpenAI model for analysis")
    openai_temperature: float = Field(default=0.1, description="OpenAI model temperature for analysis")
    openai_max_tokens: int = Field(default=4000, description="Maximum tokens for OpenAI responses")
    
    # Analysis Configuration
    max_concurrent_agents: int = Field(default=5, description="Maximum concurrent AI analysis agents")
    max_analysis_comments: int = Field(default=50, description="Maximum comments to analyze per post")
    max_thread_depth: int = Field(default=10, description="Maximum thread depth to analyze")
    
    # Default Analysis Prompts and Settings
    default_system_prompt: str = Field(
        default="Analyze the following Reddit comment for sentiment (positive/negative/neutral), main theme, and purchase intent (high/medium/low/none). Provide a concise analysis focusing on the user's opinion and any buying signals.",
        description="Default system prompt for AI analysis"
    )
    default_analysis_model: str = Field(
        default="gpt-4.1-2025-04-14",
        description="Default AI model for analysis requests"
    )
    
    # Default Request Parameters
    default_subreddit_sort: str = Field(default="hot", description="Default sort method for subreddit requests")
    default_subreddit_time: str = Field(default="week", description="Default time filter for subreddit requests")
    default_search_sort: str = Field(default="relevance", description="Default sort method for search requests")
    default_search_time: str = Field(default="all", description="Default time filter for search requests")
    default_request_limit: int = Field(default=25, description="Default number of posts to collect")

    # API Server Configuration
    host: str = Field(default="0.0.0.0", description="Server host")
    port: int = Field(default=8000, description="Server port")

    # FastAPI Configuration
    app_version: str = Field(default="v2", description="API version")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        extra = "ignore"  # Ignore extra environment variables


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Get the settings instance (singleton pattern with lru_cache)."""
    return Settings()
 