"""Thin Streamlit demo for grid outage operations.

Run:  pip install streamlit
      streamlit run demo/app.py

All logic lives in gridops/demo_helpers.py (stdlib only, fully tested);
this file only renders.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import streamlit as st  # noqa: E402  (imported lazily; pip install streamlit)

from gridops import demo_helpers as H  # noqa: E402

st.set_page_config(page_title="Grid Outage Ops", layout="wide")
st.title("Grid Outage Operations — Lakeshore Power & Light (synthetic)")

db = H.ensure_db("/tmp/gridops-demo.db")
sops = Path(__file__).resolve().parents[1] / "docs" / "sops"

tab1, tab2, tab3 = st.tabs(["Outages", "Dispatch plan", "Ask"])

with tab1:
    for o in H.outage_summary(db):
        st.write(f"**{o['outage_id']}** — {o['feeder_id']} — "
                 f"{o['customers_out']:,} customers out — ETR {o['etr_hours']}h")

with tab2:
    plan = H.dispatch_plan(db)
    st.write(f"Outage **{plan['outage_id']}** — severity **{plan['severity']}** "
             f"({plan['tier']})")
    st.code(plan["severity_breakdown"])
    st.success(f"Dispatch **{plan['crew']}** — score {plan['score']}")
    st.code(plan["breakdown"])

with tab3:
    q = st.text_input("Ask an operations question",
                      "Which outages are active and who should go to OUT-SEV-01?")
    if q:
        st.json(H.ask(db, sops, q))
