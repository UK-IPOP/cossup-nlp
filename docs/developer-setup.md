# Developer setup

## Prerequisites

- Python 3.14+
- `uv`
- network access to the configured S3 endpoint
- a reachable Ollama or OpenAI-compatible model endpoint
- a Logfire token

## Install dependencies

```bash
uv sync
```

## Required environment variables

Create a local `.env` file at the repository root:

```env
S3_BUCKET=your-bucket
S3_ACCESS_KEY=your-access-key
S3_SECRET_KEY=your-secret-key
S3_ENDPOINT=https://your-s3-endpoint
OLLAMA_MODEL=llama3.1
OLLAMA_BASE_URL=http://localhost:11434
```

Optional variables:

```env
TEMPLATE_PATH=resources/summary-template.md
```

## Validate the app

```bash
uv run python scripts/s3_ai_pipeline.py --help
```

## Run the pipeline

```bash
just s3-pipeline --overwrite --log-level INFO
```

or:

```bash
uv run python scripts/s3_ai_pipeline.py --overwrite --log-level INFO
```

## Recommended workflow

- keep secrets in `.env` and avoid committing them
- run targeted validation whenever modifying prompt logic or PDF parsing
- review any model or template change with a sample document before production use
