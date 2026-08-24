default:
    just --list

set dotenv-load := true

s3-pipeline *args:
    uv run python s3_ai_pipeline.py {{args}}
