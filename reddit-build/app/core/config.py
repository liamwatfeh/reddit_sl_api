"""
Configuration management using Pydantic Settings.
"""

from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # API Keys
    rapid_api_key: Optional[str] = Field(
        default=None, description="RapidAPI key for Reddit access"
    )
    gemini_api_key: Optional[str] = Field(
        default=None, description="Google Gemini API key"
    )
    openai_api_key: Optional[str] = Field(default=None, description="OpenAI API key")

    # Application Configuration
    log_level: str = Field(default="INFO", description="Logging level")
    max_concurrent_agents: int = Field(
        default=5, description="Maximum concurrent AI agents"
    )
    debug: bool = Field(default=False, description="Enable debug mode")

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


# Global settings instance
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """Get the settings instance (singleton pattern)."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
