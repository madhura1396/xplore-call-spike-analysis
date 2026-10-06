"""Does transcripts.detected_theme (AI-generated) carry a usable signal?

Tests: (1) agreement with the call reason (issue_type) and with the transcript text itself,
(2) does the theme mix change before vs after 26 May (would it detect the spike?).
Output: outputs/phase6/theme_vs_issue.csv, theme_before_after.csv
"""
from pathlib import Path
import numpy as np
import pandas as pd
import db

OUT = Path(__file__).resolve().parents[1] / "outputs" / "phase6"
t = db.query("""
    SELECT c.call_id, c.call_date, c.issue_type, t.detected_theme, t.transcript_text
    FROM workspace.xplore_silver.stg_technical_calls c
    JOIN workspace.xplore_silver.stg_transcripts t USING (call_id)""")
t["period"] = np.where(pd.to_datetime(t["call_date"]) < "2026-05-26", "before", "after")

# theme a sensible reader would assign from the issue type
expected = {"No Internet": "Connectivity", "Outage Inquiry": "Connectivity", "Slow Speed": "Speed Performance",
            "Hardware Issue": "Equipment", "Wi-Fi Setup": "Equipment", "Service Appointment": "Appointments",
            "Billing Question": "Billing", "Account Access": "Portal/Login"}
t["expected_theme"] = t["issue_type"].map(expected)
agree = (t["detected_theme"] == t["expected_theme"]).mean() * 100
chance = (t["detected_theme"].value_counts(normalize=True) * t["expected_theme"].value_counts(normalize=True)
          .reindex(t["detected_theme"].value_counts().index).fillna(0)).sum() * 100

xt = pd.crosstab(t["issue_type"], t["detected_theme"])
xt.to_csv(OUT / "theme_vs_issue.csv")
same_text_themes = t.groupby("transcript_text")["detected_theme"].nunique()

mix = pd.crosstab(t["detected_theme"], t["period"], normalize="columns")[["before", "after"]] * 100
mix["shift_pp"] = mix["after"] - mix["before"]
mix.round(1).to_csv(OUT / "theme_before_after.csv")

print(f"Theme matches the call reason: {agree:.0f}% of calls   (pure chance would give ~{chance:.0f}%)\n")
print("Call reason (rows) vs AI detected_theme (columns):\n", xt.to_string(), "\n")
print("Distinct themes given to the SAME transcript text (11 texts):\n", same_text_themes.sort_values().to_string(), "\n")
print("Theme mix before vs after 26 May (% of sampled calls):\n", mix.round(1).to_string())
