"""
Centralized logging configuration for Reddit Comment Analysis API.
"""

import json
import logging
import logging.handlers
import os
import sys
from pathlib import Path
from typing import Dict, Any

from .config import get_settings


class JSONFormatter(logging.Formatter):
    """Custom JSON formatter for structured logging."""
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        log_data: Dict[str, Any] = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        # Add exception information if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        
        # Add any extra data passed via the 'extra' parameter
        if hasattr(record, '__dict__'):
            for key, value in record.__dict__.items():
                if key not in ['name', 'msg', 'args', 'levelname', 'levelno', 'pathname', 'filename',
                              'module', 'lineno', 'funcName', 'created', 'msecs', 'relativeCreated',
                              'thread', 'threadName', 'processName', 'process', 'getMessage', 'exc_info',
                              'exc_text', 'stack_info', 'message']:
                    log_data[key] = value
        
        return json.dumps(log_data, default=str, ensure_ascii=False)


def setup_logging() -> None:
    """
    Set up production-grade logging configuration with rotation and structured logging.
    """
    settings = get_settings()

    # Convert string log level to logging constant
    log_level = getattr(logging, settings.log_level.upper(), logging.INFO)

    # Clear any existing handlers
    root_logger = logging.getLogger()
    root_logger.handlers.clear()

    # Create handlers list
    handlers = []

    # Console handler (always enabled)
    console_handler = logging.StreamHandler(sys.stdout)
    
    # Choose formatter based on configuration
    if settings.enable_json_logging:
        console_formatter = JSONFormatter(datefmt="%Y-%m-%d %H:%M:%S")
    else:
        console_formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
    
    console_handler.setFormatter(console_formatter)
    handlers.append(console_handler)

    # File handler with rotation (if enabled)
    if settings.enable_file_logging:
        # Ensure log directory exists
        log_dir = Path(settings.log_file_path)
        log_dir.mkdir(parents=True, exist_ok=True)
        
        # Full log file path
        log_file_path = log_dir / settings.log_file_name
        
        # Create rotating file handler
        file_handler = logging.handlers.RotatingFileHandler(
            filename=str(log_file_path),
            maxBytes=settings.log_rotation_size,
            backupCount=settings.log_retention_count,
            encoding='utf-8'
        )
        
        # Use JSON formatter for file logs if enabled
        if settings.enable_json_logging:
            file_formatter = JSONFormatter(datefmt="%Y-%m-%d %H:%M:%S")
        else:
            file_formatter = logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S"
            )
        
        file_handler.setFormatter(file_formatter)
        handlers.append(file_handler)

    # Configure basic logging with all handlers
    logging.basicConfig(
        level=log_level,
        handlers=handlers,
        force=True,  # Override any existing configuration
    )

    # Configure module-specific log levels
    for module_name, level_str in settings.module_log_levels.items():
        module_level = getattr(logging, level_str.upper(), logging.INFO)
        logging.getLogger(module_name).setLevel(module_level)

    # Log configuration info
    logger = logging.getLogger(__name__)
    logger.info("Logging system initialized", extra={
        "log_level": settings.log_level,
        "file_logging_enabled": settings.enable_file_logging,
        "json_logging_enabled": settings.enable_json_logging,
        "log_file_path": str(log_dir / settings.log_file_name) if settings.enable_file_logging else None,
        "rotation_size_mb": settings.log_rotation_size / (1024 * 1024),
        "retention_count": settings.log_retention_count,
        "module_log_levels": settings.module_log_levels
    })


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger instance with the specified name.

    Args:
        name: Name for the logger (usually __name__)

    Returns:
        Logger instance configured with the global settings
    """
    return logging.getLogger(name)
