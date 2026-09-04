# Architecture

## Components

The project is intentionally small and script-oriented.

- `scripts/s3_ai_pipeline.py` orchestrates the full workflow.
- `scripts/pipeline_config.py` loads and validates required environment variables.
- `scripts/pipeline_models.py` defines the data structures used for file, encounter, and summary output.
- `scripts/pipeline_observability.py` configures logging and optional Discord notifications.
- `resources/summary-template.md` contains the schema used for AI summarization.

## Runtime flow

```text
S3 bucket
  -> list PDF keys
  -> check for existing .summary.md
  -> download PDF bytes
  -> split by "Reason for Visit"
  -> convert each chunk to Markdown
  -> summarize each encounter
  -> summarize overall history
  -> upload final Markdown file
```

## Implementation notes

### S3 integration

The pipeline uses `boto3` with endpoint configuration and credentials loaded from environment variables. This makes the application usable with S3-compatible providers, not only AWS S3.

### PDF splitting

Within a single PDF, the split logic reads each page with `PyPDF2` and identifies a new encounter when a later page contains `Reason for Visit`. That marker acts as the divider between one visit and the next, so the script treats it as the start of a fresh encounter. The first page is intentionally excluded so the document cover or intake header does not create a false encounter boundary.

The assumption is that the record layout includes a reliable `Reason for Visit` marker at each new visit boundary. If a batch of PDFs uses a different format, the script may create too many, too few, or malformed encounter chunks.

### AI summarization

Each encounter is sent to the configured Ollama-compatible model using `pydantic-ai` and a prompt that includes the summary template. If the patient-level summary generation fails, the pipeline falls back to combining the encounter summaries directly instead of stopping the run.

### Observability

The project uses Python’s standard-library logging for runtime diagnostics and failure reporting. Logs are emitted directly to the console and can be filtered by level through the CLI flags.

## Design constraints

- The app is sequential by default, even though a `--workers` option exists.
- The workflow is tightly coupled to the current PDF format and medical summary template.
- The code is structured for a task-oriented process rather than a reusable library API.
