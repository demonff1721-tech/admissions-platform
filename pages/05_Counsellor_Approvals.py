"""Counsellor Approvals: Dedicated human-in-the-loop desk for High-lead handoffs."""

import sys
from pathlib import Path
_ROOT_DIR = Path(__file__).resolve().parent.parent
if str(_ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(_ROOT_DIR))


import json
import streamlit as st
import pandas as pd
from datetime import datetime

from src.database import get_db_connection
from src.counsellor_optimizer import execute_allocation_approval, propose_counsellor_for_lead
from src.ui import render_page_header, render_sidebar_info, render_kpi_card, inject_custom_css

st.set_page_config(page_title="Counsellor Approvals | Alliance Admissions", layout="wide")
inject_custom_css()
render_sidebar_info()

render_page_header(
    title="Counsellor Handoff & Approval Desk",
    subtitle="Human-in-the-loop approval gate for High-intent applicant allocations proposed by the SciPy Hungarian optimizer.",
    icon="👨‍🏫",
    badge="Admissions Chair Governance Desk"
)

conn = get_db_connection()
pending_high_df = pd.read_sql_query("""
SELECT * FROM leads 
WHERE classification = 'High' AND current_stage = 'S8_Handoff_Approval'
ORDER BY updated_at DESC;
""", conn)
counsellors_df = pd.read_sql_query("SELECT * FROM counsellors;", conn)
conn.close()

if len(pending_high_df) == 0:
    st.success("✅ Zero pending approvals. All High-intent leads have been confirmed or processed.")
    st.info("Submit a High-intent lead from **02_Student_Enquiries** or run **DEMO A** on the home page.")
    st.stop()

col_title, col_bulk = st.columns([1.2, 0.8])
with col_title:
    st.warning(f"⚠️ **{len(pending_high_df)} High-Intent Lead(s) Awaiting Counsellor Approval**")
with col_bulk:
    if st.button("⚡ 1-Click Approve All Pending Handoffs", use_container_width=True):
        for _, l in pending_high_df.iterrows():
            c_name = l["assigned_counsellor"]
            c_id = "C1"
            for _, c in counsellors_df.iterrows():
                if c["name"] == c_name:
                    c_id = c["counsellor_id"]
                    break
            execute_allocation_approval(
                lead_id=l["lead_id"],
                counsellor_id=c_id,
                slot=l["proposed_slot"] or "Today 03:00 PM",
                operator="Admissions Committee (Bulk Sign-off)",
                decision="Approved",
                comments="Bulk approved by admissions chair."
            )
        st.success(f"Successfully approved all {len(pending_high_df)} pending handoffs!")
        st.rerun()

st.markdown("---")

for idx, lead in pending_high_df.iterrows():
    lead_id = lead["lead_id"]
    
    with st.expander(f"📌 {lead_id} — {lead['name']} | {lead['programme_interest']} | Total Score: {lead['total_score']}/100", expanded=True):
        col_lead, col_alloc = st.columns([1.2, 1.0])
        
        with col_lead:
            st.markdown("#### 📋 Candidate Dossier")
            st.markdown(f"""
            - **Candidate Name:** **{lead['name']}**
            - **Contact:** `{lead['phone']}` | `{lead['email']}`
            - **Channel:** `{lead['channel']}`
            - **Programme Interest:** **{lead['programme_interest']}**
            - **Education:** {lead['education']}
            - **Work Experience:** {lead['work_experience']}
            - **Intended Intake:** {lead['intended_intake']}
            - **Readiness:** {lead['application_readiness']}
            """)
            
            st.markdown("**Original Inquiry Message:**")
            st.info(f"\"{lead['student_message']}\"")
            
            score_data = json.loads(lead["score_breakdown_json"] or "{}")
            if score_data:
                st.caption(f"Score Breakdown: Readiness: {score_data.get('readiness_score', 0)}/25 | Intent: {score_data.get('intent_score', 0)}/25 | Fit: {score_data.get('fit_score', 0)}/20 | Eligibility: {score_data.get('eligibility_score', 0)}/20 | Engagement: {score_data.get('engagement_score', 0)}/10")

        with col_alloc:
            st.markdown("#### 🎯 Hungarian Optimizer Proposal")
            
            c_name = lead['assigned_counsellor'] or 'Prof. Rajesh Nair'
            # Look up counsellor current load
            c_match = counsellors_df[counsellors_df["name"] == c_name]
            load_str = f"{c_match.iloc[0]['active_high_leads']}/8 leads" if len(c_match) > 0 else "Active"
            
            st.markdown(f"""
            - **Proposed Faculty Counsellor:** **{c_name}**
            - **Counsellor Workload:** `{load_str}` (Cap ≤ 8)
            - **Proposed Appointment Slot:** **{lead['proposed_slot'] or 'Today 03:00 PM'}**
            - **SLA Window:** Within 24 Working Hours
            """)

            with st.form(f"approval_form_{lead_id}"):
                operator_name = st.text_input("Approving Admissions Officer", "Prof. K. Swaminathan (Admissions Chair)")
                notes = st.text_input("Reviewer Notes", "Profile validated; degree eligibility verified.")
                
                col_btn1, col_btn2 = st.columns(2)
                with col_btn1:
                    approve_btn = st.form_submit_button("✅ Approve Handoff", use_container_width=True)
                with col_btn2:
                    reject_btn = st.form_submit_button("❌ Reject / Re-plan", use_container_width=True)

            if approve_btn:
                c_id = "C1"
                for _, c_row in counsellors_df.iterrows():
                    if c_row["name"] == c_name:
                        c_id = c_row["counsellor_id"]
                        break
                        
                execute_allocation_approval(
                    lead_id=lead_id,
                    counsellor_id=c_id,
                    slot=lead["proposed_slot"] or "Today 03:00 PM",
                    operator=operator_name,
                    decision="Approved",
                    comments=notes
                )
                st.success(f"Handoff Confirmed! Lead {lead_id} transitioned to Confirmed_Handoff.")
                st.rerun()

            if reject_btn:
                execute_allocation_approval(
                    lead_id=lead_id,
                    counsellor_id="None",
                    slot="None",
                    operator=operator_name,
                    decision="Rejected",
                    comments=notes
                )
                st.error(f"Allocation Rejected for {lead_id}. Logged in immutable audit history.")
                st.rerun()
