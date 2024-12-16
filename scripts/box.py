import logging
import os
import subprocess
import warnings
from argparse import ArgumentParser
from collections import defaultdict
from pathlib import Path
from typing import Any

import ollama
from box_sdk_gen import (
    BoxClient,
    UploadFileAttributes,
    UploadFileAttributesParentField,
)
from box_sdk_gen.box.developer_token_auth import BoxDeveloperTokenAuth
from box_sdk_gen.schemas.file_full import FileFull
from box_sdk_gen.schemas.folder_mini import FolderMini
from box_sdk_gen.schemas.web_link import WebLink
from pydantic import BaseModel, Field
from PyPDF2 import PdfReader
from rich.logging import RichHandler
from tqdm import TqdmExperimentalWarning
from tqdm.rich import tqdm

warnings.filterwarnings("ignore", category=TqdmExperimentalWarning)


# Dictionary to map environment variable strings to logging levels
LOG_LEVELS = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}


def initialize_logging():
    log_level_str = os.getenv("LOG_LEVEL", "INFO").upper()
    log_level = LOG_LEVELS.get(log_level_str, logging.WARNING)
    logging.basicConfig(
        level=log_level,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[RichHandler()],
    )


class Args(BaseModel):
    token: str
    box_folder_id: str
    fresh: bool = Field(default=False)


def parse_args() -> Args:
    parser = ArgumentParser(description="Extract OFR information")
    parser.add_argument(
        "token", type=str, help="Box Developer token from developer dashboard"
    )
    parser.add_argument(
        "box_folder_id", type=str, help="Box folder ID to look in PDFs for"
    )
    parser.add_argument(
        "--fresh",
        type=bool,
        help="Delete all the existing DOCX files in the folder for a fresh run",
        default=False,
    )
    argparse_args = parser.parse_args()
    args_dict = argparse_args.__dict__
    return Args.model_validate(args_dict)


def connect_to_box(token: str) -> BoxClient:
    auth = BoxDeveloperTokenAuth(token=token)
    client = BoxClient(auth=auth)
    return client


def setup() -> tuple[Args, BoxClient, ollama.Client]:
    initialize_logging()
    args = parse_args()
    client = connect_to_box(token=args.token)
    return args, client, ollama.Client()


class FileInfo(BaseModel):
    file_id: str
    file_name: str
    parent_folder_id: str
    parent_folder_name: str

    def model_post_init(self, __context: Any) -> None:
        # hacky hack :)
        # Replace spaces with underscores in all string fields
        for field_name, field_value in self.__dict__.items():
            if isinstance(field_value, str):
                setattr(self, field_name, field_value.replace(" ", "_"))
        return


def remove_box_docx(client: BoxClient, folder_id: str) -> int:
    folder = client.folders.get_folder_by_id(folder_id=folder_id)
    if folder.name is None:
        raise ValueError(f"Folder name is None for folder: {folder_id}")
    entries = client.folders.get_folder_items(folder_id=folder_id).entries
    if entries is None:
        raise ValueError(f"Found None entries for folder: {folder_id}")
    removed = 0
    for item in entries:
        if (name := item.name) is None:
            logging.error(f"{item} -- has no name")
            continue
        if name.lower().endswith(".docx"):
            client.files.delete_file_by_id(item.id)
            removed += 1
    return removed


def find_report(
    item: FileFull | FolderMini | WebLink,
    entries: list[FileFull | FolderMini | WebLink],
) -> FileFull | FolderMini | WebLink | None:
    if item.name is None:
        raise ValueError(f"Expected null check already for {item}")
    report_name = (
        item.name.replace(" ", "_").replace(".pdf", ".docx").replace(".PDF", ".docx")
    )
    report = next((e for e in entries if e.name == report_name), None)
    return report


def fetch_box_pdfs(client: BoxClient, folder_id: str) -> list[FileInfo]:
    folder = client.folders.get_folder_by_id(folder_id=folder_id)
    if (folder_name := folder.name) is None:
        raise ValueError(f"Folder name is None for folder: {folder_id}")
    entries = client.folders.get_folder_items(folder_id=folder_id).entries
    if entries is None:
        raise ValueError(f"Found None entries for folder: {folder_id}")
    files: list[FileInfo] = []
    for item in entries:
        if (name := item.name) is None:
            logging.error(f"{item} -- has no name")
            continue
        if name.lower().endswith(".pdf"):
            if (report := find_report(item=item, entries=entries)) is not None:
                logging.info(
                    f"Skipping over {item.name}, has matching report: {report.name}"
                )
                continue
            info = FileInfo(
                file_id=item.id,
                file_name=name,
                parent_folder_id=folder.id,
                parent_folder_name=folder_name,
            )
            files.append(info)
    return files


def download_box_file(client: BoxClient, file_id: str) -> bytes:
    stream = client.downloads.download_file(file_id=file_id)
    return stream.read()


def save_file(file_info: FileInfo, contents: bytes) -> Path:
    folder = Path().cwd() / "data" / "source-files" / file_info.parent_folder_name
    folder.mkdir(exist_ok=True, parents=True)
    file_path = folder / f"{file_info.file_name}"
    with open(file_path, "wb") as f:
        f.write(contents)
    return file_path


def parse_encounters(fpath: Path) -> list[tuple[int, str]]:
    pdf_reader = PdfReader(fpath)
    encounter_data: dict[int, list[str]] = defaultdict(list)
    encounter_count = 1
    for i, page in enumerate(pdf_reader.pages):
        text = str(page.extract_text())
        # skip checking first page
        if i == 0:
            encounter_data[encounter_count].append(text)
            continue
        if "Reason for Visit" in text:
            # increment
            encounter_count += 1
            encounter_data[encounter_count].append(text)
        else:
            # otherwise append
            encounter_data[encounter_count].append(text)
    return [(k, "\n".join(v)) for k, v in encounter_data.items()]


def load_template() -> str:
    with open(Path().cwd() / "resources" / "summary-template.md", "r") as f:
        template = f.read()
    return template


def summarize_encounter(
    client: ollama.Client,
    encounter_data: str,
    page_range: tuple[int, int],
) -> str:
    template = load_template()

    response = client.generate(
        model="llama3.2",
        prompt=f"""Given the following template: 
        
        {template}

        Fill out as much information as possible, retaining the template structure, by 
        examining the following data. Do not provide any supplemental commentary.

        {encounter_data}
        """,
    )
    result: str = response["response"]
    result += f"\n\nFound on pages: {page_range[0]}-{page_range[1]}"
    return result


def summarize_history(client: ollama.Client, history: list[str]) -> str:
    response = client.generate(
        model="llama3.2",
        prompt=f"""
        Summarize the following historical data:

        {"\n\t-\t".join(history)}
        """,
    )
    return response["response"]


class Encounter(BaseModel):
    num: int
    source_data: str
    summary: str


class Outcome(BaseModel):
    file_info: FileInfo
    history: list[Encounter]
    summary: str


def save_outcome(outcome: Outcome):
    folder = Path().cwd() / "data" / "outcomes" / outcome.file_info.parent_folder_name
    folder.mkdir(exist_ok=True, parents=True)
    file_path = folder / f"{outcome.file_info.file_name}.json"
    with open(file_path, "w") as f:
        json_data = outcome.model_dump_json(indent=2)
        f.write(json_data)


def markdown_to_docx_pandoc(outcome: Outcome, target_path: Path):
    with open("temp.md", "w") as f:
        f.write("\n# Patient Summary\n")
        f.write(outcome.summary + "\n")
        for encounter in outcome.history:
            f.write(f"\n## Encounter: {encounter.num}\n")
            f.write(encounter.summary + "\n\n")

    # use pandoc
    subprocess.run(["pandoc", "temp.md", "-o", "temp.docx"], check=True)

    # move to folder
    (Path().cwd() / "temp.docx").rename(target_path)

    # remove temp files
    (Path().cwd() / "temp.md").unlink()


def save_report(outcome: Outcome) -> Path:
    folder = Path().cwd() / "data" / "reports" / outcome.file_info.parent_folder_name
    folder.mkdir(exist_ok=True, parents=True)
    file_name = outcome.file_info.file_name.replace(".pdf", ".docx").replace(
        ".PDF", ".docx"
    )
    filepath = folder / file_name
    markdown_to_docx_pandoc(outcome=outcome, target_path=filepath)
    return filepath


def upload_file(client: BoxClient, report_path: Path, parent_folder_id: str):
    with open(report_path, "rb") as f:
        client.uploads.upload_file(
            attributes=UploadFileAttributes(
                name=report_path.name,
                parent=UploadFileAttributesParentField(id=parent_folder_id),
            ),
            file=f,
        )


def main():
    args, box_client, ollama_client = setup()
    logging.debug(args, box_client)
    if args.fresh:
        removed = remove_box_docx(client=box_client, folder_id=args.box_folder_id)
        logging.info(f"Removed {removed} DOCX files")
    files = fetch_box_pdfs(client=box_client, folder_id=args.box_folder_id)
    logging.info(f"Found {len(files)} to process")
    outcomes: list[Outcome] = []
    for item in files:
        logging.info(f"Downloading: {item.parent_folder_name} / {item.file_name}...")
        file_contents = download_box_file(client=box_client, file_id=item.file_id)
        fpath = save_file(file_info=item, contents=file_contents)
        logging.info(f"Saved source file: {item.parent_folder_name} / {item.file_name}")
        source_encounters = parse_encounters(fpath=fpath)
        encounters: list[Encounter] = []
        for enc_num, encounter in tqdm(source_encounters, leave=False):
            summary = summarize_encounter(
                client=ollama_client,
                encounter_data=encounter,
            )
            encounters.append(
                Encounter(num=enc_num, source_data=encounter, summary=summary)
            )
        history_summary = summarize_history(
            client=ollama_client,
            history=[e.summary for e in encounters],
        )
        outcome = Outcome(
            file_info=item,
            history=sorted(encounters, key=lambda x: x.num),
            summary=history_summary,
        )
        outcomes.append(outcome)
        logging.info("Saving outcome...")
        save_outcome(outcome=outcome)
        logging.info("Saving report...")
        report_path = save_report(outcome=outcome)
        logging.info(f"Saved to {report_path}")
        logging.info("Uploading report...")
        upload_file(
            client=box_client,
            report_path=report_path,
            parent_folder_id=outcome.file_info.parent_folder_id,
        )


if __name__ == "__main__":
    main()
