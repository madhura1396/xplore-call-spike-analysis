"""Location test — did the increase come from the regions that received firmware updates?

Data: fct_calls (sampled calls, with region) + fct_daily_volume (true daily totals) + stg_network_events.
Method (sample is uneven over time, A17 → re-weight):
  weight of each sampled call on day d = true_calls(d) / sampled_calls(d)
  estimated real calls for region r on day d = sum of weights of r's sampled calls on d
Compare estimated calls/day per region: before (1–25 May) vs after (26 May–30 Jun).
Firmware regions (Ontario, Prairies, Quebec) vs comparison regions (Atlantic, British Columbia).
Outputs: outputs/phase5/

NOTE (first pass): this script defines 'after' as 26 May–30 Jun. After the two independent reviews, every
call-level comparison moved to 1–25 May vs June, because the 26–31 May sample still looks like May (A19).
Final numbers: analysis/review_walkthrough.py and the app (app/data.py, app/app.py).
"""
import json
from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import db
from style import BLUE, NEUTRAL, ORANGE, TEXT, TEXT_2, source, subtitle

OUT = Path(__file__).resolve().parents[1] / "outputs" / "phase5"
OUT.mkdir(parents=True, exist_ok=True)
SPLIT = pd.Timestamp("2026-05-26")

calls = db.load("fct_calls")
daily = db.load("fct_daily_volume")
events = db.load("stg_network_events", db.SILVER)

# ---------------------------------------------------------------- re-weight the sample
daily = daily[daily["call_date"] >= calls["call_date"].min()].copy()
daily["weight"] = daily["total_calls"] / daily["sampled_calls"].replace(0, np.nan)
calls = calls.merge(daily[["call_date", "weight"]], on="call_date", how="left")
days_without_sample = int(daily["sampled_calls"].eq(0).sum())

calls["period"] = np.where(calls["call_date"] < SPLIT, "before", "after")
n_days = {"before": int((daily["call_date"] < SPLIT).sum()), "after": int((daily["call_date"] >= SPLIT).sum())}
event_regions = set(events["region"])
calls["group"] = np.where(calls["region"].isin(event_regions), "Firmware-update regions", "No-update regions")

# ---------------------------------------------------------------- per region: before vs after
reg = (calls.groupby(["region", "period"])
       .agg(sampled=("call_id", "size"), est_calls=("weight", "sum"))
       .reset_index())
reg["est_per_day"] = reg.apply(lambda r: r.est_calls / n_days[r.period], axis=1)
tbl = reg.pivot(index="region", columns="period", values=["est_per_day", "sampled"])
tbl.columns = [f"{a}_{b}" for a, b in tbl.columns]
tbl["increase_per_day"] = tbl["est_per_day_after"] - tbl["est_per_day_before"]
tbl["pct_change"] = (tbl["est_per_day_after"] / tbl["est_per_day_before"] - 1) * 100
tbl["share_of_increase_pct"] = tbl["increase_per_day"] / tbl["increase_per_day"].sum() * 100
tbl = tbl.join(events.set_index("region")[["event_date", "severity"]], how="left")
tbl["firmware_update"] = tbl["event_date"].notna()
tbl = tbl.sort_values("increase_per_day", ascending=False)

# within-period share (no weighting needed — shares inside one period)
share = pd.crosstab(calls["region"], calls["period"], normalize="columns")[["before", "after"]] * 100

# group level (firmware vs no-update) = simple difference-in-differences
grp = (calls.groupby(["group", "period"])["weight"].sum().unstack()[["before", "after"]]
       .div(pd.Series(n_days))[["before", "after"]])
grp["pct_change"] = (grp["after"] / grp["before"] - 1) * 100
grp["increase_per_day"] = grp["after"] - grp["before"]

# ---------------------------------------------------------------- weekly estimated calls per region
calls["week_start"] = calls["call_date"] - pd.to_timedelta(calls["call_date"].dt.weekday, unit="D")
wk = calls.groupby(["week_start", "region"])["weight"].sum().unstack(fill_value=0)
wk_days = daily.assign(week_start=daily["call_date"] - pd.to_timedelta(daily["call_date"].dt.weekday, unit="D")) \
               .groupby("week_start").size()
wk_per_day = wk.div(wk_days, axis=0)
full_weeks = wk_days[wk_days == 7].index
wk_per_day = wk_per_day.loc[wk_per_day.index.isin(full_weeks)]

# ---------------------------------------------------------------- save
tbl.round({c: 2 for c in tbl.select_dtypes('number').columns}).to_csv(OUT / "region_before_after.csv")
grp.round(2).to_csv(OUT / "group_before_after.csv")
wk_per_day.round(1).to_csv(OUT / "region_weekly_est_per_day.csv")
(OUT / "metrics.json").write_text(json.dumps({
    "split": str(SPLIT.date()), "days_before": n_days["before"], "days_after": n_days["after"],
    "days_without_sample": days_without_sample,
    "sampled_calls_before": int((calls["period"] == "before").sum()),
    "sampled_calls_after": int((calls["period"] == "after").sum()),
    "group": grp.round(1).to_dict(orient="index"),
    "share_pct": share.round(1).to_dict(orient="index"),
}, indent=2, default=str))

# ================================================================ CHARTS
order = tbl.index.tolist()

# R1 — estimated calls/day by region, before vs after (paired bars)
fig, ax = plt.subplots(figsize=(10, 4.6))
x = np.arange(len(order)); w = 0.36
ax.bar(x - w / 2 - 0.01, tbl["est_per_day_before"], w, color=NEUTRAL, label="Before (1–25 May)", zorder=2)
ax.bar(x + w / 2 + 0.01, tbl["est_per_day_after"], w, color=BLUE, label="After (26 May–30 Jun)", zorder=2)
for i, r in enumerate(tbl.itertuples()):
    ax.text(i + w / 2, r.est_per_day_after + 1.2, f"{r.pct_change:+.0f}%", ha="center", va="bottom",
            fontsize=9, color=TEXT, fontweight="bold")
labels = [f"{r}\n{'firmware ' + tbl.loc[r, 'event_date'].strftime('%d %b') if tbl.loc[r, 'firmware_update'] else 'no update'}"
          for r in order]
ax.set_xticks(x, labels)
ax.set_ylabel("Estimated calls per day")
ax.set_ylim(0, tbl["est_per_day_after"].max() * 1.2)
ax.legend(loc="upper right", fontsize=8.5)
top = tbl.index[0]
ax.set_title("Calls rose by a similar amount in every region — including the two with no firmware update", pad=22)
subtitle(ax, "Estimated real technical calls per day by region (sample re-weighted to true daily totals) · label = % change")
source(fig)
fig.savefig(OUT / "r1_region_before_after.png"); plt.close(fig)

# R2 — share of the increase by region
fig, ax = plt.subplots(figsize=(10, 3.8))
s = tbl["share_of_increase_pct"][::-1]
colors = [BLUE if tbl.loc[r, "firmware_update"] else NEUTRAL for r in s.index]
ax.barh(s.index, s.values, color=colors, height=0.55, zorder=2)
for i, v in enumerate(s.values):
    ax.text(v + 0.8, i, f"{v:.0f}%", va="center", fontsize=9, color=TEXT)
ax.grid(axis="y", visible=False); ax.grid(axis="x", visible=True)
ax.set_xlabel("% of the total increase in calls per day")
ax.set_xlim(0, s.max() * 1.2)
fw_share = tbl.loc[tbl["firmware_update"], "share_of_increase_pct"].sum()
fw_base = share.loc[list(event_regions), "before"].sum()
ax.set_title(f"Firmware-update regions supplied {fw_share:.0f}% of the increase — about their normal {fw_base:.0f}% share of calls", pad=22)
subtitle(ax, "Each region's share of the extra calls per day (after − before) · blue = firmware update, grey = no update")
source(fig)
fig.savefig(OUT / "r2_share_of_increase.png"); plt.close(fig)

# R3 — weekly estimated calls/day per region, with each region's event date
fig, ax = plt.subplots(figsize=(11, 4.8))
palette = {"Ontario": BLUE, "Prairies": ORANGE, "Quebec": "#1baf7a",
           "Atlantic": "#a3a29c", "British Columbia": "#52514e"}
for r in order:
    ls = "-" if r in event_regions else (0, (4, 3))
    ax.plot(wk_per_day.index, wk_per_day[r], color=palette[r], lw=2, ls=ls, marker="o", ms=5, label=r)
    ax.text(wk_per_day.index[-1] + pd.Timedelta(days=1), wk_per_day[r].iloc[-1], r, color=TEXT_2,
            fontsize=8, va="center")
ax.axvline(SPLIT, color=TEXT_2, lw=0.8)
ax.text(SPLIT, 2, " 26 May", color=TEXT_2, fontsize=8)
ax.xaxis.set_major_formatter(mdates.DateFormatter("%d %b"))
ax.set_xticks(wk_per_day.index)
ax.set_xlim(wk_per_day.index[0] - pd.Timedelta(days=2), wk_per_day.index[-1] + pd.Timedelta(days=10))
ax.set_ylim(0, wk_per_day.values.max() * 1.15)
ax.set_ylabel("Estimated calls per day (weekly avg)")
ax.legend(loc="upper left", fontsize=8, ncol=5)
ax.set_title("Week by week, all five regions step up together around 26 May — no clear firmware-only pattern", pad=22)
subtitle(ax, "Estimated real calls per day by region, complete weeks only (Mon start) · small sample before 26 May — read as direction, not precision")
source(fig)
fig.savefig(OUT / "r3_region_weekly.png"); plt.close(fig)

# ---------------------------------------------------------------- console
pd.set_option("display.width", 200)
print(tbl[["firmware_update", "event_date", "sampled_before", "sampled_after", "est_per_day_before",
           "est_per_day_after", "increase_per_day", "pct_change", "share_of_increase_pct"]].round(1).to_string())
print("\nGroup (difference-in-differences):\n", grp.round(1).to_string())
print("\nWithin-period share of sampled calls (%):\n", share.round(1).to_string())
print("\nWeekly est calls/day:\n", wk_per_day.round(1).to_string())
print("days without sample:", days_without_sample)
