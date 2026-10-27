"""Student Enquiries: Multi-channel intake and real-time AI qualification console."""

import sys
from pathlib import Path
_ROOT_DIR = Path(__file__).resolve().parent.parent
if str(_ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(_ROOT_DIR))


import streamlit as st
from datetime import datetime
from src.extraction import extract_information
from src.agent_graph import run_admissions_workflow
from src.security import check_for_duplicates, handle_duplicate_enquiry
from src.ui import render_page_header, render_sidebar_info, inject_custom_css

st.set_page_config(page_title="Student Enquiries | Alliance Admissions", layout="wide")
inject_custom_css()
render_sidebar_info()

render_page_header(
    title="Student Enquiry Intake & AI Qualification",
    subtitle="Simulate real-time student conversations across Web Chat, WhatsApp, Email, and Walk-in channels with instant extraction preview.",
    icon="💬",
    badge="Multi-Channel Intake Gateway"
)

# Quick Pre-Fill Templates
st.markdown("#### ⚡ Quick Sample Inquiries")
st.caption("Click any template chip below to instantly populate realistic inquiry scenarios:")

template_cols = st.columns(4)

with template_cols[0]:
    if st.button("🌟 High MBA Lead", use_container_width=True):
        st.session_state["inq_name"] = "Aditi Deshmukh"
        st.session_state["inq_phone"] = "+91 98440 55667"
        st.session_state["inq_email"] = "aditi.d@example.com"
        st.session_state["inq_channel"] = "Web Chat"
        st.session_state["inq_message"] = "Hi! I completed my B.Com with 74% aggregate marks and have 2 years of work experience. I am very interested in applying for the MBA Finance program for 2026. What are the upcoming deadlines and can I speak to an admissions counsellor?"

with template_cols[1]:
    if st.button("🌱 Medium Nurture Lead", use_container_width=True):
        st.session_state["inq_name"] = "Sameer Kulkarni"
        st.session_state["inq_phone"] = "+91 98330 44556"
        st.session_state["inq_email"] = "sameer.k@example.com"
        st.session_state["inq_channel"] = "WhatsApp"
        st.session_state["inq_message"] = "Could you please share the fee structure and semester installment options for the regular MBA program? Graduate in B.Sc."

with template_cols[2]:
    if st.button("🛡️ Out-of-Domain (E1)", use_container_width=True):
        st.session_state["inq_name"] = "Dr. Kiran Medical"
        st.session_state["inq_phone"] = "+91 98111 99887"
        st.session_state["inq_email"] = "kiran.m@example.com"
        st.session_state["inq_channel"] = "Email"
        st.session_state["inq_message"] = "Do you offer an MBBS degree with on-campus hospital clinical rotations and NEET counselling?"

with template_cols[3]:
    if st.button("🔍 Duplicate Contact", use_container_width=True):
        st.session_state["inq_name"] = "Rohan Sharma"
        st.session_state["inq_phone"] = "+91 98765 43210"  # Pre-seeded lead LEAD-2026-001
        st.session_state["inq_email"] = "rohan.sharma@example.com"
        st.session_state["inq_channel"] = "Web Chat"
        st.session_state["inq_message"] = "Following up on my B.Tech application. When will the interview shortlist be released?"

st.markdown("<div style='margin-top: 1rem;'></div>", unsafe_allow_html=True)

col_input, col_preview = st.columns([1.1, 0.9])

with col_input:
    st.subheader("1. Enquiry Submission Form")
    
    with st.form("new_enquiry_form"):
        channel = st.selectbox(
            "Intake Channel",
            ["Web Chat", "WhatsApp", "Email", "Walk-in Desk"],
            index=["Web Chat", "WhatsApp", "Email", "Walk-in Desk"].index(st.session_state.get("inq_channel", "Web Chat"))
        )
        name = st.text_input("Student Name", value=st.session_state.get("inq_name", "Aditi Deshmukh"))
        phone = st.text_input("Phone Number", value=st.session_state.get("inq_phone", "+91 98440 55667"))
        email = st.text_input("Email Address", value=st.session_state.get("inq_email", "aditi.d@example.com"))
        
        default_msg = st.session_state.get(
            "inq_message",
            "Hi! I completed my B.Com with 74% aggregate marks. I am very interested in applying for the MBA Finance program for 2026. What are the upcoming deadlines and can I speak to an admissions counsellor?"
        )
        message = st.text_area("Student Inquiry Message", value=default_msg, height=120)
        
        consent = st.checkbox("Student provided explicit consent for admissions communication (Rule R6 check)", value=True)
        submitted = st.form_submit_button("🚀 Submit & Execute 9-Stage AI Workflow", use_container_width=True)

with col_preview:
    st.subheader("2. Real-Time AI Extraction Preview")
    
    if message:
        extracted = extract_information(message)
        conf_pct = int(extracted.overall_confidence * 100)
        
        st.markdown(f"**Overall Confidence Score:** `{conf_pct}%`")
        st.progress(conf_pct / 100.0)
        
        preview_data = [
            ("Programme Interest", extracted.programme_interest or "Not Stated"),
            ("Education / Degree", extracted.education or "Not Stated"),
            ("Work Experience", extracted.work_experience or "Fresher"),
            ("Intended Intake", extracted.intended_intake or "Not Stated"),
            ("Application Readiness", extracted.application_readiness or "Exploratory"),
            ("Primary Concern", extracted.primary_concern or "General Enquiry"),
            ("Wants Counsellor", "Yes" if extracted.wants_counsellor else "No"),
            ("Detected Message Type", extracted.message_type)
        ]
        
        for k, v in preview_data:
            col_k, col_v = st.columns([1, 1.2])
            with col_k:
                st.caption(k)
            with col_v:
                st.markdown(f"**{v}**")
                
        if extracted.missing_fields:
            st.warning(f"⚠️ Missing Information: {', '.join(extracted.missing_fields)}")
        else:
            st.success("✅ Profile Complete for Deterministic Qualification")

if submitted:
    lead_id = f"LEAD-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    
    # 1. Duplicate check
    is_exact, is_pot, existing_id, match_type = check_for_duplicates(phone, email, name)
    if is_exact:
        success, status_msg, msg_id = handle_duplicate_enquiry(
            existing_lead_id=existing_id,
            incoming_message=message,
            channel=channel,
            name=name,
            phone=phone,
            email=email
        )
        st.warning(f"🛑 Duplicate Enquiry Detected: Matches active case **{existing_id}** ({match_type}).")
        st.success(f"📨 Incoming message successfully threaded into existing case conversation (`{msg_id}`). Lead count preserved under Rule R7.")
        st.info(f"Navigate to **03_Lead_Management** and select `{existing_id}` to review complete unified dossier and conversation history.")
    else:
        with st.spinner("Executing LangGraph 9-stage state machine..."):
            state = run_admissions_workflow(
                lead_id=lead_id,
                student_message=message,
                name=name,
                phone=phone,
                email=email,
                channel=channel
            )
        
        st.success(f"🎉 Case Created & Evaluated: **{lead_id}**")
        
        s_col1, s_col2, s_col3 = st.columns(3)
        with s_col1:
            st.metric("Total Score", f"{state['score']['total_score']}/100", state['score']['classification'])
        with s_col2:
            st.metric("Workflow Stage", state['current_stage'])
        with s_col3:
            st.metric("Status", state['current_status'])
        
        if state.get("requires_approval"):
            st.warning("⚠️ Case paused at **S8: Counsellor Handoff Approval**. Please navigate to **05_Counsellor_Approvals** to confirm handoff.")
        elif state.get("current_stage") == "S7_Nurturing":
            st.info("🌱 Lead enrolled in **Stage N1 Nurture Journey**. Navigate to **06_Nurture_Centre** to view nurture schedule.")
        elif state.get("escalation_flag"):
            st.error(f"🚨 Escalated to Exception Desk: {state.get('escalation_reason')}. Navigate to **07_Exception_Desk**.")
