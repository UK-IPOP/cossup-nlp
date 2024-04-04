"""Prep the data for consumption by tools"""

from pathlib import Path
import polars as pl
from rich import print

SOURCE_DIR = Path().cwd() / "data" / "source"
PREPPED_DIR = Path().cwd() / "data" / "prepped"
PROCESSED_DIR = Path().cwd() / "data" / "processed"

def load_records() -> pl.DataFrame:
    """Load the records from the source file.

    Returns:
        pl.DataFrame: The records dataframe.
    """
    return pl.read_excel(
        SOURCE_DIR / "CuyahogaCountyOhioHe-Nick20192022_DATA_2023-08-29_0847.xlsx"
    ).with_columns(
        [
            # Remove non-ascii characters from the narrative column
            pl.col("cause_of_death").str.replace_all(r"[^\p{Ascii}]", "")
        ]
    )


def load_narratives() -> pl.DataFrame:
    """Load the narratives from the source file.

    Combines both narratives files. Remove a random empty column
    likely due to excel formatting and cell merging. Also renames
    "Case Num" to "ccmeo_case" to match the records dataframe.

    Returns:
        pl.DataFrame: The narratives dataframe.
    """
    return (
        pl.concat(
            [
                pl.read_excel(SOURCE_DIR / "2019 and 2020 Case Narratives.xlsx"),
                pl.read_excel(
                    SOURCE_DIR / "2021 and 2022 Overdose Case Narratives.xlsx"
                ),
            ],
            how="vertical",
        )
        .drop(columns=[""])
        .rename(
            {
                "Case Num": "ccmeo_case",
                "SScene Description Full": "Scene Description Full",
            }
        )
        .with_columns(
            [
                # Remove non-ascii characters from the narrative columns
                pl.col(pl.Utf8).str.replace_all(r"[^\p{Ascii}]", "")
            ]
        )
    )


def export_geospatial_data() -> None:
    """Export a subset of the records dataframe for geospatial analysis."""
    df = load_records().select(["ccmeo_case", "street", "city", "state", "zip"])
    df.write_csv(PREPPED_DIR / "geospatial.csv")




def categorize_age(x: str) -> str | None:
    """
    Parse out the text (years/months) from the age column and return a new column with the age category.

    Args:
        x: The age text

    Returns:
        str | None: The age category

    Raises:
        ValueError: If the age is negative
    """
    num, text = x.split(" ", 1)
    if "year" not in text:
        return None
    years = int(num)
    if years < 0:
        raise ValueError(f"Invalid age: {x}")
    elif years < 18:
        return "<18"
    elif years < 25:
        return "18-24"
    elif years < 35:
        return "25-34"
    elif years < 45:
        return "35-44"
    elif years < 55:
        return "45-54"
    elif years < 65:
        return "55-64"
    else:
        return "65+"


def categorize_race(x: str) -> str:
    """Simple function to combine a few known existing typos in race column.

    Args:
        x: Race text

    Returns:
        Cleaned text

    Raises:
        ValueError if the race is unknown
    """
    if x == "White":
        return "White"
    elif x == "Black":
        return "Black"
    elif "Asian" in x:
        return "Asian"
    elif "American Indian" in x:
        return "American Indian"
    elif "Native Hawaiian" in x:
        return "Native Hawaiian"
    else:
        raise ValueError(f"Unknown race: {x}.")


CCMEO_YEAR_MAP = {
    6: 2019,
    7: 2020,
    8: 2021,
    9: 2022,
}

FENTANYL_COLS = [
    "cod_drugs_all___87",
    "cod_drugs_all___1",
    "cod_drugs_all___3",
    "cod_drugs_all___79",
    "cod_drugs_all___21",
    "cod_drugs_all___98",
    "cod_drugs_all___99",
    "cod_drugs_all___101",
    "cod_drugs_all___108",
    "cod_drugs_all___115",
    "cod_drugs_all___22",
    "cod_drugs_all___30",
    "cod_drugs_all___127", 
    "cod_drugs_all___128",
    "cod_drugs_all___129",
    "cod_drugs_all___32",
    "cod_drugs_all___135",
    "cod_drugs_all___138",
    "cod_drugs_all___154",
    "cod_drugs_all___161",
    "cod_drugs_all___162",
    "cod_drugs_all___85",
    "cod_drugs_all___167", 
    "cod_drugs_all___168",
    "cod_drugs_all___173",
    "cod_drugs_all___188",
    "cod_drugs_all___211",
]


def export_matched_data() -> None:
    """Export a subset of the records dataframe for MatchIt analysis.
    
    This subset includes only the columns needed for MatchIt analysis using R MatchIT package.
    This data will be cleaned and will match the below case/control definition:
        - Case: Carfentanil involved (**not** other fentanyls)
        - Control: Other fentanyls (**not** carfentanil)
    """
    df = load_records().select(
        [
            pl.col("ccmeo_case"),
            pl.col("age").apply(categorize_age).alias("age_category"),
            pl.col("race").apply(categorize_race).alias("race_category"),
            pl.col("hispanic").alias("hispanic_category"),
            pl.col("gender").alias("gender_category"),
            # carfentanil column per drug lookup
            pl.col("cod_drugs_all___61").alias("case_control_category"),
            pl.col("ccmeo_year").map_dict(CCMEO_YEAR_MAP).alias("year_category"),
            # carfentanil NOT fentanyl -> case
            # fentanyl NOT carfentanil -> control
            pl.col("cod_drugs_all___61").alias("carfentanil_case"),
            pl.any_horizontal(FENTANYL_COLS).alias("fentanyl_control"),
            ]
        ).with_columns([
            pl.when(
                # * switch to carfentanil + fentanyl per @CDelcher
                pl.col("carfentanil_case").eq(1) & pl.col("fentanyl_control").eq(1),
            )
            .then(1)
            .when(
                pl.col("carfentanil_case").eq(0) & pl.col("fentanyl_control").eq(1),
            )
            .then(0)
            .otherwise(None)
            .alias("case_control_category")
        ]).drop(columns=["carfentanil_case", "fentanyl_control"]).filter(
            pl.col("case_control_category").is_not_null()
        )
    # ! this is out of place at this point, but its fine
    geo_data = pl.read_csv(PROCESSED_DIR / "residential_or_apartment.csv").filter(
        pl.col("Is_RESIDENTIAL_or_APARTMENT").eq(False)
    ).to_numpy().flatten().tolist()
    # filter where not in non-residential
    df = df.filter(~pl.col("ccmeo_case").is_in(geo_data))
    df.write_csv(PREPPED_DIR / "case_control_demographics.csv")


def export_nlp_data() -> None:
    """Export a subset of the records dataframe for NLP analysis.
    
    Export file with text columns and ME-Case ID for processing by MetaMap.
    """
    df = load_narratives()
    df.write_csv(PREPPED_DIR / "narratives.csv")


# ## Combined Data
# 
# Export one file with the merged records and narratives. This file should be cleaned as well (similar to matched-export above) and be ready for consumption by post-processing analysis.

def export_merged_data() -> None:
    """Export one file with merged records and narratives.
    
    This will also contain cleaned data similar to what is done for the MatchIt export.
    """
    lookup = pl.read_csv(SOURCE_DIR / "drug_column_lookup.csv").sort(by="id", descending=True)
    column_map: dict[str, str] = {}
    # because sorted, we should have more recent rows first
    # so can ignore the three duplicate rows
    for item in lookup.to_dicts():
        if item["drug_name"] in column_map.values():
            continue
        column_map[item["row_name"]] = item["drug_name"]
    records = (
        load_records()
        .with_columns(
            [
                pl.col("age").apply(categorize_age).alias("age_category"),
                pl.col("race").apply(categorize_race).alias("race_category"),
                pl.col("hispanic").alias("hispanic_category"),
                pl.col("gender").alias("gender_category"),
                # carfentanil NOT fentanyl -> case
                # fentanyl NOT carfentanil -> control
                pl.col("cod_drugs_all___61").alias("carfentanil_case"),
                pl.any_horizontal(FENTANYL_COLS).alias("fentanyl_control"),
                pl.col("ccmeo_year").map_dict(CCMEO_YEAR_MAP).alias("year_category"),
            ]
        )
        .with_columns([
            pl.when(
                pl.col("carfentanil_case").eq(1) & pl.col("fentanyl_control").eq(0),
            )
            .then(1)
            .when(
                pl.col("carfentanil_case").eq(0) & pl.col("fentanyl_control").eq(1),
            )
            .then(0)
            .otherwise(None)
            .alias("case_control_category")
        ])
        .rename(column_map)
    )
    narratives = load_narratives()
    df = records.join(narratives, on="ccmeo_case", how="left", validate="1:1")
    df.write_csv(PREPPED_DIR / "combined.csv")


def main() -> None:
    """Run all the data prep steps."""
    export_geospatial_data()
    export_matched_data()
    export_nlp_data()
    export_merged_data()


if __name__ == "__main__":
    main()
