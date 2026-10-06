"""The 40 filter scenarios used by the audit: dates, single filters, multi-filter combinations and empty selections."""
import datetime as dt
D = dt.date
SCEN = {"default": {}}
SCEN.update({
    "dates 1-25 May": {"dates": (D(2026, 5, 1), D(2026, 5, 25))},
    "dates June": {"dates": (D(2026, 6, 1), D(2026, 6, 30))},
    "dates 26-31 May": {"dates": (D(2026, 5, 26), D(2026, 5, 31))},
    "dates 20 May-10 Jun": {"dates": (D(2026, 5, 20), D(2026, 6, 10))},
})
for r in ["Atlantic", "British Columbia", "Ontario", "Prairies", "Quebec"]:
    SCEN[f"region={r}"] = {"f_region": [r]}
for v in ["Update logged", "No update"]:
    SCEN[f"firmware={v}"] = {"f_firmware_region": [v]}
for v in ["No Internet", "Slow Speed", "Hardware Issue", "Outage Inquiry", "Service Appointment", "Billing Question",
          "Wi-Fi Setup", "Account Access"]:
    SCEN[f"reason={v}"] = {"f_issue_type": [v]}
for v in ["Residential", "Small Business"]:
    SCEN[f"segment={v}"] = {"f_customer_segment": [v]}
for v in ["Phone", "Chat", "Email"]:
    SCEN[f"channel={v}"] = {"f_channel": [v]}
for v in ["Fixed Wireless", "Fibre", "Satellite", "LTE/5G"]:
    SCEN[f"platform={v}"] = {"f_platform": [v]}
for v in ["Fibre Gigabit", "Rural Wireless", "Internet 50"]:
    SCEN[f"product={v}"] = {"f_product": [v]}
SCEN.update({
    "M1 Ontario+No Internet": {"f_region": ["Ontario"], "f_issue_type": ["No Internet"]},
    "M2 BC,Atlantic+Slow Speed": {"f_region": ["British Columbia", "Atlantic"], "f_issue_type": ["Slow Speed"]},
    "M3 Update logged+Residential+Phone": {"f_firmware_region": ["Update logged"], "f_customer_segment": ["Residential"],
                                           "f_channel": ["Phone"]},
    "M4 Prairies+Fixed Wireless+20May-30Jun": {"dates": (D(2026, 5, 20), D(2026, 6, 30)), "f_region": ["Prairies"],
                                               "f_platform": ["Fixed Wireless"]},
    "M5 No update+connectivity+Small Business": {"f_firmware_region": ["No update"],
                                                 "f_issue_type": ["No Internet", "Slow Speed"],
                                                 "f_customer_segment": ["Small Business"]},
    "M6 empty Quebec+Account Access+1-25May": {"dates": (D(2026, 5, 1), D(2026, 5, 25)), "f_region": ["Quebec"],
                                               "f_issue_type": ["Account Access"]},
    "M7 empty Atlantic+LTE/5G+Fibre Gigabit+Account Access": {"f_region": ["Atlantic"], "f_platform": ["LTE/5G"],
                                                              "f_product": ["Fibre Gigabit"],
                                                              "f_issue_type": ["Account Access"]},
    "M8 Ontario+June only": {"dates": (D(2026, 6, 1), D(2026, 6, 30)), "f_region": ["Ontario"]},
})
