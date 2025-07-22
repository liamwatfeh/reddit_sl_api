# Improvements for logging.py

This document outlines potential production-readiness improvements for the `reddit-build/app/core/logging.py` file. While the current implementation is functional and clean, these enhancements would elevate it to a truly robust, production-grade logging system.

### 1. Implement Log Rotation (High Priority)

- **Issue**: The current `FileHandler` appends to `server.log` indefinitely (`mode='a'`). In a long-running production environment, this log file will grow continuously until it consumes all available disk space, potentially crashing the server.
- **Improvement**: Replace `logging.FileHandler` with a rotating handler from the `logging.handlers` module:
  - `RotatingFileHandler`: Creates a new log file after reaching a specified size (e.g., 10MB)
  - `TimedRotatingFileHandler`: Creates a new log file on a schedule (e.g., daily at midnight)
    This is critical for maintaining system stability and preventing disk space issues.

### 2. Implement Structured (JSON) Logging

- **Issue**: The current log format is plain text, which is human-readable but difficult for machines to parse. Production logging systems (Datadog, Splunk, ELK stack) work best with structured data.
- **Improvement**: Switch to JSON formatting using a library like `python-json-logger`. This would:
  - Make logs searchable and filterable by specific fields
  - Automatically include the `extra` data passed from exception handlers as key-value pairs
  - Enable powerful dashboards and alerts (e.g., "show all logs where error_code is REDDIT_001")
  - Improve integration with modern observability tools

### 3. Externalize Log File Configuration

- **Issue**: The log filename is hardcoded as `"server.log"`, which lacks flexibility for different deployment environments.
- **Improvement**: Move log file configuration to `config.py` with settings like:
  - `LOG_FILE_PATH`: Configurable path for log files
  - `LOG_FILE_NAME`: Configurable filename
  - `ENABLE_FILE_LOGGING`: Boolean to enable/disable file logging
    This allows for environment-specific configurations (e.g., logging to `/var/log/app/` in production or stdout in containers).

### 4. Add Log Level Configuration for Individual Modules

- **Issue**: Currently, the global log level applies to all application modules. In production, you might want different verbosity levels for different components.
- **Improvement**: Allow fine-grained control over log levels for specific modules (e.g., set Reddit API calls to DEBUG while keeping everything else at INFO). This can be achieved through additional configuration settings and targeted logger configuration.
