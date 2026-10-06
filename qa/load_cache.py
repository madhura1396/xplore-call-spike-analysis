"""Load the app's data once through app/data.py (same code path as the app, local CLI mode) and pickle it."""
import os, logging, pickle, sys, warnings
warnings.filterwarnings("ignore"); logging.disable(logging.WARNING)
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app"))
import data
real = data.load()
for k, v in real.items():
    print(k, v.shape)
c = real["calls"]
print("periods:", c["period"].value_counts().to_dict())
print("weight NaN:", c["weight"].isna().sum(), "transcript NaN:", c["transcript_text"].isna().sum())
print("dtypes:", c.dtypes[["call_date", "is_repeat_contact", "has_feedback", "csat_score", "region_has_event"]].to_dict())
pickle.dump(real, open("real.pkl", "wb"))
