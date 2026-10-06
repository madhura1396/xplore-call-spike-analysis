"""Technical Call Spike Monitor — Databricks App (Streamlit, multipage).

For Customer Care leaders. Start on the one-screen Summary, then dig into one page per question:
KPIs · What drove it · Root cause · Customer voice · Monitor · Data notes (menu across the top).
Interactive: filters (shared across pages), click a table row for a pop-up, click-to-drill bars, adjustable alert lines.
Data: workspace.xplore_gold (synthetic assessment data).
"""
from functools import partial

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

st.set_page_config(page_title="Technical Call Spike Monitor", layout="wide")
# narrower sidebar (Streamlit's default is 336 px) so the top menu and cards fit on 1024–1280 px laptop screens
st.markdown("<style>section[data-testid='stSidebar']{width:270px !important;min-width:270px !important}</style>",
            unsafe_allow_html=True)

from data import SPLIT, load  # noqa: E402  (set_page_config must run first)

INK, INK2, BLUE, ORANGE, GREY, GRID = "#14213D", "#52514e", "#2E6DB4", "#D35F24", "#A9B1BB", "#e4e3df"
BEFORE_LBL, AFTER_LBL = "Pre-spike", "Post-spike"     # call details: 1–25 May vs June (A19)
VOLUME_ALERT, REPEAT_ALERT = 96, 18     # Slide 3 alert lines: 20% above the normal 80 calls/day; repeat rate above 18%
MIN_TEST = 10                           # fewer sampled calls (surveys for CSAT) than this on a side → too few to test
MIN_SAMPLE = 30                         # 10–29 on a side → "small sample": direction clear, size approximate
UNSTABLE_REBOOTS = 6                    # reboots a week that count as unstable: 3× the 3.7.4 normal of 2
NO_CALLS = "No sampled calls match these filters. Widen the dates or remove a filter."
NEED_BOTH = "Include both pre-spike (1–25 May) and post-spike (June) dates to compare."
DIMENSIONS = {"Reason": "issue_type", "Region": "region", "Firmware update": "firmware_region", "Platform": "platform",
              "Product": "product", "Segment": "customer_segment", "Channel": "channel", "Outcome": "resolution_status"}
# key: (label, unit, decimals, change shown as, higher is worse, what it measures)
KPIS = {
    "calls": ("Calls per day", "", 0, "rel", True, "Estimated technical calls a day."),
    "connection": ("Connection problems", "%", 0, "pts", True, "Share of calls: No Internet or Slow Speed."),
    "repeat": ("Repeat calls", "%", 0, "pts", True, "Share of calls from repeat callers."),
    "follow_up": ("Follow-up needed", "%", 0, "pts", True, "Share of calls not fixed first time."),
    "duration": ("Avg call duration", " min", 1, "abs", True, "Average minutes per call."),
    "agent_hours": ("Agent hours per day", "", 0, "rel", True, "Calls a day × minutes per call."),
    "tech_visits": ("Technician visits per day", "", 0, "rel", True, "Calls ending in a technician visit (proxy)."),
    "csat": ("CSAT (1–5)", "", 1, "abs", False, "Average post-call survey score."),
}
KPI_ROWS = (("What's happening", ("calls", "connection", "repeat", "follow_up")),
            ("Cost and experience", ("duration", "agent_hours", "tech_visits", "csat")))
FILTERS = (("Region", "region"), ("Firmware update in region", "firmware_region"), ("Reason for calling", "issue_type"))
MORE_FILTERS = (("Platform", "platform"), ("Product", "product"), ("Customer segment", "customer_segment"),
                ("Channel", "channel"))
FILTER_KEYS = ["dates"] + [f"f_{c}" for _, c in FILTERS + MORE_FILTERS]
PERSIST = FILTER_KEYS + ["dim", "heat_view", "vol_line", "rep_line"]
CHART_CONFIG = {"displayModeBar": False}      # no toolbar: charts are read, not edited
LAYOUT = dict(template="plotly_white", font=dict(family="sans-serif", size=13, color=INK2),
              margin=dict(l=10, r=10, t=36, b=10), hoverlabel=dict(bgcolor="white"),
              legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0))   # left: clear of the toolbar

try:
    with st.spinner("Loading 750 sampled calls and 91 days of totals from Databricks…"):
        data = load()
except Exception as exc:  # noqa: BLE001 — show a readable error state instead of a stack trace
    st.error(f"Could not load data from Databricks. Check the SQL warehouse resource and table permissions.\n\n{exc}")
    st.stop()
calls, daily, regions, devices = data["calls"], data["daily"], data["regions"], data["devices"]


@st.cache_data(ttl=None, show_spinner=False)
def loaded_at():
    """Time the data was loaded (cached with the data; shown in the sidebar)."""
    return pd.Timestamp.now(tz="UTC")


def refresh_data():
    """'Refresh data' button: clear the cached tables and load time so the next run re-queries Databricks."""
    for fn in (load, loaded_at):
        getattr(fn, "clear", lambda: None)()
fw_tag = {r.region: (f"firmware {pd.Timestamp(r.region_event_date):%d %b}" if r.region_has_event else "no update")
          for r in regions.itertuples()}
updated = ", ".join(f"{r.region} ({pd.Timestamp(r.region_event_date):%d %b})"
                    for r in regions[regions["region_has_event"]].sort_values("region_event_date").itertuples())
not_updated = ", ".join(sorted(regions.loc[~regions["region_has_event"], "region"]))
dmin, dmax = calls["call_date"].min().date(), calls["call_date"].max().date()

# ======================================================================== state shared by all pages
for k in list(st.session_state):        # keep widget values when the current page doesn't show that widget
    if k in PERSIST or k.startswith("drill_"):
        st.session_state[k] = st.session_state[k]
st.session_state.setdefault("dates", (dmin, dmax))
for _, c in FILTERS + MORE_FILTERS:
    st.session_state.setdefault(f"f_{c}", [])
st.session_state.setdefault("vol_line", VOLUME_ALERT)
st.session_state.setdefault("dim", "Reason")
st.session_state.setdefault("rep_line", REPEAT_ALERT)

start, end = map(pd.Timestamp, st.session_state["dates"])
selections = {c: st.session_state[f"f_{c}"] for _, c in FILTERS + MORE_FILTERS}
mask = calls["call_date"].between(start, end)
for col, sel in selections.items():
    if sel:
        mask &= calls[col].isin(sel)
cf = calls[mask]
segment_filtered = any(selections.values())
dates_filtered = (start.date(), end.date()) != (dmin, dmax)
scope = " · ".join(([f"{start.day} {start:%b}–{end.day} {end:%b}"] if dates_filtered else [])
                   + [", ".join(v) for v in selections.values() if v]) or "All calls"
days = daily[daily["call_date"].between(start, end) & (daily["call_date"] >= calls["call_date"].min())]
N_DAYS = days.groupby("mix_period").size().to_dict()
both_periods = bool(N_DAYS.get("before") and N_DAYS.get("after"))
full_days = daily[daily["call_date"] >= calls["call_date"].min()].groupby("mix_period").size()


# ======================================================================== helpers
def kpis(f, n_days):
    """Every KPI for a set of sampled calls covering n_days days (weights scale the sample to true totals)."""
    w, tot = f["weight"], f["weight"].sum()
    share = lambda flag: (w * f[flag]).sum() / tot * 100 if tot else np.nan  # noqa: E731
    per_day = lambda x: x / n_days if n_days else np.nan  # noqa: E731
    fb = f[f["has_feedback"]]
    return {"calls": per_day(tot), "connection": share("is_connectivity"), "repeat": share("is_repeat_contact"),
            "follow_up": share("is_follow_up"),
            "duration": np.average(f["call_duration_minutes"], weights=w) if tot else np.nan,
            "agent_hours": per_day((w * f["call_duration_minutes"]).sum() / 60),
            "tech_visits": per_day((w * f["is_technician"]).sum()),
            "csat": np.average(fb["csat_score"], weights=fb["weight"]) if len(fb) else np.nan,
            "repeat_calls": per_day((w * f["is_repeat_contact"]).sum()), "resolved": share("is_resolved_on_call"),
            "tech_share": share("is_technician"), "negative": share("is_negative_sentiment"),
            "june_note": share("has_june_note"),
            "detractors": (fb["weight"] * fb["is_detractor"]).sum() / fb["weight"].sum() * 100 if len(fb) else np.nan}


def fmt(v, suffix="", dec=0):
    """Format a number for display ('—' when missing)."""
    return "—" if pd.isna(v) else f"{v:,.{dec}f}{suffix}"


def change(key, before, after):
    """Pre- to post-spike change as displayed: relative % for counts ('+85%'), percentage points for shares ('+25 pts'), plain difference for duration and CSAT."""
    _, unit, dec, kind, _, _ = KPIS[key]
    if pd.isna(before) or pd.isna(after) or (kind == "rel" and not before):
        return None
    # absolute changes use the displayed (rounded) values, so the delta matches what the reader sees
    diff = round((after / before - 1) * 100, 0) if kind == "rel" else round(round(after, dec) - round(before, dec), dec)
    if diff == 0:
        return "no change"
    return f"{diff:+.0f}%" if kind == "rel" else f"{diff:+.{dec}f}" + (" pts" if kind == "pts" else unit)


def kpi_se(f, n_days, key):
    """Standard error of a KPI estimated from the sampled calls (normal approximation)."""
    n = len(f)
    if key in ("connection", "repeat", "follow_up"):
        p = kpis(f, n_days)[key] / 100 if n else np.nan
        return 100 * np.sqrt(p * (1 - p) / n) if n else np.nan
    if key == "csat":
        scores = f.loc[f["has_feedback"], "csat_score"]
        return scores.std(ddof=1) / np.sqrt(len(scores)) if len(scores) > 1 else np.nan
    if key == "duration":
        return f["call_duration_minutes"].std(ddof=1) / np.sqrt(n) if n > 1 else np.nan
    x = {"calls": f["weight"], "agent_hours": f["weight"] * f["call_duration_minutes"] / 60,
         "tech_visits": f["weight"] * f["is_technician"]}[key]
    return np.sqrt((x ** 2).sum()) / n_days if n_days else np.nan


def sample_size(f, key):
    """Sampled observations behind a KPI: survey answers for CSAT, sampled calls otherwise."""
    return int(f["has_feedback"].sum()) if key == "csat" else len(f)        # CSAT rests on survey answers only


def pre_post(key, frame, days=None):
    """Pre- vs post-spike for one KPI: values, smallest sample, and whether the change beats noise (2 standard errors)."""
    nb, na = days or (N_DAYS.get("before", 0), N_DAYS.get("after", 0))
    fb, fa = frame[frame["period"] == "before"], frame[frame["period"] == "after"]
    pre, post = kpis(fb, nb)[key], kpis(fa, na)[key]
    noise = 2 * np.sqrt(kpi_se(fb, nb, key) ** 2 + kpi_se(fa, na, key) ** 2)
    n_min = min(sample_size(fb, key), sample_size(fa, key))
    return {"pre": pre, "post": post, "noise": noise, "n_min": n_min, "small": MIN_TEST <= n_min < MIN_SAMPLE,
            "real": bool(n_min >= MIN_TEST and not pd.isna(noise) and abs(post - pre) > noise)}


def delta_view(key, c):
    """Delta for st.metric, its colour, and a grey note that replaces the arrow when the change isn't real."""
    d = change(key, c["pre"], c["post"])
    if d is None:
        return None, "off", None
    if c["n_min"] < MIN_TEST:
        return None, "off", (f"{d} vs pre-spike, but too few {'surveys' if key == 'csat' else 'calls'} to test it: "
                             "read as direction")
    if not c["real"]:
        return None, "off", f"Within noise: {d} vs pre-spike is smaller than the sampling error"
    return d, ("inverse" if KPIS[key][4] else "normal"), ("Small sample: direction clear, size approximate"
                                                          if c["small"] else None)


SUMMARY_WHAT = {"calls": "Technical calls a day", "connection": "Share of calls about No Internet or Slow Speed",
                "repeat": "Share of calls from customers calling back", "agent_hours": "Calls a day × minutes per call"}


def open_summary(key):
    """'See before vs after' button: remember which Summary card's pop-up to open on this run."""
    st.session_state["sum_open"] = key


def summary_card(key, c):
    """Summary card: pre-spike → post-spike, the change, what it measures, and a button for the before/after pop-up."""
    label, unit, dec, _, _, _ = KPIS[key]
    d, colour, note = delta_view(key, c)
    with st.container(border=True):
        st.metric(label, f"{fmt(c['pre'], unit, dec)} → {fmt(c['post'], unit, dec)}", d, delta_color=colour)
        # fixed two-line height so the four buttons line up whichever descriptions wrap
        st.markdown(f"<div style='min-height:3.2em;font-size:0.875rem;color:rgba(49,51,63,0.6)'>"
                    f"{note or SUMMARY_WHAT[key]}</div>", unsafe_allow_html=True)
        st.button("See before vs after", key=f"sum_btn_{key}", on_click=open_summary, args=(key,),
                  use_container_width=True)


def compare(frame, col):
    """Weighted pre- vs post-spike calls per day for each group of `col`, with change, % change, share of the increase and sample sizes ('few' = under 30 sampled calls on a side)."""
    g = frame.groupby([col, "period"])["weight"].sum().unstack(fill_value=0).reindex(columns=["before", "after"], fill_value=0)
    t = pd.DataFrame({"Before": g["before"] / N_DAYS.get("before", np.nan), "After": g["after"] / N_DAYS.get("after", np.nan)})
    t["Change"] = t["After"] - t["Before"]
    t["% change"] = (t["After"] / t["Before"].replace(0, np.nan) - 1) * 100
    total = t["Change"].sum()
    t["Share of increase %"] = t["Change"] / total * 100 if total else np.nan
    n = frame.groupby([col, "period"]).size().unstack(fill_value=0).reindex(columns=["before", "after"], fill_value=0)
    n = n.reindex(t.index, fill_value=0)
    t["Sampled calls"] = n["before"].astype(str) + " → " + n["after"].astype(str)
    t["few"] = n.min(axis=1) < MIN_SAMPLE                  # under 30 sampled calls on a side: size approximate
    t["n_pre"] = n["before"]
    return t.sort_values("After", ascending=False)


def week_start(dates):
    """Monday of each date's week (weeks run Monday to Sunday)."""
    return dates - pd.to_timedelta(dates.dt.weekday, unit="D")


SPIKE_START = week_start(pd.Series([SPLIT])).iloc[0]        # Monday of the spike week


def week_label(w):
    """Weeks relative to the spike: '2 wks before' … 'Spike week' … 'Week 4'."""
    n = (w - SPIKE_START).days // 7
    return "Spike week" if n == 0 else f"Week {n}" if n > 0 else f"{-n} wk{'s' if n < -1 else ''} before"


week_days = days.groupby(week_start(days["call_date"])).size()
FULL_WEEKS = week_days[week_days == 7].index
WEEK_LABELS = [week_label(w) for w in FULL_WEEKS]
SPIKE_WEEK = "Spike week"
POST_WEEKS = [w for w in FULL_WEEKS if (w - SPIKE_START).days >= 7]
all_days = daily[daily["call_date"] >= calls["call_date"].min()]
all_week_days = all_days.groupby(week_start(all_days["call_date"])).size()
ALL_WEEKS = all_week_days[all_week_days == 7].index                    # every full week, ignoring the date filter


def weekly_table(frame, weeks=None):
    """Every KPI for each complete week (Mon–Sun) inside the dates (or the given weeks), labelled relative to the spike."""
    weeks = FULL_WEEKS if weeks is None else weeks
    groups = dict(tuple(frame.groupby(week_start(frame["call_date"]))))
    return pd.DataFrame([kpis(groups.get(w, frame.iloc[:0]), 7) for w in weeks], index=[week_label(w) for w in weeks],
                        dtype=float)


def weekly(frame, key, weeks=None):
    """One KPI per complete week (empty when the dates hold no full week)."""
    weeks = FULL_WEEKS if weeks is None else weeks
    return weekly_table(frame, weeks)[key] if len(weeks) else pd.Series(dtype=float)


def base_fig(height=360, title=None):
    """Empty Plotly figure with the shared layout; axes are fixed so a stray drag can't pan or zoom."""
    fig = go.Figure()
    fig.update_layout(**LAYOUT, height=height)
    if title:
        fig.update_layout(title=dict(text=title, font=dict(size=14, color=INK)))
    fig.update_xaxes(showgrid=False, fixedrange=True)        # fixed: a stray drag can't pan or zoom
    fig.update_yaxes(gridcolor=GRID, zeroline=False, fixedrange=True)
    return fig


def mark_spike_week(fig, label=True, labels=None):
    """Shade the spike week (the week of 26 May) on a weekly chart, optionally labelled."""
    labels = WEEK_LABELS if labels is None else labels
    if SPIKE_WEEK in labels:
        i = labels.index(SPIKE_WEEK)
        fig.add_vrect(x0=i - 0.5, x1=i + 0.5, fillcolor=ORANGE, opacity=0.12, line_width=0)
        if label:
            fig.add_annotation(x=i, y=1, yref="paper", text="spike week", showarrow=False, yanchor="bottom",
                               font=dict(size=11, color=ORANGE))


def daily_chart(height, alert):
    """Company-wide daily totals against an alert line."""
    fig = base_fig(height)
    fig.add_trace(go.Scatter(x=daily["call_date"], y=daily["total_calls"], mode="lines", line=dict(color=BLUE, width=2),
                             hovertemplate="%{x|%d %b}: %{y} calls<extra></extra>"))
    fig.add_hline(y=alert, line=dict(color=ORANGE, width=1.5, dash="dash"))
    fig.update_layout(showlegend=False)
    fig.update_yaxes(range=[0, 200], title="Calls per day")
    return fig


def before_after_bars(t, height, selected=None, labels=None):
    """Horizontal before/after bars (names read left to right), biggest group on top."""
    y = labels or list(t.index)
    focus = dict(selectedpoints=[list(t.index).index(selected)], unselected=dict(marker=dict(opacity=0.35))) \
        if selected in t.index else {}       # fade the bars that are not drilled into
    fig = base_fig(height)
    fig.add_trace(go.Bar(y=y, x=t["Before"], orientation="h", name=BEFORE_LBL, marker=dict(color=GREY, cornerradius=4),
                         **focus, hovertemplate="%{x:.1f} calls/day<extra>Pre-spike</extra>"))
    fig.add_trace(go.Bar(y=y, x=t["After"], orientation="h", name=AFTER_LBL, marker=dict(color=BLUE, cornerradius=4),
                         **focus, text=t["After"].round(0), textposition="outside", cliponaxis=False,
                         hovertemplate="%{x:.1f} calls/day<extra>Post-spike</extra>"))
    fig.update_layout(barmode="group", bargap=0.25, bargroupgap=0.06)
    fig.update_yaxes(autorange="reversed", showgrid=False)
    top = t[["Before", "After"]].max().max()
    fig.update_xaxes(title="Calls per day", showgrid=True, gridcolor=GRID,
                     range=[0, top * 1.18 if top and not pd.isna(top) else 1])   # headroom: labels never clip
    return fig


def sparse_week_ticks(fig):
    """Label only the first, spike and last week on small weekly charts."""
    ticks = [w for w in dict.fromkeys([WEEK_LABELS[0], SPIKE_WEEK, WEEK_LABELS[-1]]) if w in WEEK_LABELS] \
        if WEEK_LABELS else []
    fig.update_xaxes(tickmode="array", tickvals=ticks, tickangle=0)


def on_bar_click(chart_key, target_key, names):
    """Bar-click callback: drill into the clicked group by setting the 'Drill into' selectbox."""
    points = st.session_state[chart_key]["selection"]["points"]
    if points:
        i = points[0].get("point_index", points[0].get("point_number"))
        st.session_state[target_key] = names[i]


def header(title, line=None):
    """Page title plus an optional one-line takeaway."""
    st.header(title, anchor=False)
    if line:
        st.markdown(line)


def showing():
    """Caption naming the active filters ('Showing: …')."""
    st.caption(f"Showing: {scope} · change the filters in the sidebar")


def status(now, line):
    """Alert status for a current value against its alert line."""
    return "n/a (no data in range)" if pd.isna(now) else ("▲ ALERT" if now > line else "● OK")


def wsum(frame, period):
    """Weighted number of calls (sum of sample weights) in one period."""
    return frame.loc[frame["period"] == period, "weight"].sum()


n_before, n_after = int((cf["period"] == "before").sum()), int((cf["period"] == "after").sum())
B = kpis(cf[cf["period"] == "before"], N_DAYS.get("before", 0))                 # your selection
A = kpis(cf[cf["period"] == "after"], N_DAYS.get("after", 0))
CB = kpis(calls[calls["period"] == "before"], full_days["before"])               # company-wide
CA = kpis(calls[calls["period"] == "after"], full_days["after"])
SEL = {k: pre_post(k, cf) for k in KPIS}                                         # your selection, with noise check
CW = {k: pre_post(k, calls, (full_days["before"], full_days["after"])) for k in KPIS}   # company-wide
normal = daily.loc[daily["period"] == "before", "total_calls"].mean()
spike = daily.loc[daily["period"] == "after", "total_calls"].mean()
conn_share = (CA["calls"] * CA["connection"] - CB["calls"] * CB["connection"]) / 100 / (CA["calls"] - CB["calls"]) * 100
after_days = daily[daily["call_date"] >= SPLIT]


# ======================================================================== pages
def summary_meaning(key):
    """One plain sentence on what the change means for the business, from the company-wide numbers."""
    if key == "calls":
        excess = (after_days["total_calls"] - normal).sum()
        above = int((after_days["total_calls"] > VOLUME_ALERT).sum())
        last = after_days["call_date"].max()
        return (f"About **{CA['calls'] - CB['calls']:.0f} more technical calls every day**, {excess:,.0f} extra calls "
                f"from 26 May to {last.day} {last:%B}. It has not come back down: calls were above the "
                f"{VOLUME_ALERT}-a-day alert line on **{above} of {len(after_days)} days** since the spike.")
    if key == "connection":
        before_, after_ = (CB["calls"] * CB["connection"] / 100, CA["calls"] * CA["connection"] / 100)
        return (f"No Internet and Slow Speed calls went from about **{before_:.0f} to {after_:.0f} a day** and make up "
                f"**{conn_share:.0f}% of the increase**: customers' connections are dropping or slowing down.")
    if key == "repeat":
        at_old_rate = CA["calls"] * CB["repeat"] / 100
        return (f"Repeat calls went from about **{CB['repeat_calls']:.0f} to {CA['repeat_calls']:.0f} a day**. At the "
                f"pre-spike rate there would be about {at_old_rate:.0f}, so **about "
                f"{CA['repeat_calls'] - at_old_rate:.0f} extra calls a day** come from customers calling back: the problem "
                "isn't being fixed on the first call.")
    extra = CA["agent_hours"] - CB["agent_hours"]
    return (f"{CB['calls']:.0f} calls × {CB['duration']:.1f} min pre-spike vs {CA['calls']:.0f} calls × "
            f"{CA['duration']:.1f} min post-spike: **about {extra:.0f} extra agent hours a day**, roughly "
            f"{extra / 8:.0f} extra full-time agents (8-hour shifts).")


def summary_detail(key):
    """Pop-up body: pre-spike vs post-spike bars for one Summary KPI, and what the change means."""
    label, unit, dec, _, _, _ = KPIS[key]
    pre, post = CW[key]["pre"], CW[key]["post"]
    st.markdown(f"**{fmt(pre, unit, dec)} → {fmt(post, unit, dec)}** · {change(key, pre, post)} · "
                f"{post / pre:.1f}× the pre-spike level")
    fig = base_fig(200)
    fig.add_trace(go.Bar(y=[BEFORE_LBL, AFTER_LBL], x=[pre, post], orientation="h",
                         marker=dict(color=[GREY, BLUE], cornerradius=4), text=[fmt(pre, unit, dec), fmt(post, unit, dec)],
                         textposition="outside", cliponaxis=False, textfont=dict(size=15, color=INK), hoverinfo="skip"))
    fig.update_yaxes(autorange="reversed", showgrid=False)
    fig.update_xaxes(title=SUMMARY_WHAT[key], range=[0, post * 1.2], showgrid=True, gridcolor=GRID,
                     ticksuffix="%" if unit == "%" else "")
    fig.update_layout(showlegend=False, bargap=0.35)
    st.plotly_chart(fig, use_container_width=True, config=CHART_CONFIG)
    st.markdown(summary_meaning(key))
    st.caption("Pre-spike = 1–25 May · post-spike = June · daily averages, company-wide · week-by-week trends are on "
               "the KPIs page")


def page_summary():
    """Summary page (company-wide): headline, four pre → post KPI cards with before-vs-after pop-ups, and the what drove it / why / what customers say / what to do cards."""
    st.title(f"Technical calls jumped {(spike / normal - 1) * 100:.0f}% overnight on 26 May, and stayed high",
             anchor=False)
    st.caption("Company-wide · daily averages, pre-spike (1–25 May) → post-spike (June) · synthetic assessment data · "
               "not affected by filters")
    # this page only: "28% → 53%" wraps on narrow screens instead of being cut to "28% → 5…"
    st.markdown("<style>[data-testid='stMetricValue']{font-size:2rem}[data-testid='stMetricValue'] > div"
                "{white-space:normal;overflow:visible;text-overflow:clip}</style>", unsafe_allow_html=True)
    for column, key in zip(st.columns(4), ("calls", "connection", "repeat", "agent_hours")):
        with column:
            summary_card(key, CW[key])
    st.caption("pts = percentage points")
    cards = (("What drove it", f"“No Internet” and “Slow Speed” make up **{conn_share:.0f}%** of the increase, "
                               "in every region", "drivers", "See what drove it"),
             ("Why", "**Two suspects:** firmware 3.8.1, or a nationwide change. Neither is proven yet.",
              "cause", "See the root cause"),
             ("What customers say", "Internet keeps dropping, slow speed. CSAT is low (~3.3) and unchanged.",
              "voice", "See customer voice"),
             ("What to do", f"Confirm the cause, contain the volume, alert at **{VOLUME_ALERT}** calls a day "
                            f"or **{REPEAT_ALERT}%** repeats.", "monitor", "See the monitor"))
    for column, (label, text, page, link) in zip(st.columns(4), cards):
        with column.container(border=True):
            st.caption(label.upper())
            st.markdown(text)
            st.page_link(PAGES[page], label=link, icon=":material/arrow_forward:")
    st.page_link(PAGES["kpis"], label="All 8 KPIs, week by week, with filters", icon=":material/arrow_forward:")
    opened = st.session_state.pop("sum_open", None)
    if opened in SUMMARY_WHAT:
        st.dialog(KPIS[opened][0], width="large")(summary_detail)(opened)


def trend_since_spike(frame, key):
    """First two vs last two post-spike weeks: 'rising'/'easing' only if beyond noise and at least 10% (CSAT 0.2)."""
    if len(POST_WEEKS) < 4:
        return "—"
    window = lambda a, b: frame[frame["call_date"].between(a, b + pd.Timedelta(days=6))]  # noqa: E731
    early, late = window(POST_WEEKS[0], POST_WEEKS[1]), window(POST_WEEKS[-2], POST_WEEKS[-1])
    if min(sample_size(early, key), sample_size(late, key)) < MIN_TEST:
        return "—"
    e, l_ = kpis(early, 14)[key], kpis(late, 14)[key]
    if pd.isna(e) or pd.isna(l_) or not e:
        return "—"
    noise = 2 * np.sqrt(kpi_se(early, 14, key) ** 2 + kpi_se(late, 14, key) ** 2)
    meaningful = abs(l_ - e) >= 0.2 if key == "csat" else abs(l_ / e - 1) >= 0.1
    return "flat" if abs(l_ - e) <= noise or not meaningful else "rising" if l_ > e else "easing"


def kpi_status(key, c, trend):
    """Plain-language status and its box (error / warning / success / info); noise-aware, small samples marked."""
    state, box = _kpi_status(key, c, trend)
    return (f"{state} (small sample)", box) if c["small"] and box != "info" else (state, box)


def _kpi_status(key, c, trend):
    """Status rules, in order: enough data? → real change (noise check)? → size (post ÷ pre: ≥ 1.2 high, > 1.1 slightly above), with the trend splitting 'high' into getting worse / easing / not recovering. Returns (text, colour box)."""
    pre, post = c["pre"], c["post"]
    if pd.isna(pre) or pd.isna(post) or not pre:
        return "Not enough data", "info"
    if c["n_min"] < MIN_TEST:
        return f"Too few {'surveys' if key == 'csat' else 'calls'} to tell", "info"
    if not c["real"]:
        return "Within noise", "info"
    if key == "csat":
        return ("Worse than pre-spike", "error") if post < pre else ("Better than pre-spike", "success")
    ratio = post / pre
    if ratio >= 1.2:
        return {"rising": ("Getting worse", "error"), "easing": ("Easing, still high", "warning"),
                "flat": ("Still high, not recovering", "error")}.get(trend, ("Still high", "error"))
    if ratio > 1.1:
        return "Slightly above pre-spike", "warning"
    return ("Close to pre-spike level", "success") if ratio >= 0.9 else ("Below pre-spike", "success")


def on_row_open(table_key, items, target):
    """Row click → open that row's pop-up on this run; a fresh table key clears the selection so any row reopens."""
    rows = st.session_state[table_key]["selection"]["rows"]
    if rows:
        st.session_state[f"{target}_open"] = items[rows[0]]
        st.session_state[f"{target}_n"] = st.session_state.get(f"{target}_n", 0) + 1


def kpi_detail(key, weeks, trend):
    """Pop-up body: status line, pre/post-spike numbers and the week-by-week chart for one KPI."""
    label, unit, dec, _, _, _ = KPIS[key]
    c = SEL[key]
    pre, post = c["pre"], c["post"]
    state, box = kpi_status(key, c, trend)
    d, colour, note = delta_view(key, c)
    raw = change(key, pre, post)
    getattr(st, box)(f"**{state}.** {fmt(post, unit, dec)} post-spike vs {fmt(pre, unit, dec)} pre-spike "
                     f"({raw or 'no comparison'}{', within noise' if raw and c['n_min'] >= MIN_TEST and not c['real'] else ''}). "
                     f"Trend since the spike: {trend}.")
    t1, t2, t3 = st.columns(3)
    t1.metric("Pre-spike", fmt(pre, unit, dec))
    t2.metric("Post-spike", fmt(post, unit, dec), d, delta_color=colour)
    if note:
        t2.caption(note)
    t3.metric("Trend since the spike", {"rising": "↗ Rising", "easing": "↘ Easing", "flat": "→ Flat"}.get(trend, "—"))
    if not len(weeks):
        st.info("Widen the dates to at least one full week (Monday to Sunday) to see the weekly chart.")
        return
    v = weeks[key]
    is_pre = [w.endswith("before") for w in v.index]
    post_v = v[[w.startswith("Week") for w in v.index]]
    fig = base_fig(360)
    fig.add_trace(go.Scatter(x=list(v.index), y=[pre] * len(v), mode="lines", name="Pre-spike normal",
                             line=dict(color=GREY, width=1.5, dash="dash"), hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=v.index[is_pre], y=v[is_pre], mode="markers", name="Pre-spike weeks (few calls)",
                             marker=dict(size=10, color="#D5D9DF", line=dict(color=GREY, width=1)),
                             hovertemplate=f"%{{x}}: %{{y:,.{dec}f}}{unit}<extra></extra>"))
    fig.add_trace(go.Scatter(x=[SPIKE_WEEK], y=[v.get(SPIKE_WEEK)], mode="markers", name="Spike week",
                             marker=dict(size=10, color=ORANGE), hovertemplate=f"%{{x}}: %{{y:,.{dec}f}}{unit}<extra></extra>"))
    fig.add_trace(go.Scatter(x=post_v.index, y=post_v, mode="lines+markers+text", name="Post-spike weeks",
                             line=dict(color=BLUE, width=2.5), marker=dict(size=10),
                             text=[""] * (len(post_v) - 1) + [fmt(post_v.iloc[-1], unit, dec)] if len(post_v) else [],
                             textposition="top center", textfont=dict(color=INK),
                             hovertemplate=f"%{{x}}: %{{y:,.{dec}f}}{unit}<extra></extra>"))
    mark_spike_week(fig, label=False)
    fig.update_yaxes(title=label + (f" ({unit.strip()})" if unit.strip() else ""), rangemode="tozero",
                     ticksuffix="%" if unit == "%" else "")
    st.plotly_chart(fig, use_container_width=True, config=CHART_CONFIG)
    st.caption("Pre-spike weeks rest on few sampled calls, so they jump around: read them against the dashed "
               "pre-spike normal · close this window to pick another KPI")


def open_from_pick(pick_key, target):
    """'Open details for…' selectbox → open that row's pop-up; a new key resets the selectbox to its placeholder."""
    value = st.session_state.get(pick_key)
    if value is not None:
        st.session_state[f"{target}_open"] = value
        st.session_state[f"{target}_n"] = st.session_state.get(f"{target}_n", 0) + 1


def open_details_box(items, target, placeholder, fmt_item=str):
    """'Open details for' selectbox: a visible alternative to ticking a table row to open its pop-up."""
    pick_key = f"{target}_pick_{st.session_state.get(f'{target}_n', 0)}"
    st.columns([1, 2])[0].selectbox("Open details for", items, index=None, format_func=fmt_item, placeholder=placeholder,
                                    key=pick_key, on_change=open_from_pick, args=(pick_key, target))


def page_kpis():
    """KPIs page (filtered): verdict line, the 8-KPI status table with weekly sparklines, and a week-by-week pop-up per KPI."""
    header("KPIs and trend")
    showing()
    if cf.empty:
        st.warning(NO_CALLS)
        return
    if not both_periods:
        st.info(NEED_BOTH)
        return
    weeks = weekly_table(cf) if len(FULL_WEEKS) else pd.DataFrame(columns=list(KPIS))
    trends = {k: trend_since_spike(cf, k) for k in KPIS}
    status = {k: kpi_status(k, SEL[k], trends[k]) for k in KPIS}
    def bucket(state, box):
        if box in ("error", "warning", "success"):
            return {"error": "still high or getting worse", "warning": "easing or slightly above",
                    "success": "close to or better than pre-spike"}[box]
        return "within noise" if state == "Within noise" else "too few calls to tell"
    counts = pd.Series([bucket(*v) for v in status.values()]).value_counts()
    order = ["still high or getting worse", "easing or slightly above", "within noise",
             "close to or better than pre-spike", "too few calls to tell"]
    st.markdown(f"**Of {len(KPIS)} KPIs: " + " · ".join(f"{counts[o]} {o}" for o in order if o in counts) + ".** "
                "Tick the box at the left of a row, or pick a KPI below, for its week-by-week chart.")
    keys = list(KPIS)
    pre_weeks = [w for w in weeks.index if w.endswith("before")]

    def spark(k):        # pre-spike weeks drawn at the pre-spike average (their weekly values are noise), then weekly
        vals = [B[k]] * len(pre_weeks) + list(weeks.loc[~weeks.index.isin(pre_weeks), k])
        return [round(x, 2) for x in vals if not pd.isna(x)]          # weeks with no data are skipped

    def change_cell(k):  # flag changes that rest on too few calls or are within noise
        raw = change(k, SEL[k]["pre"], SEL[k]["post"]) or "—"
        if SEL[k]["real"] or raw == "—":
            return raw
        return f"{raw} (few {'surveys' if k == 'csat' else 'calls'})" if SEL[k]["n_min"] < MIN_TEST else f"{raw} (noise)"

    overview = pd.DataFrame([{
        "KPI": KPIS[k][0], "Status": status[k][0],
        "Pre → post": f"{fmt(B[k], KPIS[k][1], KPIS[k][2])} → {fmt(A[k], KPIS[k][1], KPIS[k][2])}",
        "Change": change_cell(k), "Week by week": spark(k) if len(weeks) else []} for k in keys])
    colour = {"error": "#B42318", "warning": "#B54708", "success": "#067647", "info": "#52514e"}
    styled = overview.style.apply(lambda col: [f"color: {colour[status[k][1]]}; font-weight: 600" for k in keys],
                                  subset=["Status"])
    table_key = f"kpi_table_{st.session_state.get('kpi_n', 0)}"
    st.dataframe(styled, hide_index=True, use_container_width=True, height=36 * (len(keys) + 1) + 3,
                 on_select=partial(on_row_open, table_key, keys, "kpi"), selection_mode="single-row", key=table_key,
                 column_config={"KPI": st.column_config.TextColumn(width="medium"),
                                "Pre → post": st.column_config.TextColumn("Pre-spike → post-spike"),
                                "Change": st.column_config.TextColumn(width="small"),
                                "Week by week": st.column_config.LineChartColumn(
                                    "Week by week", y_min=0, help="Pre-spike average, then each week from the spike"),
                                "Status": st.column_config.TextColumn(width="medium")})
    open_details_box(keys, "kpi", "Choose a KPI…", lambda k: KPIS[k][0])
    in_range = [n for n, p in ((n_before, "before"), (n_after, "after")) if N_DAYS.get(p)]
    if in_range and min(in_range) < MIN_SAMPLE:
        st.warning(f"Fewer than {MIN_SAMPLE} sampled calls on one side: treat the numbers as rough direction only.")
    st.caption(f"{n_before} sampled calls pre-spike, {n_after} post-spike · not in the data: call rate per customer, "
               "true dispatch rate, firmware per call")
    opened = st.session_state.pop("kpi_open", None)
    if opened in KPIS:
        st.dialog(KPIS[opened][0], width="large")(kpi_detail)(opened, weeks, trends[opened])


def page_drivers():
    """Drivers page (filtered): pre- vs post-spike calls per day by any dimension, takeaway line, drill-down panel, numbers table and region × reason heatmap."""
    header(f"What drove the increase · by {st.session_state['dim'].lower()}")
    showing()
    if cf.empty:
        st.info(NO_CALLS)
        return
    if not both_periods:
        st.info(NEED_BOTH)
        return
    dim = st.session_state["dim"]                   # set in the sidebar ("Break down by")
    col = DIMENSIONS[dim]
    t = compare(cf, col)
    names = list(t.index)
    drill_key = f"drill_{col}"
    if st.session_state.get(drill_key) not in names:
        st.session_state[drill_key] = t["Change"].idxmax()
    chosen = st.session_state[drill_key]
    total = t["Change"].sum()
    lead = t.sort_values("Change", ascending=False).head(2)
    if len(t) == 1:
        st.markdown(f"**Only one {dim.lower()} group in this selection: {names[0]}** · "
                    f"{fmt(t['After'].iloc[0])} calls a day post-spike ({t['% change'].iloc[0]:+.0f}% vs pre-spike)")
    elif total > 0:
        st.markdown(f"**{' and '.join(lead.index)} {'add' if len(lead) > 1 else 'adds'} the most: "
                    f"{lead['Change'].sum() / total * 100:.0f}% of the increase** · "
                    f"{int((t['Change'] > 0).sum())} of {len(t)} groups rose")
    else:
        st.markdown("**No overall increase for this selection**")

    left, right = st.columns([3, 2], gap="medium")
    with left:
        labels = [f"{n}{' · ' + fw_tag[n] if col == 'region' else ''}<br><b>{pc:+.0f}%{'*' if few else ''}</b>"
                  if not pd.isna(pc) else n for n, pc, few in zip(names, t["% change"], t["few"])]
        chart_key = f"bars_{col}_{chosen}"
        st.plotly_chart(before_after_bars(t, 120 + 46 * len(t), chosen, labels), use_container_width=True, key=chart_key, config=CHART_CONFIG,
                        selection_mode="points", on_select=partial(on_bar_click, chart_key, drill_key, names))
        few = t[t["few"]]
        st.caption("Estimated calls per day · **click a bar to drill in**"
                   + (f" · \\* small sample ({few['n_pre'].min()}–{few['n_pre'].max()} sampled calls pre-spike): "
                      "the direction holds where the change beats noise, the exact % is approximate" if len(few) else ""))
    with right, st.container(border=True):
        st.selectbox("Drill into", names, key=drill_key)
        r = t.loc[chosen]
        d, colour, note = delta_view("calls", pre_post("calls", cf[cf[col] == chosen]))
        st.metric("Post-spike calls per day", fmt(r["After"]), d, delta_color=colour,           # stacked: labels fit
                  help=f"Pre-spike: {r['Before']:.1f} a day")
        if note:
            st.caption(note)
        st.metric("Share of the increase", fmt(r["Share of increase %"], "%"), help=f"{r['Change']:+.1f} calls a day")
        sub_col, sub_name = ("region", "region") if col == "issue_type" else ("issue_type", "reason")
        trend_tab, split_tab = st.tabs(["Week by week", f"By {sub_name}"])
        s = weekly(cf[cf[col] == chosen], "calls")
        fig = base_fig(250)
        fig.add_trace(go.Scatter(x=s.index, y=s.values, mode="lines+markers", line=dict(color=BLUE, width=2),
                                 marker=dict(size=8), hovertemplate="%{x}: %{y:.1f} a day<extra></extra>"))
        mark_spike_week(fig, label=False)
        sparse_week_ticks(fig)
        fig.update_yaxes(title="Calls per day", rangemode="tozero")
        trend_tab.plotly_chart(fig, use_container_width=True, config=CHART_CONFIG)
        sub = compare(cf[cf[col] == chosen], sub_col)
        split_tab.plotly_chart(before_after_bars(sub, 60 + 34 * len(sub)), use_container_width=True, config=CHART_CONFIG)

    with st.expander("Numbers behind the chart"):
        st.dataframe(t.drop(columns=["few", "n_pre"]), use_container_width=True, column_config={
            "Sampled calls": st.column_config.TextColumn("Sampled calls (pre → post)"),
            "Before": st.column_config.NumberColumn("Pre-spike", format="%.1f"),
            "After": st.column_config.NumberColumn("Post-spike", format="%.1f"),
            "Change": st.column_config.NumberColumn("Change (calls/day)", format="%+.1f"),
            "% change": st.column_config.NumberColumn(format="%+.0f%%"),
            "Share of increase %": st.column_config.NumberColumn(format="%.0f%%")})
    with st.expander("Heatmap: region × reason"):
        view = st.radio("Show", ["Calls per day post-spike", "Change vs pre-spike"], horizontal=True, key="heat_view",
                        label_visibility="collapsed")
        g = cf.groupby(["region", "issue_type", "period"])["weight"].sum().unstack(fill_value=0).reindex(columns=["before", "after"], fill_value=0)
        g = pd.DataFrame({"before": g["before"] / N_DAYS["before"], "after": g["after"] / N_DAYS["after"]})
        z = (g["after"] if view.startswith("Calls") else g["after"] - g["before"]).unstack(fill_value=0)
        z = z.loc[z.sum(axis=1).sort_values(ascending=False).index, z.sum().sort_values(ascending=False).index]
        fig = go.Figure(go.Heatmap(z=z.values, x=z.columns, y=[f"{r} ({fw_tag.get(r, '')})" for r in z.index],
                                   colorscale=[[0, "#f4f8fc"], [1, BLUE]], text=np.round(z.values, 1),
                                   texttemplate="%{text}", hovertemplate="%{y} · %{x}: %{z:.1f}<extra></extra>",
                                   showscale=False))
        fig.update_layout(**LAYOUT, height=320)
        fig.update_xaxes(fixedrange=True)
        fig.update_yaxes(autorange="reversed", fixedrange=True)
        st.plotly_chart(fig, use_container_width=True, config=CHART_CONFIG)
        st.caption("Small cells rest on few sampled calls: read as direction")


def page_cause():
    """Root cause page (company-wide): Suspect 1 = device telemetry by firmware; Suspect 2 = BC + Atlantic share vs the firmware-only counterfactual; plus the data gaps."""
    header("Root cause: two suspects, neither proven yet")
    st.caption("Company-wide, not affected by filters")
    dv = devices.groupby("firmware_version").agg(devices=("customer_id", "size"), reboots=("reboot_count_7d", "mean"),
                                                 low_signal=("signal_quality_band", lambda s: (s == "Low").mean() * 100))
    no_upd = calls[~calls["region_has_event"]]                      # BC + Atlantic: no firmware update logged
    shares = (wsum(no_upd, "before") / wsum(calls, "before") * 100, wsum(no_upd, "after") / wsum(calls, "after") * 100,
              # if only updated provinces had risen, BC + Atlantic would have kept their before volume per day
              (wsum(no_upd, "before") / full_days["before"]) / (wsum(calls, "after") / full_days["after"]) * 100)
    s1, s2 = st.columns(2)
    with s1.container(border=True):
        st.markdown("**Suspect 1 · Firmware 3.8.1**")
        st.caption("Average reboots per device in a week")
        fig = base_fig(240)
        fig.add_trace(go.Bar(x=[f"{i} ({n} devices)" for i, n in zip(dv.index, dv["devices"])], y=dv["reboots"],
                             marker=dict(color=[GREY if "3.7" in i else ORANGE for i in dv.index], cornerradius=4),
                             text=[f"{r:.0f}× a week · {w:.0f}% weak signal" for r, w in zip(dv["reboots"], dv["low_signal"])],
                             textposition="outside", hoverinfo="skip"))
        fig.update_layout(showlegend=False)
        fig.update_yaxes(range=[0, dv["reboots"].max() * 1.3], showticklabels=False)
        st.plotly_chart(fig, use_container_width=True, config=CHART_CONFIG)
        st.markdown("- 3.8.1 devices reboot **12× a week (vs 2)**, all with weak signal\n"
                    "- The jump came 1–4 days after the Ontario and Prairies updates\n"
                    "- **To confirm:** rollback pilot · firmware version per caller")
    with s2.container(border=True):
        st.markdown("**Suspect 2 · A nationwide change**")
        st.caption("BC + Atlantic share of all calls")
        fig = base_fig(240)
        fig.add_trace(go.Bar(x=["Pre-spike", "Post-spike", "Post-spike, if only<br>updated provinces were hit"], y=shares,
                             marker=dict(color=[BLUE, BLUE, "white"], line=dict(color=BLUE, width=1.5), cornerradius=4),
                             text=[f"{v:.0f}%" for v in shares], textposition="outside", hoverinfo="skip"))
        fig.update_layout(showlegend=False)
        fig.update_yaxes(range=[0, 50], showticklabels=False)
        st.plotly_chart(fig, use_container_width=True, config=CHART_CONFIG)
        st.markdown("- BC and Atlantic had no update, yet kept their share of calls\n"
                    "- One overnight jump everywhere; no second jump after Quebec's 2 Jun update\n"
                    "- **To confirm:** network change log, 1 Apr–30 Jun")
    st.markdown("**Why these are still hypotheses: missing data**")
    gaps = (("technical_calls", "no firmware_version", "which firmware each caller had"),
            ("network_events", "no firmware_version", "which version each update installed"),
            ("device_health", "customer IDs ≠ callers", "whether callers' devices were the unstable ones"),
            ("Network change log", "not provided", "any central change, 1 Apr–30 Jun"))
    for column, (table, issue, would_show) in zip(st.columns(4), gaps):
        with column.container(border=True):
            st.markdown(f"**{table}** · {issue}")
            st.caption(f"Would show {would_show}")


def voice_detail(reason):
    """Pop-up body: how this call reason changed and what those callers say."""
    gr = cf[cf["issue_type"] == reason]
    a = kpis(gr[gr["period"] == "after"], N_DAYS.get("after", 0))
    for column, key in zip(st.columns(4), ("calls", "repeat", "follow_up", "csat")):
        label, unit, dec, _, _, _ = KPIS[key]
        c = pre_post(key, gr)
        d, colour, note = delta_view(key, c)
        column.metric(label, fmt(c["post"], unit, dec), d, delta_color=colour, help=f"Pre-spike: {fmt(c['pre'], unit, dec)}")
        if note:
            column.caption(note)
    period = "after" if (gr["period"] == "after").any() else "before"
    said = gr[gr["period"] == period].groupby("core_text")["weight"].sum().sort_values(ascending=False)
    if said.empty:
        st.info("No transcripts for this reason pre- or post-spike.")
        return
    st.markdown(f"**What these callers say** ({'post' if period == 'after' else 'pre'}-spike)")
    for text, w in said.head(2).items():
        st.markdown(f"> “{text}”  \n> <small>{w / said.sum() * 100:.0f}% of these calls</small>", unsafe_allow_html=True)
    if a["june_note"] > 0:
        st.markdown(f"**Agent note** on {a['june_note']:.0f}% of these calls post-spike: *“June notes suggest increased "
                    "regional instability, repeat troubleshooting contacts, and customer frustration.”*")
    st.caption("Call summaries are templated, not verbatim speech · close this window to pick another reason")


def page_voice():
    """Voice page (filtered): post-spike pain points per call reason; each reason opens a pop-up with noise-tested KPIs and its (templated) call summaries."""
    header("Customer voice: what callers report")
    showing()
    if cf.empty:
        st.info(NO_CALLS)
        return
    if not N_DAYS.get("after"):
        st.info("Pain points are measured post-spike: include June in the dates.")
        return
    rows = []
    for reason, gr in cf.groupby("issue_type"):
        b = kpis(gr[gr["period"] == "before"], N_DAYS.get("before", 0))
        a = kpis(gr[gr["period"] == "after"], N_DAYS.get("after", 0))
        rows.append({"Reason": reason, "Calls/day": a["calls"],
                     "Change": (a["calls"] / b["calls"] - 1) * 100 if b["calls"] else np.nan,
                     "Weekly": weekly(gr, "calls").round(1).tolist(), "Repeat": a["repeat"],
                     "Follow-up": a["follow_up"], "Negative": a["negative"], "CSAT": a["csat"]})
    sc = pd.DataFrame(rows).sort_values("Calls/day", ascending=False).reset_index(drop=True)
    n_pre = cf[cf["period"] == "before"].groupby("issue_type").size().reindex(sc["Reason"], fill_value=0)
    few = n_pre[n_pre < MIN_SAMPLE]
    st.markdown("**Pain points post-spike** · tick the box at the left of a row, or pick a reason below, to read what "
                "those callers say")
    bar = lambda name: st.column_config.ProgressColumn(name, min_value=0, max_value=100, format="%.0f%%",  # noqa: E731
                                                       width="small")
    table_key = f"voice_table_{st.session_state.get('voice_n', 0)}"
    st.dataframe(sc, hide_index=True, use_container_width=True, on_select=partial(on_row_open, table_key,
                 sc["Reason"].tolist(), "voice"), selection_mode="single-row", key=table_key, column_config={
                     "Reason": st.column_config.TextColumn(width="medium"),
                     "Calls/day": st.column_config.NumberColumn("Calls/day", format="%.1f", width="small"),
                     "Change": st.column_config.NumberColumn("vs pre-spike" + ("*" if len(few) else ""),
                                                             format="%+.0f%%", width="small"),
                     "Weekly": st.column_config.LineChartColumn("Week by week", y_min=0, width="small"),
                     "Repeat": bar("Repeats"), "Follow-up": bar("Follow-up"), "Negative": bar("Negative"),
                     "CSAT": st.column_config.NumberColumn("CSAT", format="%.1f", width="small")})
    if not N_DAYS.get("before"):
        note = " · “vs pre-spike” is blank because the dates leave out 1–25 May"
    elif len(few) == len(sc):
        note = (f" · \\* small samples ({few.min()}–{few.max()} sampled pre-spike calls per reason): large changes "
                "are clear, exact % approximate")
    elif len(few):
        note = (f" · \\* {len(few)} reasons rest on fewer than {MIN_SAMPLE} sampled pre-spike calls: exact % "
                "approximate")
    else:
        note = ""
    open_details_box(sc["Reason"].tolist(), "voice", "Choose a call reason…")
    st.caption("Post-spike values · bars show the share of each reason's calls" + note)
    opened = st.session_state.pop("voice_open", None)
    if opened in set(sc["Reason"]):
        st.dialog(opened, width="large")(voice_detail)(opened)


def page_monitor():
    """Monitor page (company-wide, as of the latest data): what's at stake, alert cards against adjustable alert lines, daily and weekly charts."""
    latest = daily["call_date"].max()
    header("Monitor recovery")
    st.caption(f"Company-wide · status as of {latest.day} {latest:%b} (latest data) · filters don't apply here")
    st.caption("WHAT'S AT STAKE")
    k1, k2, k3 = st.columns(3)
    with k1.container(border=True):
        st.metric("Repeat calls", fmt(CA["repeat"], "%"), change("repeat", CB["repeat"], CA["repeat"]),
                  delta_color="inverse")
        st.caption(f"Retention risk · {fmt(CA['detractors'], '%')} of surveyed callers are detractors")
    with k2.container(border=True):
        st.metric("Agent hours per day", fmt(CA["agent_hours"]),
                  change("agent_hours", CB["agent_hours"], CA["agent_hours"]), delta_color="inverse")
        st.caption(f"Cost to serve · {CA['agent_hours'] / CB['agent_hours']:.1f}× the pre-spike workload")
    with k3.container(border=True):
        st.metric(f"Days above {VOLUME_ALERT} calls", f"{(after_days['total_calls'] > VOLUME_ALERT).sum()}")
        st.caption("Reputation · every day since the spike")

    vol_line, rep_line = st.session_state["vol_line"], st.session_state["rep_line"]      # set in the sidebar
    st.caption("ALERTS · MOVE THE ALERT LINES IN THE SIDEBAR (SLIDE 3: 96 CALLS A DAY, 18% REPEATS)")
    last7 = daily.sort_values("call_date").tail(7)                       # latest 7 days, whatever the filters
    vol_now, rep_now = last7["total_calls"].mean(), CW["repeat"]["post"]
    first7 = last7["call_date"].min()
    n_unstable = int((devices["reboot_count_7d"] >= UNSTABLE_REBOOTS).sum())
    alerts = (("Volume (calls per day)", fmt(vol_now), status(vol_now, vol_line),
               f"Alert above {vol_line} · normal {normal:.0f} · average of {first7.day}–{latest.day} {latest:%b}"),
              ("Repeat calls", fmt(rep_now, "%"), status(rep_now, rep_line),
               f"Alert above {rep_line}% · normal {fmt(CB['repeat'], '%')} · post-spike (June)"),
              ("Unstable devices", f"{n_unstable} / {len(devices)}", "● Watch",
               f"Rebooting {UNSTABLE_REBOOTS}+ times a week (normal 2) · not yet linked to callers"))
    for column, (label, now, state, note) in zip(st.columns(3), alerts):
        with column.container(border=True):
            st.metric(label, now)
            color = "red" if state.startswith("▲") else "green" if state == "● OK" else "gray"
            st.markdown(f":{color}[**{state}**]")
            st.caption(note)
    calls_tab, repeat_tab = st.tabs(["Daily calls vs alert line", "Weekly repeat rate vs alert line"])
    with calls_tab:
        st.plotly_chart(daily_chart(300, alert=vol_line), use_container_width=True, config=CHART_CONFIG)
        st.caption(f"Above the line on {(after_days['total_calls'] > vol_line).sum()} of {len(after_days)} days "
                   "since the spike")
    with repeat_tab:
        s = weekly(calls, "repeat", ALL_WEEKS)
        fig = base_fig(300)
        fig.add_trace(go.Scatter(x=s.index, y=s.values, mode="lines+markers", line=dict(color=BLUE, width=2),
                                 marker=dict(size=8), hovertemplate="%{x}: %{y:.0f}%<extra></extra>"))
        fig.add_hline(y=rep_line, line=dict(color=ORANGE, width=1.5, dash="dash"))
        mark_spike_week(fig, label=False, labels=list(s.index))
        fig.update_layout(showlegend=False)
        fig.update_yaxes(range=[0, 45], ticksuffix="%", title="Repeat calls")
        st.plotly_chart(fig, use_container_width=True, config=CHART_CONFIG)
        st.caption(f"Above the line in {int((s > rep_line).sum())} of {len(s)} full weeks")
    st.caption("Next app enhancements: automatic notifications on these lines and a daily data refresh.")


def page_notes():
    """Notes page: method, periods, noise check, proxies and data limits in plain language."""
    header("Data notes: how to read these numbers")
    st.markdown("""
- **Where the numbers come from.** We were given two views of the same calls: `call_volume_daily` with the true number
  of technical calls each day (7,336 in May–June), and `technical_calls` with details for only 750 of them (about 10%).
  The call details arrived as a sample; we did not sample them. The share varies (about 6% of calls on 1–25 May, 4% on
  26–31 May, 13% in June), so each sampled call is weighted by *true calls that day ÷ sampled calls that day*, and
  unfiltered totals match the true daily counts exactly.
- **Periods.** Daily totals split at 26 May. Call comparisons use **1–25 May vs June**: the 34 sampled calls for
  26–31 May still look like May (connectivity 29%, repeats 9%, no June agent note), so they are left out.
- **Noise check.** A change counts only if it is bigger than two standard errors (the sampling error). It needs at
  least 10 sampled calls (10 surveys for CSAT) on each side, otherwise the app says “Too few calls to tell”; results
  resting on 10–29 are marked “small sample” (direction clear, size approximate). Changes smaller than the sampling
  error say “Within noise”. The same test decides whether a post-spike trend is rising or easing.
- **Proxies.** Technician visits = calls ending “Technician scheduled” (`truck_rolls` not provided). Firmware filter =
  whether the caller's region had a logged update (no firmware per caller). Unstable devices = 6+ reboots a week.
- **Not available.** Call rate per customer (`customer_base_daily` not provided), true dispatch rate, wait times,
  cost and churn.
- **Labels.** Platform, product and region labels look randomly assigned (e.g. “Fibre Gigabit” on Satellite), so
  they are not used as a proxy for equipment.
- **Excluded AI fields.** `detected_theme` matched the call reason only at chance level (18% vs 17%);
  `ai_sentiment` is a copy of `customer_sentiment`.
- **Definitions.** “Resolved on call” = resolved during that call (no true first-contact measure). Agents are never
  evaluated individually. All data is synthetic, created for the assessment.
""")
    st.caption("Source: workspace.xplore_gold (fct_calls, fct_daily_volume, dim_region, fct_device_health) and "
               "workspace.xplore_silver.stg_transcripts")


# ======================================================================== navigation + sidebar filters
PAGES = {
    "summary": st.Page(page_summary, title="Summary", icon=":material/dashboard:", url_path="summary", default=True),
    "kpis": st.Page(page_kpis, title="KPIs", icon=":material/monitoring:", url_path="kpis"),
    "drivers": st.Page(page_drivers, title="Drivers", icon=":material/bar_chart:", url_path="drivers"),
    "cause": st.Page(page_cause, title="Root cause", icon=":material/troubleshoot:", url_path="root-cause"),
    "voice": st.Page(page_voice, title="Voice", icon=":material/forum:", url_path="voice"),
    "monitor": st.Page(page_monitor, title="Monitor", icon=":material/notifications_active:", url_path="monitor"),
    "notes": st.Page(page_notes, title="Notes", icon=":material/info:", url_path="notes"),
}
FILTERED_PAGES = {"KPIs", "Drivers", "Voice"}
current = st.navigation(list(PAGES.values()), position="hidden")     # menu drawn as a top bar below


def reset_filters(first, last):
    """'Reset filters' button: restore the full date range and clear every filter."""
    st.session_state["dates"] = (first, last)
    for _, c_ in FILTERS + MORE_FILTERS:
        st.session_state[f"f_{c_}"] = []


with st.sidebar:
    if current.title == "Drivers":
        st.subheader("View", anchor=False)
        st.selectbox("Break down by", list(DIMENSIONS), key="dim")
    if current.title == "Monitor":
        st.subheader("Alert lines", anchor=False)
        st.slider("Volume alert: calls per day above", 80, 160, key="vol_line")
        st.slider("Repeat alert: repeat rate above (%)", 10, 40, key="rep_line")
        st.caption(f"Slide 3: {VOLUME_ALERT} calls a day, {REPEAT_ALERT}% repeats")
    if current.title in FILTERED_PAGES:
        st.subheader("Filters", anchor=False)
        st.slider("Dates", min_value=dmin, max_value=dmax, key="dates", format="D MMM")
        help_ = {"firmware_region": f"Region-level stand-in (no firmware per caller). No update: {not_updated}."}

        def pick(label, c_):
            st.multiselect(label, sorted(calls[c_].dropna().unique()), key=f"f_{c_}", placeholder="All",
                           help=help_.get(c_))

        for label, c in FILTERS:
            pick(label, c)
        with st.expander("More filters", expanded=any(st.session_state[f"f_{c}"] for _, c in MORE_FILTERS)):
            for label, c in MORE_FILTERS:
                pick(label, c)
        st.button("Reset filters", on_click=reset_filters, args=(dmin, dmax), use_container_width=True)
        st.caption("Filters apply on every page that shows them. Call details were provided for about 10% of calls, "
                   "weighted up to the true daily totals.")
    else:
        st.caption("This page shows all calls. Filters appear on KPIs, Drivers and Voice"
                   + (f" (now: {scope})." if scope != "All calls" else "."))
    st.divider()
    st.button("Refresh data", on_click=refresh_data, use_container_width=True,
              help="Reload the tables from Databricks (the data is static, so this is rarely needed)")
    st.caption(f"Data loaded {loaded_at():%H:%M} UTC")

menu_widths = [len(p.title) + 0.6 * sum(ch in "mwMW" for ch in p.title) + 4 for p in PAGES.values()]
for column, page in zip(st.columns(menu_widths, gap="small"), PAGES.values()):  # top menu: short labels, no icons
    column.page_link(page, label=page.title, use_container_width=True)
st.divider()
current.run()
