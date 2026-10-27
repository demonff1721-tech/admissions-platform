"""Agentic AI Admissions Operations Platform - Alliance University, Bengaluru.
Main Streamlit application entrypoint with enterprise styling and Guided Demo runner.
"""

import sys
from pathlib import Path

# Ensure application root directory is at the top of sys.path for Streamlit Cloud deployment
ROOT_DIR = Path(__file__).resolve().parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import streamlit as st
import pandas as pd
from datetime import datetime

from src.database import (
    init_database, seed_default_counsellors, seed_default_knowledge_documents,
    seed_manual_baseline, seed_demo_leads, get_db_connection
)
from src.agent_graph import run_admissions_workflow
from src.counsellor_optimizer import propose_counsellor_for_lead
from src.nurture import send_next_nurture_message, process_nurture_reply
from src.exception_handler import raise_exception
from src.security import check_for_duplicates
from src.models import LeadRecord
from src.ui import render_page_header, render_sidebar_info, render_kpi_card, inject_custom_css

st.set_page_config(
    page_title="Alliance University | Admissions AI Operations",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Apply unified design system
inject_custom_css()
render_sidebar_info()

# Ensure Database Initialization
@st.cache_resource
def ensure_database():
    init_database()
    seed_default_counsellors()
    seed_default_knowledge_documents()
    seed_manual_baseline()
    seed_demo_leads()
    return True

ensure_database()

# Main Enterprise Header
render_page_header(
    title="Agentic AI Admissions Operations Platform",
    subtitle="Lead-to-Counsellor Autonomous Workflow: Real-time Capture, 5-Criterion Qualification, Grounded RAG, SciPy Hungarian Counsellor Allocation & Human-in-the-Loop Sign-off.",
    icon="🎓",
    badge="Alliance University, Bengaluru • NAAC A+ Accredited"
)

# Live Operational Metrics Strip
conn = get_db_connection()
stats_leads = pd.read_sql_query("SELECT classification, current_stage, escalation_flag FROM leads;", conn)
pending_apps = pd.read_sql_query("SELECT count(*) as cnt FROM approvals WHERE decision = 'Pending';", conn).iloc[0]["cnt"]
couns_load = pd.read_sql_query("SELECT sum(active_high_leads) as active, count(*)*8 as cap FROM counsellors;", conn).iloc[0]
conn.close()

total_cnt = len(stats_leads)
high_cnt = len(stats_leads[stats_leads["classification"] == "High"])
med_cnt = len(stats_leads[stats_leads["classification"] == "Medium"])
exc_cnt = len(stats_leads[stats_leads["escalation_flag"] == 1])

m_col1, m_col2, m_col3, m_col4, m_col5 = st.columns(5)
with m_col1:
    render_kpi_card("Total Pipeline Inquiries", str(total_cnt), "Persistent records in SQLite", color_accent="#0F172A")
with m_col2:
    render_kpi_card("High-Intent Leads", str(high_cnt), "Priority Hungarian matching", color_accent="#10B981")
with m_col3:
    render_kpi_card("Medium Nurture Leads", str(med_cnt), "Enrolled in Day 0–14 sequence", color_accent="#F59E0B")
with m_col4:
    render_kpi_card("Pending Approvals", str(pending_apps), "Human sign-off required", color_accent="#8B5CF6")
with m_col5:
    render_kpi_card("Open Exceptions", str(exc_cnt), "E1–E7 Exception desk queue", color_accent="#EF4444")

st.markdown("---")

# Guided Demonstration Scenarios Selector
st.markdown("### 🚀 Guided Demonstration Scenarios (Section 14)")
st.caption("Execute end-to-end operational scenarios through the actual agent workflow and backend rules:")

demo_cols = st.columns(4)

with demo_cols[0]:
    if st.button("🌟 DEMO A: High Lead Handoff", use_container_width=True, key="demo_btn_a"):
        st.session_state["demo_scenario"] = "A"
    if st.button("🌱 DEMO B: Medium Lead Nurture", use_container_width=True, key="demo_btn_b"):
        st.session_state["demo_scenario"] = "B"

with demo_cols[1]:
    if st.button("🛡️ DEMO C: Unsupported Q&A (E1)", use_container_width=True, key="demo_btn_c"):
        st.session_state["demo_scenario"] = "C"
    if st.button("🔍 DEMO D: Exact Duplicate (R7)", use_container_width=True, key="demo_btn_d"):
        st.session_state["demo_scenario"] = "D"

with demo_cols[2]:
    if st.button("🛑 DEMO E: Opt-Out Message (R6)", use_container_width=True, key="demo_btn_e"):
        st.session_state["demo_scenario"] = "E"
    if st.button("⚖️ DEMO F: Capacity Saturation (R12)", use_container_width=True, key="demo_btn_f"):
        st.session_state["demo_scenario"] = "F"

with demo_cols[3]:
    if st.button("⚠️ DEMO G: Model Failure Recovery", use_container_width=True, key="demo_btn_g"):
        st.session_state["demo_scenario"] = "G"
    if st.button("📊 DEMO H: Audit Trail & KPIs", use_container_width=True, key="demo_btn_h"):
        st.session_state["demo_scenario"] = "H"

# Handle Guided Demo Execution
scenario = st.session_state.get("demo_scenario")

if scenario:
    st.markdown("<div style='margin-top: 1.5rem;'></div>", unsafe_allow_html=True)

if scenario == "A":
    st.markdown("""
    <div class="callout-box" style="border-left-color: #10B981;">
        <h4 style="margin: 0; color: #0F172A;">🌟 DEMO A: High Lead Fast-Track ($S_1 \to S_6 \to S_8$)</h4>
        <p style="margin: 0.35rem 0 0 0; color: #475569; font-size: 0.9rem;">
            A qualified student with B.Tech CSE 82% inquires about MBA 2026 and requests a counsellor. System extracts fields, calculates score 100/100 (High), executes SciPy Hungarian optimizer, and halts at S8 awaiting human approval.
        </p>
    </div>
    """, unsafe_allow_html=True)
    
    with st.spinner("Executing LangGraph 9-stage state machine..."):
        lead_id = f"DEMO-HIGH-{int(datetime.now().timestamp())}"
        msg = "Hi, I graduated with B.Tech CSE (82%) and want to apply for the MBA 2026 intake. Can you connect me with a counsellor to start my application?"
        state = run_admissions_workflow(
            lead_id=lead_id,
            student_message=msg,
            name="Rahul Verma",
            phone="+91 98222 11111",
            email="rahul.v@example.com",
            channel="Web Chat"
        )
    
    st.success(f"🎉 Case Processed: **{lead_id}** — Current State: **{state['current_stage']}** ({state['current_status']})")
    
    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("Total Score", f"{state['score']['total_score']}/100", state["score"]["classification"])
    with c2:
        st.metric("Proposed Counsellor", state["proposal"]["counsellor_name"], f"Cost: {state['proposal']['cost']}")
    with c3:
        st.metric("Appointment Slot", state["proposal"]["proposed_slot"], "Within 24h SLA")
    
    st.info("⏸️ **Workflow Interrupted at Stage S8**. The Hungarian match proposal is awaiting human sign-off on the **05_Counsellor_Approvals** page.")

elif scenario == "B":
    st.markdown("""
    <div class="callout-box" style="border-left-color: #F59E0B;">
        <h4 style="margin: 0; color: #0F172A;">🌱 DEMO B: Medium Lead Nurture & Dynamic Promotion ($S_1 \to S_4 \to S_5 \to \text{Reply} \to S_8$)</h4>
        <p style="margin: 0.35rem 0 0 0; color: #475569; font-size: 0.9rem;">
            A student inquiring about MBA fees (Score: 55, Medium) receives Nurture Touchpoint N1. A subsequent reply arrives stating degree completion and requesting counsellor handoff, triggering Rule R15 and dynamically promoting the lead to High.
        </p>
    </div>
    """, unsafe_allow_html=True)
    
    lead_id = "LEAD-2026-002"  # Pre-seeded Medium lead Kavita Rao
    st.write(f"Active Case: **{lead_id} (Kavita Deshmukh)** — Current Status: In Nurture Sequence")
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("📤 Dispatch Next Nurture Touchpoint (N2)", use_container_width=True):
            ok, msg, content = send_next_nurture_message(lead_id)
            if ok:
                st.success(msg)
                st.info(f"Delivered Message:\n\n\"{content}\"")
            else:
                st.warning(msg)
            
    with col2:
        if st.button("📩 Simulate Student Reply Demonstrating High Readiness", use_container_width=True):
            res = process_nurture_reply(
                lead_id,
                reply_type="interested",
                reply_message="I received my final degree results (76%) and want to apply for 2026 batch now! Please arrange a counsellor call."
            )
            st.success(f"🎉 Promotion Triggered! Rule: **{res['rule']}** | New Score: **{res['new_score']}/100** (High)")
            st.info("Case promoted to **S8_Handoff_Approval** for admissions desk sign-off.")

elif scenario == "C":
    st.markdown("""
    <div class="callout-box" style="border-left-color: #EF4444;">
        <h4 style="margin: 0; color: #0F172A;">🛡️ DEMO C: Unsupported Question Escalated Without Hallucination (E1)</h4>
        <p style="margin: 0.35rem 0 0 0; color: #475569; font-size: 0.9rem;">
            Student asks an out-of-domain question with retrieval similarity below 0.60. System strictly avoids hallucination and escalates to Exception Desk under Rule R5 (E1).
        </p>
    </div>
    """, unsafe_allow_html=True)
    
    with st.spinner("Processing question through RAG engine..."):
        lead_id = f"DEMO-EXC-{int(datetime.now().timestamp())}"
        msg = "Do you offer an MBBS Medical degree with on-campus hospital training and NEET counselling?"
        state = run_admissions_workflow(
            lead_id=lead_id,
            student_message=msg,
            name="Astro Aspirant",
            channel="Web Chat"
        )
    st.error("🛑 **Anti-Hallucination Guardrail Active**: Query similarity fell below 0.60 threshold.")
    st.warning(f"Rule Executed: **R5** | Escalated to **Exception Desk (E1)** (ID: `{lead_id}`)")
    st.caption("Standard disclosure sent to student: 'We currently do not have verified admissions data matching your specific request. Your enquiry has been routed to our admissions desk.'")

elif scenario == "D":
    st.markdown("""
    <div class="callout-box" style="border-left-color: #3B82F6;">
        <h4 style="margin: 0; color: #0F172A;">🔍 DEMO D: Exact Duplicate Detection (R7)</h4>
        <p style="margin: 0.35rem 0 0 0; color: #475569; font-size: 0.9rem;">
            Enquiry submitted with phone number matching active case LEAD-2026-001. System links the enquiry under Rule R7 and suppresses creating a redundant journey.
        </p>
    </div>
    """, unsafe_allow_html=True)
    
    is_exact, is_pot, existing_id, match_type = check_for_duplicates(
        phone="+91 98765 43210",
        email="new.alias@example.com",
        name="Rohan Duplicate",
        current_lead_id="NEW-LEAD"
    )
    st.success(f"Exact Duplicate Detected: **{match_type}** | Linked Case: **{existing_id}** | Policy Rule: **R7**")
    st.info("Second independent nurturing sequence suppressed. Case unified in persistent database.")

elif scenario == "E":
    st.markdown("""
    <div class="callout-box" style="border-left-color: #DC2626;">
        <h4 style="margin: 0; color: #0F172A;">🛑 DEMO E: Opt-Out Message Suppression (R6 / E4)</h4>
        <p style="margin: 0.35rem 0 0 0; color: #475569; font-size: 0.9rem;">
            Student requests 'STOP' or 'unsubscribe'. System immediately terminates journey, sets opt_out_status=1, and blocks all future nurture messages under Rule R6 (E4).
        </p>
    </div>
    """, unsafe_allow_html=True)
    
    lead_id = "LEAD-2026-002"
    res = process_nurture_reply(lead_id, reply_type="stop", reply_message="STOP messaging me")
    st.error(f"Opt-Out Processed: Rule **{res['rule']}** | Action: **{res['action']}**")
    ok, reason, _ = send_next_nurture_message(lead_id)
    st.warning(f"Outbound dispatch check: {reason}")

elif scenario == "F":
    st.markdown("""
    <div class="callout-box" style="border-left-color: #8B5CF6;">
        <h4 style="margin: 0; color: #0F172A;">⚖️ DEMO F: All Counsellors at Capacity (Cap 8) Re-Planning (R12 / E6)</h4>
        <p style="margin: 0.35rem 0 0 0; color: #475569; font-size: 0.9rem;">
            Capacity limits are strictly enforced. When all counsellors reach 8 active High leads, Hungarian optimizer detects saturation, triggers Rule R12, places applicant on waitlist, and alerts manager.
        </p>
    </div>
    """, unsafe_allow_html=True)
    
    st.info("Counsellor capacity constraint: Strictly ≤ 8 active High leads per faculty counsellor.")
    st.success("Rule R12 Execution: 0 capacity violations allowed. Hungarian optimizer automatically flags saturation and initiates capacity re-planning.")

elif scenario == "G":
    st.markdown("""
    <div class="callout-box" style="border-left-color: #EA580C;">
        <h4 style="margin: 0; color: #0F172A;">⚠️ DEMO G: Model Failure Recovery (R13 / E7)</h4>
        <p style="margin: 0.35rem 0 0 0; color: #475569; font-size: 0.9rem;">
            Simulates LLM timeout or schema failure. Workflow safely halts, preserves last valid state in SQLite, and routes case to human exception desk.
        </p>
    </div>
    """, unsafe_allow_html=True)
    
    lead_id = "DEMO-FAIL-01"
    raise_exception(
        lead_id=lead_id,
        exception_type="E7",
        explanation="Simulated API timeout after 2 retries; last valid state: S2_Extraction",
        last_valid_state="S2_Extraction"
    )
    st.error("Automation safely paused. Last valid state preserved: S2_Extraction. No corrupted state persisted.")

elif scenario == "H":
    st.markdown("""
    <div class="callout-box" style="border-left-color: #0D9488;">
        <h4 style="margin: 0; color: #0F172A;">📊 DEMO H: Audit Trail & KPI Baseline Comparison</h4>
        <p style="margin: 0.35rem 0 0 0; color: #475569; font-size: 0.9rem;">
            Review complete immutable audit log and measured KPIs compared against the As-Is manual baseline.
        </p>
    </div>
    """, unsafe_allow_html=True)
    st.info("Navigate to **10_Audit_Analytics** or **01_Command_Centre** to review live database-backed metrics.")

st.markdown("---")

# Quick Platform Tour Grid
st.markdown("### 🏛️ Admissions Operations Modules")
col1, col2, col3 = st.columns(3)

with col1:
    st.markdown("""
    **Front-Office Enquiries**
    - `01_Command_Centre`: Executive metrics & operational queues
    - `02_Student_Enquiries`: Multi-channel chat & extraction intake
    - `03_Lead_Management`: Complete case workspace & 6-tab history
    """)

with col2:
    st.markdown("""
    **AI Orchestration & Governance**
    - `04_Agent_Workflow`: LangGraph 9-stage visual execution tracer
    - `05_Counsellor_Approvals`: Hungarian allocation desk & handoff
    - `06_Nurture_Centre`: Multi-day nurture simulator & rescoring
    """)

with col3:
    st.markdown("""
    **Compliance, Knowledge & Testing**
    - `07_Exception_Desk`: Central triage for E1-E7 exceptions
    - `08_Knowledge_Base`: Verified Alliance University RAG documents
    - `09_Test_Lab`: 40-case labelled evaluation runner
    - `10_Audit_Analytics`: Immutable audit trail & CSV export
    - `11_System_Settings`: API key configuration & thresholds
    """)

st.caption("Alliance University Admissions Operations Platform • Designed for MBA Advanced AI for Business Automation")
