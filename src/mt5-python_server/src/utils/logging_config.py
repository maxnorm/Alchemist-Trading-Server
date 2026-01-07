"""
Logging configuration for the trading system
Separates logs between tick streamer and AI model
Supports both traditional and structured JSON logging
"""

import os
import logging
from logging.handlers import RotatingFileHandler
from typing import Optional

# Import structured logging components
try:
    from utils.structured_logging import StructuredLogger, JSONFormatter

    STRUCTURED_LOGGING_AVAILABLE = True
except ImportError:
    STRUCTURED_LOGGING_AVAILABLE = False


def _get_log_directory() -> str:
    """
    Get the log directory path.
    Uses LOG_DIR environment variable if set, otherwise:
    - /app/logs for Docker containers
    - ./logs for local development (relative to project root)
    """
    # Check environment variable first
    if "LOG_DIR" in os.environ:
        return os.environ["LOG_DIR"]

    # Check if we're in Docker (common indicator)
    if os.path.exists("/app"):
        return "/app/logs"

    # For local development, use ./logs relative to project root
    # Try to find project root by looking for common files
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = current_dir
    for _ in range(5):  # Go up max 5 levels
        if os.path.exists(
            os.path.join(project_root, "docker-compose.yml")
        ) or os.path.exists(os.path.join(project_root, "README.md")):
            return os.path.join(project_root, "logs")
        parent = os.path.dirname(project_root)
        if parent == project_root:  # Reached filesystem root
            break
        project_root = parent

    # Fallback: use logs in current working directory
    return os.path.join(os.getcwd(), "logs")


def setup_logger(name: str, log_file: str, level=logging.INFO) -> logging.Logger:
    """
    Set up a logger with file and console handlers

    :param name: Logger name
    :param log_file: Path to log file
    :param level: Logging level
    :return: Configured logger
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # Avoid duplicate handlers if logger already exists
    if logger.handlers:
        return logger

    # Create logs directory if it doesn't exist
    log_dir = os.path.dirname(log_file)
    if log_dir and not os.path.exists(log_dir):
        os.makedirs(log_dir, exist_ok=True)

    # File handler with rotation (10MB max, keep 5 backups)
    file_handler = RotatingFileHandler(
        log_file, maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8"
    )  # 10MB
    file_handler.setLevel(level)

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)

    # Formatter with timestamp, logger name, level, and message
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger


def get_tick_streamer_logger() -> logging.Logger:
    """
    Get logger for tick streamer operations

    :return: Tick streamer logger
    """
    log_dir = _get_log_directory()
    log_file = os.path.join(log_dir, "tick_streamer.log")
    return setup_logger("tick_streamer", log_file)


def get_ai_model_logger() -> logging.Logger:
    """
    Get logger for AI model training and trading operations

    :return: AI model logger
    """
    log_dir = _get_log_directory()
    log_file = os.path.join(log_dir, "ai_model.log")
    # Allow DEBUG level via environment variable for more verbose logging
    log_level = os.getenv("AI_MODEL_LOG_LEVEL", "INFO").upper()
    level = getattr(logging, log_level, logging.INFO)
    return setup_logger("ai_model", log_file, level=level)


def get_server_logger() -> logging.Logger:
    """
    Get logger for server operations

    :return: Server logger
    """
    log_dir = _get_log_directory()
    log_file = os.path.join(log_dir, "server.log")
    return setup_logger("server", log_file)


def _should_use_structured_logging() -> bool:
    """
    Check if structured logging should be used
    Controlled by USE_STRUCTURED_LOGGING environment variable

    :return: True if structured logging should be used
    """
    if not STRUCTURED_LOGGING_AVAILABLE:
        return False
    return os.getenv("USE_STRUCTURED_LOGGING", "false").lower() == "true"


def _get_log_format() -> str:
    """
    Get log format preference
    Controlled by LOG_FORMAT environment variable (json|readable)

    :return: 'json' or 'readable'
    """
    return os.getenv("LOG_FORMAT", "json").lower()


def setup_structured_logger(
    name: str,
    log_file: str,
    level: int = logging.INFO,
    use_json_file: bool = True,
    use_readable_console: bool = True,
) -> StructuredLogger:
    """
    Set up a structured logger with JSON file output and readable console output

    :param name: Logger name (component name)
    :param log_file: Path to log file
    :param level: Logging level
    :param use_json_file: Whether to use JSON format for file handler
    :param use_readable_console: Whether to use readable format for console handler
    :return: StructuredLogger instance
    """
    if not STRUCTURED_LOGGING_AVAILABLE:
        raise ImportError("Structured logging module not available")

    logger = logging.getLogger(name)
    logger.setLevel(level)

    # Avoid duplicate handlers if logger already exists
    if logger.handlers:
        return StructuredLogger(name, logger)

    # Create logs directory if it doesn't exist
    log_dir = os.path.dirname(log_file)
    if log_dir and not os.path.exists(log_dir):
        os.makedirs(log_dir, exist_ok=True)

    # File handler with rotation (10MB max, keep 5 backups)
    file_handler = RotatingFileHandler(
        log_file, maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8"
    )  # 10MB
    file_handler.setLevel(level)

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)

    # Set formatters based on preferences
    if use_json_file:
        file_handler.setFormatter(JSONFormatter())
    else:
        file_handler.setFormatter(
            logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )

    if use_readable_console:
        console_handler.setFormatter(
            logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )
    else:
        console_handler.setFormatter(JSONFormatter())

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return StructuredLogger(name, logger)


def get_structured_logger(
    component_name: str, log_file_name: Optional[str] = None
) -> StructuredLogger:
    """
    Get structured logger for a component

    :param component_name: Name of the component
    :param log_file_name: Optional log file name (defaults to {component_name}.log)
    :return: StructuredLogger instance
    """
    log_dir = _get_log_directory()
    if log_file_name is None:
        log_file_name = f"{component_name}.log"
    log_file = os.path.join(log_dir, log_file_name)

    # Determine format preferences from environment
    log_format = _get_log_format()
    use_json_file = log_format == "json"
    use_readable_console = True  # Always use readable for console

    # Allow DEBUG level via environment variable
    log_level = os.getenv(f"{component_name.upper()}_LOG_LEVEL", "INFO").upper()
    level = getattr(logging, log_level, logging.INFO)

    return setup_structured_logger(
        component_name,
        log_file,
        level=level,
        use_json_file=use_json_file,
        use_readable_console=use_readable_console,
    )


def get_structured_tick_streamer_logger() -> StructuredLogger:
    """
    Get structured logger for tick streamer operations

    :return: Structured tick streamer logger
    """
    return get_structured_logger("tick_streamer", "tick_streamer.log")


def get_structured_ai_model_logger() -> StructuredLogger:
    """
    Get structured logger for AI model training and trading operations

    :return: Structured AI model logger
    """
    return get_structured_logger("ai_model", "ai_model.log")


def get_structured_server_logger() -> StructuredLogger:
    """
    Get structured logger for server operations

    :return: Structured server logger
    """
    return get_structured_logger("server", "server.log")


def get_logger(component_name: str, log_file_name: Optional[str] = None):
    """
    Get logger (structured or traditional based on configuration)
    This is a convenience function that returns structured logger if enabled,
    otherwise returns traditional logger

    :param component_name: Name of the component
    :param log_file_name: Optional log file name
    :return: StructuredLogger or logging.Logger instance
    """
    if _should_use_structured_logging():
        return get_structured_logger(component_name, log_file_name)
    else:
        log_dir = _get_log_directory()
        if log_file_name is None:
            log_file_name = f"{component_name}.log"
        log_file = os.path.join(log_dir, log_file_name)
        return setup_logger(component_name, log_file)
