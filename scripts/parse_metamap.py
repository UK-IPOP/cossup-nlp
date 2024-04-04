"""Parse MetaMap output."""
from pathlib import Path
from typing import TypedDict
import orjson
from rich import print
from tqdm.rich import tqdm
import warnings


warnings.filterwarnings("ignore")


DATA_DIR = Path().cwd() / "data"
KNOWLEDGE_BASE_DIR = Path().cwd().parent / "knowledge_base_data"
PROCESSED_DIR = Path().cwd() / "data" / "processed"


# copied from `run_metamap.py`
class MetaMapResult(TypedDict):
    """The type of the output of metamap."""

    identifier: str
    """The identifier of the row in the dataset."""
    result: str
    """The output of metamap (the fielded MMI string).
    
    This should be only ONE MMI line thus representing one concept.
    """


# def load_snomed_name_map() -> dict[str, str]:
#     """Load SNOMED CT names and return a map from concept ID to name.

#     Returns:
#         dict[str, str]: Map from concept ID to name
#     """
#     print("[cyan]Loading SNOMED CT name map...[/cyan]")
#     mapper = {}
#     with open(DATA_DIR / "snomed.jsonl", "r") as f:
#         for line in tqdm(f):
#             line_data = orjson.loads(line)
#             mapper[line_data["concept_id"]] = line_data["canonical_name"]
#     return mapper


def load_cui_to_snomed_map() -> dict[str, str]:
    """Load MRCONSO.RRF and return a map from CUI to SNOMED CT ID.

    Returns:
        dict[str, str]: Map from CUI to SNOMED CT ID
    """
    print("[cyan]Loading CUI to SNOMED CT map...[/cyan]")
    mapper: dict[str, str] = {}
    with open(KNOWLEDGE_BASE_DIR / "MRCONSO.RRF", "r") as f:
        for line in tqdm(f.readlines()):
            parts = line.strip().split("|")
            # active concept and preferred term and not obsolete
            if parts[11] == "SNOMEDCT_US" and parts[12] == "FN":
                mapper[parts[0]] = parts[13]
    return mapper


def load_concept_children() -> dict[str, set[str]]:
    """Load SNOMED CT relationships and return a map from concept to children.

    Returns:
        dict[str, set[str]]: Map from concept to children
    """
    print("[cyan]Loading concept children...[/cyan]")
    mapper: dict[str, set[str]] = {}
    with open(
        KNOWLEDGE_BASE_DIR
        / "SnomedCT_USEditionRF2_PRODUCTION_20220901T120000Z"
        / "Snapshot"
        / "Terminology"
        / "sct2_Relationship_Snapshot_US1000124_20220901.txt",
        "r",
    ) as f:
        for line in tqdm(f.readlines()):
            parts = line.split("\t")
            # active concept and "is a" relationship
            if parts[2] == "1" and parts[7] == "116680003":
                source = parts[4]
                target = parts[5]
                if target not in mapper:
                    mapper[target] = set()
                mapper[target].add(source)
    return mapper


def get_children(
    node: str, lookup: dict[str, set[str]], children: set[str]
) -> set[str]:
    """Get children of a node in a lookup.

    Args:
        node (str): Node to get children of
        lookup (dict[str, set[str]]): Lookup to use
        children (set[str]): Set to add children to

    Returns:
        set[str]: Set of children"""
    children.add(node)
    if node in lookup:
        for child in lookup[node]:
            children.add(child)
            get_children(node=child, lookup=lookup, children=children)
    return children


def get_all_children(targets: list[str]) -> dict[str, set[str]]:
    """Get all children of a list of targets.

    Args:
        targets (list[str]): List of targets

    Returns:
        dict[str, set[str]]: Map each target to its set of children
    """
    concept_children = load_concept_children()
    data = {}
    count = 0
    for target in targets:
        children = set()
        print(f"[cyan]Getting all children of {target}...[/cyan]")
        children = get_children(node=target, lookup=concept_children, children=children)
        data[target] = children
        count += len(children)
    print(f"[green]Found {count} children[/green]")
    return data


class CleanOutput(TypedDict):
    """Cleaned MetaMap data with only relevant fields."""

    identifier: str
    """The identifier of the row in the dataset."""
    name: str
    """The name of the concept."""
    sui: str
    """The SNOMED ID of the concept."""
    category: str
    """The category of the concept."""


TARGETS = {
    "284349006": "home premises",
    "364830008": "body position",
}


def main():
    """Runs the script."""
    print("[yellow]Setting up required lookups...[/yellow]")
    children = get_all_children(targets=list(TARGETS.keys()))
    cui_to_sui = load_cui_to_snomed_map()
    print("[yellow]Loading metamap results...[/yellow]")
    invalid_cuis: set[str] = set()
    with open(PROCESSED_DIR / "metamap_results.jsonl", "rb") as in_file:
        with open(PROCESSED_DIR / "metamap_results_parsed.jsonl", "wb") as out_file:
            for line in tqdm(in_file.readlines()):
                data: MetaMapResult = orjson.loads(line)
                fielded_mmi = data["result"].strip().split("|")
                name = fielded_mmi[3]
                cui = fielded_mmi[4]
                if cui not in cui_to_sui:
                    invalid_cuis.add(cui)
                    continue
                snomed_id = cui_to_sui[cui]
                for key, values in children.items():
                    if snomed_id in values:
                        category = TARGETS[key]
                        break
                else:
                    # not a child of any target
                    continue
                output: CleanOutput = {
                    "identifier": data["identifier"],
                    "name": name,
                    "sui": snomed_id,
                    "category": category,
                }
                out_file.write(orjson.dumps(output) + b"\n")
    print("[green]Done!")
    print(f"[red]Invalid CUIs: {len(invalid_cuis)}[/red]")
    # for cui in invalid_cuis:
    #     print(f"[red][bold]Invalid CUI:[/bold] {cui}[/red]")


if __name__ == "__main__":
    main()
