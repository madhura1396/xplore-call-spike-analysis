"""Data access for the Technical Call Spike Monitor.

Single source of truth: gold views in Unity Catalog (workspace.xplore_gold) + transcript text from silver.
- In Databricks Apps: SQL warehouse via databricks-sql-connector, authenticated as the app's service principal
  (SDK Config() picks up the injected credentials; warehouse id comes from app.yaml valueFrom).
- Local development: queries run through the Databricks CLI (`xplore` profile), because the local
  ~/.databrickscfg cannot be parsed by the Python SDK at the moment.

Estimation method (same as analysis/p4_drivers.py): technical_calls is an uneven ~10% sample, so every sampled
call gets weight = true calls that day / sampled calls that day. Weighted sums reproduce the true daily totals.

Periods: daily totals split at 26 May (spike start). Call-level comparisons use 1–25 May vs June; 26–31 May is
'transition' and left out, because its sampled calls still look like May (assumption A19).
"""
import io
import os
import subprocess

import numpy as np
import pandas as pd
import streamlit as st

GOLD = "workspace.xplore_gold"
SILVER = "workspace.xplore_silver"
SPLIT = pd.Timestamp("2026-05-26")           # first day of the spike (analysis/p3_trend.py)
MIX_START = pd.Timestamp("2026-06-01")       # call-level "after" = June (A19)
CONNECTIVITY = ["No Internet", "Slow Speed"]
IN_DATABRICKS = bool(os.getenv("DATABRICKS_APP_NAME"))
LOCAL_PROFILE, LOCAL_WAREHOUSE = "xplore", "57a2634cf87879cc"


@st.cache_resource(ttl=300)
def _connection():
    """SQL warehouse connection for the deployed app, authenticated as the app's service principal (cached)."""
    from databricks import sql
    from databricks.sdk.core import Config

    cfg = Config()
    return sql.connect(
        server_hostname=cfg.host.replace("https://", ""),
        http_path=f"/sql/1.0/warehouses/{os.getenv('DATABRICKS_WAREHOUSE_ID')}",
        credentials_provider=lambda: cfg.authenticate,
    )


def _query(statement: str) -> pd.DataFrame:
    """Run SQL and return a DataFrame: SQL warehouse when deployed, Databricks CLI when run locally."""
    if IN_DATABRICKS:
        with _connection().cursor() as cur:
            cur.execute(statement)
            rows = cur.fetchall()
            return pd.DataFrame([tuple(r) for r in rows], columns=[c[0] for c in cur.description])
    out = subprocess.run(
        ["databricks", "experimental", "aitools", "tools", "query", statement,
         "-p", LOCAL_PROFILE, "--warehouse", LOCAL_WAREHOUSE, "--output", "csv"],
        capture_output=True, text=True, check=True).stdout
    return pd.read_csv(io.StringIO(out))


def _types(df: pd.DataFrame) -> pd.DataFrame:
    """Restore date and true/false columns (query results arrive as text)."""
    for col in df.columns:
        if col.endswith("_date") or col in ("week_start", "month_start", "call_month_start"):
            df[col] = pd.to_datetime(df[col])
        elif df[col].dtype == object and set(df[col].dropna().astype(str).str.lower().unique()) <= {"true", "false"}:
            df[col] = df[col].astype(str).str.lower().map({"true": True, "false": False})
    return df


def _mix_period(dates: pd.Series) -> np.ndarray:
    """Label each date before (1–25 May), transition (26–31 May, left out of call-level comparisons) or after (June)."""
    return np.select([dates < SPLIT, dates >= MIX_START], ["before", "after"], "transition")


@st.cache_data(ttl=None, show_spinner=False)   # static assessment data: load once; "Refresh data" reloads
def load() -> dict:
    """Load the gold tables once, attach transcripts, add sample weights, periods and derived flags, and assert that the weights reconcile to the true daily totals."""
    calls = _types(_query(f"SELECT * FROM {GOLD}.fct_calls"))
    daily = _types(_query(f"SELECT * FROM {GOLD}.fct_daily_volume"))
    regions = _types(_query(f"SELECT * FROM {GOLD}.dim_region"))
    devices = _types(_query(f"SELECT * FROM {GOLD}.fct_device_health"))
    texts = _query(f"SELECT call_id, transcript_text FROM {SILVER}.stg_transcripts")

    # weights: sample → true daily totals (only days covered by the call sample)
    covered = daily[daily["call_date"] >= calls["call_date"].min()].copy()
    covered["weight"] = covered["total_calls"] / covered["sampled_calls"]
    calls = calls.merge(covered[["call_date", "weight"]], on="call_date", how="left").merge(texts, on="call_id", how="left")

    calls["period"] = _mix_period(calls["call_date"])
    daily["period"] = np.where(daily["call_date"] < SPLIT, "before", "after")
    daily["mix_period"] = _mix_period(daily["call_date"])
    calls["is_connectivity"] = calls["issue_type"].isin(CONNECTIVITY)
    calls["is_resolved_on_call"] = calls["resolution_status"].eq("Resolved on call")
    calls["is_follow_up"] = calls["resolution_status"].eq("Follow-up required")
    calls["has_june_note"] = calls["transcript_text"].str.contains("June notes", regex=False, na=False)
    calls["core_text"] = calls["transcript_text"].str.split(" June notes").str[0]
    for col in ("is_repeat_contact", "is_negative_sentiment", "has_feedback", "is_detractor", "region_has_event"):
        calls[col] = calls[col].fillna(False).astype(bool)
    calls["is_technician"] = calls["resolution_status"].eq("Technician scheduled")      # dispatch proxy (no truck_rolls)
    calls["firmware_region"] = np.where(calls["region_has_event"], "Update logged", "No update")  # firmware proxy

    assert abs(calls.groupby("call_date")["weight"].sum()
               - covered.set_index("call_date")["total_calls"]).abs().max() < 1e-6, "weights do not reconcile"
    return {"calls": calls, "daily": daily, "regions": regions, "devices": devices}
