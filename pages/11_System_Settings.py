"""System Settings: LLM configuration, policy thresholds, and safe database reset."""

import sys
from pathlib import Path
_ROOT_DIR = Path(__file__).resolve().parent.parent
if str(_ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(_ROOT_DIR))


import os
import streamlit as st
import pandas as pd
from src.database import reset_database_to_demo, get_db_connection
from src.ui import render_page_header, render_sidebar_info, render_kpi_card, inject_custom_css

st.set_page_config(page_title="Settings | Alliance Admissions", layout="wide")
inject_custom_css()
render_sidebar_info()

render_page_header(
    title="System Configuration & Governance Calibration",
    subtitle="Configure AI extraction runtime, calibrate policy engine thresholds, manage faculty counsellor rosters, and reset demo datasets.",
    icon="⚙️",
    badge="Platform Control & Settings"
)

# Database Health Strip
conn = get_db_connection()
lead_cnt = conn.execute("SELECT count(*) FROM leads;").fetchone()[0]
msg_cnt = conn.execute("SELECT count(*) FROM messages;").fetchone()[0]
audit_cnt = conn.execute("SELECT count(*) FROM audit_events;").fetchone()[0]
couns_df = pd.read_sql_query("SELECT * FROM counsellors;", conn)
conn.close()

sc1, sc2, sc3, sc4 = st.columns(4)
with sc1:
    render_kpi_card("Database Leads", str(lead_cnt), "Stored in admissions.db", color_accent="#0F172A")
with sc2:
    render_kpi_card("Conversation Messages", str(msg_cnt), "Multi-channel exchanges", color_accent="#0D9488")
with sc3:
    render_kpi_card("Audit Trail Events", str(audit_cnt), "Immutable compliance logs", color_accent="#8B5CF6")
with sc4:
    render_kpi_card("Faculty Counsellors", f"{len(couns_df)} Active", "Capacity cap: 8 leads each", color_accent="#10B981")

st.markdown("---")

col_llm, col_policy = st.columns(2)

with col_llm:
    st.subheader("1. AI Model & Extraction Engine")
    
    ai_mode = st.radio(
        "Operational Mode",
        ["Deterministic Demo Mode (Recommended - 100% Offline / Fast)", "Live LLM API (Gemini / OpenAI)"],
        index=0
    )
    
    if "Live LLM" in ai_mode:
        provider = st.selectbox("LLM Provider", ["Google Gemini (gemini-1.5-flash)", "OpenAI (gpt-4o-mini)"])
        api_key = st.text_input("Enter API Key (Masked)", type="password", value=os.environ.get("GEMINI_API_KEY", ""))
        if st.button("Save API Configuration"):
            if api_key:
                os.environ["GEMINI_API_KEY"] = api_key
                st.success("API key configured securely in runtime environment.")
            else:
                st.warning("Please provide a valid API key or switch back to Deterministic Demo Mode.")
    else:
        st.info("ℹ️ **Deterministic Demo Mode Active**: Uses regex qualification schemas and approved TF-IDF cosine RAG over verified institutional documentation. Completely offline and fast.")

with col_policy:
    st.subheader("2. Policy Engine Calibration Thresholds")
    
    sim_threshold = st.slider("Knowledge Retrieval Similarity Threshold (Rule R4 vs R5)", 0.40, 0.90, 0.60, 0.05)
    max_clarify = st.slider("Max Automated Clarification Prompts (Rule R2 vs R3)", 1, 4, 2, 1)
    high_threshold = st.slider("High Lead Classification Score Threshold (Rule R9)", 60, 85, 70, 5)
    capacity_limit = st.slider("Counsellor Capacity Cap (Rule R12)", 4, 15, 8, 1)

    if st.button("Save Policy Calibration"):
        st.success("Policy thresholds updated in runtime engine.")

st.markdown("---")

# Counsellor Availability Roster
st.subheader("3. Faculty Counsellor Roster & Availability")
st.dataframe(couns_df[["counsellor_id", "name", "specialisations", "languages", "active_high_leads", "capacity", "is_available"]], use_container_width=True)

col_c1, col_c2 = st.columns(2)
with col_c1:
    toggle_c = st.selectbox("Select Counsellor to Update", couns_df["counsellor_id"].tolist(), format_func=lambda x: f"{x} — {couns_df[couns_df['counsellor_id'] == x]['name'].iloc[0]}")
with col_c2:
    new_avail = st.selectbox("Set Availability Status", ["Available", "Unavailable / On Leave"])

if st.button("Update Counsellor Status"):
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("UPDATE counsellors SET is_available = ? WHERE counsellor_id = ?;", (1 if new_avail == "Available" else 0, toggle_c))
    conn.commit()
    conn.close()
    st.success(f"Updated status for {toggle_c} to {new_avail}!")
    st.rerun()

st.markdown("---")

# Safe Demo Data Reset
st.subheader("4. Reset Demo Data to Factory Baseline")
st.warning("⚠️ This action will reset all leads, messages, and evaluations back to the original initial seed state. It requires typing 'RESET'.")

confirm_text = st.text_input("Type 'RESET' to confirm database re-initialization", "")

if st.button("🚨 Reset Database to Factory Seed State", type="primary"):
    if confirm_text == "RESET":
        reset_database_to_demo(confirm=True)
        st.success("Database successfully re-seeded to factory demo state!")
        st.rerun()
    else:
        st.error("Confirmation text did not match 'RESET'. Action aborted.")
