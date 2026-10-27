"""Lead Management: Searchable enterprise CRM table and deep case workspace."""

import sys
from pathlib import Path
_ROOT_DIR = Path(__file__).resolve().parent.parent
if str(_ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(_ROOT_DIR))


import json
import streamlit as st
import pandas as pd
from src.database import get_db_connection
from src.ui import render_page_header, render_sidebar_info, render_kpi_card, inject_custom_css

st.set_page_config(page_title="Lead Management | Alliance Admissions", layout="wide")
inject_custom_css()
render_sidebar_info()

render_page_header(
    title="Lead Management & Case Workspace",
    subtitle="Enterprise case repository with multi-attribute filtering, complete message histories, 5-criterion scoring breakdowns, and regulatory audit traces.",
    icon="🗂️",
    badge="Admissions CRM Case Registry"
)

conn = get_db_connection()
leads_df = pd.read_sql_query("SELECT * FROM leads ORDER BY created_at DESC;", conn)
conn.close()

if len(leads_df) == 0:
    st.info("No leads found in database. Create a new lead from Student Enquiries or reset demo data in Settings.")
    st.stop()

# Multi-Attribute Filters
st.markdown("#### 🔍 Filter Case Records")
f_col1, f_col2, f_col3, f_col4 = st.columns(4)

with f_col1:
    class_filter = st.multiselect("Classification", ["High", "Medium", "Low", "Uncertain"], default=[])
with f_col2:
    channel_filter = st.multiselect("Channel", leads_df["channel"].dropna().unique().tolist(), default=[])
with f_col3:
    stage_filter = st.multiselect("Stage", leads_df["current_stage"].dropna().unique().tolist(), default=[])
with f_col4:
    search_query = st.text_input("Search Name, Phone, Email, or Lead ID", "")

# Apply Filters
filtered_df = leads_df.copy()
if class_filter:
    filtered_df = filtered_df[filtered_df["classification"].isin(class_filter)]
if channel_filter:
    filtered_df = filtered_df[filtered_df["channel"].isin(channel_filter)]
if stage_filter:
    filtered_df = filtered_df[filtered_df["current_stage"].isin(stage_filter)]
if search_query:
    q = search_query.lower()
    filtered_df = filtered_df[
        filtered_df["name"].str.lower().str.contains(q, na=False) |
        filtered_df["lead_id"].str.lower().str.contains(q, na=False) |
        filtered_df["email"].str.lower().str.contains(q, na=False) |
        filtered_df["phone"].str.lower().str.contains(q, na=False)
    ]

st.markdown(f"**Displaying {len(filtered_df)} of {len(leads_df)} Leads**")

# Display Table
st.dataframe(
    filtered_df[[
        "lead_id", "created_at", "name", "channel", "programme_interest",
        "total_score", "classification", "current_stage", "current_status",
        "assigned_counsellor", "proposed_slot"
    ]],
    use_container_width=True
)

st.download_button(
    "📥 Export Filtered Leads to CSV",
    data=filtered_df.to_csv(index=False).encode("utf-8"),
    file_name=f"alliance_leads_{len(filtered_df)}.csv",
    mime="text/csv"
)

st.markdown("---")

# Deep Case Workspace Inspector
st.markdown("### 🔎 Case Workspace Deep Inspector")

if len(filtered_df) == 0:
    st.warning("No leads match the current filter criteria. Clear filters above to inspect leads.")
    st.stop()

selected_lead_id = st.selectbox(
    "Select Lead Record to Inspect",
    filtered_df["lead_id"].tolist(),
    format_func=lambda x: f"{x} — {filtered_df[filtered_df['lead_id'] == x]['name'].iloc[0]} ({filtered_df[filtered_df['lead_id'] == x]['programme_interest'].iloc[0] or 'General'})"
)

if selected_lead_id:
    lead_row = leads_df[leads_df["lead_id"] == selected_lead_id].iloc[0]
    
    tab_ov, tab_conv, tab_score, tab_trace, tab_app, tab_audit = st.tabs([
        "📋 Overview", "💬 Conversation History", "📊 5-Criterion Score Breakdown",
        "🔄 Workflow Trace", "✍️ Approvals", "📜 Audit History"
    ])

    with tab_ov:
        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown(f"**Lead ID:** `{lead_row['lead_id']}`")
            st.markdown(f"**Name:** {lead_row['name']}")
            st.markdown(f"**Phone:** `{lead_row['phone']}`")
            st.markdown(f"**Email:** `{lead_row['email']}`")
            st.markdown(f"**Channel:** {lead_row['channel']}")

        with c2:
            st.markdown(f"**Programme Interest:** **{lead_row['programme_interest']}**")
            st.markdown(f"**Education:** {lead_row['education']}")
            st.markdown(f"**Work Experience:** {lead_row['work_experience']}")
            st.markdown(f"**Intended Intake:** {lead_row['intended_intake']}")
            st.markdown(f"**Readiness:** {lead_row['application_readiness']}")

        with c3:
            st.markdown(f"**Classification:** `{lead_row['classification']}`")
            st.markdown(f"**Total Score:** `{lead_row['total_score']}/100`")
            st.markdown(f"**Current Stage:** `{lead_row['current_stage']}`")
            st.markdown(f"**Current Status:** `{lead_row['current_status']}`")
            st.markdown(f"**Assigned Counsellor:** {lead_row['assigned_counsellor'] or 'None'}")
            st.markdown(f"**Proposed Slot:** {lead_row['proposed_slot'] or 'None'}")

        if lead_row["escalation_flag"]:
            st.error(f"🚨 Active Escalation: {lead_row['escalation_reason']}")

        st.markdown("#### Initial Student Inquiry")
        st.info(f"\"{lead_row['student_message']}\"")

    with tab_conv:
        st.subheader("Simulated Message Log")
        conn = get_db_connection()
        messages_df = pd.read_sql_query("SELECT * FROM messages WHERE lead_id = ? ORDER BY timestamp ASC;", conn, params=(selected_lead_id,))
        conn.close()

        if len(messages_df) > 0:
            for _, msg in messages_df.iterrows():
                with st.chat_message("user" if msg["direction"] == "incoming" else "assistant"):
                    st.caption(f"{msg['timestamp']} | Channel: {msg['channel']} | Type: {msg['message_type']} | Source: {msg['content_source']}")
                    st.write(msg["content"])
        else:
            st.info("No recorded conversation messages for this lead.")

    with tab_score:
        st.subheader("5-Criterion Deterministic Scoring Breakdown")
        score_json_str = lead_row["score_breakdown_json"]
        if score_json_str and score_json_str != "{}":
            score_data = json.loads(score_json_str)
            
            sc1, sc2, sc3, sc4, sc5 = st.columns(5)
            with sc1:
                render_kpi_card("1. Readiness", f"{score_data.get('readiness_score', 0)}/25", score_data.get("readiness_rationale", "")[:35] + "...", color_accent="#2563EB")
            with sc2:
                render_kpi_card("2. Intent", f"{score_data.get('intent_score', 0)}/25", score_data.get("intent_rationale", "")[:35] + "...", color_accent="#0D9488")
            with sc3:
                render_kpi_card("3. Fit", f"{score_data.get('fit_score', 0)}/20", score_data.get("fit_rationale", "")[:35] + "...", color_accent="#7C3AED")
            with sc4:
                render_kpi_card("4. Eligibility", f"{score_data.get('eligibility_score', 0)}/20", score_data.get("eligibility_rationale", "")[:35] + "...", color_accent="#F59E0B")
            with sc5:
                render_kpi_card("5. Engagement", f"{score_data.get('engagement_score', 0)}/10", score_data.get("engagement_rationale", "")[:35] + "...", color_accent="#10B981")

            st.markdown(f"### Overall Score: `{score_data.get('total_score', 0)}/100` ➔ Classification: `{score_data.get('classification', 'Uncertain')}`")
            if score_data.get("is_uncertain"):
                st.error(f"⚠️ Uncertain Override Reason: {', '.join(score_data.get('uncertain_reasons', []))}")
        else:
            st.info("No score breakdown JSON recorded for this lead.")

    with tab_trace:
        st.subheader("LangGraph Workflow & Policy Trace")
        st.markdown(f"""
        - **Current Stage:** `{lead_row['current_stage']}`
        - **Current Status:** `{lead_row['current_status']}`
        - **Extraction Confidence:** `{lead_row['extraction_confidence']}`
        - **Clarification Attempts:** `{lead_row['clarification_count']}/2`
        - **Nurture Stage:** `{lead_row['nurture_stage'] or 'Not Enrolled'}` (Messages Sent: `{lead_row['nurture_messages_sent']}`)
        - **Opt-Out Status:** `{'Opted Out (Contact Suppressed)' if lead_row['opt_out_status'] else 'Active'}`
        """)

    with tab_app:
        st.subheader("Human-in-the-Loop Approval Decisions")
        conn = get_db_connection()
        apps_df = pd.read_sql_query("SELECT * FROM approvals WHERE lead_id = ? ORDER BY timestamp DESC;", conn, params=(selected_lead_id,))
        conn.close()

        if len(apps_df) > 0:
            st.dataframe(apps_df[["approval_id", "timestamp", "proposed_action", "decision", "approving_person", "comments"]], use_container_width=True)
        else:
            st.info("No approval events recorded for this lead.")

    with tab_audit:
        st.subheader("Immutable Audit Trail")
        conn = get_db_connection()
        lead_audit_df = pd.read_sql_query("SELECT * FROM audit_events WHERE lead_id = ? ORDER BY timestamp DESC;", conn, params=(selected_lead_id,))
        conn.close()

        if len(lead_audit_df) > 0:
            st.dataframe(lead_audit_df[["event_id", "timestamp", "workflow_stage", "rule_id", "action", "autonomy_level", "tool_invoked"]], use_container_width=True)
        else:
            st.info("No audit events recorded for this lead.")
