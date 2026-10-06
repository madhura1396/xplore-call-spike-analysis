"""Q6 — What do transcripts and VOC feedback say about customer pain points?

Why Python (not an LLM): transcripts use 11 distinct texts and VOC verbatims 8 — exact counting is
precise and checkable; the dataset's own AI fields proved unreliable (A10, A11).

Data: gold.fct_calls (transcript text, call reason, repeat flag, resolution, sentiment, CSAT/NPS via VOC)
      + gold.fct_daily_volume (true totals, for weighting the uneven sample — same method as p4_drivers.py)
Before = 1–25 May · After = 26 May–30 Jun.
Outputs: outputs/phase6/  transcript_texts.csv, pain_points.csv, quotes.csv, voc_topics.csv, checks.csv

NOTE (first pass): this script defines 'after' as 26 May–30 Jun. After the two independent reviews, every
call-level comparison moved to 1–25 May vs June, because the 26–31 May sample still looks like May (A19).
Final numbers: analysis/review_walkthrough.py and the app (app/data.py, app/app.py).
"""
from pathlib import Path

import numpy as np
import pandas as pd

import db

OUT = Path(__file__).resolve().parents[1] / "outputs" / "phase6"
OUT.mkdir(parents=True, exist_ok=True)
SPLIT = pd.Timestamp("2026-05-26")
JUNE_NOTE = " June notes suggest increased regional instability, repeat troubleshooting contacts, and customer frustration."
pd.set_option("display.width", 230, "display.max_colwidth", 120, "display.max_columns", 20)

# ---------------------------------------------------------------- load + weight
calls = db.load("fct_calls")
texts = db.query("SELECT call_id, transcript_text FROM workspace.xplore_silver.stg_transcripts")
calls = calls.merge(texts, on="call_id", how="left")
daily = db.load("fct_daily_volume")
daily = daily[daily["call_date"] >= calls["call_date"].min()].copy()
daily["weight"] = daily["total_calls"] / daily["sampled_calls"]
calls = calls.merge(daily[["call_date", "weight"]], on="call_date")
calls["period"] = np.where(calls["call_date"] < SPLIT, "before", "after")
daily["period"] = np.where(daily["call_date"] < SPLIT, "before", "after")
DAYS = daily.groupby("period").size()

calls["has_june_note"] = calls["transcript_text"].str.contains("June notes", regex=False)
calls["core_text"] = calls["transcript_text"].str.replace(JUNE_NOTE, "", regex=False).str.strip()


def per_day(frame, by):
    """Weighted calls per day for each group of `by`, per period."""
    return frame.groupby([by, "period"])["weight"].sum().unstack(fill_value=0).div(DAYS)[["before", "after"]]


def wavg(frame, col):
    """Weighted average (NaN for an empty frame)."""
    return np.average(frame[col], weights=frame["weight"]) if len(frame) else np.nan


# ---------------------------------------------------------------- 1. transcript texts: frequency before vs after
tt = per_day(calls, "core_text")
tt["increase_per_day"] = tt["after"] - tt["before"]
tt["share_after_%"] = tt["after"] / tt["after"].sum() * 100
tt["sampled_calls"] = calls.groupby("core_text").size()
tt["with_june_note_after_%"] = (calls[calls["period"] == "after"].groupby("core_text")["has_june_note"].mean() * 100)
tt = tt.sort_values("after", ascending=False)
tt.round(1).to_csv(OUT / "transcript_texts.csv")

# ---------------------------------------------------------------- 2. pain-point scorecard per call reason (after period)
rows = []
for reason, g in calls.groupby("issue_type"):
    a, b = g[g["period"] == "after"], g[g["period"] == "before"]
    fa = a[a["has_feedback"]]
    rows.append({
        "pain_point": reason,
        "calls_per_day_before": b["weight"].sum() / DAYS["before"],
        "calls_per_day_after": a["weight"].sum() / DAYS["after"],
        "repeat_rate_%": wavg(a, "is_repeat_contact") * 100,
        "follow_up_required_%": wavg(a.assign(f=a["resolution_status"].eq("Follow-up required")), "f") * 100,
        "resolved_on_call_%": wavg(a.assign(f=a["resolution_status"].eq("Resolved on call")), "f") * 100,
        "negative_sentiment_%": wavg(a, "is_negative_sentiment") * 100,
        "avg_duration_min": wavg(a, "call_duration_minutes"),
        "avg_csat": wavg(fa, "csat_score"),
        "detractor_%": wavg(fa, "is_detractor") * 100,
        "june_instability_note_%": wavg(a, "has_june_note") * 100,
        "feedback_n": len(fa),
    })
pp = pd.DataFrame(rows).set_index("pain_point")
pp["increase_per_day"] = pp["calls_per_day_after"] - pp["calls_per_day_before"]
pp["pct_change_%"] = (pp["calls_per_day_after"] / pp["calls_per_day_before"] - 1) * 100
pp = pp.sort_values("increase_per_day", ascending=False)
overall_after = calls[calls["period"] == "after"]
pp.loc["ALL CALLS (after)"] = {
    "calls_per_day_before": calls.loc[calls["period"] == "before", "weight"].sum() / DAYS["before"],
    "calls_per_day_after": overall_after["weight"].sum() / DAYS["after"],
    "repeat_rate_%": wavg(overall_after, "is_repeat_contact") * 100,
    "follow_up_required_%": wavg(overall_after.assign(f=overall_after["resolution_status"].eq("Follow-up required")), "f") * 100,
    "resolved_on_call_%": wavg(overall_after.assign(f=overall_after["resolution_status"].eq("Resolved on call")), "f") * 100,
    "negative_sentiment_%": wavg(overall_after, "is_negative_sentiment") * 100,
    "avg_duration_min": wavg(overall_after, "call_duration_minutes"),
    "avg_csat": wavg(overall_after[overall_after["has_feedback"]], "csat_score"),
    "detractor_%": wavg(overall_after[overall_after["has_feedback"]], "is_detractor") * 100,
    "june_instability_note_%": wavg(overall_after, "has_june_note") * 100,
    "feedback_n": int(overall_after["has_feedback"].sum()),
}
pp.round(1).to_csv(OUT / "pain_points.csv")

# ---------------------------------------------------------------- 3. representative quotes (most frequent text per top reason, after)
top_reasons = pp.drop("ALL CALLS (after)").head(4).index
quotes = []
for reason in top_reasons:
    a = calls[(calls["issue_type"] == reason) & (calls["period"] == "after")]
    full = a.groupby("transcript_text")["weight"].sum().sort_values(ascending=False)
    quotes.append({"pain_point": reason, "transcript_quote": full.index[0],
                   "share_of_reason_calls_%": full.iloc[0] / full.sum() * 100,
                   "voc_verbatim": a["verbatim_comment"].dropna().mode().iloc[0] if a["verbatim_comment"].notna().any() else ""})
quotes = pd.DataFrame(quotes)
quotes.round(1).to_csv(OUT / "quotes.csv", index=False)

# ---------------------------------------------------------------- 4. VOC by topic (CSAT before vs after)
fb = calls[calls["has_feedback"]]
voc = fb.groupby(["issue_type", "period"]).apply(
    lambda g: pd.Series({"avg_csat": wavg(g, "csat_score"), "detractor_%": wavg(g, "is_detractor") * 100, "n": len(g)}),
    include_groups=False).unstack("period")
voc.round(2).to_csv(OUT / "voc_topics.csv")

# ---------------------------------------------------------------- CHECKS
checks = []
def check(name, ok, detail=""):
    """Record a reconciliation check and stop the script if it fails."""
    checks.append({"check": name, "passed": bool(ok), "detail": detail}); assert ok, f"FAILED: {name} {detail}"

check("750 calls, every call has transcript text", len(calls) == 750 and calls["transcript_text"].notna().all())
check("11 distinct transcript texts", calls["transcript_text"].nunique() == 11, str(calls["transcript_text"].nunique()))
check("8 core texts once the June note is removed", calls["core_text"].nunique() == 8, str(calls["core_text"].nunique()))
check("June note never appears before 26 May", not calls.loc[calls["period"] == "before", "has_june_note"].any())
check("transcript text counts sum to true calls/day after",
      abs(tt["after"].sum() - daily.loc[daily["period"] == "after", "total_calls"].sum() / DAYS["after"]) < 1e-6)
# each core text belongs to exactly one call reason → transcript text agrees with issue_type
agree = calls.groupby("core_text")["issue_type"].nunique()
check("each transcript text maps to exactly one call reason", (agree == 1).all(), agree.to_dict().__str__()[:200])
check("scorecard calls/day (after) sum to the overall figure",
      abs(pp.drop("ALL CALLS (after)")["calls_per_day_after"].sum() - pp.loc["ALL CALLS (after)", "calls_per_day_after"]) < 1e-6)
pd.DataFrame(checks).to_csv(OUT / "checks.csv", index=False)

# ---------------------------------------------------------------- print
print("── 1. Transcript texts, most frequent after 26 May (est. calls/day) " + "─" * 40)
print(tt[["before", "after", "increase_per_day", "share_after_%", "with_june_note_after_%"]].round(1).to_string(), "\n")
print("── 2. Pain-point scorecard (after period unless stated) " + "─" * 50)
cols = ["calls_per_day_before", "calls_per_day_after", "pct_change_%", "repeat_rate_%", "follow_up_required_%",
        "resolved_on_call_%", "negative_sentiment_%", "avg_csat", "detractor_%", "june_instability_note_%", "feedback_n"]
print(pp[cols].round(1).to_string(), "\n")
print("── 3. Representative quotes " + "─" * 80)
for _, q in quotes.iterrows():
    print(f"[{q.pain_point}] ({q['share_of_reason_calls_%']:.0f}% of these calls)\n   Transcript: {q.transcript_quote}\n   VOC:        {q.voc_verbatim}\n")
print("── 4. VOC: CSAT and detractors by call reason, before vs after " + "─" * 40)
print(voc.round(2).to_string(), "\n")
print("── Checks " + "─" * 90)
print(pd.DataFrame(checks)[["check", "passed"]].to_string(index=False))
print(f"\nALL {len(checks)} CHECKS PASSED")
