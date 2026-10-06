"""Run the real app headlessly (AppTest) and extract every displayed value to JSON.
Data: app/data.py's own load(), cached in real.pkl (see load_cache.py). Nothing in app/ is modified."""
import os, datetime as dt, json, logging, pickle, sys, warnings
warnings.filterwarnings("ignore"); logging.disable(logging.WARNING)
APP = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app")
sys.path.insert(0, APP)
import data
real = pickle.load(open("real.pkl", "rb"))
data.load = lambda: {k: v.copy() for k, v in real.items()}
import pandas as pd
from streamlit.testing.v1 import AppTest
from streamlit.util import calc_md5

D = dt.date
PAGES = ["summary", "kpis", "drivers", "root-cause", "voice", "monitor", "notes"]


def df_records(d):
    """Table element → list of row dicts (handles styled tables)."""
    v = d.value
    if hasattr(v, "data"):          # Styler
        v = v.data
    v = v.reset_index() if not isinstance(v.index, pd.RangeIndex) else v
    return json.loads(v.to_json(orient="records", default_handler=str))


import base64, numpy as np
def dec(v):
    """Decode plotly's binary arrays {'dtype','bdata'(,'shape')} to lists."""
    if isinstance(v, dict) and "bdata" in v:
        a = np.frombuffer(base64.b64decode(v["bdata"]), dtype=np.dtype(v["dtype"]))
        if "shape" in v:
            a = a.reshape([int(x) for x in str(v["shape"]).split(",")])
        return a.tolist()
    return v


def snap(at):
    """Capture everything a page displays (text, metrics, tables, chart data) for comparison with SQL."""
    out = {"exception": [e.value for e in at.exception]}
    out["title"] = [t.value for t in at.title]
    out["header"] = [h.value for h in at.header]
    out["markdown"] = [m.value for m in at.markdown]
    out["caption"] = [c.value for c in at.caption]
    out["metric"] = [{"label": m.label, "value": m.value, "delta": m.delta, "help": m.proto.help} for m in at.metric]
    out["info"] = [e.value for e in at.info]
    out["warning"] = [e.value for e in at.warning]
    out["error"] = [e.value for e in at.error]
    out["success"] = [e.value for e in at.success]
    out["dataframe"] = [df_records(d) for d in at.dataframe]
    charts = []
    for p in at.get("plotly_chart"):
        spec = json.loads(p.proto.spec)
        charts.append({"traces": [{k: dec(t.get(k)) for k in ("type", "name", "x", "y", "z", "text") if k in t}
                                  for t in spec["data"]],
                       "annotations": [a.get("text") for a in spec["layout"].get("annotations", [])],
                       "shapes_y": [s.get("y0") for s in spec["layout"].get("shapes", []) if s.get("y0") == s.get("y1")]})
    out["plotly"] = charts
    out["selectbox"] = [{"key": s.key, "label": s.label, "options": list(s.options), "value": s.value} for s in at.selectbox]
    out["multiselect"] = [{"key": s.key, "options": list(s.options), "value": list(s.value)} for s in at.multiselect]
    out["slider"] = [{"key": s.key, "value": str(s.value)} for s in at.slider]
    out["button"] = [b.label for b in at.button]
    return out


def goto(at, page):
    """Switch the headless app to another page."""
    at._page_hash = calc_md5(page)
    return at.run()


def start(spec=None, page="kpis"):
    """Open the app headlessly and apply a filter scenario through the sidebar widgets."""
    at = AppTest.from_file(f"{APP}/app.py", default_timeout=120)
    at.run()
    goto(at, "kpis")                      # filters live in the sidebar of filtered pages
    for key, val in (spec or {}).items():
        (at.slider(key=key) if key == "dates" else at.multiselect(key=key)).set_value(val)
    at.run()
    if page != "kpis":
        goto(at, page)
    return at
