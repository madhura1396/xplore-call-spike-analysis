"""Compare the app (app_filters.json, from run_filters.py) with independent bronze SQL (qa_sql.scenario) per scenario."""
import json
import math
import pickle

import numpy as np
import pandas as pd

import qa_sql as Q
from scenarios import SCEN

app = json.load(open("app_filters.json"))
default_app = app["default"]
rows = []
sql_cache = {}


def check(scn, page, item, a, s, ok=None, tol=1e-6):
    """Record one app-vs-SQL comparison (numbers within tolerance, text exactly)."""
    if ok is None:
        if isinstance(a, (int, float)) and isinstance(s, (int, float)) and a is not None and s is not None:
            if (pd.isna(a) and pd.isna(s)):
                ok = True
            else:
                ok = (not pd.isna(a)) and (not pd.isna(s)) and math.isclose(a, s, rel_tol=tol, abs_tol=tol)
        else:
            ok = (a == s) or (a is None and s is not None and pd.isna(s))
    rows.append({"scenario": scn, "page": page, "item": item, "app": a, "sql": s, "ok": bool(ok)})
    return ok


def num(v):
    """None → NaN, otherwise float."""
    return np.nan if v is None else float(v)


for name, spec in SCEN.items():
    s = Q.scenario(spec)
    sql_cache[name] = s
    a = app[name]
    nb, na = s["nb"], s["na"]
    n_tot = s["n_before"] + s["n_after"]
    k = a["kpis"]
    any_rows = len(s["vtext"]) > 0                         # any sampled call at all in the filtered range
    # ---------------- KPIs page
    overview = next((d for d in k["dataframe"] if d and "KPI" in d[0]), None)
    if not any_rows:
        check(name, "KPIs", "empty-state warning", k["warning"][:1],
              ["No sampled calls match these filters. Widen the dates or remove a filter."])
    elif not (nb and na):
        check(name, "KPIs", "need-both-periods info", k["info"][:1],
              ["Include both pre-spike (1–25 May) and post-spike (June) dates to compare."])
    else:
        check(name, "KPIs", "overview table present", overview is not None, True)
        labels = dict(zip(Q.KPIS, ["Calls per day", "Connection problems", "Repeat calls", "Follow-up needed",
                                   "Avg call duration", "Agent hours per day", "Technician visits per day", "CSAT (1–5)"]))
        app_rows = {r["KPI"]: r for r in overview}
        for key, lab in labels.items():
            ar, sr = app_rows[lab], s["kpis"][key]
            check(name, "KPIs", f"{lab}: pre → post", ar["Pre → post"], sr["pre_post"])
            check(name, "KPIs", f"{lab}: change", ar["Change"], sr["change"])
            check(name, "KPIs", f"{lab}: trend", ar["Trend"], sr["trend"])
            check(name, "KPIs", f"{lab}: status", ar["Status"], sr["status"])
            check(name, "KPIs", f"{lab}: sparkline", ar["Week by week"], s["spark"][key],
                  ok=len(ar["Week by week"]) == len(s["spark"][key]) and
                  all(abs(x - y) <= 0.0051 for x, y in zip(ar["Week by week"], s["spark"][key])))
        cap = next(c for c in k["caption"] if "sampled calls pre-spike" in c)
        check(name, "KPIs", "sampled-call caption", cap.split(" ·")[0],
              f"{s['n_before']} sampled calls pre-spike, {s['n_after']} post-spike")
        want_warn = min(s["n_before"], s["n_after"]) < 30
        check(name, "KPIs", "<30 sampled calls warning shown", any("Fewer than 30" in w for w in k["warning"]), want_warn)
        sts = [s["kpis"][x]["status"] for x in Q.KPIS]
        bad = sum(st in ("Getting worse", "Still high, not recovering", "Worse than pre-spike") for st in sts)
        mid = sum(st in ("Easing, still high", "Slightly above pre-spike") for st in sts)
        head = next(m for m in k["markdown"] if " of 8 KPIs" in m)
        check(name, "KPIs", "headline count line (bad/mid/ok)", head.split("**")[1].split(",")[0].split(" of")[0] + "/" +
              head.split(", ")[1].split(" ")[0] + "/" + head.split(", ")[2].split(" ")[0],
              f"{bad}/{mid}/{8 - bad - mid}")
    # ---------------- What drove it (Reason)
    d = a["drivers"]
    tbl = next((x for x in d["dataframe"] if x and "issue_type" in x[0]), None)
    if any_rows and nb and na:
        st_ = s["reason"]
        check(name, "What drove it", "reason table: groups (order)", [r["issue_type"] for r in tbl], list(st_.index))
        for r in tbl:
            g = r["issue_type"]
            for col in ("Before", "After", "Change", "% change", "Share of increase %"):
                check(name, "What drove it", f"{g}: {col}", num(r[col]), float(st_.loc[g, col]))
            check(name, "What drove it", f"{g}: sampled calls", int(r["Sampled calls"]), int(st_.loc[g, "Sampled calls"]))
        tot = st_["Change"].sum()
        lead = st_.sort_values("Change", ascending=False).head(2)
        if len(st_) == 1:
            exp = f"**Only one reason group in this selection: {st_.index[0]}**"
        elif tot > 0:
            exp = (f"**{' and '.join(lead.index)} {'add' if len(lead) > 1 else 'adds'} the most: "
                   f"{lead['Change'].sum() / tot * 100:.0f}% of the increase** · {int((st_['Change'] > 0).sum())} of "
                   f"{len(st_)} groups rose")
        else:
            exp = "**No overall increase for this selection**"
        got = next((m for m in d["markdown"] if m.startswith("**")), "")
        check(name, "What drove it", "takeaway line", got if not exp.startswith("**Only") else got.split(" · ")[0], exp)
    else:
        check(name, "What drove it", "empty / need-both message", (d["info"] or [""])[0][:20],
              ("No sampled calls match" if not any_rows else "Include both pre-spik")[:20])
    # ---------------- Customer voice
    v = a["voice"]
    vt = next((x for x in v["dataframe"] if x and "Reason" in x[0]), None)
    if any_rows:
        sv = s["voice"].set_index("Reason")
        if vt is None:
            check(name, "Customer voice", "table present", False, True)
        else:
            check(name, "Customer voice", "reasons listed", sorted(r["Reason"] for r in vt), sorted(sv.index))
            for r in vt:
                for col in ("Calls/day", "Change", "Repeat", "Follow-up", "Negative", "CSAT"):
                    check(name, "Customer voice", f"{r['Reason']}: {col}", num(r[col]), float(sv.loc[r["Reason"], col]))
            if not (nb and na):
                check(name, "Customer voice", "UX: table without both periods shows blank/NaN cells",
                      "blank cells, no explanation", "should explain (like other pages)", ok=False)
    else:
        check(name, "Customer voice", "empty message", (v["info"] or [""])[0][:22], "No sampled calls match"[:22])
    # ---------------- Monitor (selection-dependent parts)
    m = a["monitor"]
    met = {x["label"]: x["value"] for x in m["metric"]}
    rep = s["post"]["repeat"]
    check(name, "Monitor", "repeat alert value", met.get("Repeat calls"), Q.fmt(rep, "%"))
    states = [x for x in m["markdown"] if x.startswith((":red[", ":green[", ":gray["))]
    exp_state = "n/a (no data in range)" if pd.isna(rep) else ("▲ ALERT" if rep > 18 else "● OK")
    check(name, "Monitor", "repeat alert status", states[1].split("**")[1] if len(states) > 1 else None, exp_state)
    # ---------------- company-wide pages must ignore filters
    for page in ("summary", "root-cause"):
        same = [(x["label"], x["value"], x["delta"]) for x in a[page]["metric"]] == \
               [(x["label"], x["value"], x["delta"]) for x in default_app[page]["metric"]] and \
               a[page]["plotly"] == default_app[page]["plotly"]
        check(name, page, "company-wide page unchanged by filters", same, True)
    # ---------------- persistence: same "Showing:" caption on every filtered page, incl. after other pages
    shows = {p: next((c for c in a[p]["caption"] if c.startswith("Showing:")), None)
             for p in ("kpis", "drivers", "voice", "monitor", "kpis_again")}
    check(name, "all", "filters persist across pages", len(set(shows.values())) == 1, True)
    if spec:
        vals = [x for kk, vv in spec.items() if kk != "dates" for x in vv]
        check(name, "all", "scope caption names the filters", all(x in shows["kpis"] for x in vals), True)
    # ---------------- no NaN text anywhere visible
    blob = json.dumps([a[p]["markdown"] + a[p]["caption"] + [str(x) for x in a[p]["metric"]] for p in a]).lower()
    check(name, "all", "no 'nan' in text/metrics", " nan" in blob or "nan%" in blob or "'nan'" in blob, False)

pickle.dump(sql_cache, open("sql_scenarios.pkl", "wb"))
df = pd.DataFrame(rows)
df.to_csv("filter_checks.csv", index=False)
print("checks:", len(df), "passed:", int(df["ok"].sum()), "failed:", int((~df["ok"]).sum()))
print(df[~df["ok"]].to_string(max_colwidth=90))
