"""
Logging configuration for the Task Manager API.
Provides consistent logging across the application.
"""

import logging
import sys
from pathlib import Path


def setup_logging():
    """
    Configure application-wide logging.

    Logs are written to both:
    - Console (stdout) - for development
    - File (logs/app.log) - for persistence

    Log format includes timestamp, logger name, level, and message.
    """

    # Create logs directory if it doesn't exist
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)

    # Define log format
    log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"

    # Configure root logger
    logging.basicConfig(
        level=logging.INFO,  # Set minimum log level
        format=log_format,
        datefmt=date_format,
        handlers=[
            # Console handler (prints to terminal)
            logging.StreamHandler(sys.stdout),
            # File handler (writes to file)
            logging.FileHandler(
                log_dir / "app.log", mode="a", encoding="utf-8"  # Append mode
            ),
        ],
    )

    # Set specific log levels for noisy libraries
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)  # Reduc uvicorn noise
    logging.getLogger("sqlalchemy.engine").setLevel(
        logging.WARNING
    )  # Reduce SQL query logging

    # Log that logging is configured
    logger = logging.getLogger(__name__)
    logger.info("Logging configured successfully")
