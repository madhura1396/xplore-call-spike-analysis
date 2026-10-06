"""Headless test of the multipage app (app/app.py) with Streamlit AppTest and real data (loaded once via the CLI).
Visits every page under edge-case filters, checks that filters survive page changes, and drives every control
AppTest can reach (sidebar radio + sliders, drill-down selectboxes, heatmap view, reset). Chart clicks and table-row
clicks cannot be simulated here; their fallbacks (selectbox / first row) are tested.
Run: app/.venv/bin/python app/test_app.py   → expect FAILURES: 0
"""
import datetime as dt
import logging
import os
import sys
import warnings

warnings.filterwarnings("ignore")
logging.disable(logging.WARNING)
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, f"{ROOT}/app")
import data  # noqa: E402

real = data.load()
data.load = lambda: {k: v.copy() for k, v in real.items()}   # app.py does `from data import load` -> patched
from streamlit.testing.v1 import AppTest  # noqa: E402
from streamlit.util import calc_md5  # noqa: E402

D = dt.date
KPI_KEYS = ["calls", "connection", "repeat", "follow_up", "duration", "agent_hours", "tech_visits", "csat"]
KPI_LABELS = ["Calls per day", "Connection problems", "Repeat calls", "Follow-up needed", "Avg call duration",
              "Agent hours per day", "Technician visits per day", "CSAT (1–5)"]
# page url_path → text that proves the page rendered
PAGES = {"summary": "jumped", "kpis": "KPIs and trend", "drivers": "What drove the increase", "root-cause": "Suspect 1",
         "voice": "Customer voice", "monitor": "Monitor recovery", "notes": "Where the numbers come from"}
SCENARIOS = {
    "default": {},
    "dates 1-25 May": {"dates": (D(2026, 5, 1), D(2026, 5, 25))},
    "dates 1-30 Jun": {"dates": (D(2026, 6, 1), D(2026, 6, 30))},
    "dates 26-31 May": {"dates": (D(2026, 5, 26), D(2026, 5, 31))},
    "dates 20 May-10 Jun": {"dates": (D(2026, 5, 20), D(2026, 6, 10))},
    "Ontario only": {"f_region": ["Ontario"]},
    "empty: Quebec+Account Access+1-25 May": {"dates": (D(2026, 5, 1), D(2026, 5, 25)), "f_region": ["Quebec"],
                                              "f_issue_type": ["Account Access"]},
    "empty: Atlantic+LTE/5G+Fibre Gigabit+Account Access": {"f_region": ["Atlantic"], "f_platform": ["LTE/5G"],
                                                            "f_product": ["Fibre Gigabit"], "f_issue_type": ["Account Access"]},
    "Atlantic only": {"f_region": ["Atlantic"]},
    "Ontario + No Internet": {"f_region": ["Ontario"], "f_issue_type": ["No Internet"]},
    "firmware: No update": {"f_firmware_region": ["No update"]},
    "channel: Email": {"f_channel": ["Email"]},
}
failures = 0


def fail(msg):
    global failures
    failures += 1
    print("  FAIL:", msg)


def alert_states(at):
    """Status lines of the three alert cards on the Monitor page, e.g. ':red[**▲ ALERT**]'."""
    return [m.value for m in at.markdown if m.value.startswith((":red[", ":green[", ":gray["))]


def goto(at, page):
    at._page_hash = calc_md5(page)
    return at.run()


def texts(at):
    return " ".join([m.value for m in at.markdown] + [h.value for h in at.header] + [t.value for t in at.title]
                    + [c.value for c in at.caption] + [m.label for m in at.metric])


def start(spec=None):
    """Open the app, go to the KPIs page (it shows the filters), apply the filters."""
    at = AppTest.from_file(f"{ROOT}/app/app.py", default_timeout=120)
    at.run()
    goto(at, "kpis")
    for key, val in (spec or {}).items():
        (at.slider(key=key) if key == "dates" else at.multiselect(key=key)).set_value(val)
    return at.run()


for name, spec in SCENARIOS.items():
    at = start(spec)
    print(f"\n=== {name}")
    overview = next((d.value for d in at.dataframe if "KPI" in d.value.columns), None)
    if overview is None:
        print("  KPIs page:", " ".join(e.value for e in list(at.info) + list(at.warning))[:90])
    else:
        print("  KPIs:", " | ".join(f"{r['KPI']} {r['Pre → post']} ({r['Change']}: {r['Status']})"
                                    for _, r in overview.iterrows()))
        st_of = dict(zip(overview["KPI"], overview["Status"]))
        if name == "default" and (st_of["CSAT (1–5)"] != "Within noise" or st_of["Connection problems"] != "Getting worse"):
            fail(f"noise check, default: {st_of}")
        if name == "Ontario + No Internet" and "Too few calls to tell" not in st_of.values():
            fail(f"noise check, tiny segment: {st_of}")
        if name == "Atlantic only" and not any("(small sample)" in v for v in st_of.values()):   # 10–29 calls marked
            fail(f"small-sample marking, Atlantic: {st_of}")
        headline = next((m.value for m in at.markdown if m.value.startswith("**Of ")), "")
        if name == "Ontario + No Internet" and "too few calls to tell" not in headline:   # audit D1
            fail(f"headline should count 'too few calls': {headline}")
        if name == "dates 20 May-10 Jun" and overview["Status"].str.contains("not recovering").any():  # audit D4
            fail(f"{name}: 'not recovering' shown although no trend can be computed for this range")
        print("  headline:", headline)
        text = overview.drop(columns=["Week by week"]).astype(str)
        if len(overview) != 8 or text.apply(lambda c: c.str.contains("nan")).any().any():
            fail(f"{name}: KPI overview table wrong: {overview.to_dict('records')}")
    for w in at.warning:
        print("  warning:", w.value)
    showing = next(c.value for c in at.caption if c.value.startswith("Showing:"))
    for page, must in PAGES.items():        # filters must survive every page change, including pages without them
        goto(at, page)
        if at.exception:
            fail(f"{name}/{page}: {at.exception[0].value}")
        elif must not in texts(at):
            fail(f"{name}/{page}: '{must}' not rendered")
        if "nan" in " ".join(f"{m.value} {m.delta}" for m in at.metric).lower():
            fail(f"{name}/{page}: nan shown in a metric")
        if page == "monitor":
            print("  monitor:", " | ".join(alert_states(at)))
            if "0 of 0 full weeks" in texts(at):                                            # audit D7
                fail(f"{name}: '0 of 0 full weeks' caption")
            if at.multiselect or "Company-wide · status as of" not in texts(at):             # UI audit F1/E2
                fail(f"{name}: Monitor should be company-wide with no filter widgets")
            if alert_states(at)[:2] != [":red[**▲ ALERT**]", ":red[**▲ ALERT**]"]:          # company-wide status
                fail(f"{name}: Monitor alerts should not depend on filters: {alert_states(at)}")
        if page == "voice" and name.startswith("dates 1-25 May") and not at.info:          # audit D3
            fail(f"{name}: Customer voice should explain that post-spike dates are needed")
    goto(at, "drivers")
    after = next((c.value for c in at.caption if c.value.startswith("Showing:")), "")
    print("  ", showing, "| after visiting every page:", "kept" if after == showing else f"CHANGED to {after}")
    if after != showing:
        fail(f"{name}: filters lost after page changes")

# summary numbers: pre → post cards, each card's button opens its before/after pop-up
at = AppTest.from_file(f"{ROOT}/app/app.py", default_timeout=120)
at.run()
print("\n=== summary:", at.title[0].value)
print("  ", " | ".join(f"{m.label}={m.value} ({m.delta})" for m in at.metric))
expected = {"Calls per day": "80 → 148", "Connection problems": "28% → 53%", "Repeat calls": "13% → 29%",
            "Agent hours per day": "21 → 44"}
if {m.label: m.value for m in at.metric} != expected:
    fail(f"summary cards: {[(m.label, m.value) for m in at.metric]}")
if at.get("plotly_chart"):
    fail("summary: the page should show no chart until a card is opened")
for k in ("calls", "connection", "repeat", "agent_hours"):
    at.button(key=f"sum_btn_{k}").click().run()
    shown = " ".join(m.value for m in at.markdown) + " " + " ".join(c.value for c in at.caption)
    if at.exception:
        fail(f"summary pop-up {k}: {at.exception[0].value}")
    elif "Pre-spike = 1–25 May · post-spike = June" not in shown or not at.get("plotly_chart"):
        fail(f"summary pop-up {k}: pop-up did not render")
    else:
        print(f"   {k}: " + next(m.value for m in at.markdown if "the pre-spike level" in m.value))

# every control on the default view and on a filtered view
for name, spec in (("default", {}), ("Ontario + No Internet", SCENARIOS["Ontario + No Internet"])):
    at = start(spec)
    for k in KPI_KEYS:                           # every KPI's pop-up (row clicks can't be simulated: open it directly)
        at.session_state["kpi_open"] = k
        at.run()
        if at.exception:
            fail(f"kpi pop-up {name}/{k}: {at.exception[0].value}")
        elif not any(m.label == "Pre-spike" for m in at.metric):
            fail(f"kpi pop-up {name}/{k}: pop-up did not render")
    goto(at, "kpis")                             # UI audit I1: the visible "Open details for" path opens pop-ups
    for k in ("connection", "csat"):
        pick = next(s_ for s_ in at.selectbox if s_.key and s_.key.startswith("kpi_pick_"))
        pick.set_value(k).run()
        if at.exception or not any(m.label == "Pre-spike" for m in at.metric):
            fail(f"kpi 'Open details for' {name}/{k}: pop-up did not open")
    goto(at, "voice")
    pick = next(s_ for s_ in at.selectbox if s_.key and s_.key.startswith("voice_pick_"))
    pick.set_value(pick.options[0]).run()
    if at.exception or "What these callers say" not in " ".join(m.value for m in at.markdown):
        fail(f"voice 'Open details for' {name}: pop-up did not open")
    goto(at, "voice")                            # the pop-up of every reason listed under these filters
    listed = next(d.value for d in at.dataframe if "Reason" in d.value.columns)["Reason"].tolist()
    for reason in listed:
        at.session_state["voice_open"] = reason
        at.run()
        texts_now = " ".join(m.value for m in at.markdown)
        if at.exception:
            fail(f"voice pop-up {name}/{reason}: {at.exception[0].value}")
        elif "What these callers say" not in texts_now and not at.info:
            fail(f"voice pop-up {name}/{reason}: pop-up did not render")
    goto(at, "drivers")
    n_drill = 0
    for dim in at.selectbox(key="dim").options:
        at.selectbox(key="dim").set_value(dim).run()
        drill = next(s for s in at.selectbox if s.key and s.key.startswith("drill_"))
        for opt in drill.options:
            at.selectbox(key=drill.key).set_value(opt).run()
            n_drill += 1
            if at.exception:
                fail(f"drill {name}/{dim}/{opt}: {at.exception[0].value}")
    for view in at.radio(key="heat_view").options:
        at.radio(key="heat_view").set_value(view).run()
        if at.exception:
            fail(f"heatmap {name}/{view}: {at.exception[0].value}")
    print(f"\n=== {name}: all 8 KPI pop-ups, all reason pop-ups, {n_drill} drill-downs, both heatmap views checked")

# alert sliders (sidebar on Monitor) change the status; reset clears every filter
at = start()
goto(at, "monitor")
at.slider(key="vol_line").set_value(160).run()
at.slider(key="rep_line").set_value(40).run()
if alert_states(at)[:2] != [":green[**● OK**]", ":green[**● OK**]"]:
    fail(f"alert sliders: expected OK at 160/day and 40%, got {alert_states(at)}")
at = start(SCENARIOS["empty: Quebec+Account Access+1-25 May"])
next(b for b in at.button if b.label == "Reset filters").click().run()
showing = next(c.value for c in at.caption if c.value.startswith("Showing:"))
if not showing.startswith("Showing: All calls") or any(at.multiselect(key=k).value for k in ("f_region", "f_issue_type")):
    fail(f"reset: {showing}")
print("\n=== alert sliders + reset: checked")

print("\nFAILURES:", failures)
