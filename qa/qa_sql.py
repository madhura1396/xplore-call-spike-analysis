"""Independent recomputation in Databricks SQL, written from scratch against the BRONZE tables
(workspace.xplore.*), so it checks silver + gold + the app's pandas logic at once.
Python only builds the SQL text, runs it through the Databricks CLI and applies the app's display rules
(rounding, noise test, status wording) to the SQL results."""
import datetime as dt
import io
import subprocess
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pandas as pd

B = "workspace.xplore"
PRE0, PRE1, POST0, POST1 = dt.date(2026, 5, 1), dt.date(2026, 5, 25), dt.date(2026, 6, 1), dt.date(2026, 6, 30)


def q(sql: str) -> pd.DataFrame:
    """Run SQL through the Databricks CLI and return a DataFrame."""
    out = subprocess.run(["databricks", "experimental", "aitools", "tools", "query", sql, "-p", "xplore",
                          "--output", "csv"], capture_output=True, text=True)
    if out.returncode:
        raise RuntimeError(out.stderr[-2000:] + "\n" + sql)
    return pd.read_csv(io.StringIO(out.stdout))


def qmany(sqls: dict) -> dict:
    """Run several queries in parallel."""
    with ThreadPoolExecutor(6) as ex:
        futs = {k: ex.submit(q, s) for k, s in sqls.items()}
        return {k: f.result() for k, f in futs.items()}


# One row per sampled call, built from bronze. Weight = true calls that day / sampled calls that day.
BASE = f"""
WITH vol AS (SELECT `date` AS d, technical_calls AS total FROM {B}.call_volume_daily),
smp AS (SELECT call_date AS d, count(*) AS n FROM {B}.technical_calls GROUP BY call_date),
ev AS (SELECT DISTINCT trim(region) AS r FROM {B}.network_events),
c AS (
  SELECT trim(t.call_id) AS call_id, t.call_date,
         trim(t.region) AS region, trim(t.platform) AS platform, trim(t.product) AS product,
         trim(t.customer_segment) AS customer_segment, trim(t.channel) AS channel, trim(t.issue_type) AS issue_type,
         trim(t.resolution_status) AS resolution_status,
         CASE WHEN ev.r IS NOT NULL THEN 'Update logged' ELSE 'No update' END AS firmware_region,
         CAST(t.repeat_contact_flag = 1 AS INT) AS rep,
         t.call_duration_minutes AS dur,
         CAST(trim(t.customer_sentiment) = 'Negative' AS INT) AS neg,
         CAST(trim(t.issue_type) IN ('No Internet', 'Slow Speed') AS INT) AS conn,
         CAST(trim(t.resolution_status) = 'Follow-up required' AS INT) AS fu,
         CAST(trim(t.resolution_status) = 'Technician scheduled' AS INT) AS tech,
         CAST(trim(t.resolution_status) = 'Resolved on call' AS INT) AS resolved,
         v.call_id IS NOT NULL AS has_fb, v.csat_score_1_to_5 AS csat,
         CAST(trim(v.nps_group) = 'Detractor' AS INT) AS detr,
         CAST(tr.transcript_text LIKE '%June notes%' AS INT) AS jn,
         split(tr.transcript_text, ' June notes')[0] AS core,
         vol.total / smp.n AS w,
         CASE WHEN t.call_date <= DATE'2026-05-25' THEN 'pre'
              WHEN t.call_date >= DATE'2026-06-01' THEN 'post' ELSE 'trans' END AS per,
         date_trunc('WEEK', t.call_date)::DATE AS wk
  FROM {B}.technical_calls t
  JOIN vol ON vol.d = t.call_date
  JOIN smp ON smp.d = t.call_date
  LEFT JOIN ev ON ev.r = trim(t.region)
  LEFT JOIN {B}.voc_feedback v ON trim(v.call_id) = trim(t.call_id)
  LEFT JOIN {B}.transcripts tr ON trim(tr.call_id) = trim(t.call_id)
)"""

AGG = """count(*) AS n, sum(w) AS sw,
  100 * sum(w * conn) / sum(w) AS connection, 100 * sum(w * rep) / sum(w) AS repeat,
  100 * sum(w * fu) / sum(w) AS follow_up, sum(w * dur) / sum(w) AS duration,
  sum(w * dur) / 60 AS agent_hours_tot, sum(w * tech) AS tech_tot, sum(w * rep) AS repeat_tot,
  sum(CASE WHEN has_fb THEN w * csat END) / sum(CASE WHEN has_fb THEN w END) AS csat,
  100 * sum(CASE WHEN has_fb THEN w * detr END) / sum(CASE WHEN has_fb THEN w END) AS detractors,
  100 * sum(w * neg) / sum(w) AS negative, 100 * sum(w * resolved) / sum(w) AS resolved,
  100 * sum(w * tech) / sum(w) AS tech_share, 100 * sum(w * jn) / sum(w) AS june_note,
  count_if(has_fb) AS n_fb, stddev_samp(dur) AS sd_dur, stddev_samp(CASE WHEN has_fb THEN csat END) AS sd_csat,
  sqrt(sum(w * w)) AS rss_calls, sqrt(sum(pow(w * dur / 60, 2))) AS rss_ah, sqrt(sum(CASE WHEN tech = 1 THEN w * w ELSE 0 END)) AS rss_tech"""


def where(spec: dict) -> str:
    """SQL WHERE clause for a filter scenario."""
    start, end = spec.get("dates", (PRE0, POST1))
    parts = [f"call_date BETWEEN DATE'{start}' AND DATE'{end}'"]
    for k, vals in spec.items():
        if k == "dates" or not vals:
            continue
        col = k[2:]
        parts.append(f"{col} IN ({', '.join(repr(v) for v in vals)})")
    return " AND ".join(parts)


def ndays(spec: dict) -> tuple:
    """Days of the pre-spike and post-spike periods inside the scenario's dates."""
    start, end = spec.get("dates", (PRE0, POST1))
    nb = max(0, (min(end, PRE1) - max(start, PRE0)).days + 1)
    na = max(0, (min(end, POST1) - max(start, POST0)).days + 1)
    return nb, na


def full_weeks(spec):
    """Mondays of the complete Mon–Sun weeks inside the date range (and inside 1 May–30 Jun)."""
    start, end = spec.get("dates", (PRE0, POST1))
    start, end = max(start, PRE0), min(end, POST1)
    d = start + dt.timedelta(days=(7 - start.weekday()) % 7)
    out = []
    while d + dt.timedelta(days=6) <= end:
        out.append(d)
        d += dt.timedelta(days=7)
    return out


def kpi_sql(spec):
    """All KPI aggregates per period."""
    return f"{BASE} SELECT per, {AGG} FROM c WHERE {where(spec)} GROUP BY per"


def week_sql(spec):
    """All KPI aggregates per week."""
    return f"{BASE} SELECT wk, {AGG} FROM c WHERE {where(spec)} GROUP BY wk ORDER BY wk"


def window_sql(spec, a, b, label):
    """All KPI aggregates for one date window (early vs late June trend)."""
    return (f"{BASE} SELECT '{label}' AS win, {AGG} FROM c WHERE {where(spec)} "
            f"AND call_date BETWEEN DATE'{a}' AND DATE'{b}'")


def breakdown_sql(spec, col):
    """Sampled count and weighted calls per group and period."""
    return (f"{BASE} SELECT {col} AS grp, per, count(*) AS n, sum(w) AS sw FROM c WHERE {where(spec)} "
            f"GROUP BY {col}, per")


def voice_sql(spec):
    """KPI aggregates per call reason and period."""
    return f"{BASE} SELECT issue_type, per, {AGG} FROM c WHERE {where(spec)} GROUP BY issue_type, per"


def voice_text_sql(spec):
    """Weighted call summaries per reason and period."""
    return (f"{BASE} SELECT issue_type, per, core, count(*) AS n, sum(w) AS sw FROM c WHERE {where(spec)} "
            f"GROUP BY issue_type, per, core")


def heat_sql(spec):
    """Weighted calls per region × reason × period."""
    return (f"{BASE} SELECT region, issue_type, per, sum(w) AS sw FROM c WHERE {where(spec)} "
            f"GROUP BY region, issue_type, per")


# ---------------------------------------------------------------- app display rules applied to SQL results
KPIS = {"calls": ("", 0, "rel", True), "connection": ("%", 0, "pts", True), "repeat": ("%", 0, "pts", True),
        "follow_up": ("%", 0, "pts", True), "duration": (" min", 1, "abs", True), "agent_hours": ("", 0, "rel", True),
        "tech_visits": ("", 0, "rel", True), "csat": ("", 1, "abs", False)}


def fmt(v, suffix="", dec=0):
    """Display formatting, same rule as the app."""
    return "—" if v is None or pd.isna(v) else f"{v:,.{dec}f}{suffix}"


def values(row, days):
    """KPI values + standard errors from one SQL aggregate row."""
    if row is None or row["n"] == 0:
        return {k: np.nan for k in list(KPIS) + ["negative", "detractors", "resolved", "june_note", "repeat_calls"]}, \
               {k: np.nan for k in KPIS}, 0, 0
    pd_ = (lambda x: x / days) if days else (lambda x: np.nan)
    v = {"calls": pd_(row["sw"]), "connection": row["connection"], "repeat": row["repeat"],
         "follow_up": row["follow_up"], "duration": row["duration"], "agent_hours": pd_(row["agent_hours_tot"]),
         "tech_visits": pd_(row["tech_tot"]), "csat": row["csat"], "negative": row["negative"],
         "detractors": row["detractors"], "resolved": row["resolved"], "june_note": row["june_note"],
         "repeat_calls": pd_(row["repeat_tot"]), "tech_share": row["tech_share"]}
    n, nfb = int(row["n"]), int(row["n_fb"])
    se = {}
    for k in ("connection", "repeat", "follow_up"):
        p = v[k] / 100
        se[k] = 100 * np.sqrt(p * (1 - p) / n)
    se["csat"] = row["sd_csat"] / np.sqrt(nfb) if nfb > 1 else np.nan
    se["duration"] = row["sd_dur"] / np.sqrt(n) if n > 1 else np.nan
    se["calls"] = pd_(row["rss_calls"])
    se["agent_hours"] = pd_(row["rss_ah"])
    se["tech_visits"] = pd_(row["rss_tech"])
    return v, se, n, nfb


def change(key, before, after):
    """Change formatting, same rule as the app."""
    unit, dec, kind, _ = KPIS[key]
    if pd.isna(before) or pd.isna(after) or (kind == "rel" and not before):
        return None
    diff = round((after / before - 1) * 100, 0) if kind == "rel" else round(round(after, dec) - round(before, dec), dec)
    if diff == 0:
        return "no change"
    return f"{diff:+.0f}%" if kind == "rel" else f"{diff:+.{dec}f}" + (" pts" if kind == "pts" else unit)


def compare_kpi(key, b, a):
    """b, a = (values, se, n, nfb) for pre and post."""
    vb, sb, nb_, fb_ = b
    va, sa, na_, fa_ = a
    pre, post = vb[key], va[key]
    noise = 2 * np.sqrt(sb[key] ** 2 + sa[key] ** 2)
    n_min = min(fb_, fa_) if key == "csat" else min(nb_, na_)
    real = bool(n_min >= 30 and not pd.isna(noise) and abs(post - pre) > noise)
    return {"pre": pre, "post": post, "noise": noise, "n_min": n_min, "real": real}


def trend(key, e, l_):
    """e, l_ = (values, se, n, nfb) for the first two / last two post-spike weeks (14 days each)."""
    if e is None or l_ is None:
        return "—"
    ne = e[3] if key == "csat" else e[2]
    nl = l_[3] if key == "csat" else l_[2]
    if min(ne, nl) < 30:
        return "—"
    ev, lv = e[0][key], l_[0][key]
    if pd.isna(ev) or pd.isna(lv) or not ev:
        return "—"
    noise = 2 * np.sqrt(e[1][key] ** 2 + l_[1][key] ** 2)
    meaningful = abs(lv - ev) >= 0.2 if key == "csat" else abs(lv / ev - 1) >= 0.1
    return "flat" if abs(lv - ev) <= noise or not meaningful else "rising" if lv > ev else "easing"


def status(key, c, tr):
    """The app's status rules, re-implemented independently. Minimum sample = 30, the rule at audit time; the app later moved to 10 with a 'small sample' marker (numbers unchanged, see the audit report section 8)."""
    pre, post = c["pre"], c["post"]
    if pd.isna(pre) or pd.isna(post) or not pre:
        return "Not enough data"
    if c["n_min"] < 30:
        return f"Too few {'surveys' if key == 'csat' else 'calls'} to tell"
    if not c["real"]:
        return "No real change"
    if key == "csat":
        return "Worse than pre-spike" if post < pre else "Better than pre-spike"
    r = post / pre
    if r >= 1.2:
        return {"rising": "Getting worse", "easing": "Easing, still high"}.get(tr, "Still high, not recovering")
    if r > 1.1:
        return "Slightly above pre-spike"
    return "Close to pre-spike level" if r >= 0.9 else "Below pre-spike"


def change_cell(key, c):
    """Change cell text with '(noise)' / '(few calls)', as in the app at audit time."""
    raw = change(key, c["pre"], c["post"]) or "—"
    if c["real"] or raw == "—":
        return raw
    return f"{raw} (few {'surveys' if key == 'csat' else 'calls'})" if c["n_min"] < 30 else f"{raw} (noise)"


TREND_TXT = {"rising": "↗ rising", "easing": "↘ easing", "flat": "→ flat"}


def scenario(spec: dict) -> dict:
    """Everything the filtered pages show for one filter scenario, from SQL."""
    nb, na = ndays(spec)
    weeks = full_weeks(spec)
    post_weeks = [w for w in weeks if w >= POST0]
    sqls = {"kpi": kpi_sql(spec), "week": week_sql(spec), "reason": breakdown_sql(spec, "issue_type"),
            "voice": voice_sql(spec), "vtext": voice_text_sql(spec)}
    if len(post_weeks) >= 4:
        sqls["early"] = window_sql(spec, post_weeks[0], post_weeks[1] + dt.timedelta(days=6), "early")
        sqls["late"] = window_sql(spec, post_weeks[-2], post_weeks[-1] + dt.timedelta(days=6), "late")
    r = qmany(sqls)
    k = r["kpi"].set_index("per")
    pre = values(k.loc["pre"] if "pre" in k.index else None, nb)
    post = values(k.loc["post"] if "post" in k.index else None, na)
    e = values(r["early"].iloc[0], 14) if "early" in r and r["early"]["n"].iloc[0] else None
    l_ = values(r["late"].iloc[0], 14) if "late" in r and r["late"]["n"].iloc[0] else None
    out = {"n_before": pre[2], "n_after": post[2], "nb": nb, "na": na, "kpis": {}, "pre": pre[0], "post": post[0]}
    for key, (unit, dec, _, _) in KPIS.items():
        c = compare_kpi(key, pre, post)
        tr = trend(key, e, l_)
        out["kpis"][key] = {"pre_post": f"{fmt(pre[0][key], unit, dec)} → {fmt(post[0][key], unit, dec)}",
                            "change": change_cell(key, c), "trend": TREND_TXT.get(tr, "—"),
                            "status": status(key, c, tr), "raw": c, "trend_raw": tr}
    # weekly values (sparkline): pre-spike weeks drawn at the pre average, then spike week + post weeks
    wk = r["week"].copy()
    wk["wk"] = pd.to_datetime(wk["wk"]).dt.date
    wk = wk.set_index("wk")
    spike_monday = dt.date(2026, 5, 25)
    out["weeks"] = {}
    for key in KPIS:
        vals = []
        for w in weeks:
            row = wk.loc[w] if w in wk.index else None
            vals.append(values(row, 7)[0][key])
        out["weeks"][key] = dict(zip(weeks, vals))
        pre_w = [w for w in weeks if w < spike_monday]
        sp = [pre[0][key]] * len(pre_w) + [v for w, v in zip(weeks, vals) if w >= spike_monday]
        out.setdefault("spark", {})[key] = [round(x, 2) for x in sp if not pd.isna(x)]
    # breakdown by reason
    out["reason"] = breakdown(r["reason"], nb, na)
    # voice table
    vrows = []
    for reason, g in r["voice"].groupby("issue_type"):
        g = g.set_index("per")
        b = values(g.loc["pre"] if "pre" in g.index else None, nb)[0]
        a = values(g.loc["post"] if "post" in g.index else None, na)[0]
        vrows.append({"Reason": reason, "Calls/day": a["calls"],
                      "Change": (a["calls"] / b["calls"] - 1) * 100 if b["calls"] and not pd.isna(b["calls"]) else np.nan,
                      "Repeat": a["repeat"], "Follow-up": a["follow_up"], "Negative": a["negative"], "CSAT": a["csat"],
                      "june_note": a["june_note"]})
    out["voice"] = pd.DataFrame(vrows)
    out["vtext"] = r["vtext"]
    return out


def breakdown(df, nb, na):
    """Turn breakdown_sql output into the app's comparison table."""
    g = df.pivot_table(index="grp", columns="per", values="sw", aggfunc="sum", fill_value=0)
    n = df[df["per"].isin(["pre", "post"])].groupby("grp")["n"].sum()
    for p in ("pre", "post"):
        if p not in g:
            g[p] = 0.0
    t = pd.DataFrame({"Before": g["pre"] / (nb or np.nan), "After": g["post"] / (na or np.nan)})
    t["Change"] = t["After"] - t["Before"]
    t["% change"] = (t["After"] / t["Before"].replace(0, np.nan) - 1) * 100
    tot = t["Change"].sum()
    t["Share of increase %"] = t["Change"] / tot * 100 if tot else np.nan
    t["Sampled calls"] = n
    return t.sort_values("After", ascending=False)
