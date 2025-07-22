"""
Configuration management using Pydantic Settings.
"""

from functools import lru_cache
from typing import Optional, List
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

    # Application Configuration
    log_level: str = Field(default="INFO", description="Logging level")
    max_concurrent_agents: int = Field(
        default=5, description="Maximum concurrent AI agents"
    )
    debug: bool = Field(default=False, description="Enable debug mode")

    # AI Model Configuration
    primary_ai_model: str = Field(
        default="gpt-4.1-2025-04-14", 
        description="Primary AI model for comment analysis"
    )

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
 