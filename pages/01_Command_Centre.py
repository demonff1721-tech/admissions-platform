"""Command Centre: Executive KPI dashboard and operational queues."""

import sys
from pathlib import Path
_ROOT_DIR = Path(__file__).resolve().parent.parent
if str(_ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(_ROOT_DIR))


import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from src.database import get_db_connection
from src.ui import render_page_header, render_sidebar_info, render_kpi_card, inject_custom_css

st.set_page_config(page_title="Command Centre | Alliance Admissions", layout="wide")
inject_custom_css()
render_sidebar_info()

render_page_header(
    title="Admissions Command Centre",
    subtitle="Executive pipeline intelligence, real-time workload balancing, and live operational work queues.",
    icon="📊",
    badge="Admissions Operations • Alliance University"
)

# Fetch Real Database Records
conn = get_db_connection()
leads_df = pd.read_sql_query("SELECT * FROM leads ORDER BY created_at DESC;", conn)
approvals_df = pd.read_sql_query("SELECT * FROM approvals ORDER BY timestamp DESC;", conn)
exceptions_df = pd.read_sql_query("SELECT * FROM leads WHERE escalation_flag = 1 ORDER BY updated_at DESC;", conn)
counsellors_df = pd.read_sql_query("SELECT * FROM counsellors;", conn)
audit_df = pd.read_sql_query("SELECT * FROM audit_events ORDER BY timestamp DESC LIMIT 200;", conn)
conn.close()

total_leads = len(leads_df)
high_leads = len(leads_df[leads_df["classification"] == "High"])
med_leads = len(leads_df[leads_df["classification"] == "Medium"])
low_leads = len(leads_df[leads_df["classification"] == "Low"])
uncertain_leads = len(leads_df[leads_df["classification"] == "Uncertain"])
pending_approvals = len(approvals_df[approvals_df["decision"] == "Pending"])
open_exceptions = len(exceptions_df)

# Straight-through processing rate: (Total - Open Exceptions - Pending) / Total
stp_count = total_leads - open_exceptions - pending_approvals
automation_rate = round((stp_count / max(1, total_leads)) * 100.0, 1)

# Top KPI Metric Cards
c1, c2, c3, c4 = st.columns(4)
with c1:
    render_kpi_card("Total Inquiries", str(total_leads), "Persistent records in SQLite", color_accent="#0F172A")
    render_kpi_card("High-Intent Leads", str(high_leads), "Priority Hungarian matching", color_accent="#10B981")

with c2:
    render_kpi_card("Medium-Intent Leads", str(med_leads), "In Nurture Journey (N1–N5)", color_accent="#F59E0B")
    render_kpi_card("Low-Intent Leads", str(low_leads), "Broadcast Information Track", color_accent="#64748B")

with c3:
    render_kpi_card("Pending Approvals", str(pending_approvals), "Awaiting Counsellor Sign-off", color_accent="#8B5CF6")
    render_kpi_card("Open Exceptions", str(open_exceptions), "Escalated E1–E7 Desk Cases", color_accent="#EF4444")

with c4:
    render_kpi_card("Uncertain Cases", str(uncertain_leads), "Confidence < 0.70 Overrides", color_accent="#F97316")
    render_kpi_card("Straight-Through Rate", f"{automation_rate}%", "Target: ≥ 55.0% Automation", color_accent="#0D9488")

st.markdown("---")

# Visual Analytics Tabs
tab_overview, tab_queues, tab_workload = st.tabs(["📈 Pipeline Analytics", "📋 Operational Work Queues", "👨‍🏫 Counsellor Workload"])

with tab_overview:
    col_chart1, col_chart2 = st.columns(2)
    
    with col_chart1:
        st.subheader("Leads by Qualification Category")
        if total_leads > 0:
            fig_class = px.pie(
                leads_df,
                names="classification",
                hole=0.45,
                color="classification",
                color_discrete_map={
                    "High": "#10B981",
                    "Medium": "#F59E0B",
                    "Low": "#64748B",
                    "Uncertain": "#EF4444"
                }
            )
            fig_class.update_traces(textposition='inside', textinfo='percent+label')
            fig_class.update_layout(
                margin=dict(t=15, b=15, l=15, r=15),
                height=320,
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)"
            )
            st.plotly_chart(fig_class, use_container_width=True)
        else:
            st.info("No lead data available.")

    with col_chart2:
        st.subheader("Enquiries by Intake Channel")
        if total_leads > 0:
            channel_counts = leads_df["channel"].value_counts().reset_index()
            channel_counts.columns = ["Channel", "Volume"]
            fig_channel = px.bar(
                channel_counts,
                x="Channel",
                y="Volume",
                color="Channel",
                color_discrete_sequence=["#0A192F", "#0D9488", "#2563EB", "#7C3AED"],
                text="Volume"
            )
            fig_channel.update_traces(textposition='outside')
            fig_channel.update_layout(
                margin=dict(t=15, b=15, l=15, r=15),
                height=320,
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                yaxis=dict(showgrid=True, gridcolor="#E2E8F0")
            )
            st.plotly_chart(fig_channel, use_container_width=True)
        else:
            st.info("No channel data available.")

    col_funnel, col_stages = st.columns(2)
    with col_funnel:
        st.subheader("Workflow Stage Distribution")
        if total_leads > 0:
            stage_counts = leads_df["current_stage"].value_counts().reset_index()
            stage_counts.columns = ["Stage", "Count"]
            fig_stages = px.bar(
                stage_counts,
                x="Count",
                y="Stage",
                orientation="h",
                color_discrete_sequence=["#0D9488"],
                text="Count"
            )
            fig_stages.update_traces(textposition='outside')
            fig_stages.update_layout(
                margin=dict(t=15, b=15, l=15, r=15),
                height=300,
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                xaxis=dict(showgrid=True, gridcolor="#E2E8F0")
            )
            st.plotly_chart(fig_stages, use_container_width=True)

    with col_stages:
        st.subheader("Exception Types Distribution")
        if open_exceptions > 0:
            exc_types = exceptions_df["escalation_reason"].apply(lambda x: str(x)[:2] if x else "E1").value_counts().reset_index()
            exc_types.columns = ["Exception Type", "Count"]
            fig_exc = px.pie(
                exc_types,
                names="Exception Type",
                values="Count",
                color_discrete_sequence=px.colors.sequential.Reds_r,
                hole=0.4
            )
            fig_exc.update_layout(
                margin=dict(t=15, b=15, l=15, r=15),
                height=300,
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)"
            )
            st.plotly_chart(fig_exc, use_container_width=True)
        else:
            st.success("Zero open exceptions. All pipelines operating normally.")

with tab_queues:
    st.subheader("Operational Queues Requiring Attention")
    
    q_sel = st.selectbox("Select Active Queue", [
        "High Leads Awaiting Counsellor Approval",
        "Open Exception Queue",
        "Leads in Multi-Day Nurture",
        "Recent New Inquiries"
    ])

    if q_sel == "High Leads Awaiting Counsellor Approval":
        pending_high = leads_df[(leads_df["classification"] == "High") & (leads_df["current_stage"] == "S8_Handoff_Approval")]
        if len(pending_high) > 0:
            st.dataframe(
                pending_high[["lead_id", "name", "channel", "programme_interest", "total_score", "assigned_counsellor", "proposed_slot", "current_status"]],
                use_container_width=True
            )
            st.info("👉 Navigate to **05_Counsellor_Approvals** to confirm counsellor allocation.")
        else:
            st.success("✅ Zero pending counsellor approvals.")

    elif q_sel == "Open Exception Queue":
        if len(exceptions_df) > 0:
            st.dataframe(
                exceptions_df[["lead_id", "name", "programme_interest", "classification", "escalation_reason", "current_stage", "updated_at"]],
                use_container_width=True
            )
            st.warning("👉 Navigate to **07_Exception_Desk** to resolve exceptions.")
        else:
            st.success("✅ Zero open exceptions.")

    elif q_sel == "Leads in Multi-Day Nurture":
        nurture_leads = leads_df[leads_df["current_stage"] == "S7_Nurturing"]
        if len(nurture_leads) > 0:
            st.dataframe(
                nurture_leads[["lead_id", "name", "programme_interest", "total_score", "nurture_stage", "nurture_messages_sent", "last_contact_at"]],
                use_container_width=True
            )
            st.info("👉 Navigate to **06_Nurture_Centre** to advance simulation.")
        else:
            st.info("No active leads currently in nurture sequence.")

    elif q_sel == "Recent New Inquiries":
        st.dataframe(
            leads_df[["lead_id", "created_at", "name", "channel", "programme_interest", "total_score", "classification", "current_stage", "current_status"]].head(15),
            use_container_width=True
        )

with tab_workload:
    st.subheader("Faculty Counsellor Capacity & Workload")
    st.caption("Maximum Capacity: Strictly ≤ 8 active High leads per counsellor (Hard policy constraint).")

    if len(counsellors_df) > 0:
        counsellors_df["Capacity Available"] = counsellors_df["capacity"] - counsellors_df["active_high_leads"]
        fig_cap = go.Figure(data=[
            go.Bar(name='Active High Leads', x=counsellors_df['name'], y=counsellors_df['active_high_leads'], marker_color='#0D9488'),
            go.Bar(name='Available Bandwidth', x=counsellors_df['name'], y=counsellors_df['Capacity Available'], marker_color='#E2E8F0')
        ])
        fig_cap.update_layout(
            barmode='stack',
            margin=dict(t=20, b=20, l=10, r=10),
            height=320,
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            yaxis=dict(showgrid=True, gridcolor="#E2E8F0")
        )
        st.plotly_chart(fig_cap, use_container_width=True)

        st.dataframe(
            counsellors_df[["counsellor_id", "name", "specialisations", "languages", "active_high_leads", "capacity", "is_available"]],
            use_container_width=True
        )
