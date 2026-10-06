# Technical Call Spike Monitor (Databricks App · Streamlit)

A multipage app for Customer Care leaders: what happened to technical calls, what drove it, why, what customers say
and what to monitor. It reads the gold layer in Unity Catalog live through a SQL warehouse.

**Live:** https://call-spike-monitor-7474647701694312.aws.databricksapps.com (Databricks sign-in required; Databricks
Apps cannot be made public, and on Free Edition an app stops 24 hours after it was last started).

## Pages

Menu across the top (Summary · KPIs · Drivers · Root cause · Voice · Monitor · Notes); the sidebar holds the filters
(only on KPIs, Drivers and Voice; they stay set when you change page), a **Refresh data** button and the time the data
was loaded. Charts are fixed (no accidental pan or zoom) and the data stays loaded between visits.

| Page | What you see | How to interact |
|---|---|---|
| **Summary** | Headline; 4 key numbers as pre-spike → post-spike (1–25 May → June); cards: what drove it · why · what customers say · what to do | Each number card opens a before-vs-after pop-up with what the change means; the other cards link to the matching page. Company-wide (not filtered) |
| **KPIs** | One-line verdict and a status table of 8 KPIs: status, pre-spike → post-spike, change, weekly sparkline | Tick the box at the left of a row, or pick a KPI in “Open details for”: pop-up with the status, pre/post/trend and the weekly chart |
| **Drivers** (what drove it) | Pre- vs post-spike calls per day for the chosen breakdown, a one-line takeaway, drill-down panel, region × reason heatmap | Pick “Break down by” in the sidebar; click a bar (or use “Drill into”) to drill in |
| **Root cause** | Suspect 1 (firmware 3.8.1, device telemetry) vs suspect 2 (a nationwide change, BC + Atlantic share test) and the 4 data gaps | Company-wide (not filtered) |
| **Voice** (customer voice) | Pain points per call reason: calls per day, change, weekly sparkline, repeats, follow-ups, negative sentiment, CSAT | Tick a row's box or pick a reason in “Open details for”: pop-up with that reason's numbers, its most common call summaries and the agent-note share |
| **Monitor** | Company-wide status as of the latest data (30 Jun): what's at stake (repeat calls, agent hours, days above the alert line), three alert cards, daily and weekly charts | Move the alert lines in the sidebar (defaults from the deck: 96 calls a day, 18% repeats). Filters don't apply |
| **Notes** (data notes) | Method, noise check, proxies, gaps, excluded fields | |

**Filters:** dates · region · firmware update in region · reason for calling · (more) platform, product, customer
segment, channel · Reset.

**KPIs:** calls per day · connection problems (“No Internet” + “Slow Speed” share) · repeat calls · follow-up needed ·
average call duration · agent hours per day · technician visits per day (proxy) · CSAT. Negative sentiment is shown per
call reason on Customer voice.

## How the numbers are built

- **Re-weighting:** call details were provided for only ~10% of calls (`call_volume_daily` has the true daily totals);
  each sampled call is scaled by *true calls that day ÷ sampled calls that day* (`data.py`), so unfiltered estimates
  match the true daily totals exactly.
- **Pre-spike vs post-spike:** daily totals split at 26 May; call-level comparisons use 1–25 May vs June (26–31 May is
  left out because its sampled calls still look like May; assumption A19 in `notes/assumptions.md`).
- **Noise check:** a change counts only if it exceeds two standard errors (the sampling error) and rests on ≥10
  sampled calls (≥10 surveys for CSAT) on each side; 10–29 is marked “small sample” (direction clear, size
  approximate). Otherwise the app shows “Within noise” or “Too few calls to tell”. Trends compare the first two with
  the last two post-spike weeks using the same test.
- **Proxies, labelled in the app:** technician visits = calls ending in “Technician scheduled” (`truck_rolls` not
  provided); firmware filter = whether the caller's region had a logged update (no firmware version on calls).

## Files

| File | Purpose |
|---|---|
| `app.py` | Pages, navigation, filters, KPIs, charts, pop-ups |
| `data.py` | Data access (SQL warehouse when deployed, Databricks CLI locally), weights, periods, derived flags |
| `test_app.py` | Headless test (Streamlit AppTest, real data): every page under 12 filter scenarios, all pop-ups, drill-downs, sliders, reset, filters kept across pages. Not deployed |
| `app.yaml` | Start command + SQL warehouse resource (`valueFrom: sql-warehouse`) |
| `requirements.txt` | `streamlit==1.38.0` (the tested version), plotly, databricks-sql-connector, databricks-sdk |
| `.streamlit/config.toml` | Theme: light, blue accent |

**Data:** `workspace.xplore_gold` (`fct_calls`, `fct_daily_volume`, `dim_region`, `fct_device_health`) and
`workspace.xplore_silver.stg_transcripts`. The app's service principal has `USE CATALOG` on `workspace` and
`USE SCHEMA` + `SELECT` on `xplore_gold` and `xplore_silver` only.

## Run locally

```bash
python3.11 -m venv app/.venv && app/.venv/bin/pip install -r app/requirements.txt pandas numpy
app/.venv/bin/streamlit run app/app.py --theme.base light --theme.primaryColor "#2E6DB4"
```

Locally, `data.py` queries through the Databricks CLI: set `LOCAL_PROFILE` and `LOCAL_WAREHOUSE` at the top of
`data.py` to your profile and SQL warehouse id.

## Test (before every deploy)

```bash
app/.venv/bin/python app/test_app.py
```

Expect `FAILURES: 0`.

## Deploy

First time only: `databricks apps create call-spike-monitor -p <profile>`, add the SQL warehouse as an app resource
named `sql-warehouse` (CAN_USE), and grant the app's service principal read access to the two schemas. Then, for every
release, upload only the five deployed files (never `.venv`) and deploy:

```bash
mkdir -p /tmp/stage/.streamlit
cp app/app.py app/data.py app/app.yaml app/requirements.txt /tmp/stage/
cp app/.streamlit/config.toml /tmp/stage/.streamlit/
databricks workspace import-dir /tmp/stage /Workspace/Users/<you>/call-spike-monitor --overwrite -p <profile>
databricks apps deploy call-spike-monitor --source-code-path /Workspace/Users/<you>/call-spike-monitor -p <profile>
databricks apps logs call-spike-monitor -p <profile> --tail-lines 50
```

To share the app, open it in the workspace (Compute → Apps), click **Share** and give a user **CAN USE**.
