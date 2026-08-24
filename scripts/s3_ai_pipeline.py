#!/usr/bin/env python3
"""
S3 AI Pipeline

Downloads PDFs from S3, converts to Markdown using docling,
parses encounters, generates summaries via PydanticAI + Ollama,
and uploads the summary markdown files back to S3.
"""

import argparse
import asyncio
import logging
import os
import sys
import time
from io import BytesIO

import boto3
import httpx
from botocore.exceptions import ClientError
from docling.document_converter import DocumentConverter
from docling_core.types.io import DocumentStream
from pydantic_ai import Agent
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.ollama import OllamaProvider
from PyPDF2 import PdfReader, PdfWriter

from scripts.pipeline_config import (
    OLLAMA_BASE_URL,
    OLLAMA_MODEL,
    S3_ACCESS_KEY,
    S3_BUCKET,
    S3_ENDPOINT,
    S3_SECRET_KEY,
    TEMPLATE_PATH,
)
from scripts.pipeline_models import Encounter, FileInfo, Outcome, ProcessingStats
from scripts.pipeline_observability import initialize_logging, send_dm


class S3AIPipeline:
    """Coordinate S3 I/O, PDF conversion, and AI summarization."""

    def __init__(
        self,
        workers: int = 4,
        overwrite: bool = False,
        log_level: str = "INFO",
    ):
        """Initialize clients, converters, models, and run state."""
        self.bucket = S3_BUCKET
        self.workers = workers
        self.overwrite = overwrite
        self.log_level = log_level

        self.s3_client = boto3.client(
            "s3",
            aws_access_key_id=S3_ACCESS_KEY,
            aws_secret_access_key=S3_SECRET_KEY,
            endpoint_url=S3_ENDPOINT,
        )
        self.converter = DocumentConverter()
        self.stats = ProcessingStats()
        self.template = self._load_template()

        os.environ.setdefault("OLLAMA_BASE_URL", OLLAMA_BASE_URL)
        http_client = httpx.AsyncClient(timeout=120.0)
        provider = OllamaProvider(base_url=OLLAMA_BASE_URL, http_client=http_client)
        model = OpenAIChatModel(OLLAMA_MODEL, provider=provider)
        self.agent = Agent(model=model)

        initialize_logging(log_level)
        self.logger = logging.getLogger(__name__)

    def _load_template(self) -> str:
        """Load the summary template from file."""
        with open(TEMPLATE_PATH, "r") as f:
            return f.read()

    def list_pdf_keys(self) -> list[str]:
        """List all PDF objects in the bucket (recursive)."""
        self.logger.info(f"Scanning bucket '{self.bucket}' for PDF files...")

        pdf_keys = []
        paginator = self.s3_client.get_paginator("list_objects_v2")

        try:
            for page in paginator.paginate(Bucket=self.bucket):
                if "Contents" not in page:
                    continue

                for obj in page["Contents"]:
                    key = obj["Key"]
                    if key.lower().endswith(".pdf"):
                        pdf_keys.append(key)
                        self.logger.debug(f"Found PDF: {key}")

        except ClientError as e:
            self.logger.error(f"Failed to list bucket contents: {e}")
            raise

        self.logger.info(f"Found {len(pdf_keys)} PDF file(s)")
        return pdf_keys

    def _split_pdf_into_encounters(
        self, pdf_bytes: bytes
    ) -> list[tuple[tuple[int, int], bytes]]:
        """Split PDF into encounter chunks using 'Reason for Visit' markers."""
        pdf_reader = PdfReader(BytesIO(pdf_bytes))
        encounters: list[tuple[tuple[int, int], bytes]] = []

        current_pages: list = []
        page_min = 0

        for i, page in enumerate(pdf_reader.pages):
            text = str(page.extract_text())
            current_pages.append(page)

            if i == 0:
                continue

            if "Reason for Visit" in text:
                page_max = i - 1

                writer = PdfWriter()
                for p in current_pages:
                    writer.add_page(p)

                encounter_bytes = BytesIO()
                writer.write(encounter_bytes)
                encounters.append(((page_min, page_max), encounter_bytes.getvalue()))

                current_pages = [page]
                page_min = i

        if current_pages:
            page_max = len(pdf_reader.pages) - 1
            writer = PdfWriter()
            for p in current_pages:
                writer.add_page(p)

            encounter_bytes = BytesIO()
            writer.write(encounter_bytes)
            encounters.append(((page_min, page_max), encounter_bytes.getvalue()))

        return encounters

    def _convert_encounter_to_markdown(
        self, encounter_bytes: bytes, encounter_num: int
    ) -> str:
        """Convert a single encounter PDF chunk to markdown."""
        stream = DocumentStream(
            name=f"encounter_{encounter_num}.pdf", stream=BytesIO(encounter_bytes)
        )
        result = self.converter.convert(stream)
        return result.document.export_to_markdown()

    async def _summarize_encounter(
        self, markdown: str, page_range: tuple[int, int]
    ) -> str:
        """Generate summary for a single encounter using PydanticAI."""
        prompt = f"""Given the following template: 

{self.template}

Fill out as much information as possible, retaining the template structure, by 
examining the following data. Do not provide any supplemental commentary.

{markdown}
"""
        result = await self.agent.run(prompt)
        summary = result.output
        if isinstance(summary, str):
            summary += f"\n\nFound on pages: {page_range[0]}-{page_range[1]}"
        return summary

    async def _summarize_history(self, encounters: list[Encounter]) -> str:
        """Generate overall summary from all encounter summaries."""
        prompt = f"""
Summarize the following historical data:

{"\n\t-\t".join([e.summary for e in encounters])}
"""
        result = await self.agent.run(prompt)
        return result.output if isinstance(result.output, str) else str(result.output)

    def process_single_pdf(self, pdf_key: str) -> bool:
        """Download, convert, summarize, and upload one PDF object."""
        summary_key = pdf_key.rsplit(".", 1)[0] + ".summary.md"

        self.logger.debug(f"[{pdf_key}] Starting processing")

        if not self.overwrite:
            try:
                self.s3_client.head_object(Bucket=self.bucket, Key=summary_key)
                self.logger.info(
                    f"[{pdf_key}] Skipping - .summary.md already exists (use --overwrite to replace)"
                )
                self.stats.skipped += 1
                return True
            except ClientError as e:
                if e.response["Error"]["Code"] != "404":
                    self.logger.warning(
                        f"[{pdf_key}] Error checking .summary.md existence: {e}"
                    )

        try:
            self.logger.debug(f"[{pdf_key}] Downloading from S3...")
            response = self.s3_client.get_object(Bucket=self.bucket, Key=pdf_key)
            pdf_bytes = response["Body"].read()
            self.logger.debug(f"[{pdf_key}] Downloaded {len(pdf_bytes)} bytes")
        except ClientError as e:
            self.logger.error(f"[{pdf_key}] Failed to download PDF: {e}")
            self.stats.failed += 1
            return False

        try:
            self.logger.debug(f"[{pdf_key}] Splitting PDF into encounters...")
            encounter_chunks = self._split_pdf_into_encounters(pdf_bytes)
            self.logger.debug(f"[{pdf_key}] Found {len(encounter_chunks)} encounter(s)")
        except Exception as e:
            self.logger.error(f"[{pdf_key}] Failed to split PDF into encounters: {e}")
            self.stats.failed += 1
            return False

        encounters: list[Encounter] = []
        for idx, (page_range, encounter_bytes) in enumerate(encounter_chunks, start=1):
            try:
                self.logger.debug(
                    f"[{pdf_key}] Converting encounter {idx} to markdown..."
                )
                markdown = self._convert_encounter_to_markdown(encounter_bytes, idx)
                self.logger.debug(f"[{pdf_key}] Summarizing encounter {idx}...")
                summary = asyncio.run(self._summarize_encounter(markdown, page_range))
                enc = Encounter(
                    num=idx,
                    page_range=page_range,
                    source_data=markdown,
                    summary=summary,
                )
                encounters.append(enc)
            except Exception as e:
                self.logger.warning(
                    f"[{pdf_key}] Failed to process encounter {idx}: {e}"
                )

        if not encounters:
            self.logger.error(f"[{pdf_key}] No encounters processed successfully")
            self.stats.failed += 1
            return False

        try:
            self.logger.debug(f"[{pdf_key}] Generating overall summary...")
            overall_summary = asyncio.run(self._summarize_history(encounters))
        except Exception as e:
            self.logger.warning(f"[{pdf_key}] Failed to generate overall summary: {e}")
            overall_summary = "\n\n".join([e.summary for e in encounters])

        outcome = Outcome(
            file_info=FileInfo(s3_key=pdf_key),
            history=sorted(encounters, key=lambda x: x.num),
            summary=overall_summary,
        )

        output_markdown = f"# Patient Summary\n\n{outcome.summary}\n\n"
        for enc in outcome.history:
            output_markdown += f"## Encounter: {enc.num}\n\n{enc.summary}\n\n"

        try:
            self.logger.debug(f"[{pdf_key}] Uploading {summary_key} to S3...")
            self.s3_client.put_object(
                Bucket=self.bucket,
                Key=summary_key,
                Body=output_markdown.encode("utf-8"),
                ContentType="text/markdown",
            )
            self.logger.info(f"[{pdf_key}] Successfully uploaded {summary_key}")
        except ClientError as e:
            self.logger.error(f"[{pdf_key}] Failed to upload summary: {e}")
            self.stats.failed += 1
            return False

        self.stats.processed += 1

        return True

    def run(self):
        """List PDFs and process each one sequentially."""
        start_time = time.time()

        self.logger.info("=" * 50)
        self.logger.info("S3 AI Pipeline Started")
        self.logger.info("=" * 50)
        self.logger.info(f"Bucket:          {self.bucket}")
        self.logger.info("Processing:       Sequential")
        self.logger.info(f"Overwrite:       {self.overwrite}")
        self.logger.info(f"Log Level:       {self.log_level}")
        self.logger.info(f"Ollama Model:    {OLLAMA_MODEL}")
        self.logger.info("=" * 50)

        pdf_keys = self.list_pdf_keys()

        if not pdf_keys:
            self.logger.warning("No PDF files found in bucket")
            return

        self.stats.total = len(pdf_keys)

        self.logger.info(f"Processing {len(pdf_keys)} file(s) sequentially...")

        for pdf_key in pdf_keys:
            if "172_Johnson" in pdf_key:
                self.logger.warning("CONTINUING SKIPPING INVALID KEY")
                continue

            try:
                self.process_single_pdf(pdf_key)
            except Exception as e:
                self.logger.error(f"[{pdf_key}] Unexpected error: {e}")
                self.stats.failed += 1

        elapsed = time.time() - start_time
        self._print_summary(elapsed)

    def _print_summary(self, elapsed: float):
        """Print final processing summary."""
        self.logger.info("")
        self.logger.info("=" * 50)
        self.logger.info("Processing Complete")
        self.logger.info("=" * 50)
        self.logger.info(f"Total PDFs found:       {self.stats.total:>5}")
        self.logger.info(f"Processed successfully: {self.stats.processed:>5}")
        self.logger.info(f"Skipped (existing):     {self.stats.skipped:>5}")
        self.logger.info(f"Failed:                 {self.stats.failed:>5}")
        self.logger.info(f"Total time:             {elapsed:>6.2f}s")
        self.logger.info("=" * 50)

        if self.stats.failed > 0:
            message = (
                f"S3 AI Pipeline FAILED: "
                f"{self.stats.processed} processed, {self.stats.skipped} skipped, "
                f"{self.stats.failed} failed in {elapsed:.2f}s"
            )
            asyncio.run(send_dm(message))


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments for a pipeline run."""
    parser = argparse.ArgumentParser(
        description="Download PDFs from S3, convert to Markdown, parse encounters, "
        "generate summaries via PydanticAI + Ollama, and upload .summary.md to S3."
    )

    parser.add_argument(
        "--workers", type=int, default=4, help="Number of worker threads (default: 4)"
    )

    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing .summary.md files (default: skip)",
    )

    parser.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level (default: INFO)",
    )

    return parser.parse_args()


def main():
    """Entry point."""
    args = parse_args()

    if args.workers < 1:
        print("Error: --workers must be at least 1", file=sys.stderr)
        sys.exit(1)

    pipeline = S3AIPipeline(
        workers=args.workers,
        overwrite=args.overwrite,
        log_level=args.log_level,
    )

    try:
        pipeline.run()
    except KeyboardInterrupt:
        logging.warning("Interrupted by user")
        sys.exit(130)
    except Exception as e:
        logging.error(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
