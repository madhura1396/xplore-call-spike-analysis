"""Default (unfiltered) view: every page, every KPI pop-up, every voice pop-up, every drill-down."""
from harness import *
res = {}
at = AppTest.from_file(f"{APP}/app.py", default_timeout=120); at.run()
res["summary"] = snap(at)
for p in PAGES[1:]:
    goto(at, p); res[p] = snap(at)
# KPI pop-ups
at = start()
res["kpi_popups"] = {}
for k in ["calls", "connection", "repeat", "follow_up", "duration", "agent_hours", "tech_visits", "csat"]:
    at.session_state["kpi_open"] = k; at.run(); res["kpi_popups"][k] = snap(at)
# voice pop-ups
goto(at, "voice")
reasons = [r["Reason"] for r in res["voice"]["dataframe"][0]]
res["voice_popups"] = {}
for r in reasons:
    at.session_state["voice_open"] = r; at.run(); res["voice_popups"][r] = snap(at)
# drivers: every dimension, every drill choice
goto(at, "drivers")
res["drivers_dims"] = {}
for dim in at.selectbox(key="dim").options:
    at.selectbox(key="dim").set_value(dim).run()
    s = snap(at)
    drill = next(x for x in at.selectbox if x.key and x.key.startswith("drill_"))
    s["drills"] = {}
    for opt in drill.options:
        at.selectbox(key=drill.key).set_value(opt).run()
        d = snap(at)
        s["drills"][opt] = {"metric": d["metric"], "plotly": d["plotly"][1:], "exception": d["exception"]}
    for view in at.radio(key="heat_view").options:
        at.radio(key="heat_view").set_value(view).run()
        s["heat_" + view] = snap(at)["plotly"][-1]
    res["drivers_dims"][dim] = s
json.dump(res, open("app_default.json", "w"), indent=1, default=str)
print("done", {k: (len(v) if isinstance(v, dict) else '') for k, v in res.items()})
