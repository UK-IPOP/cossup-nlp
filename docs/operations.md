# Operations

## Typical run sequence

When the pipeline starts, it:

1. connects to the configured S3 endpoint
2. lists all `.pdf` objects in the bucket
3. checks whether a sibling `.summary.md` already exists
4. downloads and processes only missing work unless `--overwrite` is set
5. converts each encounter to Markdown
6. summarizes each encounter and then the combined history
7. uploads the final markdown back to S3

## Output behavior

The script uploads a generated Markdown file that follows this general pattern:

```md
# Patient Summary

<overall summary>

## Encounter: 1

<encounter summary>
```

The output uses the same object prefix as the source PDF and replaces the extension with `.summary.md`.

## Logging

The project uses Python’s standard-library logging for diagnostics and failure reporting. Each run emits structured log lines with timestamps and log levels, and failed jobs are reported via the logger instead of a Discord hook.

## Runtime notes

- The pipeline is intentionally sequential; `--workers` is accepted but not used in the execution loop.
- A run exits early when no PDF files are found in the bucket.
- Failures are tracked in `ProcessingStats` and reported at the end of a run.
- Invalid or empty encounter generation causes that document to be treated as failed.

## Operational caution

This project is suitable for controlled, domain-specific processing, but it is not yet a generalized enterprise workflow product. The logic depends strongly on the input document structure and model configuration.
