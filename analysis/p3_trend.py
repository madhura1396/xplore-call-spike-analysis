"""Phase 3 — Q1 (did technical calls truly increase?) and Q2 (when did it begin?).

All data loaded from Databricks gold views; all calculations in pandas.
Outputs: outputs/phase3/  (charts .png, metrics.json, sensitivity.csv, daily_flags.csv)

Rules fixed BEFORE looking at the result:
  BASELINE   = 2026-04-01 .. (earliest network event - 8 days)  -> no event contamination
  THRESHOLD  = max(baseline_mean + 3*SD, baseline_mean * 1.20)
  SPIKE START= first day of the first run of >= 5 consecutive days above THRESHOLD
  POST       = spike start .. last day of data
"""
import json
from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import db
from style import BLUE, NEUTRAL, ORANGE, TEXT, TEXT_2, BAND, source, subtitle

OUT = Path(__file__).resolve().parents[1] / "outputs" / "phase3"
OUT.mkdir(parents=True, exist_ok=True)

K_SD, MIN_UPLIFT, RUN_DAYS = 3, 0.20, 5

# ---------------------------------------------------------------- load
daily = db.load("fct_daily_volume").sort_values("call_date").reset_index(drop=True)
events = db.load("stg_network_events", db.SILVER).sort_values("event_date")
calls = db.load("fct_calls")

first_event = events["event_date"].min()
baseline_end = first_event - pd.Timedelta(days=8)
data_start, data_end = daily["call_date"].min(), daily["call_date"].max()

# ---------------------------------------------------------------- baseline + threshold
is_base = daily["call_date"] <= baseline_end
base = daily.loc[is_base, "total_calls"]
base_mean, base_sd = base.mean(), base.std(ddof=1)


def threshold(k_sd=K_SD, uplift=MIN_UPLIFT):
    """Spike threshold: the stricter of baseline mean + k × SD and baseline mean × (1 + uplift)."""
    return max(base_mean + k_sd * base_sd, base_mean * (1 + uplift))


def spike_start(thr, run_days=RUN_DAYS):
    """First day of the first run of >= run_days consecutive days above thr (after baseline)."""
    above = (daily["total_calls"] > thr) & ~is_base
    run_id = (above != above.shift()).cumsum()
    runs = daily[above].groupby(run_id[above])["call_date"].agg(["min", "count"])
    runs = runs[runs["count"] >= run_days]
    return runs["min"].iloc[0] if len(runs) else pd.NaT


THR = threshold()
START = spike_start(THR)
daily["above_threshold"] = daily["total_calls"] > THR
daily["period"] = np.select(
    [is_base, daily["call_date"] < START], ["baseline", "pre-spike gap"], "post")
post = daily[daily["period"] == "post"]

# ---------------------------------------------------------------- magnitude + persistence
post_mean = post["total_calls"].mean()
uplift_pct = (post_mean / base_mean - 1) * 100
excess_total = (post["total_calls"] - base_mean).sum()
slope_per_week = np.polyfit(np.arange(len(post)), post["total_calls"], 1)[0] * 7
first7, last7 = post["total_calls"].head(7).mean(), post["total_calls"].tail(7).mean()
days_above_in_post = int(post["above_threshold"].sum())
max_day = daily.loc[daily["total_calls"].idxmax()]

# last day before START + jump size
day_before = daily.loc[daily["call_date"] == START - pd.Timedelta(days=1), "total_calls"].iloc[0]
start_val = daily.loc[daily["call_date"] == START, "total_calls"].iloc[0]

# ---------------------------------------------------------------- artefact checks
# day-of-week pattern in baseline
dow = daily[is_base].groupby("day_name")["total_calls"].mean()
dow_cv = dow.std() / dow.mean() if dow.mean() else 0

# sample ratio stability (technical_calls covers May-Jun only)
in_sample = daily["call_date"] >= calls["call_date"].min()
smp = daily[in_sample].copy()
smp["sample_period"] = np.where(smp["call_date"] < START, "before spike", "post")
ratio_by_period = (smp.groupby("sample_period")[["sampled_calls", "total_calls"]].sum()
                   .assign(ratio=lambda d: d.sampled_calls / d.total_calls))
weekly_ratio = (smp.groupby("week_start")[["sampled_calls", "total_calls"]].sum()
                .assign(ratio=lambda d: d.sampled_calls / d.total_calls))
shape_corr = smp["sampled_calls"].corr(smp["total_calls"])

# channel mix before vs after (re-routing check), from the sample
calls["period"] = np.where(calls["call_date"] < START, "before spike", "post")
channel_mix = pd.crosstab(calls["channel"], calls["period"], normalize="columns").round(3)

# ---------------------------------------------------------------- sensitivity grid
rows = []
for k in (2, 3):
    for up in (0.10, 0.20, 0.30):
        for n in (3, 5, 7):
            t = threshold(k, up)
            rows.append({"k_sd": k, "min_uplift": up, "run_days": n,
                         "threshold": round(t, 1), "spike_start": spike_start(t, n)})
sens = pd.DataFrame(rows)
sens["days_vs_main_rule"] = (sens["spike_start"] - START).dt.days
sens.to_csv(OUT / "sensitivity.csv", index=False)

# ---------------------------------------------------------------- save metrics
metrics = {
    "data_range": [str(data_start.date()), str(data_end.date())],
    "baseline_window": [str(data_start.date()), str(baseline_end.date())],
    "baseline_days": int(is_base.sum()),
    "baseline_mean_calls_per_day": round(base_mean, 1),
    "baseline_sd": round(base_sd, 2),
    "threshold_calls_per_day": round(THR, 1),
    "spike_start": str(START.date()),
    "calls_day_before_start": int(day_before),
    "calls_on_start_day": int(start_val),
    "first_network_event": str(first_event.date()),
    "days_from_first_event_to_spike": int((START - first_event).days),
    "post_window": [str(START.date()), str(data_end.date())],
    "post_days": int(len(post)),
    "post_mean_calls_per_day": round(post_mean, 1),
    "uplift_pct": round(uplift_pct, 1),
    "excess_calls_total_post": int(round(excess_total)),
    "excess_calls_per_week": round(excess_total / len(post) * 7, 0),
    "post_days_above_threshold": days_above_in_post,
    "post_trend_calls_per_day_per_week": round(slope_per_week, 2),
    "post_first7_mean": round(first7, 1),
    "post_last7_mean": round(last7, 1),
    "peak_day": str(max_day["call_date"].date()),
    "peak_calls": int(max_day["total_calls"]),
    "baseline_day_of_week_cv": round(dow_cv, 3),
    "sample_ratio_before_spike": round(ratio_by_period.loc["before spike", "ratio"], 3),
    "sample_ratio_post": round(ratio_by_period.loc["post", "ratio"], 3),
    "sample_vs_total_daily_correlation": round(shape_corr, 3),
    "sensitivity_start_range": [str(sens["spike_start"].min().date()), str(sens["spike_start"].max().date())],
    "channel_mix": channel_mix.to_dict(),
}
(OUT / "metrics.json").write_text(json.dumps(metrics, indent=2, default=str))
daily.to_csv(OUT / "daily_flags.csv", index=False)

# ================================================================ CHARTS
ev_rows = list(events.itertuples())
date_fmt = mdates.DateFormatter("%d %b")


def mark_events(ax, y_text, labels=True):
    """Draw the logged firmware-update dates on a chart."""
    for i, e in enumerate(ev_rows):
        ax.axvline(e.event_date, color=ORANGE, lw=1, ls=(0, (3, 3)), zorder=1)
        if labels:
            ax.text(e.event_date, y_text - i * 0.055 * y_text, f" {e.region} FW update ({e.severity})",
                    color=TEXT_2, fontsize=7.5, va="top")


# C1 — daily trend with baseline, threshold, events, spike start
fig, ax = plt.subplots(figsize=(11, 4.6))
ax.axvspan(START, data_end + pd.Timedelta(days=0.5), color=BAND, alpha=0.45, lw=0, zorder=0)
ax.plot(daily["call_date"], daily["total_calls"], color=BLUE, lw=1.6, zorder=3, label="Daily technical calls")
ax.axhline(base_mean, color=NEUTRAL, lw=1.2, zorder=2)
ax.axhline(THR, color=NEUTRAL, lw=1, ls=(0, (4, 3)), zorder=2)
ax.text(data_start, base_mean - 3, f"Baseline {base_mean:.0f}/day", color=TEXT_2, fontsize=8, va="top")
ax.text(data_start, THR + 2, f"Threshold {THR:.0f}/day", color=TEXT_2, fontsize=8, va="bottom")
ymax = daily["total_calls"].max() * 1.18
mark_events(ax, ymax - 2)
ax.annotate(f"Spike starts {START:%d %b}\n{day_before} → {start_val} calls",
            xy=(START, start_val), xytext=(START - pd.Timedelta(days=24), start_val + 12),
            color=TEXT, fontsize=9, arrowprops=dict(arrowstyle="-", color=TEXT_2, lw=0.8))
ax.set_ylim(0, ymax)
ax.xaxis.set_major_formatter(date_fmt)
ax.set_ylabel("Calls per day")
ax.set_title(f"Technical calls jumped {uplift_pct:.0f}% from {START:%d %b} and stayed elevated", pad=22)
subtitle(ax, f"Daily technical calls, {data_start:%d %b}–{data_end:%d %b} 2026 · shaded = post-spike period · dashed orange = firmware events")
source(fig)
fig.savefig(OUT / "c1_daily_trend.png"); plt.close(fig)

# C2 — weekly totals, complete weeks only (partial weeks shown but muted + labelled)
wk = daily.groupby("week_start").agg(calls=("total_calls", "sum"), days=("total_calls", "size")).reset_index()
wk["complete"] = wk["days"] == 7
wk["post"] = wk["week_start"] + pd.Timedelta(days=6) >= START
fig, ax = plt.subplots(figsize=(11, 4.2))
for r in wk.itertuples():
    color = (BLUE if r.post else NEUTRAL) if r.complete else "#e4e3df"
    ax.bar(r.week_start, r.calls, width=5.6, color=color, zorder=2)
    ax.text(r.week_start, r.calls + 12, f"{r.calls:,}" if r.complete else f"{r.calls}\n({r.days}d)",
            ha="center", va="bottom", fontsize=7.5, color=TEXT_2)
ax.xaxis.set_major_formatter(date_fmt)
ax.set_xticks(wk["week_start"])
ax.tick_params(axis="x", labelsize=8, rotation=0)
ax.set_ylabel("Calls per week")
ax.set_ylim(0, wk["calls"].max() * 1.15)
ax.set_title("Weekly calls stepped up from ~560 to ~1,000+ and did not come back down", pad=22)
subtitle(ax, "Technical calls by week (Mon start) · grey = baseline weeks, blue = weeks with the spike · pale = partial week (fewer than 7 days)")
source(fig)
fig.savefig(OUT / "c2_weekly_totals.png"); plt.close(fig)

# C3 — zoom on the start: daily values vs threshold, run highlighted
z = daily[(daily["call_date"] >= first_event - pd.Timedelta(days=14)) &
          (daily["call_date"] <= START + pd.Timedelta(days=14))]
fig, ax = plt.subplots(figsize=(11, 4.2))
ax.plot(z["call_date"], z["total_calls"], color=BLUE, lw=1.6, zorder=2)
above = z["total_calls"] > THR
ax.scatter(z.loc[~above, "call_date"], z.loc[~above, "total_calls"], s=26, color=NEUTRAL, zorder=3, label="At/below threshold")
ax.scatter(z.loc[above, "call_date"], z.loc[above, "total_calls"], s=26, color=BLUE, zorder=3, label="Above threshold")
ax.axhline(THR, color=NEUTRAL, lw=1, ls=(0, (4, 3)))
ax.text(z["call_date"].min(), THR + 2, f"Threshold {THR:.0f}", color=TEXT_2, fontsize=8, va="bottom")
mark_events(ax, z["total_calls"].max() * 1.2 - 2)
ax.set_ylim(0, z["total_calls"].max() * 1.2)
ax.xaxis.set_major_locator(mdates.DayLocator(interval=2))
ax.xaxis.set_major_formatter(date_fmt)
ax.tick_params(axis="x", labelsize=8)
ax.legend(loc="lower right", fontsize=8)
ax.set_ylabel("Calls per day")
lag = (START - first_event).days
ax.set_title(f"The jump happens overnight on {START:%d %b}: {lag} days after Ontario's and 1 day after the Prairies' firmware updates", pad=22)
subtitle(ax, f"Daily calls ±2 weeks around the start · rule: first of ≥{RUN_DAYS} consecutive days above threshold")
source(fig)
fig.savefig(OUT / "c3_spike_start_zoom.png"); plt.close(fig)

# C4 — before vs after average per day
fig, ax = plt.subplots(figsize=(6, 4.2))
labels = [f"Baseline\n{data_start:%d %b}–{baseline_end:%d %b}", f"Post-spike\n{START:%d %b}–{data_end:%d %b}"]
vals = [base_mean, post_mean]
ax.bar(labels, vals, width=0.5, color=[NEUTRAL, BLUE], zorder=2)
for i, v in enumerate(vals):
    ax.text(i, v + 2, f"{v:.0f}", ha="center", va="bottom", fontsize=11, color=TEXT, fontweight="bold")
ax.text(0.5, max(vals) * 1.12, f"+{uplift_pct:.0f}%  (+{post_mean - base_mean:.0f} calls/day)",
        ha="center", fontsize=10, color=TEXT)
ax.set_ylim(0, max(vals) * 1.25)
ax.set_ylabel("Average calls per day")
ax.set_title("Average daily calls nearly doubled", pad=22)
subtitle(ax, "Mean technical calls per day, baseline vs post-spike")
source(fig)
fig.savefig(OUT / "c4_before_after.png"); plt.close(fig)

# C5 — cumulative excess calls vs baseline
d = daily.copy()
d["excess"] = np.where(d["call_date"] >= START, d["total_calls"] - base_mean, 0)
d["cum_excess"] = d["excess"].cumsum()
fig, ax = plt.subplots(figsize=(11, 4.2))
ax.fill_between(d["call_date"], d["cum_excess"], color=BLUE, alpha=0.18, lw=0)
ax.plot(d["call_date"], d["cum_excess"], color=BLUE, lw=2)
ax.text(d["call_date"].iloc[-1], d["cum_excess"].iloc[-1], f"  {d['cum_excess'].iloc[-1]:,.0f}",
        color=TEXT, fontsize=10, fontweight="bold", va="center")
mark_events(ax, d["cum_excess"].max() * 1.15, labels=False)
ax.xaxis.set_major_formatter(date_fmt)
ax.set_ylim(0, d["cum_excess"].max() * 1.15)
ax.set_xlim(data_start, data_end + pd.Timedelta(days=6))
ax.set_ylabel("Cumulative extra calls")
ax.set_title(f"~{excess_total:,.0f} extra calls above baseline by 30 Jun — still climbing in a straight line", pad=22)
subtitle(ax, f"Running total of (daily calls − baseline {base_mean:.0f}) from the spike start · a straight line = a sustained step change, not a one-off spike")
source(fig)
fig.savefig(OUT / "c5_cumulative_excess.png"); plt.close(fig)

# C6 — sample ratio by week (is technical_calls a stable sample?)
wr = weekly_ratio.reset_index()
overall = smp["sampled_calls"].sum() / smp["total_calls"].sum()
fig, ax = plt.subplots(figsize=(11, 3.8))
ax.plot(wr["week_start"], wr["ratio"] * 100, color=BLUE, marker="o", ms=6, lw=1.6)
ax.axhline(overall * 100, color=NEUTRAL, lw=1, ls=(0, (4, 3)))
ax.text(wr["week_start"].min(), overall * 100 + 0.3, f"Overall {overall:.1%}", color=TEXT_2, fontsize=8, va="bottom")
ax.axvline(START, color=TEXT_2, lw=0.8)
ax.text(START, 1, f" spike start {START:%d %b}", color=TEXT_2, fontsize=8)
ax.set_ylim(0, max(wr["ratio"].max() * 100 * 1.3, 15))
ax.xaxis.set_major_formatter(date_fmt)
ax.set_ylabel("% of true calls in sample")
b, a = ratio_by_period.loc["before spike", "ratio"], ratio_by_period.loc["post", "ratio"]
ax.set_title(f"The call-level table is NOT a steady sample: ~{b:.0%} of calls before the spike vs ~{a:.0%} after", pad=22)
subtitle(ax, "Weekly sampled calls (technical_calls) ÷ true calls (call_volume_daily) · use the sample for within-period shares only; take volumes and timing from the daily totals")
source(fig)
fig.savefig(OUT / "c6_sample_ratio.png"); plt.close(fig)

# ---------------------------------------------------------------- console summary
print(json.dumps({k: v for k, v in metrics.items() if k != "channel_mix"}, indent=2, default=str))
print("\nBaseline day-of-week means:\n", dow.round(1).to_string())
print("\nSample ratio by period:\n", ratio_by_period.round(3).to_string())
print("\nChannel mix (sample):\n", channel_mix.to_string())
print("\nSensitivity:\n", sens.to_string(index=False))
