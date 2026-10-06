"""Phase 4 (+ parts of 5/6) — What changed between BEFORE (1–25 May) and AFTER (26 May–30 Jun)?

Answers Q3 (drivers), and gives first numbers for Q5 (repeat contacts) and Q6 (transcripts / VOC).

Data (all loaded from Databricks): gold.fct_calls (750 sampled calls), gold.fct_daily_volume (true daily
totals), gold.fct_device_health.

Method
  1. Weight every sampled call so the sample adds up to the true daily totals (the sample is uneven: ~6% of
     calls before the spike, ~12% after — A17):   weight = true_calls(day) / sampled_calls(day)
  2. For each column (issue type, platform, ...), per period:
       share         = sum of weights in the category / sum of all weights   (weighted %)
       est_per_day   = sum of weights in the category / number of days in the period
  3. Compare before vs after:
       share_shift_pp     = share_after − share_before          (did the MIX change?)
       increase_per_day   = est_per_day_after − est_per_day_before
       pct_change         = est_per_day_after / est_per_day_before − 1
       share_of_increase  = increase_per_day / total increase per day
  4. Chi-square test per column (on raw sampled counts): "is the before/after mix different by more than
     chance?" p < 0.05 = probably a real change; p ≥ 0.05 = could easily be chance.

Correctness checks (asserts) run at the end — the script fails loudly if any number doesn't reconcile.
Outputs: outputs/phase4/*.csv, outputs/phase4/summary.json

NOTE (first pass): this script defines 'after' as 26 May–30 Jun. After the two independent reviews, every
call-level comparison moved to 1–25 May vs June, because the 26–31 May sample still looks like May (A19).
Final numbers: analysis/review_walkthrough.py and the app (app/data.py, app/app.py).
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import chi2_contingency

import db

OUT = Path(__file__).resolve().parents[1] / "outputs" / "phase4"
OUT.mkdir(parents=True, exist_ok=True)
SPLIT = pd.Timestamp("2026-05-26")
pd.set_option("display.width", 220, "display.max_columns", 30)

# ================================================================ 1. load + weight
calls = db.load("fct_calls")
daily = db.load("fct_daily_volume")
devices = db.load("fct_device_health")

daily = daily[daily["call_date"] >= calls["call_date"].min()].copy()          # May–Jun (sample range)
daily["weight"] = daily["total_calls"] / daily["sampled_calls"]
calls = calls.merge(daily[["call_date", "weight"]], on="call_date", how="left")
calls["period"] = np.where(calls["call_date"] < SPLIT, "before", "after")
daily["period"] = np.where(daily["call_date"] < SPLIT, "before", "after")
DAYS = daily.groupby("period").size()                     # before 25, after 36
TRUE_TOTAL = daily.groupby("period")["total_calls"].sum()  # true calls per period
TOTAL_INCREASE = TRUE_TOTAL["after"] / DAYS["after"] - TRUE_TOTAL["before"] / DAYS["before"]

# ================================================================ 2–3. per-column comparison
def compare(col: str) -> pd.DataFrame:
    """Weighted share and calls per day of each group of `col`, before vs after, and its contribution to the increase."""
    w = calls.groupby([col, "period"])["weight"].sum().unstack(fill_value=0)[["before", "after"]]
    n = calls.groupby([col, "period"]).size().unstack(fill_value=0)[["before", "after"]]
    t = pd.DataFrame(index=w.index)
    t["n_before"], t["n_after"] = n["before"], n["after"]
    t["share_before_%"] = w["before"] / w["before"].sum() * 100
    t["share_after_%"] = w["after"] / w["after"].sum() * 100
    t["share_shift_pp"] = t["share_after_%"] - t["share_before_%"]
    t["est_per_day_before"] = w["before"] / DAYS["before"]
    t["est_per_day_after"] = w["after"] / DAYS["after"]
    t["increase_per_day"] = t["est_per_day_after"] - t["est_per_day_before"]
    t["pct_change_%"] = (t["est_per_day_after"] / t["est_per_day_before"] - 1) * 100
    t["share_of_increase_%"] = t["increase_per_day"] / TOTAL_INCREASE * 100
    t["low_n_flag"] = n["before"] < 10
    return t.sort_values("increase_per_day", ascending=False)


def chi_square(col: str):
    """Chi-square test: did the mix of `col` change between periods? Returns (p-value, any expected cell < 5)."""
    tab = pd.crosstab(calls[col], calls["period"])
    chi2, p, dof, expected = chi2_contingency(tab)
    return round(p, 4), bool((expected < 5).any())


DIMENSIONS = ["issue_type", "platform", "product", "customer_segment", "region", "channel",
              "resolution_status", "customer_sentiment", "transcript_language"]
results, tests = {}, []
for col in DIMENSIONS:
    results[col] = compare(col)
    results[col].round(2).to_csv(OUT / f"{col}.csv")
    p, small = chi_square(col)
    biggest = results[col]["share_shift_pp"].abs().idxmax()
    tests.append({"column": col, "chi2_p_value": p, "mix_changed (p<0.05)": p < 0.05,
                  "small_expected_counts": small, "biggest_mover": biggest,
                  "biggest_shift_pp": round(results[col].loc[biggest, "share_shift_pp"], 1)})
tests = pd.DataFrame(tests).sort_values("chi2_p_value")
tests.to_csv(OUT / "mix_change_tests.csv", index=False)

# ================================================================ rates before vs after (weighted)
def wrate(mask_col, frame=None):
    """Weighted % of calls with a flag, per period."""
    f = calls if frame is None else frame
    return f.groupby("period").apply(lambda g: (g[mask_col] * g["weight"]).sum() / g["weight"].sum() * 100,
                                     include_groups=False)


def wmean(val_col, frame):
    """Weighted average of a value, per period."""
    return frame.groupby("period").apply(lambda g: np.average(g[val_col], weights=g["weight"]),
                                         include_groups=False)


fb = calls[calls["has_feedback"]]
rates = pd.DataFrame({
    "repeat_contact_rate_%": wrate("is_repeat_contact"),
    "negative_sentiment_rate_%": wrate("is_negative_sentiment"),
    "avg_call_duration_min": wmean("call_duration_minutes", calls),
    "feedback_coverage_%": wrate("has_feedback"),
    "avg_csat_1to5": wmean("csat_score", fb),
    "detractor_rate_%": wrate("is_detractor", fb),
    "satisfied_rate_%_(csat4-5)": wrate("is_satisfied", fb),
    "mentions_regional_instability_%": wrate("mentions_regional_instability"),
    "mentions_recurring_issue_%": wrate("mentions_recurring_issue"),
    "mentions_frustration_%": wrate("mentions_frustration"),
    "mentions_outage_%": wrate("mentions_outage"),
    "mentions_wifi_%": wrate("mentions_wifi"),
    "mentions_equipment_%": wrate("mentions_equipment"),
    "mentions_firmware_%": wrate("mentions_firmware"),
}).T[["before", "after"]]
rates["change"] = rates["after"] - rates["before"]
rates.round(2).to_csv(OUT / "rates_before_after.csv")

# repeat contacts: how much of the extra volume are repeats?
rep = calls.groupby(["period", "is_repeat_contact"])["weight"].sum().unstack()
rep_per_day = rep.div(DAYS, axis=0)
repeat_extra = rep_per_day.loc["after", True] - rep_per_day.loc["before", True]
first_extra = rep_per_day.loc["after", False] - rep_per_day.loc["before", False]

# "June notes ... regional instability" phrase — which issue types carry it, and does it ever appear before?
phrase = (calls.groupby(["issue_type", "period"])["mentions_regional_instability"].mean().unstack() * 100)[["before", "after"]]
phrase_first_date = calls.loc[calls["mentions_regional_instability"], "call_date"].min()

# platform x issue (after period) — is the growth concentrated in one combination?
plat_issue = (calls.groupby(["platform", "issue_type", "period"])["weight"].sum().unstack(fill_value=0)
              .div(DAYS)[["before", "after"]])
plat_issue["increase_per_day"] = plat_issue["after"] - plat_issue["before"]
plat_issue = plat_issue.sort_values("increase_per_day", ascending=False)
plat_issue.round(2).to_csv(OUT / "platform_x_issue.csv")

# device health (standalone — cannot be linked to callers, A4)
dev = devices.groupby("firmware_version").agg(devices=("customer_id", "size"),
                                              avg_reboots_7d=("reboot_count_7d", "mean"),
                                              low_signal_pct=("signal_quality_band", lambda s: (s == "Low").mean() * 100))
dev["share_of_devices_%"] = dev["devices"] / dev["devices"].sum() * 100

# ================================================================ 4. CORRECTNESS CHECKS
checks = []
def check(name, ok, detail):
    """Record a reconciliation check and stop the script if it fails."""
    checks.append({"check": name, "passed": bool(ok), "detail": detail})
    assert ok, f"CHECK FAILED: {name} — {detail}"

check("750 sampled calls loaded, all with a weight",
      len(calls) == 750 and calls["weight"].notna().all(), f"rows={len(calls)}, missing weights={calls['weight'].isna().sum()}")
for p in ("before", "after"):
    est = calls.loc[calls["period"] == p, "weight"].sum()
    check(f"weights add up to true total calls ({p})", abs(est - TRUE_TOTAL[p]) < 1e-6,
          f"weighted={est:.1f}, true={TRUE_TOTAL[p]}")
for col, t in results.items():
    check(f"{col}: shares sum to 100% in each period",
          abs(t["share_before_%"].sum() - 100) < 1e-6 and abs(t["share_after_%"].sum() - 100) < 1e-6, "ok")
    check(f"{col}: category increases sum to total increase",
          abs(t["increase_per_day"].sum() - TOTAL_INCREASE) < 1e-6,
          f"sum={t['increase_per_day'].sum():.2f}, total={TOTAL_INCREASE:.2f}")
# independent cross-check: recount issue_type x period directly in Databricks SQL
sql_counts = db.query("""
    SELECT issue_type, CASE WHEN call_date < DATE'2026-05-26' THEN 'before' ELSE 'after' END AS period, count(*) AS n
    FROM workspace.xplore_gold.fct_calls GROUP BY ALL""").pivot(index="issue_type", columns="period", values="n").fillna(0)
py_counts = results["issue_type"][["n_before", "n_after"]].rename(columns={"n_before": "before", "n_after": "after"})
check("issue_type counts match an independent SQL recount in Databricks",
      (sql_counts[["before", "after"]].sort_index().astype(int).values == py_counts.sort_index().astype(int).values).all(),
      "pandas == SQL")
# hand-checkable example: total increase per day from the daily table
check("total increase per day = (after total / 36) − (before total / 25)",
      abs(TOTAL_INCREASE - (TRUE_TOTAL["after"] / 36 - TRUE_TOTAL["before"] / 25)) < 1e-9,
      f"{TRUE_TOTAL['after']}/36 − {TRUE_TOTAL['before']}/25 = {TOTAL_INCREASE:.2f}")
pd.DataFrame(checks).to_csv(OUT / "correctness_checks.csv", index=False)

# ================================================================ save summary + print
summary = {
    "periods": {"before": "2026-05-01..2026-05-25", "after": "2026-05-26..2026-06-30",
                "days": DAYS.to_dict(), "true_calls": TRUE_TOTAL.to_dict(),
                "sampled_calls": calls.groupby("period").size().to_dict()},
    "true_calls_per_day": {"before": TRUE_TOTAL["before"] / DAYS["before"], "after": TRUE_TOTAL["after"] / DAYS["after"],
                           "increase": TOTAL_INCREASE},
    "repeat_contacts": {"repeat_calls_per_day": rep_per_day[True].round(1).to_dict(),
                        "first_contact_calls_per_day": rep_per_day[False].round(1).to_dict(),
                        "share_of_increase_from_repeats_%": round(repeat_extra / TOTAL_INCREASE * 100, 1),
                        "share_of_increase_from_first_contacts_%": round(first_extra / TOTAL_INCREASE * 100, 1)},
    "instability_phrase_first_seen": str(phrase_first_date.date()),
    "checks_passed": f"{sum(c['passed'] for c in checks)}/{len(checks)}",
}
(OUT / "summary.json").write_text(json.dumps(summary, indent=2, default=str))

show = ["n_before", "n_after", "share_before_%", "share_after_%", "share_shift_pp",
        "est_per_day_before", "est_per_day_after", "pct_change_%", "share_of_increase_%"]
print(f"TRUE calls/day: before {TRUE_TOTAL['before']/DAYS['before']:.1f} | after {TRUE_TOTAL['after']/DAYS['after']:.1f} "
      f"| increase {TOTAL_INCREASE:.1f}/day   (sampled calls: {summary['periods']['sampled_calls']})\n")
for col in ["issue_type", "platform", "product", "customer_segment", "resolution_status", "customer_sentiment"]:
    print(f"── {col} ".ljust(110, "─"))
    print(results[col][show].round(1).to_string(), "\n")
print("── Did the MIX change? (chi-square, raw sampled counts) ".ljust(110, "─"))
print(tests.to_string(index=False), "\n")
print("── Rates before vs after (weighted) ".ljust(110, "─"))
print(rates.round(1).to_string(), "\n")
print("── Repeat contacts ".ljust(110, "─"))
print(json.dumps(summary["repeat_contacts"], indent=1), "\n")
print("── 'regional instability' phrase by issue type (% of calls) ── first seen:", phrase_first_date.date())
print(phrase.round(0).to_string(), "\n")
print("── Top platform × issue combinations by increase (est calls/day) ".ljust(110, "─"))
print(plat_issue.head(8).round(1).to_string(), "\n")
print("── Device health (standalone) ".ljust(110, "─"))
print(dev.round(1).to_string(), "\n")
print("── Correctness checks ".ljust(110, "─"))
print(pd.DataFrame(checks)[["check", "passed"]].to_string(index=False))
print(f"\nALL {len(checks)} CHECKS PASSED")
