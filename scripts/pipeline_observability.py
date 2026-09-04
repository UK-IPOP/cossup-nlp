"""Logging configuration for the S3 AI pipeline."""

import logging

LOG_LEVELS = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}


def initialize_logging(log_level: str = "INFO") -> None:
    """Configure standard-library logging for the pipeline."""
    level = LOG_LEVELS.get(log_level.upper(), logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)-8s | %(message)s",
        force=True,
    )
