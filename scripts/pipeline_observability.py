"""Logging and failure notifications for the S3 AI pipeline."""

import asyncio
import logging
from datetime import datetime

import discord
import logfire

from scripts.pipeline_config import DISCORD_TOKEN, DISCORD_USER_ID, LOGFIRE_TOKEN


LOG_LEVELS = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}


async def send_dm(message: str) -> None:
    """Send a failure notification to the configured Discord user."""
    if not DISCORD_TOKEN or not DISCORD_USER_ID:
        return

    intents = discord.Intents.default()

    async with discord.Client(intents=intents) as client:

        @client.event
        async def on_ready():
            user = await client.fetch_user(DISCORD_USER_ID)
            await user.send(f"TS: {datetime.now()} :: {message}")
            await client.close()

        await client.start(DISCORD_TOKEN)


def initialize_logging(log_level: str = "INFO") -> None:
    """Configure standard-library logging to emit through Logfire."""
    level = LOG_LEVELS.get(log_level.upper(), logging.INFO)
    logfire.configure(token=LOGFIRE_TOKEN)
    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)-8s | %(message)s",
        handlers=[logfire.LogfireLoggingHandler()],
    )
    logfire.instrument_pydantic_ai()
