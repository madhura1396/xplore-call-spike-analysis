# Independent number-and-filter audit

Scripts used by the audit agent to check every number and filter in the Databricks App against SQL written
independently on the **bronze** tables. Full results and findings: [`../notes/app_test_report.md`](../notes/app_test_report.md).
Result tables from the run on 2026-10-04: [`results/filter_checks.csv`](results/filter_checks.csv) (filter matrix,
4,443 checks) and [`results/static_checks.csv`](results/static_checks.csv) (company-wide pages, drill-downs, pop-ups,
heatmap, hardcoded text, provenance).

| Script | What it does |
|---|---|
| `load_cache.py` | Loads the data once through the app's own `app/data.py` and caches it (`real.pkl`) |
| `harness.py` | Runs the real app headlessly (Streamlit AppTest) and extracts every displayed value |
| `run_default.py` | Unfiltered app values → `app_default.json` |
| `scenarios.py`, `run_filters.py` | 40 filter scenarios → `app_filters.json` |
| `qa_sql.py` | Independent bronze SQL and the app's display rules (rounding, noise test) |
| `compare_filters.py` | App vs SQL for every scenario → `filter_checks.csv` |
| `checks_static.py` | Company-wide pages, drill-downs, pop-ups, heatmap, hardcoded text, provenance → `static_checks.csv` |
| `reset_test.py` | Reset button and persistence after reset |

Run from this folder (needs the Databricks CLI profile used by `app/data.py` and `qa_sql.py`):

```bash
cd qa
../app/.venv/bin/python load_cache.py      # ~10 s
../app/.venv/bin/python run_default.py     # ~15 s
../app/.venv/bin/python run_filters.py     # ~45 s
../.venv/bin/python compare_filters.py     # ~6 min (SQL)
../.venv/bin/python checks_static.py       # ~1 min (SQL)
../app/.venv/bin/python reset_test.py
```
