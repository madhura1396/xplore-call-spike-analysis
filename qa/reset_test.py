"""Reset test: apply five filters and a date range, click Reset, check every filter is cleared and stays cleared."""
from harness import *
from scenarios import SCEN
# Reset: apply 5 filters + dates, click Reset, check everything cleared
spec = {"dates": (D(2026, 5, 20), D(2026, 6, 10)), "f_region": ["Quebec"], "f_issue_type": ["Slow Speed"],
        "f_platform": ["Fibre"], "f_customer_segment": ["Residential"], "f_channel": ["Phone"]}
at = start(spec)
before = next(c.value for c in at.caption if c.value.startswith("Showing:"))
next(b for b in at.button if b.label == "Reset filters").click().run()
after = next(c.value for c in at.caption if c.value.startswith("Showing:"))
vals = {k: at.multiselect(key=k).value for k in ["f_region", "f_firmware_region", "f_issue_type", "f_platform", "f_product", "f_customer_segment", "f_channel"]}
print("RESET before:", before); print("RESET after:", after, "| multiselects:", vals, "| dates:", at.slider(key="dates").value)
# Reset then visit another page: still reset?
goto(at, "drivers"); print("RESET persists on drivers:", next(c.value for c in at.caption if c.value.startswith("Showing:")))
# firmware filter label + help text
ms = [m for m in at.multiselect if m.key == "f_firmware_region"][0]
print("FIRMWARE label:", ms.label, "| help:", ms.proto.help, "| options:", ms.options)
# sidebar on company-wide page with a filter set
at = start({"f_region": ["Ontario"]}); goto(at, "root-cause")
print("ROOT sidebar:", [c.value for c in at.sidebar.caption] if hasattr(at.sidebar, "caption") else [c.value for c in at.caption if "now:" in c.value])
print("ROOT has filter widgets:", [m.key for m in at.multiselect])
# Monitor sliders change status (default 96 / 18 -> ALERT; 160 / 40 -> OK)
at = start(); goto(at, "monitor")
at.slider(key="vol_line").set_value(150).run(); at.slider(key="rep_line").set_value(30).run()
print("MONITOR 150/30:", [m.value for m in at.markdown if m.value.startswith(":")], [c.value for c in at.caption if c.value.startswith(("Above", "Alert"))])
