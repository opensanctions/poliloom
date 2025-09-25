"""Centralized logging configuration for PoliLoom."""

import logging
import os


def setup_logging() -> None:
    """
    Configure application-wide logging using LOG_LEVEL environment variable.

    Defaults to INFO if LOG_LEVEL is not set.
    """
    # Get log level from environment variable
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()

    # Convert string to logging constant (will raise AttributeError if invalid)
    numeric_level = getattr(logging, log_level)

    # Configure root logger
    logging.basicConfig(
        level=numeric_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        force=True,  # Override any existing configuration
    )

    # Configure httpx logging to respect the same level
    logging.getLogger("httpx").setLevel(numeric_level)
    logging.getLogger("httpcore").setLevel(numeric_level)

    # Configure dicttoxml to only log INFO when in DEBUG mode
    dicttoxml_level = (
        logging.WARNING if numeric_level > logging.DEBUG else numeric_level
    )
    logging.getLogger("dicttoxml").setLevel(dicttoxml_level)

    # Log the configured level
    logger = logging.getLogger(__name__)
    logger.info(f"Logging configured at {log_level} level")
