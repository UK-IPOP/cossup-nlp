# cossup

S3 AI Medical Record Summarization Pipeline

This repository contains a Python application that searches an S3-compatible bucket for medical-record PDFs, splits each document into encounter-level sections, converts those sections into text, summarizes them with an AI model, and writes Markdown summaries back to the same storage location.

The project is designed to support workflow-oriented medical-record review by generating both a patient-level summary and encounter-by-encounter summaries for each record.

## Repository purpose

The system performs the following tasks:

- discover PDF files in an S3 bucket
- skip already-processed outputs unless overwrite mode is enabled
- download candidate records
- split a document into encounter chunks using page markers
- convert each encounter to Markdown
- generate summaries using a configured AI model
- upload the final Markdown summary back to S3

## Repository structure

- `scripts/s3_ai_pipeline.py` — main orchestration entry point
- `scripts/pipeline_config.py` — environment variable validation and defaults
- `scripts/pipeline_models.py` — data models for file, encounter, and outcome metadata
- `scripts/pipeline_observability.py` — logging and optional Discord notifications
- `resources/summary-template.md` — prompt template used to structure output
- `justfile` — convenience commands for running the pipeline
- `docs/` — developer-facing wiki and operational documentation
- `pyproject.toml` — Python dependencies and project metadata

## Developer documentation

Start with the docs index:

- `docs/README.md`

## Prerequisites

- Python 3.14+
- `uv` for dependency management
- access to an S3-compatible storage endpoint
- access to an Ollama-compatible model server or OpenAI-compatible endpoint

## Local setup

1. Install dependencies:

   ```bash
   uv sync
   ```

2. Create a local `.env` file in the repository root with the required variables:

   ```env
   S3_BUCKET=your-bucket
   S3_ACCESS_KEY=your-access-key
   S3_SECRET_KEY=your-secret-key
   S3_ENDPOINT=https://your-s3-endpoint
   OLLAMA_MODEL=llama3.1
   OLLAMA_BASE_URL=http://localhost:11434
   ```

   Optional values include:

   ```env
   TEMPLATE_PATH=resources/summary-template.md
   ```

3. Validate the CLI help:

   ```bash
   uv run python scripts/s3_ai_pipeline.py --help
   ```

## Running the pipeline

Using the project helper:

```bash
just s3-pipeline --overwrite --log-level INFO
```

Or directly:

```bash
uv run python scripts/s3_ai_pipeline.py --overwrite --log-level INFO
```

## Runtime behavior

The current runtime flow is:

1. list PDF objects in the configured bucket
2. skip existing `.summary.md` outputs unless overwrite is enabled
3. download the source PDF
4. split a single PDF into encounter chunks using the `Reason for Visit` divider after page 1
5. convert each encounter to Markdown using Docling
6. summarize each encounter with the configured AI model
7. create a patient-level summary from the encounter summaries
8. upload the final Markdown output to S3

## Known operational caveats

- `scripts/s3_ai_pipeline.py` currently processes files sequentially, even though `--workers` is accepted.
- The project assumes a specific PDF layout and encounter segmentation heuristic; output quality will vary by source document structure.
- The application is script-based rather than packaged as a service or Python package.

## Reason for Visit heuristic

Within a single PDF, each new encounter begins when a page contains `Reason for Visit` after page 1. The code reads each page with `PyPDF2`, keeps a running buffer of pages, and starts a new encounter when that divider appears. The first page is intentionally excluded from this split rule so the document header does not trigger a false encounter break.

This heuristic works when the source PDFs consistently label each new visit with that exact phrase. If the layout varies, the script may split encounters incorrectly or miss boundaries entirely. That is a known operational assumption of the current implementation.

## License

This project is licensed under the MIT License. See `LICENSE` for details.
