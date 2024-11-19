default:
    just --list

set dotenv-load := true

run:
    uv run scripts/box.py $BOX_KEY 286195233329
