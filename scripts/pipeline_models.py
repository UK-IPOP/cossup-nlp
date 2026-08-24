"""Data models used by the S3 AI pipeline."""

from pydantic import BaseModel


class ProcessingStats:
    """Counters collected while processing a pipeline run."""

    def __init__(self):
        self.total = 0
        self.processed = 0
        self.skipped = 0
        self.failed = 0


class FileInfo(BaseModel):
    """Metadata identifying a source object in S3."""

    s3_key: str
    s3_etag: str | None = None
    size: int | None = None


class Encounter(BaseModel):
    """Extracted and summarized data for one encounter."""

    num: int
    page_range: tuple[int, int]
    source_data: str
    summary: str


class Outcome(BaseModel):
    """Complete summary produced for one source PDF."""

    file_info: FileInfo
    history: list[Encounter]
    summary: str
