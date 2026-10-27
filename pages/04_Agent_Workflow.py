"""Agent Workflow: Interactive LangGraph state machine visualizer and stage stepper."""

import sys
from pathlib import Path
_ROOT_DIR = Path(__file__).resolve().parent.parent
if str(_ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(_ROOT_DIR))


import json
import streamlit as st
import pandas as pd
from datetime import datetime
from src.agent_graph import run_admissions_workflow
from src.database import get_db_connection
from src.ui import render_page_header, render_sidebar_info, render_kpi_card, inject_custom_css

st.set_page_config(page_title="Agent Workflow | Alliance Admissions", layout="wide")
inject_custom_css()
render_sidebar_info()

render_page_header(
    title="Agentic AI Workflow Orchestrator",
    subtitle="Stateful LangGraph architecture with checkpointing, deterministic policy routing, and human-in-the-loop interrupt gates.",
    icon="🔄",
    badge="LangGraph Execution Visualizer"
)

# Visual Workflow Blueprint
st.markdown("### 🗺️ 9-Stage Architecture Blueprint")

st.markdown("""
```mermaid
graph LR
    S1["S1: Intake & Trigger"] --> S2["S2: Field Extraction"]
    S2 --> S3["S3: Grounded RAG"]
    S3 --> S4["S4: Duplicate Check"]
    S4 --> S5["S5: 5-Criterion Rubric"]
    S5 --> S6["S6: Policy & Allocation"]
    S6 -->|High ≥ 70| S8["S8: Counsellor Approval"]
    S6 -->|Med 40–69| S7["S7: Multi-Day Nurture"]
    S6 -->|Low < 40| S7Low["Low-Touch Info Track"]
    S3 -->|Similarity < 0.60| ExcDesk["Exception Desk E1"]
    S7 -->|Promotion Reply| S8
    S8 -->|Counsellor Sign-off| Outcome["Recorded Outcome"]
```
""")

st.markdown("---")

st.subheader("🧪 Interactive Workflow Runner & State Inspector")
st.caption("Execute an inquiry through the state machine and inspect intermediate state transitions at each checkpoint.")

# Quick Sample Scenario Buttons
st.markdown("**Quick Preset Inquiries:**")
preset_cols = st.columns(4)

with preset_cols[0]:
    if st.button("🌟 Qualified MBA Lead", use_container_width=True):
        st.session_state["wf_name"] = "Vikrant Malhotra"
        st.session_state["wf_channel"] = "Web Chat"
        st.session_state["wf_msg"] = "Hello, I completed B.Tech with 80% aggregate and got 85 percentile in CAT 2025. I want to apply for the MBA Marketing program for July 2026 intake. Can you arrange a counsellor call to complete my form?"

with preset_cols[1]:
    if st.button("🌱 Medium BBA Inquiry", use_container_width=True):
        st.session_state["wf_name"] = "Pooja Hegde"
        st.session_state["wf_channel"] = "WhatsApp"
        st.session_state["wf_msg"] = "What are the semester installments and hostel fees for the Bachelor of Business Administration (BBA) course? Currently awaiting 12th standard results."

with preset_cols[2]:
    if st.button("📊 Placements Question", use_container_width=True):
        st.session_state["wf_name"] = "Abhishek Sen"
        st.session_state["wf_channel"] = "Email"
        st.session_state["wf_msg"] = "What was the highest international package and average placement package for the MBA batch last year? Which companies recruit on campus?"

with preset_cols[3]:
    if st.button("🛡️ Out-of-Domain (E1)", use_container_width=True):
        st.session_state["wf_name"] = "Dr. S. Nair"
        st.session_state["wf_channel"] = "Web Chat"
        st.session_state["wf_msg"] = "Does Alliance University offer a degree in Aeronautical Submarine Engineering with NASA funding?"

with st.form("workflow_exec_form"):
    c_name, c_channel = st.columns(2)
    with c_name:
        test_name = st.text_input("Candidate Name", st.session_state.get("wf_name", "Vikrant Malhotra"))
    with c_channel:
        test_channel = st.selectbox(
            "Channel",
            ["Web Chat", "WhatsApp", "Email", "Walk-in Desk"],
            index=["Web Chat", "WhatsApp", "Email", "Walk-in Desk"].index(st.session_state.get("wf_channel", "Web Chat"))
        )
        
    test_msg = st.text_area(
        "Candidate Inquiry Message",
        st.session_state.get(
            "wf_msg",
            "Hello, I completed B.Tech with 80% aggregate and got 85 percentile in CAT 2025. I want to apply for the MBA Marketing program for July 2026 intake. Can you arrange a counsellor call to complete my form?"
        ),
        height=100
    )
    run_btn = st.form_submit_button("▶️ Execute Full LangGraph Pipeline", use_container_width=True)

if run_btn:
    lead_id = f"WF-LEAD-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    
    with st.spinner("Invoking LangGraph Compiled Graph..."):
        final_state = run_admissions_workflow(
            lead_id=lead_id,
            student_message=test_msg,
            name=test_name,
            channel=test_channel
        )
    
    st.success(f"🎉 Graph Execution Complete! Terminal Stage: **{final_state['current_stage']}** ({final_state['current_status']})")
    
    # State Inspection Stepper
    stages = [
        ("S1: Case Creation & AI Transparency Disclosure", "S1_Trigger", {"lead_id": lead_id, "channel": test_channel, "ai_disclosure": "Sent", "status": "Registered"}),
        ("S2: Structured Information Extraction", "S2_Extraction", final_state.get("extracted")),
        ("S3: Grounded Knowledge Retrieval (RAG)", "S3_RAG", final_state.get("rag_result")),
        ("S4: Duplicate & Opt-Out Validation", "S4_Validation", {"duplicates_checked": True, "contact_permitted": True}),
        ("S5: Deterministic Scoring (5 Criteria Rubric)", "S5_Scoring", final_state.get("score")),
        ("S6: Policy Evaluation & Hungarian Allocation", "S6_Allocation", final_state.get("proposal"))
    ]
    
    for title, code, payload in stages:
        with st.expander(f"📍 {title}", expanded=(code in ["S5_Scoring", "S6_Allocation"])):
            st.json(payload or {"status": "Completed"})
            
    if final_state.get("requires_approval"):
        st.warning("⏸️ **Workflow Interrupted at Stage S8**: High lead requires human counsellor allocation sign-off. Navigate to **05_Counsellor_Approvals**.")
    elif final_state.get("escalation_flag"):
        st.error(f"🚨 **Escalated to Exception Desk**: {final_state.get('escalation_reason')}. Navigate to **07_Exception_Desk**.")
    elif final_state.get("current_stage") == "S7_Nurturing":
        st.info("🌱 Lead enrolled in **Stage N1 Nurture Journey**. Navigate to **06_Nurture_Centre**.")
