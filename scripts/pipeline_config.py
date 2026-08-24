"""Configuration values for the S3 AI pipeline."""

import os
from pathlib import Path


def required_env(name: str) -> str:
    """Return a required environment variable or raise a clear error."""
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Required environment variable {name} is not set")
    return value


S3_BUCKET = required_env("S3_BUCKET")
S3_ACCESS_KEY = required_env("S3_ACCESS_KEY")
S3_SECRET_KEY = required_env("S3_SECRET_KEY")
S3_ENDPOINT = required_env("S3_ENDPOINT")
OLLAMA_MODEL = required_env("OLLAMA_MODEL")
OLLAMA_BASE_URL = required_env("OLLAMA_BASE_URL")
LOGFIRE_TOKEN = required_env("LOGFIRE_TOKEN")
TEMPLATE_PATH = Path(os.getenv("TEMPLATE_PATH", "resources/summary-template.md"))
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
DISCORD_USER_ID = int(os.getenv("DISCORD_USER_ID", "0"))
