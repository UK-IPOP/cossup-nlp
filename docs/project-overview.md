# Project overview

## Purpose

`cossup` is a document-processing pipeline for medical records stored in an S3-compatible object store. It finds source PDFs, extracts text from encounter sections, summarizes those sections with an AI model, and writes a final Markdown summary back to the same storage location.

## Business value

The project is designed to reduce manual effort when reviewing patient records. A typical PDF may contain multiple visits and many pages. The pipeline makes that information easier to evaluate by producing:

- a patient-level historical summary
- encounter-level summaries for each visit segment
- a consistent output structure for downstream review

## Intended workflow

1. Inventory `.pdf` objects in the configured S3 bucket.
2. Determine whether a summary already exists.
3. Download the source PDF if it needs processing.
4. Split the PDF into encounter chunks.
5. Extract structured text from each segment.
6. Generate an AI summary for each encounter.
7. Generate a final patient summary.
8. Upload the resulting `.summary.md` file back to storage.

## Output contract

For each processed PDF, the pipeline writes a sibling file named like:

```text
records/case.pdf -> records/case.summary.md
```

The output is Markdown and contains:

- a patient history section
- one or more encounter sections
- summary text intended for human review
