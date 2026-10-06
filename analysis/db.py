"""Load tables from Databricks into pandas.

Single source of truth = the gold/silver views in Unity Catalog, queried on the
Serverless Starter Warehouse through the Databricks CLI (`xplore` profile).

Why the CLI and not databricks-sql-connector: ~/.databrickscfg currently contains a malformed
profile that the Python SDK cannot parse. Once it is removed, `query()` can be swapped for
databricks.sql.connect(...) without changing any analysis script.
"""
import io
import subprocess

import pandas as pd

PROFILE = "xplore"
WAREHOUSE_ID = "57a2634cf87879cc"
GOLD = "workspace.xplore_gold"
SILVER = "workspace.xplore_silver"

DATE_COLS = ("date_key", "week_start", "month_start", "call_month_start")


def query(statement: str) -> pd.DataFrame:
    """Run SQL on the warehouse and return a DataFrame (types parsed)."""
    out = subprocess.run(
        ["databricks", "experimental", "aitools", "tools", "query", statement,
         "-p", PROFILE, "--warehouse", WAREHOUSE_ID, "--output", "csv"],
        capture_output=True, text=True, check=True,
    ).stdout
    df = pd.read_csv(io.StringIO(out))
    for col in df.columns:
        if col.endswith("_date") or col in DATE_COLS:
            df[col] = pd.to_datetime(df[col])
        elif df[col].dtype == object and set(df[col].dropna().unique()) <= {"true", "false"}:
            df[col] = df[col].map({"true": True, "false": False})
    return df


def load(table: str, schema: str = GOLD) -> pd.DataFrame:
    """Load a full table/view."""
    return query(f"SELECT * FROM {schema}.{table}")
