"""Run every filter scenario through the real app headlessly and save what each page shows (app_filters.json)."""
from harness import *
from scenarios import SCEN
res = {}
for name, spec in SCEN.items():
    at = start(spec)
    out = {"kpis": snap(at)}
    for p in ["drivers", "voice", "monitor", "summary", "root-cause", "notes", "kpis"]:
        goto(at, p)
        out[p if p != "kpis" else "kpis_again"] = snap(at)
    res[name] = out
    print(name, "exc:", sum(len(v["exception"]) for v in out.values()))
json.dump(res, open("app_filters.json", "w"), default=str)
