"""Evidence for walking through review_comparison.md rows 2–6 (charts + numbers).

Data: raw CSVs in Data/ (independent of the gold layer) + true daily totals.
Outputs: outputs/review/rw*.png and printed numbers.
"""
from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from style import BLUE, NEUTRAL, ORANGE, TEXT, TEXT_2, source, subtitle

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs" / "review"
OUT.mkdir(parents=True, exist_ok=True)
DARK = "#184f95"
SRC = "Source: raw CSVs (synthetic data)"

calls = pd.read_csv(ROOT / "Data/technical_calls.csv", parse_dates=["call_date"])
tx = pd.read_csv(ROOT / "Data/transcripts.csv")[["call_id", "transcript_text"]]
daily = pd.read_csv(ROOT / "Data/call_volume_daily.csv", parse_dates=["date"]).rename(columns={"date": "call_date", "technical_calls": "total"})
events = pd.read_csv(ROOT / "Data/network_events.csv", parse_dates=["event_date"])
calls = calls.merge(tx, on="call_id")
calls["conn"] = calls["issue_type"].isin(["No Internet", "Slow Speed"])
calls["june_note"] = calls["transcript_text"].str.contains("June notes")
calls["window"] = np.select([calls["call_date"] < "2026-05-26", calls["call_date"] < "2026-06-01"],
                            ["1–25 May", "26–31 May"], "June")

# ------------------------------------------------------------------ ROW 2: 26 May vs 1 June
mix = calls.groupby("window").agg(sampled=("call_id", "size"), connectivity=("conn", "mean"),
                                  repeats=("repeat_contact_flag", "mean"), june_note=("june_note", "mean")) \
    .reindex(["1–25 May", "26–31 May", "June"])
print("ROW 2 — call mix by window (sampled calls, unweighted):\n", (mix.assign(**{c: mix[c] * 100 for c in ["connectivity", "repeats", "june_note"]})).round(1).to_string())
samp = calls.groupby("call_date").size().reindex(daily.loc[daily.call_date >= "2026-05-01", "call_date"], fill_value=0)
per_win = daily[daily.call_date >= "2026-05-01"].assign(window=lambda d: np.select(
    [d.call_date < "2026-05-26", d.call_date < "2026-06-01"], ["1–25 May", "26–31 May"], "June"))
print("\nTrue calls/day vs sampled calls/day by window:\n",
      per_win.assign(s=samp.values).groupby("window").agg(true_per_day=("total", "mean"), sampled_per_day=("s", "mean")).round(1).to_string())

fig, axes = plt.subplots(2, 1, figsize=(11, 6.4), sharex=True, gridspec_kw={"hspace": 0.35})
d = daily[daily.call_date >= "2026-05-01"]
axes[0].plot(d.call_date, d.total, color=BLUE, lw=2)
axes[0].set_ylim(0, 180); axes[0].set_ylabel("True calls/day")
axes[0].set_title("Real call volume jumps on 26 May …", loc="left", fontsize=11)
axes[1].bar(samp.index, samp.values, color=NEUTRAL, width=0.8)
axes[1].set_ylim(0, 40); axes[1].set_ylabel("Sampled calls/day")
axes[1].set_title("… but the detailed call sample only jumps on 1 June", loc="left", fontsize=11)
for ax in axes:
    for x, lbl in ((pd.Timestamp("2026-05-26"), "26 May"), (pd.Timestamp("2026-06-01"), "1 Jun")):
        ax.axvline(x, color=ORANGE, lw=1, ls=(0, (3, 3)))
        ax.text(x, ax.get_ylim()[1] * 0.92, f" {lbl}", color=TEXT_2, fontsize=8.5)
axes[1].xaxis.set_major_formatter(mdates.DateFormatter("%d %b"))
fig.suptitle("Two data sources, two different change dates", x=0.125, ha="left", fontsize=12, fontweight="bold")
source(fig, SRC); fig.savefig(OUT / "rw2a_two_dates.png"); plt.close(fig)

fig, ax = plt.subplots(figsize=(10, 4.4))
metrics = [("connectivity", "“No Internet” + “Slow Speed”\nshare of calls"), ("repeats", "Repeat calls"), ("june_note", "“June notes … regional\ninstability” in transcript")]
colors = {"1–25 May": NEUTRAL, "26–31 May": "#9ec5f4", "June": BLUE}
w = 0.26
for i, (m, label) in enumerate(metrics):
    for j, win in enumerate(["1–25 May", "26–31 May", "June"]):
        v = mix.loc[win, m] * 100
        ax.bar(i + (j - 1) * (w + 0.02), v, w, color=colors[win], label=win if i == 0 else None)
        ax.text(i + (j - 1) * (w + 0.02), v + 1.2, f"{v:.0f}%", ha="center", fontsize=9.5, color=TEXT)
ax.set_xticks(range(3), [l for _, l in metrics]); ax.tick_params(axis="x", length=0)
ax.set_ylim(0, 75); ax.set_ylabel("% of sampled calls"); ax.legend(loc="upper left", fontsize=9)
ax.set_title("The first six spike days (26–31 May) look like normal May — the change shows up from 1 June", pad=22)
subtitle(ax, f"Sampled calls: 1–25 May n={mix.loc['1–25 May','sampled']}, 26–31 May n={mix.loc['26–31 May','sampled']}, June n={mix.loc['June','sampled']}")
source(fig, SRC); fig.savefig(OUT / "rw2b_mix_by_window.png"); plt.close(fig)

# driver share of increase: original "after" vs June-only
def wsplit(after_mask):
    """Connectivity share of the increase (%) for a given definition of 'after' (26 May–30 Jun vs June only), re-weighting the raw sample."""
    dd = daily[daily.call_date >= "2026-05-01"].copy()
    dd["s"] = samp.values; dd["wt"] = dd.total / dd.s
    c = calls.merge(dd[["call_date", "wt"]], on="call_date")
    b = c[c.call_date < "2026-05-26"]; a = c[after_mask(c)]
    nb = (dd.call_date < "2026-05-26").sum(); na = after_mask(dd).sum()
    inc_total = a.wt.sum() / na - b.wt.sum() / nb
    inc_conn = a.loc[a.conn, "wt"].sum() / na - b.loc[b.conn, "wt"].sum() / nb
    return inc_conn / inc_total * 100
print(f"\nConnectivity share of the increase: after=26 May–30 Jun {wsplit(lambda f: f.call_date >= '2026-05-26'):.1f}% | "
      f"after=June only {wsplit(lambda f: f.call_date >= '2026-06-01'):.1f}%")

# ------------------------------------------------------------------ ROW 3: one step vs staircase (H1 vs H3)
before = calls[calls.call_date < "2026-05-26"]
share = before["region"].value_counts(normalize=True)
z = daily[(daily.call_date >= "2026-05-15") & (daily.call_date <= "2026-06-08")].copy()
uplift = 148.2 / 80 - 1
z["staircase"] = 80.0
for e in events.itertuples():
    z.loc[z.call_date >= e.event_date, "staircase"] += 80 * share[e.region] * uplift
fig, ax = plt.subplots(figsize=(11, 4.6))
ax.plot(z.call_date, z.total, color=BLUE, lw=2.5, marker="o", ms=4, label="Actual daily calls")
ax.plot(z.call_date, z.staircase, color=TEXT_2, lw=1.6, ls=(0, (4, 3)), drawstyle="steps-post",
        label="What 3 regional rollouts would look like (illustration)")
for i, e in enumerate(events.sort_values("event_date").itertuples()):
    ax.axvline(e.event_date, color=ORANGE, lw=1, ls=(0, (3, 3)))
    ax.text(e.event_date, 172 - i * 9, f" {e.region} update", color=TEXT_2, fontsize=8.5)
ax.set_ylim(0, 180); ax.set_ylabel("Calls per day")
ax.xaxis.set_major_locator(mdates.DayLocator(interval=2)); ax.xaxis.set_major_formatter(mdates.DateFormatter("%d %b"))
ax.tick_params(axis="x", labelsize=8); ax.legend(loc="lower right", fontsize=9)
ax.set_title("Actual: one overnight jump on 26 May. A staggered regional rollout would have made a staircase", pad=22)
subtitle(ax, "Staircase = each region's normal calls rising +85% from its own update date (Ontario 27%, Prairies 24%, Quebec 17% of calls)")
source(fig, SRC); fig.savefig(OUT / "rw3a_one_step_vs_staircase.png"); plt.close(fig)
print("\nROW 3 — daily totals around events:\n", z[["call_date", "total", "staircase"]].assign(staircase=lambda d: d.staircase.round(0)).to_string(index=False))

# no-update regions' share (weighted with the solution's daily weights)
dd = daily[daily.call_date >= "2026-05-01"].copy(); dd["s"] = samp.values; dd["wt"] = dd.total / dd.s
cw = calls.merge(dd[["call_date", "wt"]], on="call_date")
noupd = ~cw.region.isin(events.region)
sb = cw.loc[(cw.call_date < "2026-05-26") & noupd, "wt"].sum() / cw.loc[cw.call_date < "2026-05-26", "wt"].sum() * 100
sa = cw.loc[(cw.call_date >= "2026-06-01") & noupd, "wt"].sum() / cw.loc[cw.call_date >= "2026-06-01", "wt"].sum() * 100
expected = sb / 100 * 80 / 148.2 * 100
print(f"\nNo-update regions (Atlantic+BC) share: before {sb:.1f}% | June {sa:.1f}% | if only updated regions rose: {expected:.1f}%")
fig, ax = plt.subplots(figsize=(8.5, 4.2))
vals = [("Before\n(1–25 May)", sb, NEUTRAL), ("June\n(actual)", sa, BLUE), ("June if ONLY the 3\nupdated regions rose", expected, "#e4e3df")]
for i, (l, v, c) in enumerate(vals):
    ax.bar(i, v, 0.55, color=c, edgecolor=TEXT_2 if c == "#e4e3df" else c, ls="--" if c == "#e4e3df" else "-")
    ax.text(i, v + 1, f"{v:.0f}%", ha="center", fontsize=11, fontweight="bold", color=TEXT)
ax.set_xticks(range(3), [v[0] for v in vals]); ax.tick_params(axis="x", length=0)
ax.set_ylim(0, 45); ax.set_ylabel("% of all technical calls")
ax.set_title("BC + Atlantic (no update) kept their normal share of calls", pad=22)
subtitle(ax, "If firmware in Ontario/Prairies/Quebec were the only cause, their share would have shrunk")
source(fig, SRC); fig.savefig(OUT / "rw3b_noupdate_share.png"); plt.close(fig)

# ------------------------------------------------------------------ ROW 4: repeat decomposition
rb = (cw.loc[cw.call_date < "2026-05-26"].pipe(lambda f: (f.wt * f.repeat_contact_flag).sum() / f.wt.sum()))
ra = (cw.loc[cw.call_date >= "2026-05-26"].pipe(lambda f: (f.wt * f.repeat_contact_flag).sum() / f.wt.sum()))
rep_b, rep_a = 80 * rb, 148.2 * ra
old_rate_new_vol = 148.2 * rb
vol_effect, rate_effect = old_rate_new_vol - rep_b, rep_a - old_rate_new_vol
print(f"\nROW 4 — repeat rate {rb*100:.1f}% → {ra*100:.1f}% | repeats/day {rep_b:.1f} → {rep_a:.1f} "
      f"| extra repeats {rep_a-rep_b:.1f} = volume effect {vol_effect:.1f} + rate effect {rate_effect:.1f} "
      f"| rate effect = {rate_effect/68.2*100:.0f}% of the +68.2/day increase (repeats total = {(rep_a-rep_b)/68.2*100:.0f}%)")
fig, ax = plt.subplots(figsize=(9, 4.6))
ax.bar(0, 80 - rep_b, 0.5, color="#e4e3df"); ax.bar(0, rep_b, 0.5, bottom=80 - rep_b, color=NEUTRAL)
first_a = 148.2 - rep_a
ax.bar(1, first_a, 0.5, color="#e4e3df"); ax.bar(1, old_rate_new_vol, 0.5, bottom=first_a, color=NEUTRAL)
ax.bar(1, rate_effect, 0.5, bottom=first_a + old_rate_new_vol, color=BLUE)
ax.text(0, (80 - rep_b) / 2, f"First-time\n{80 - rep_b:.0f}", ha="center", va="center", fontsize=9)
ax.text(0.28, 80 - rep_b / 2, f"Repeats {rep_b:.0f}", va="center", fontsize=9)
ax.text(1, first_a / 2, f"First-time\n{first_a:.0f}", ha="center", va="center", fontsize=9)
ax.text(1.28, first_a + old_rate_new_vol / 2, f"Repeats at the OLD rate ({rb*100:.0f}%): {old_rate_new_vol:.0f}\n(more callers → more repeats anyway)", va="center", fontsize=8.5)
ax.text(1.28, first_a + old_rate_new_vol + rate_effect / 2, f"Extra from the HIGHER rate: {rate_effect:.0f}\n= {rate_effect/68.2*100:.0f}% of the increase", va="center", fontsize=8.5, fontweight="bold")
ax.set_xticks([0, 1], ["Before (1–25 May)", "After (26 May–30 Jun)"]); ax.tick_params(axis="x", length=0)
ax.set_xlim(-0.5, 2.3); ax.set_ylim(0, 170); ax.set_ylabel("Calls per day")
ax.set_title("Only the blue part is caused by the repeat rate going up: ~18 calls/day, about a quarter", pad=22)
subtitle(ax, "Repeat calls per day split into 'more volume at the old rate' and 'extra from the higher rate'")
source(fig, SRC); fig.savefig(OUT / "rw4a_repeat_split.png"); plt.close(fig)

rr = calls[calls.window != "26–31 May"].groupby(["issue_type", "window"])["repeat_contact_flag"].mean().unstack() * 100
rr["x"] = rr["June"] / rr["1–25 May"]
print("\nRepeat rate by reason, 1–25 May vs June (%):\n", rr.round(1).sort_values("x", ascending=False).to_string())
res = calls.groupby("window").apply(lambda g: (g.resolution_status == "Resolved on call").mean() * 100, include_groups=False)
print("\nResolved on call % by window:", res.round(1).to_dict())

# ------------------------------------------------------------------ ROW 5: region % change with uncertainty
rng = np.random.default_rng(7)
b_all, a_all = cw[cw.call_date < "2026-05-26"], cw[cw.call_date >= "2026-05-26"]
nb, na = 25, 36
regions = sorted(cw.region.unique())
def reg_change(b, a):
    """% change in weighted calls per day by region, before vs after."""
    return {r: (a.loc[a.region == r, "wt"].sum() / na) / (b.loc[b.region == r, "wt"].sum() / nb) * 100 - 100 for r in regions}
point = reg_change(b_all, a_all)
boots = pd.DataFrame([reg_change(b_all.sample(len(b_all), replace=True, random_state=int(rng.integers(1e9))),
                                 a_all.sample(len(a_all), replace=True, random_state=int(rng.integers(1e9)))) for _ in range(1000)])
lo, hi = boots.quantile(0.025), boots.quantile(0.975)
order = sorted(regions, key=lambda r: point[r])
print("\nROW 5 — region % change, point and 95% range:\n", pd.DataFrame({"point": point, "low": lo, "high": hi}).round(0).loc[order[::-1]].to_string())
fig, ax = plt.subplots(figsize=(9.5, 4.2))
fwset = set(events.region)
for i, r in enumerate(order):
    c = BLUE if r in fwset else NEUTRAL
    ax.plot([lo[r], hi[r]], [i, i], color=c, lw=6, alpha=0.35, solid_capstyle="round")
    ax.scatter(point[r], i, s=70, color=c, zorder=3)
    ax.text(point[r], i + 0.28, f"{point[r]:+.0f}%", ha="center", fontsize=9, color=TEXT)
ax.set_yticks(range(len(order)), [f"{r} ({'update' if r in fwset else 'no update'})" for r in order])
ax.grid(axis="y", visible=False); ax.grid(axis="x", visible=True)
ax.set_xlabel("% change in calls per day (dot = estimate, bar = plausible range)")
ax.set_title("Every region rose, but the ranges overlap almost completely — ranking regions is noise", pad=22)
subtitle(ax, "Bootstrap 95% range: resampling the 129 'before' and 621 'after' sampled calls 1,000 times")
source(fig, SRC); fig.savefig(OUT / "rw5_region_ranges.png"); plt.close(fig)
print("\nsaved charts to", OUT)

# ------------------------------------------------------------------ ROW 4 (corrected window, per row 2): 1–25 May vs June
J = cw[cw.call_date >= "2026-06-01"]
ra_j = (J.wt * J.repeat_contact_flag).sum() / J.wt.sum()
vol_j = daily.loc[daily.call_date >= "2026-06-01", "total"].mean()
rep_aj, old_j = vol_j * ra_j, vol_j * rb
rate_j, inc_j = rep_aj - old_j, vol_j - 80
print(f"\nROW 4 (June basis) — repeat rate {rb*100:.1f}% → {ra_j*100:.1f}% | repeats/day {rep_b:.1f} → {rep_aj:.1f} "
      f"| old rate on new volume {old_j:.1f} | rate effect {rate_j:.1f} = {rate_j/inc_j*100:.0f}% of +{inc_j:.1f}/day")
fig, ax = plt.subplots(figsize=(9.5, 4.6)); ax.set_axisbelow(True)
first_b, first_j = 80 - rep_b, vol_j - rep_aj
ax.bar(0, first_b, 0.5, color="#e4e3df"); ax.bar(0, rep_b, 0.5, bottom=first_b, color=NEUTRAL)
ax.bar(1, first_j, 0.5, color="#e4e3df"); ax.bar(1, old_j, 0.5, bottom=first_j, color=NEUTRAL)
ax.bar(1, rate_j, 0.5, bottom=first_j + old_j, color=BLUE)
ax.text(0, first_b / 2, f"First-time\n{first_b:.0f}", ha="center", va="center", fontsize=9)
ax.text(0.28, first_b + rep_b / 2, f"Repeats {rep_b:.0f}  ({rb*100:.0f}% of calls)", va="center", fontsize=9)
ax.text(1, first_j / 2, f"First-time\n{first_j:.0f}", ha="center", va="center", fontsize=9)
ax.text(1.28, first_j + old_j / 2, f"Repeats at the OLD {rb*100:.0f}% rate: {old_j:.0f}\n(more callers → more repeats anyway)", va="center", fontsize=8.5)
ax.text(1.28, first_j + old_j + rate_j / 2, f"Extra from the HIGHER rate ({ra_j*100:.0f}%): {rate_j:.0f}/day\n= {rate_j/inc_j*100:.0f}% of the +{inc_j:.0f}/day increase", va="center", fontsize=8.5, fontweight="bold")
ax.set_xticks([0, 1], ["Before (1–25 May)", "June"]); ax.tick_params(axis="x", length=0)
ax.set_xlim(-0.5, 2.4); ax.set_ylim(0, 170); ax.set_ylabel("Calls per day")
ax.set_title(f"Only the blue part comes from customers calling back more often: ~{rate_j:.0f} calls/day, about a third", pad=22)
subtitle(ax, "Repeat calls per day split into 'more volume at the old rate' and 'extra from the higher rate' · before = 1–25 May, after = June")
source(fig, SRC); fig.savefig(OUT / "rw4b_repeat_split_june.png"); plt.close(fig)

# ------------------------------------------------------------------ ROW 5 (corrected window, per row 2): 1–25 May vs June
a_j = cw[cw.call_date >= "2026-06-01"]
def reg_change_j(b, a):
    """Same as reg_change with June as 'after' (30 days vs 25)."""
    return {r: (a.loc[a.region == r, "wt"].sum() / 30) / (b.loc[b.region == r, "wt"].sum() / 25) * 100 - 100 for r in regions}
def grp_change(b, a):
    """% change for regions with a logged firmware update vs regions without (June vs 1–25 May)."""
    f = lambda fr, n: fr.loc[fr.region.isin(fwset), "wt"].sum() / n, lambda fr, n: fr.loc[~fr.region.isin(fwset), "wt"].sum() / n
    up = f[0](a, 30) / f[0](b, 25) * 100 - 100; no = f[1](a, 30) / f[1](b, 25) * 100 - 100
    return up, no
pj = reg_change_j(b_all, a_j); gj = grp_change(b_all, a_j)
bj, gb = [], []
for _ in range(1000):
    bs = b_all.sample(len(b_all), replace=True, random_state=int(rng.integers(1e9)))
    as_ = a_j.sample(len(a_j), replace=True, random_state=int(rng.integers(1e9)))
    bj.append(reg_change_j(bs, as_)); u, n = grp_change(bs, as_); gb.append(u - n)
bj = pd.DataFrame(bj); loj, hij = bj.quantile(0.025), bj.quantile(0.975)
gb = pd.Series(gb)
sample_n = b_all.region.value_counts()
print("\nROW 5 (June basis) — region % change, 95% range, before-sample size:\n",
      pd.DataFrame({"point": pj, "low": loj, "high": hij, "before_n": sample_n}).round(0).sort_values("point", ascending=False).to_string())
print(f"Updated regions {gj[0]:+.0f}% vs no-update {gj[1]:+.0f}% | gap {gj[0]-gj[1]:+.0f} pts, 95% range {gb.quantile(.025):+.0f} to {gb.quantile(.975):+.0f}")
order_j = sorted(regions, key=lambda r: pj[r])
fig, ax = plt.subplots(figsize=(9.5, 4.4))
for i, r in enumerate(order_j):
    c = BLUE if r in fwset else NEUTRAL
    ax.plot([loj[r], hij[r]], [i, i], color=c, lw=7, alpha=0.35, solid_capstyle="round")
    ax.scatter(pj[r], i, s=70, color=c, zorder=3)
    ax.text(pj[r], i + 0.3, f"{pj[r]:+.0f}%", ha="center", fontsize=9, color=TEXT)
ax.set_yticks(range(len(order_j)), [f"{r} ({'update' if r in fwset else 'no update'}, {sample_n[r]} calls before)" for r in order_j])
ax.grid(axis="y", visible=False); ax.grid(axis="x", visible=True); ax.axvline(0, color=TEXT_2, lw=0.8)
ax.set_ylim(-0.6, len(order_j) - 0.2)
ax.set_xlabel("% change in calls per day, 1–25 May → June (dot = estimate, bar = plausible range)")
ax.set_title("Every region clearly rose — but the ranges overlap, so we can't rank regions", pad=22)
subtitle(ax, "Bootstrap 95% range (resampling the 129 'before' and 587 June records 1,000 times) · blue = firmware update, grey = no update")
source(fig, SRC); fig.savefig(OUT / "rw5b_region_ranges_june.png"); plt.close(fig)
