"""Company-wide pages, drill-downs, pop-ups, heatmap and hardcoded text figures vs independent bronze SQL."""
import datetime as dt
import json
import math

import numpy as np
import pandas as pd

import qa_sql as Q
from qa_sql import B, BASE, q, qmany

app = json.load(open("app_default.json"))
rows = []


def check(page, item, a, s, ok=None, tol=1e-6, note=""):
    """Record one app-vs-SQL comparison (numbers within tolerance, text exactly)."""
    if ok is None:
        if isinstance(a, (int, float)) and isinstance(s, (int, float)):
            ok = math.isclose(a, s, rel_tol=tol, abs_tol=tol)
        else:
            ok = a == s
    rows.append({"page": page, "item": item, "app": a, "sql": s, "ok": bool(ok), "note": note})


R = qmany({
    "daily": f"""SELECT
        avg(CASE WHEN `date` <= '2026-05-25' THEN technical_calls END) AS before_avg,
        avg(CASE WHEN `date` >= '2026-05-26' THEN technical_calls END) AS after_avg,
        avg(CASE WHEN `date` BETWEEN '2026-06-01' AND '2026-06-30' THEN technical_calls END) AS june_avg,
        stddev_samp(CASE WHEN `date` <= '2026-05-25' THEN technical_calls END) AS before_sd,
        min(CASE WHEN `date` <= '2026-05-25' THEN technical_calls END) AS before_min,
        max(CASE WHEN `date` <= '2026-05-25' THEN technical_calls END) AS before_max,
        count_if(`date` >= '2026-05-26' AND technical_calls > 96) AS days_above_96,
        count_if(`date` >= '2026-05-26') AS days_after,
        min(CASE WHEN `date` >= '2026-05-26' THEN technical_calls END) AS after_min,
        avg(CASE WHEN `date` BETWEEN '2026-06-24' AND '2026-06-30' THEN technical_calls END) AS last7,
        sum(CASE WHEN `date` >= '2026-05-26' THEN technical_calls - 80 END) AS extra_calls,
        max(CASE WHEN `date` = '2026-05-26' THEN technical_calls END) AS d0526,
        max(CASE WHEN `date` = '2026-05-25' THEN technical_calls END) AS d0525,
        min(CASE WHEN `date` = (SELECT min(`date`) FROM {B}.call_volume_daily WHERE technical_calls > 80) THEN `date` END) AS first_above_80,
        max(CASE WHEN `date` = '2026-06-30' THEN technical_calls END) AS d0630
        FROM {B}.call_volume_daily""",
    "around_quebec": f"SELECT `date`, technical_calls FROM {B}.call_volume_daily WHERE `date` BETWEEN '2026-05-20' AND '2026-06-06' ORDER BY 1",
    "devices": f"""SELECT trim(firmware_version) fw, count(*) n, avg(reboot_count) reboots,
        100 * avg(CASE WHEN trim(signal_quality) = 'Low' THEN 1 ELSE 0 END) low_pct,
        min(reboot_count) mn, max(reboot_count) mx, count_if(reboot_count >= 6) unstable
        FROM {B}.device_health GROUP BY 1 ORDER BY 1""",
    "events": f"SELECT trim(region) region, event_date, datediff(DATE'2026-05-26', event_date) AS days_before_spike FROM {B}.network_events ORDER BY 2",
    "shares": f"""{BASE} SELECT per, sum(CASE WHEN firmware_region = 'No update' THEN w END) AS sw_noupd, sum(w) AS sw,
        count(*) n FROM c GROUP BY per""",
    "conn_by_region": f"""{BASE} SELECT region, sum(CASE WHEN per='pre' THEN w*conn END)/25 AS pre, sum(CASE WHEN per='post' THEN w*conn END)/30 AS post
        FROM c GROUP BY region ORDER BY region""",
    "sample_rates": f"""WITH s AS (SELECT call_date, count(*) n FROM {B}.technical_calls GROUP BY 1)
        SELECT CASE WHEN v.`date` <= '2026-05-25' THEN '1-25 May' WHEN v.`date` <= '2026-05-31' THEN '26-31 May' ELSE 'June' END AS p,
        sum(coalesce(s.n,0)) sampled, sum(v.technical_calls) total, 100*sum(coalesce(s.n,0))/sum(v.technical_calls) pct
        FROM {B}.call_volume_daily v LEFT JOIN s ON s.call_date = v.`date` WHERE v.`date` >= '2026-05-01' GROUP BY 1 ORDER BY 1""",
    "transition": f"""{BASE} SELECT count(*) n, 100*avg(conn) conn_unw, 100*sum(w*conn)/sum(w) conn_w, 100*avg(rep) rep_unw,
        100*sum(w*rep)/sum(w) rep_w, sum(jn) june_notes FROM c WHERE per = 'trans'""",
    "theme": f"""WITH t AS (SELECT trim(c.issue_type) it, trim(t.detected_theme) th FROM {B}.technical_calls c JOIN {B}.transcripts t ON trim(t.call_id)=trim(c.call_id)),
        m AS (SELECT it, th, CASE it WHEN 'No Internet' THEN 'Connectivity' WHEN 'Outage Inquiry' THEN 'Connectivity' WHEN 'Slow Speed' THEN 'Speed Performance'
              WHEN 'Hardware Issue' THEN 'Equipment' WHEN 'Wi-Fi Setup' THEN 'Equipment' WHEN 'Service Appointment' THEN 'Appointments'
              WHEN 'Billing Question' THEN 'Billing' WHEN 'Account Access' THEN 'Portal/Login' END AS exp FROM t),
        pt AS (SELECT th, count(*)/750 p FROM m GROUP BY th), pe AS (SELECT exp, count(*)/750 p FROM m GROUP BY exp)
        SELECT (SELECT 100*avg(CASE WHEN th = exp THEN 1 ELSE 0 END) FROM m) AS agree_pct,
               (SELECT 100*sum(pt.p * coalesce(pe.p,0)) FROM pt LEFT JOIN pe ON pe.exp = pt.th) AS chance_pct""",
    "ai_sent": f"SELECT count(*) n, count_if(trim(t.ai_sentiment) = trim(c.customer_sentiment)) same FROM {B}.technical_calls c JOIN {B}.transcripts t ON trim(t.call_id)=trim(c.call_id)",
    "fibre_sat": f"SELECT count(*) n FROM {B}.technical_calls WHERE trim(product) = 'Fibre Gigabit' AND trim(platform) = 'Satellite'",
    "june_text": f"SELECT count(*) n, count_if(transcript_text LIKE '%June notes suggest increased regional instability, repeat troubleshooting contacts, and customer frustration.%') exact FROM {B}.transcripts WHERE transcript_text LIKE '%June notes%'",
    "csat_all": f"""{BASE} SELECT avg(csat) unweighted_all, sum(w*csat)/sum(w) weighted_all,
        avg(CASE WHEN per='pre' THEN csat END) pre_unw, avg(CASE WHEN per='post' THEN csat END) post_unw,
        100*avg(CASE WHEN per='post' THEN detr END) post_detr_unw FROM c WHERE has_fb""",
    "weeks_all": f"{BASE} SELECT wk, {Q.AGG} FROM c GROUP BY wk ORDER BY wk",
    "heat": Q.heat_sql({}),
    "vtext": Q.voice_text_sql({}),
    "voice": Q.voice_sql({}),
    "voice_weeks": f"{BASE} SELECT issue_type, wk, sum(w)/7 AS per_day FROM c GROUP BY 1, 2",
    "options": f"""SELECT 'region' col, collect_set(trim(region)) v FROM {B}.technical_calls UNION ALL
        SELECT 'platform', collect_set(trim(platform)) FROM {B}.technical_calls UNION ALL
        SELECT 'product', collect_set(trim(product)) FROM {B}.technical_calls UNION ALL
        SELECT 'customer_segment', collect_set(trim(customer_segment)) FROM {B}.technical_calls UNION ALL
        SELECT 'channel', collect_set(trim(channel)) FROM {B}.technical_calls UNION ALL
        SELECT 'issue_type', collect_set(trim(issue_type)) FROM {B}.technical_calls UNION ALL
        SELECT 'resolution_status', collect_set(trim(resolution_status)) FROM {B}.technical_calls""",
    "trim_check": f"""SELECT count_if(region <> trim(region) OR platform <> trim(platform) OR product <> trim(product)
        OR issue_type <> trim(issue_type) OR channel <> trim(channel) OR customer_segment <> trim(customer_segment)
        OR resolution_status <> trim(resolution_status)) untrimmed FROM {B}.technical_calls""",
})
# dimension breakdowns + per-group 'calls' noise inputs for every drill-down
DIMS = {"Reason": "issue_type", "Region": "region", "Firmware update": "firmware_region", "Platform": "platform",
        "Product": "product", "Segment": "customer_segment", "Channel": "channel", "Outcome": "resolution_status"}
R.update(qmany({f"dim_{col}": f"{BASE} SELECT {col} AS grp, per, count(*) n, sum(w) sw, sqrt(sum(w*w)) rss FROM c GROUP BY 1, 2"
                for col in DIMS.values()}))
R.update(qmany({f"wk_{col}": f"{BASE} SELECT {col} AS grp, wk, sum(w)/7 per_day FROM c GROUP BY 1, 2" for col in DIMS.values()}))
R.update(qmany({f"sub_{col}": (f"{BASE} SELECT {col} AS grp, {'region' if col == 'issue_type' else 'issue_type'} AS sub, per, sum(w) sw "
                               f"FROM c GROUP BY 1, 2, 3") for col in DIMS.values()}))

# ======================================================================= Summary page
d = R["daily"].iloc[0]
S = app["summary"]
check("Summary", "title % jump", S["title"][0], f"Technical calls jumped {(d.after_avg / d.before_avg - 1) * 100:.0f}% overnight on 26 May, and stayed high")
check("Summary", "daily chart line: before avg (1 Apr–25 May)", S["plotly"][0]["traces"][1]["y"][0], float(d.before_avg))
check("Summary", "daily chart line: after avg (26 May–30 Jun)", S["plotly"][0]["traces"][2]["y"][0], float(d.after_avg))
check("Summary", "chart heading", S["markdown"][0], f"**Daily technical calls: {d.before_avg:.0f} → {d.after_avg:.0f} a day**")
vol = q(f"SELECT technical_calls FROM {B}.call_volume_daily ORDER BY `date`")["technical_calls"].tolist()
check("Summary", "daily chart series = call_volume_daily (91 days)", S["plotly"][0]["traces"][0]["y"], vol)
sc = Q.scenario({})
pre, post = sc["pre"], sc["post"]
for i, (key, lab) in enumerate((("calls", "Calls per day"), ("connection", "Connection problems"), ("repeat", "Repeat calls"),
                                 ("agent_hours", "Agent hours per day"))):
    unit, dec, _, _ = Q.KPIS[key]
    m = S["metric"][i]
    check("Summary", f"card {lab}: value", m["value"], Q.fmt(post[key], unit, dec))
    exp_delta = Q.change(key, pre[key], post[key]) if sc["kpis"][key]["raw"]["real"] else ""
    check("Summary", f"card {lab}: delta", m["delta"], exp_delta)
    check("Summary", f"card {lab}: pre-spike (help)", m["help"].split("Pre-spike: ")[1], Q.fmt(pre[key], unit, dec) + ".")
conn_share = (post["calls"] * post["connection"] - pre["calls"] * pre["connection"]) / 100 / (post["calls"] - pre["calls"]) * 100
check("Summary", "'% of the increase' (No Internet + Slow Speed)", S["markdown"][1].split("**")[1], f"{conn_share:.0f}%",
      note=f"exact = {conn_share:.2f}%")
cr = R["conn_by_region"]
check("Summary", "'in every region' (connectivity calls/day rose in all 5 regions)", "claimed", "claimed" if (cr["post"] > cr["pre"]).all() else "false",
      note="; ".join(f"{r.region} {r.pre:.1f}→{r.post:.1f}" for r in cr.itertuples()))
ca = R["csat_all"].iloc[0]
check("Summary", "'CSAT is low (~3.3) and unchanged'", "~3.3, unchanged",
      f"pre {pre['csat']:.2f} / post {post['csat']:.2f}; all calls weighted {ca.weighted_all:.2f}, unweighted {ca.unweighted_all:.2f}; change within noise",
      ok=abs(ca.weighted_all - 3.3) < 0.1 and not sc["kpis"]["csat"]["raw"]["real"],
      note="KPIs page shows 3.2 → 3.4 for the same metric")
check("Summary", "alert lines 96 / 18% (policy values from Slide 3)", "96 / 18%", f"{1.2 * d.before_avg:.0f} / (normal {pre['repeat']:.0f}%)",
      ok=True, note="96 = 1.2 × 80 normal; 18% is a chosen line above the 13% normal; matches deck notes")

# ======================================================================= Root cause page
dv = R["devices"].set_index("fw")
rc = app["root-cause"]
fwbar = rc["plotly"][0]["traces"][0]
check("Root cause", "device bars: labels", fwbar["x"], [f"{i} ({int(r.n)} devices)" for i, r in dv.iterrows()])
check("Root cause", "device bars: avg reboots", fwbar["y"], [float(x) for x in dv["reboots"]],
      ok=all(abs(a - b) < 1e-9 for a, b in zip(fwbar["y"], dv["reboots"])))
check("Root cause", "device bars: text", fwbar["text"], [f"{r.reboots:.0f}× a week · {r.low_pct:.0f}% weak signal" for _, r in dv.iterrows()])
check("Root cause", "'12× a week (vs 2), all with weak signal'", "12 vs 2, 100% weak",
      f"{dv.loc['FW_3.8.1', 'reboots']:.0f} vs {dv.loc['FW_3.7.4', 'reboots']:.0f}, {dv.loc['FW_3.8.1', 'low_pct']:.0f}% weak",
      ok=dv.loc["FW_3.8.1", "reboots"] == 12 and dv.loc["FW_3.7.4", "reboots"] == 2 and dv.loc["FW_3.8.1", "low_pct"] == 100)
ev = R["events"]
check("Root cause", "'jump came 1–4 days after Ontario and Prairies updates'", "1–4 days",
      ", ".join(f"{r.region} {r.days_before_spike} d" for r in ev.itertuples()),
      ok=sorted(ev.loc[ev.region.isin(["Ontario", "Prairies"]), "days_before_spike"]) == [1, 4])
aq = R["around_quebec"]
aq["date"] = pd.to_datetime(aq["date"]).dt.date
seq = dict(zip(aq["date"], aq["technical_calls"]))
check("Root cause", "'no second jump after Quebec's 2 Jun update'", "no second jump",
      "  ".join(f"{k:%d %b}:{v}" for k, v in seq.items() if dt.date(2026, 5, 29) <= k <= dt.date(2026, 6, 5)),
      ok=abs(seq[dt.date(2026, 6, 2)] - seq[dt.date(2026, 6, 1)]) <= 2 and abs(seq[dt.date(2026, 6, 3)] - seq[dt.date(2026, 6, 2)]) <= 2,
      note="day-to-day steps of ±1 or a −10 reset; no step up at 2 Jun")
sh = R["shares"].set_index("per")
shares = [sh.loc["pre", "sw_noupd"] / sh.loc["pre", "sw"] * 100, sh.loc["post", "sw_noupd"] / sh.loc["post", "sw"] * 100,
          (sh.loc["pre", "sw_noupd"] / 25) / (sh.loc["post", "sw"] / 30) * 100]
bar2 = rc["plotly"][1]["traces"][0]
for lab, a_, s_ in zip(["pre-spike", "post-spike", "if only updated provinces hit"], bar2["y"], shares):
    check("Root cause", f"BC + Atlantic share: {lab}", a_, float(s_), note=f"{s_:.2f}%")
check("Root cause", "BC + Atlantic share labels", bar2["text"], [f"{v:.0f}%" for v in shares])

# ======================================================================= Monitor page
mo = app["monitor"]
met = {m["label"]: m for m in mo["metric"]}
check("Monitor", "retention risk: repeat calls value", met["Retention risk: repeat calls"]["value"], Q.fmt(post["repeat"], "%"))
check("Monitor", "retention risk: delta", met["Retention risk: repeat calls"]["delta"], Q.change("repeat", pre["repeat"], post["repeat"]))
check("Monitor", "detractors (help)", met["Retention risk: repeat calls"]["help"], f"{post['detractors']:.0f}% of surveyed callers are detractors.")
check("Monitor", "agent hours/day value", met["Cost to serve: agent hours per day"]["value"], Q.fmt(post["agent_hours"]))
check("Monitor", "agent hours delta", met["Cost to serve: agent hours per day"]["delta"], Q.change("agent_hours", pre["agent_hours"], post["agent_hours"]))
check("Monitor", "workload ratio (help)", met["Cost to serve: agent hours per day"]["help"], f"{post['agent_hours'] / pre['agent_hours']:.1f}× the pre-spike workload.")
check("Monitor", "days above 96 since spike", met["Reputation: days above 96 calls"]["value"], str(int(d.days_above_96)))
check("Monitor", "'Every day since the spike.'", "every day", f"{int(d.days_above_96)} of {int(d.days_after)} (min {int(d.after_min)})",
      ok=d.days_above_96 == d.days_after)
check("Monitor", "volume alert: last 7 days avg (24–30 Jun)", met["Volume: calls per day"]["value"], f"{d.last7:,.0f}", note=f"{d.last7:.2f}")
check("Monitor", "repeat alert value", met["Repeat calls"]["value"], Q.fmt(post["repeat"], "%"))
check("Monitor", "unstable devices (6+ reboots)", met["Unreported outages: unstable devices"]["value"], f"{int(dv['unstable'].sum())} of {int(dv['n'].sum())}")
check("Monitor", "alert statuses", [m for m in mo["markdown"] if m.startswith(":")],
      [":red[**▲ ALERT**]" if d.last7 > 96 else ":green[**● OK**]", ":red[**▲ ALERT**]" if post["repeat"] > 18 else ":green[**● OK**]", ":gray[**● Watch**]"])
check("Monitor", "normal values in captions", [c for c in mo["caption"] if c.startswith("Alert above")][:2],
      [f"Alert above 96 · normal {d.before_avg:.0f} · company-wide, last 7 days in the dates", f"Alert above 18% · normal {pre['repeat']:.0f}% · post-spike"])
check("Monitor", "days above the line caption", next(c for c in mo["caption"] if c.startswith("Above the line on")),
      f"Above the line on {int(d.days_above_96)} of {int(d.days_after)} days since the spike")
wa = R["weeks_all"].copy()
wa["wk"] = pd.to_datetime(wa["wk"]).dt.date
full = Q.full_weeks({})
wrep = [float(wa.set_index("wk").loc[w, "repeat"]) for w in full]
rep_chart = mo["plotly"][1]["traces"][0]["y"]
check("Monitor", "weekly repeat-rate chart values", [round(x, 2) for x in rep_chart], [round(x, 2) for x in wrep],
      ok=all(abs(a - b) < 1e-6 for a, b in zip(rep_chart, wrep)))
check("Monitor", "weeks above 18% caption", next(c for c in mo["caption"] if "full weeks" in c),
      f"Above the line in {sum(x > 18 for x in wrep)} of {len(wrep)} full weeks · company-wide")
check("Monitor", "daily chart (alert view) = call_volume_daily", mo["plotly"][0]["traces"][0]["y"], vol)

# ======================================================================= KPI pop-ups: weekly charts (raw weekly values)
labels = {"calls": "Calls per day", "connection": "Connection problems", "repeat": "Repeat calls", "follow_up": "Follow-up needed",
          "duration": "Avg call duration", "agent_hours": "Agent hours per day", "tech_visits": "Technician visits per day", "csat": "CSAT (1–5)"}
for key, pop in app["kpi_popups"].items():
    unit, dec, _, _ = Q.KPIS[key]
    tr = {t["name"]: t for t in pop["plotly"][-1]["traces"]}
    got = tr["Pre-spike weeks (few calls)"]["y"] + tr["Spike week"]["y"] + tr["Post-spike weeks"]["y"]
    exp = [sc["weeks"][key][w] for w in full]
    check("KPIs pop-up", f"{labels[key]}: 8 weekly values", [round(x, 2) for x in got], [round(x, 2) for x in exp],
          ok=all(abs(a - b) < 1e-6 for a, b in zip(got, exp)))
    check("KPIs pop-up", f"{labels[key]}: dashed pre-spike normal", tr["Pre-spike normal"]["y"][0], float(pre[key]))
    m = {x["label"]: x for x in pop["metric"]}
    check("KPIs pop-up", f"{labels[key]}: pre / post metrics", (m["Pre-spike"]["value"], m["Post-spike"]["value"]),
          (Q.fmt(pre[key], unit, dec), Q.fmt(post[key], unit, dec)))
    check("KPIs pop-up", f"{labels[key]}: trend metric", m["Trend since the spike"]["value"],
          {"rising": "↗ Rising", "easing": "↘ Easing", "flat": "→ Flat"}.get(sc["kpis"][key]["trend_raw"], "—"))
    box = (pop["error"] + pop["warning"] + pop["info"] + pop["success"])[0]
    check("KPIs pop-up", f"{labels[key]}: status sentence starts", box.split(".**")[0].strip("*"), sc["kpis"][key]["status"])

# ======================================================================= What drove it: every drill-down + heatmap
for dim, col in DIMS.items():
    g = R[f"dim_{col}"]
    t = Q.breakdown(g, 25, 30)
    rss = g.set_index(["grp", "per"])
    wk = R[f"wk_{col}"].copy()
    wk["wk"] = pd.to_datetime(wk["wk"]).dt.date
    sub = R[f"sub_{col}"]
    a_dim = app["drivers_dims"][dim]
    for opt, dr in a_dim["drills"].items():
        r = t.loc[opt]
        m = {x["label"]: x for x in dr["metric"]}
        check("What drove it (drill)", f"{dim}={opt}: post calls/day", m["Post-spike calls/day"]["value"], Q.fmt(r["After"]))
        check("What drove it (drill)", f"{dim}={opt}: pre (help)", m["Post-spike calls/day"]["help"], f"Pre-spike: {r['Before']:.1f} a day")
        check("What drove it (drill)", f"{dim}={opt}: share of increase", m["Share of the increase"]["value"], Q.fmt(r["Share of increase %"], "%"))
        check("What drove it (drill)", f"{dim}={opt}: change (help)", m["Share of the increase"]["help"], f"{r['Change']:+.1f} calls a day")
        # delta: noise test on weighted counts for this group
        nb_ = int(rss.loc[(opt, "pre"), "n"]) if (opt, "pre") in rss.index else 0
        na_ = int(rss.loc[(opt, "post"), "n"]) if (opt, "post") in rss.index else 0
        se_b = rss.loc[(opt, "pre"), "rss"] / 25 if nb_ else np.nan
        se_a = rss.loc[(opt, "post"), "rss"] / 30 if na_ else np.nan
        real = min(nb_, na_) >= 30 and abs(r["After"] - r["Before"]) > 2 * np.sqrt(se_b ** 2 + se_a ** 2)
        exp_delta = Q.change("calls", r["Before"], r["After"]) if real else ""
        check("What drove it (drill)", f"{dim}={opt}: delta (noise-tested, n_min={min(nb_, na_)})", m["Post-spike calls/day"]["delta"], exp_delta)
        wseries = dr["plotly"][0]["traces"][0]
        exp_w = [float(wk[(wk.grp == opt) & (wk.wk == w)]["per_day"].sum()) for w in full]
        check("What drove it (drill)", f"{dim}={opt}: weekly chart", [round(x, 2) for x in wseries["y"]], [round(x, 2) for x in exp_w],
              ok=all(abs(a - b) < 1e-6 for a, b in zip(wseries["y"], exp_w)))
        st_ = Q.breakdown(sub[sub.grp == opt].rename(columns={"grp": "g0", "sub": "grp"}).assign(n=0), 25, 30)
        bars = dr["plotly"][1]["traces"]
        ok = list(bars[0]["y"]) == list(st_.index) and all(abs(a - b) < 1e-6 for a, b in zip(bars[0]["x"], st_["Before"])) \
            and all(abs(a - b) < 1e-6 for a, b in zip(bars[1]["x"], st_["After"]))
        check("What drove it (drill)", f"{dim}={opt}: split chart by {'region' if col == 'issue_type' else 'reason'}",
              "bars match" if ok else f"{bars[0]['y']}", "bars match", ok=ok)
    # main bars for the dimension
    bars = a_dim["plotly"][0]["traces"]
    ok = all(abs(a - b) < 1e-6 for a, b in zip(bars[0]["x"], t["Before"])) and all(abs(a - b) < 1e-6 for a, b in zip(bars[1]["x"], t["After"]))
    check("What drove it", f"{dim}: main bar chart (pre/post per group)", "bars match" if ok else "differs", "bars match", ok=ok)
    pct_lbl = [lab.split("<b>")[1].split("</b>")[0] for lab in bars[0]["y"]]
    check("What drove it", f"{dim}: % change labels", pct_lbl, [f"{v:+.0f}%" for v in t["% change"]])
    tbl = a_dim["dataframe"][0]
    ok = all(abs(rw[c] - t.loc[rw[col], c]) < 1e-6 for rw in tbl for c in ("Before", "After", "Change", "% change", "Share of increase %"))
    check("What drove it", f"{dim}: numbers table (all cells)", "match" if ok else "differs", "match", ok=ok)
    tot = t["Change"].sum()
    lead = t.sort_values("Change", ascending=False).head(2)
    check("What drove it", f"{dim}: takeaway line", a_dim["markdown"][0],
          f"**{' and '.join(lead.index)} add the most: {lead['Change'].sum() / tot * 100:.0f}% of the increase** · "
          f"{int((t['Change'] > 0).sum())} of {len(t)} groups rose")
# heatmap (Reason view): both views, every cell
h = R["heat"].pivot_table(index=["region", "issue_type"], columns="per", values="sw", aggfunc="sum", fill_value=0)
h["after_pd"], h["before_pd"] = h["post"] / 30, h["pre"] / 25
for view, val in (("Calls per day post-spike", h["after_pd"]), ("Change vs pre-spike", h["after_pd"] - h["before_pd"])):
    hm = app["drivers_dims"]["Reason"][f"heat_{view}"]["traces"][0]
    ys = [y.split(" (")[0] for y in hm["y"]]
    errs = [(y, x) for i, y in enumerate(ys) for j, x in enumerate(hm["x"])
            if abs(hm["z"][i][j] - float(val.get((y, x), 0.0))) > 1e-6]
    check("What drove it", f"heatmap '{view}': all {len(ys) * len(hm['x'])} cells", f"{len(errs)} mismatches", "0 mismatches")
    check("What drove it", f"heatmap '{view}': row labels carry firmware tag", hm["y"][:2], hm["y"][:2], ok=all("(" in y for y in hm["y"]))

# ======================================================================= Customer voice: table weekly column + pop-ups
vw = R["voice_weeks"].copy()
vw["wk"] = pd.to_datetime(vw["wk"]).dt.date
vt = app["voice"]["dataframe"][0]
for r in vt:
    exp = [round(float(vw[(vw.issue_type == r["Reason"]) & (vw.wk == w)]["per_day"].sum()), 1) for w in full]
    check("Customer voice", f"{r['Reason']}: week-by-week sparkline", r["Weekly"], exp)
vtext = R["vtext"]
vg = R["voice"]
for reason, pop in app["voice_popups"].items():
    g = vg[vg.issue_type == reason].set_index("per")
    b = Q.values(g.loc["pre"], 25)
    a = Q.values(g.loc["post"], 30)
    m = {x["label"]: x for x in pop["metric"]}
    for key, lab in (("calls", "Calls per day"), ("repeat", "Repeat calls"), ("follow_up", "Follow-up needed"), ("csat", "CSAT (1–5)")):
        unit, dec, _, _ = Q.KPIS[key]
        c = Q.compare_kpi(key, b, a)
        check("Customer voice pop-up", f"{reason}: {lab} post / pre", (m[lab]["value"], m[lab]["help"]),
              (Q.fmt(a[0][key], unit, dec), f"Pre-spike: {Q.fmt(b[0][key], unit, dec)}"))
        check("Customer voice pop-up", f"{reason}: {lab} comparison shown?", m[lab]["delta"] or "(too few / noise note)",
              Q.change(key, b[0][key], a[0][key]) if c["real"] else "(too few / noise note)", note=f"n_min={c['n_min']}")
    said = vtext[(vtext.issue_type == reason) & (vtext.per == "post")].sort_values("sw", ascending=False)
    quotes = [x for x in pop["markdown"] if x.startswith(">")]
    exp_q = [f"> “{rw.core}”  \n> <small>{rw.sw / said.sw.sum() * 100:.0f}% of these calls</small>" for rw in said.head(2).itertuples()]
    check("Customer voice pop-up", f"{reason}: top call summaries + shares", quotes, exp_q)
    jn = a[0]["june_note"]
    note = [x for x in pop["markdown"] if x.startswith("**Agent note")]
    check("Customer voice pop-up", f"{reason}: June agent-note share", note[0].split(" of these")[0] if note else "(none)",
          f"**Agent note** on {jn:.0f}%" if jn > 0 else "(none)")

# ======================================================================= Data notes: hardcoded figures
sr = R["sample_rates"].set_index("p")
tr_ = R["transition"].iloc[0]
th = R["theme"].iloc[0]
ai = R["ai_sent"].iloc[0]
notes = " ".join(app["notes"]["markdown"])
check("Data notes", "'6% of calls on 1–25 May, 4% on 26–31 May, 13% in June'", "6% / 4% / 13%",
      f"{sr.loc['1-25 May', 'pct']:.1f}% / {sr.loc['26-31 May', 'pct']:.1f}% / {sr.loc['June', 'pct']:.1f}%",
      ok=[round(sr.loc[p, "pct"]) for p in ("1-25 May", "26-31 May", "June")] == [6, 4, 13])
check("Data notes", "'~10% sample'", "~10%", f"{sr['sampled'].sum() / sr['total'].sum() * 100:.1f}% (750 of {int(sr['total'].sum())})",
      ok=abs(sr['sampled'].sum() / sr['total'].sum() * 100 - 10) < 1)
check("Data notes", "'34 sampled calls for 26–31 May'", 34, int(tr_.n))
check("Data notes", "'connectivity 29%' (26–31 May)", "29%", f"unweighted {tr_.conn_unw:.1f}% / weighted {tr_.conn_w:.1f}%",
      ok=round(tr_.conn_unw) == 29, note="matches the unweighted share; the app's own (weighted) method gives 31%")
check("Data notes", "'repeats 9%' (26–31 May)", "9%", f"unweighted {tr_.rep_unw:.1f}% / weighted {tr_.rep_w:.1f}%",
      ok=round(tr_.rep_unw) == 9 or round(tr_.rep_w) == 9)
check("Data notes", "'no June agent note' (26–31 May)", 0, int(tr_.june_notes))
check("Data notes", "'detected_theme matched … 18% vs 17%'", "18% vs 17%", f"{th.agree_pct:.1f}% vs {th.chance_pct:.1f}%",
      ok=round(th.agree_pct) == 18 and round(th.chance_pct) == 17)
check("Data notes", "'ai_sentiment is a copy of customer_sentiment'", "copy", f"{int(ai.same)} of {int(ai.n)} identical", ok=ai.same == ai.n)
check("Data notes", "'Fibre Gigabit on Satellite' example", "exists", f"{int(R['fibre_sat'].iloc[0].n)} calls", ok=R["fibre_sat"].iloc[0].n > 0)
jt = R["june_text"].iloc[0]
check("Customer voice pop-up", "agent-note quote is the exact transcript text", "exact", f"{int(jt.exact)} of {int(jt.n)} 'June notes' transcripts", ok=jt.exact == jt.n)
check("Data notes", "'Unstable devices = 6+ reboots a week'", "6+", "3.7.4 = 2, 3.8.1 = 12 (no values in between)",
      ok=set(dv["mn"]) | set(dv["mx"]) == {2, 12})

# ======================================================================= filter option lists vs distinct values
opts = {r.col: sorted(json.loads(r.v)) for r in R["options"].itertuples()}
ms = {m["key"]: m["options"] for m in app["kpis"]["multiselect"]}
for col in ("region", "issue_type", "platform", "product", "customer_segment", "channel"):
    check("Filters", f"option list: {col}", ms[f"f_{col}"], opts[col])
check("Filters", "option list: firmware_region (proxy)", ms["f_firmware_region"], ["No update", "Update logged"])
check("Filters", "bronze values need no trimming", 0, int(R["trim_check"].iloc[0].untrimmed))
dims_opts = next(s for s in app["drivers"]["selectbox"] if s["key"] == "dim")["options"]
check("Filters", "'Break down by' options", dims_opts, list(DIMS))

df = pd.DataFrame(rows)
df.to_csv("static_checks.csv", index=False)
print("checks:", len(df), "passed:", int(df.ok.sum()), "failed:", int((~df.ok).sum()))
pd.set_option("display.width", 250)
print(df[~df.ok].to_string(max_colwidth=120))
print("\nSELECTED VALUES")
print(df[df.note != ""][["page", "item", "app", "sql", "note"]].to_string(max_colwidth=110))
