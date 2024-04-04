"""Runs metamap on the dataset.

This script runs metamap on the dataset and saves the output to a file.
"""
import subprocess
from pathlib import Path
from typing import TypedDict
import warnings

import polars as pl
import orjson
from rich import print
from tqdm.rich import tqdm

warnings.filterwarnings("ignore")


PREPPED_DIR = Path().cwd() / "data" / "prepped"
PROCESSED_DIR = Path().cwd() / "data" / "processed"

PROCESSED_DIR.mkdir(parents=True, exist_ok=True)


class MetaMapInput(TypedDict):
    """The type of the input to metamap."""

    identifier: str
    """The identifier of the row in the dataset."""
    text: str
    """The text to run metamap on."""


class MetaMapResult(TypedDict):
    """The type of the output of metamap."""

    identifier: str
    """The identifier of the row in the dataset."""
    result: str
    """The output of metamap (the fielded MMI string).
    
    This should be only ONE MMI line thus representing one concept.
    """


def load_dataset(path: Path, target_column: str) -> list[MetaMapInput]:
    """Loads the dataset.

    Args:
        path (Path): The path to the dataset.
        target_column (str): The column to run metamap on.

    Returns:
        list[MetaMapInput]: A list of data to input to metamap.
    """
    data = (
        pl.scan_csv(
            path,
            low_memory=False,
        )
        .select(["ccmeo_case", target_column])
        .drop_nulls(subset=[target_column])
        .collect()
        .to_dicts()
    )
    return [
        {"identifier": item["ccmeo_case"], "text": item[target_column]} for item in data
    ]


def metamap(text: str) -> str | None:
    """Runs metamap on the given text. Guaranteed to not be null.

    Args:
        text (str): The text to run metamap on.

    Returns:
        str | None: The output of metamap without header line.
    """
    if text == "":
        return None
    command = [
        "/Users/nick/public_mm/bin/metamap",
        "-Ny",  # fielded MMI with word sense disambiguation
        "--silent",  # don't print header
        "-R",
        "SNOMEDCT_US",  # restrict to SNOMEDCT_US
    ]
    pipeline = subprocess.Popen(
        command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT
    )
    result = pipeline.communicate(input=text.encode("utf-8"))[0]
    string_result = result.decode("utf-8")
    end_header = "SNOMEDCT_US"
    end_header_index = string_result.find(end_header)
    if end_header_index == -1:
        # no metamap output
        return None
    formatted_result = string_result[end_header_index + len(end_header) + 1 :].strip()
    return formatted_result


def expand_metamap_result(mmi_str: str, identifier: str) -> list[MetaMapResult]:
    results: list[MetaMapResult] = []
    for line in mmi_str.strip().split("\n"):
        data: MetaMapResult = {
            "identifier": identifier,
            "result": line,
        }
        results.append(data)
    return results


def main():
    """Runs the script."""
    print("[red][bold]WARNING:[/bold] MAKE SURE YOU HAVE STARTED THE METAMAP SERVERS")
    config = (
        (PREPPED_DIR / "combined.csv", "cause_of_death"),
        (PREPPED_DIR / "narratives.csv", "Brief History"),
        (PREPPED_DIR / "narratives.csv", "Scene Description Full"),
    )

    errors = []
    print("[cyan]Running metamap...")
    with open(PROCESSED_DIR / "metamap_results.jsonl", "wb") as f:
        for filepath, column in config:
            data = load_dataset(path=filepath, target_column=column)
            for row in tqdm(data, desc=f"Processing {filepath.name} -- {column}..."):
                output = metamap(row["text"])
                # filter out null metamap output
                if output is None or "ERROR" in output:
                    errors.append(output)
                    continue
                for result in expand_metamap_result(output, row["identifier"]):
                    f.write(orjson.dumps(result) + b"\n")
    print("[green]Done!")
    print(f"[red]Errors: {len(errors)}[/red]")
    for error in errors:
        print(error)


if __name__ == "__main__":
    main()
