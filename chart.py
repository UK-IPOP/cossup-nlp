import plotly.express as px
import pandas as pd


source = pd.read_csv("./data/processed/matched_case_controls.csv")

metamap = pd.read_json(
    "./data/processed/metamap_results_parsed.jsonl", orient="records", lines=True
)

df = pd.merge(source, metamap, left_on="ccmeo_case", right_on="identifier")

df = df[df["category"] == "body position"]
print(df)


groups = df.groupby(["name", "year_category"], as_index=False).size()
groups["year_category"] = groups["year_category"].astype(str)

fig = px.bar(
    groups,
    x="name",
    y="size",
    color="year_category",
    labels={"size": "Count", "name": "Body Position", "year_category": "Year"},
    title="Body Position by Year",
    barmode="group",
)

fig.show()
