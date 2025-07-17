"""
Centralized logging configuration for Reddit Comment Analysis API.
"""

import logging
import sys
from .config import get_settings


def setup_logging() -> None:
    """
    Set up logging configuration for the application.
    """
    settings = get_settings()

    # Convert string log level to logging constant
    log_level = getattr(logging, settings.log_level.upper(), logging.INFO)

    # Configure basic logging
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[logging.StreamHandler(sys.stdout)],
        force=True,  # Override any existing configuration
    )

    # Reduce noise from third-party libraries
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance with the specified name.

    Args:
        name: Name for the logger (usually __name__)

    Returns:
        Logger instance
    """
    return logging.getLogger(name)
