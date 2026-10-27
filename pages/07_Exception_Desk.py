"""Exception Desk: Central triage queue for exception paths E1 through E7."""

import sys
from pathlib import Path
_ROOT_DIR = Path(__file__).resolve().parent.parent
if str(_ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(_ROOT_DIR))


import streamlit as st
import pandas as pd
from datetime import datetime

from src.database import get_db_connection
from src.exception_handler import list_open_exceptions, resolve_exception, EXCEPTION_DEFINITIONS
from src.ui import render_page_header, render_sidebar_info, render_kpi_card, inject_custom_css

st.set_page_config(page_title="Exception Desk | Alliance Admissions", layout="wide")
inject_custom_css()
render_sidebar_info()

render_page_header(
    title="Admissions Exception & Triage Desk",
    subtitle="Central operational triage queue for governance policy exceptions (E1 to E7), ungrounded queries, student complaints, and system recovery.",
    icon="🛡️",
    badge="Admissions Governance & Recovery"
)

# Exception Taxonomy Reference
with st.expander("ℹ️ Exception Taxonomy & Rules Matrix (E1 to E7)"):
    tax_data = [
        {"Code": k, "Exception Type": v["title"], "Severity": v["severity"], "Detection Rule": v["detection_rule"], "Recommended Action": v["recommended_action"]}
        for k, v in EXCEPTION_DEFINITIONS.items()
    ]
    st.dataframe(pd.DataFrame(tax_data), use_container_width=True)

open_exceptions = list_open_exceptions()

if len(open_exceptions) == 0:
    st.success("✅ Zero active exceptions in queue. All automated workflows are operating within normal parameters.")
    st.info("Trigger an exception via **DEMO C** (Unsupported Q&A) or **DEMO G** (Model Failure) on the home page.")
    st.stop()

st.warning(f"⚠️ **{len(open_exceptions)} Open Exception(s) Requiring Human Intervention**")

for exc in open_exceptions:
    lead_id = exc["lead_id"]
    exc_type = exc["exception_type"]
    
    with st.expander(f"🚨 [{exc_type}] {exc['title']} — Lead: {lead_id} ({exc['name']})", expanded=True):
        col_info, col_resolve = st.columns([1.2, 1.0])
        
        with col_info:
            st.markdown(f"""
            - **Lead ID:** `{lead_id}`
            - **Applicant Name:** **{exc['name']}**
            - **Channel:** `{exc['channel']}`
            - **Severity:** `{exc['severity']}`
            - **Detection Rule:** `{exc['detection_rule']}`
            - **Explanation:** {exc['explanation']}
            - **Recommended Action:** *{exc['recommended_action']}*
            """)
            
            # Fetch latest student message
            conn = get_db_connection()
            cur = conn.cursor()
            cur.execute("SELECT student_message FROM leads WHERE lead_id = ?;", (lead_id,))
            msg_row = cur.fetchone()
            conn.close()
            if msg_row:
                st.caption("Latest Student Message Received:")
                st.info(f"\"{msg_row['student_message']}\"")

        with col_resolve:
            st.markdown("#### ✍️ Human Operator Resolution")
            
            with st.form(f"resolve_form_{lead_id}"):
                operator = st.text_input("Admissions Officer", "S. Narayana (Admissions Coordinator)")
                action = st.selectbox("Resolution Action", [
                    "Resolved & Resume Workflow",
                    "Request Additional Info from Student",
                    "Close Case (Ineligible / Out-of-Domain)",
                    "Manual Counsellor Assignment"
                ])
                res_stage = st.selectbox("Resume Workflow From Stage", ["S5_Scoring", "S2_Extraction", "S6_Allocation"])
                notes = st.text_area("Resolution Notes", "Reviewed query; provided manual university clarification.", height=70)
                
                submit_res = st.form_submit_button("✅ Execute Resolution", use_container_width=True)

            if submit_res:
                resolved = resolve_exception(
                    lead_id=lead_id,
                    resolution_action=action,
                    resolution_notes=notes,
                    operator=operator,
                    target_stage=res_stage if "Resume" in action else "Closed"
                )
                if resolved:
                    st.success(f"Exception resolved for **{lead_id}**! Resumed from **{res_stage}**." if "Resume" in action else f"Case **{lead_id}** closed.")
                    st.rerun()
                else:
                    st.error(f"❌ Resolution rejected for **{lead_id}**: Policy violation (e.g. attempting to resume an opted-out applicant under Rule R6). Lead left in review state.")
