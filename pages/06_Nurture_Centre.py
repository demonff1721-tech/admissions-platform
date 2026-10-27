"""Nurture Centre: Multi-day simulated nurture journey and dynamic rescoring console."""

import sys
from pathlib import Path
_ROOT_DIR = Path(__file__).resolve().parent.parent
if str(_ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(_ROOT_DIR))


import streamlit as st
import pandas as pd
from datetime import datetime

from src.database import get_db_connection
from src.nurture import send_next_nurture_message, process_nurture_reply, NURTURE_STAGES
from src.ui import render_page_header, render_sidebar_info, render_kpi_card, inject_custom_css

st.set_page_config(page_title="Nurture Centre | Alliance Admissions", layout="wide")
inject_custom_css()
render_sidebar_info()

render_page_header(
    title="Multi-Day Nurturing Simulator",
    subtitle="Automated staged nurturing journey (N1 to N5) with simulated date advancement, student reply classification, and dynamic rescoring.",
    icon="🌱",
    badge="Admissions Nurture Automation"
)

conn = get_db_connection()
nurture_leads_df = pd.read_sql_query("""
SELECT * FROM leads 
WHERE current_stage = 'S7_Nurturing'
ORDER BY updated_at DESC;
""", conn)
conn.close()

# Overview of Nurture Journey Stages
st.markdown("### 🗺️ Nurture Touchpoint Sequence (Day 0 to Day 14)")
n_cols = st.columns(5)
for i, stage_info in enumerate(NURTURE_STAGES):
    with n_cols[i]:
        render_kpi_card(f"Touchpoint N{i+1}", f"Day {stage_info['day']}", stage_info["title"], color_accent="#0D9488")

st.markdown("---")

if len(nurture_leads_df) == 0:
    st.info("ℹ️ No active leads currently in nurture sequence. Submit a medium-intent inquiry or run **DEMO B** on the main dashboard.")
    st.stop()

st.subheader(f"Active Leads in Nurture Journey ({len(nurture_leads_df)})")

selected_lead_id = st.selectbox(
    "Select Lead in Nurture",
    nurture_leads_df["lead_id"].tolist(),
    format_func=lambda x: f"{x} — {nurture_leads_df[nurture_leads_df['lead_id'] == x]['name'].iloc[0]} (Stage: {nurture_leads_df[nurture_leads_df['lead_id'] == x]['nurture_stage'].iloc[0] or 'N1_Day0'})"
)

lead_row = nurture_leads_df[nurture_leads_df["lead_id"] == selected_lead_id].iloc[0]

col_progress, col_actions = st.columns([1.1, 0.9])

with col_progress:
    st.markdown("#### 📋 Lead Status & Nurture Progress")
    st.markdown(f"""
    - **Lead ID:** `{lead_row['lead_id']}`
    - **Student Name:** **{lead_row['name']}**
    - **Programme Interest:** {lead_row['programme_interest']}
    - **Current Score:** `{lead_row['total_score']}/100` ({lead_row['classification']})
    - **Current Touchpoint:** `{lead_row['nurture_stage'] or 'N1_Day0'}`
    - **Messages Delivered:** `{lead_row['nurture_messages_sent']}/5 touchpoints`
    - **Last Contacted:** `{lead_row['last_contact_at'] or 'None'}`
    """)

    # Visual Progress Indicator
    sent_cnt = lead_row['nurture_messages_sent'] or 0
    st.progress(min(1.0, sent_cnt / 5.0))

    # Nurture dispatch control
    if st.button("⏩ Advance Simulated Day & Dispatch Next Touchpoint", use_container_width=True):
        ok, msg, content = send_next_nurture_message(selected_lead_id)
        if ok:
            st.success(f"Dispatched: {msg}")
            st.info(f"Delivered Outgoing Message:\n\n\"{content}\"")
            st.rerun()
        else:
            st.warning(msg)

with col_actions:
    st.markdown("#### 💬 Simulate Incoming Student Reply")
    st.caption("Replies trigger dynamic re-extraction, re-scoring, and policy rule re-evaluation.")

    reply_type = st.selectbox(
        "Reply Classification",
        ["interested", "question", "not_now", "stop"],
        format_func=lambda x: {
            "interested": "🌟 Interested / Ready to Apply (Triggers R15 Promotion)",
            "question": "❓ Factual Admissions Question (Triggers R4 RAG)",
            "not_now": "⏳ Undecided / Later Intake",
            "stop": "🛑 Opt-Out Request (Triggers R6 Suppression)"
        }[x]
    )

    default_msgs = {
        "interested": "I received my final degree results (78%) and want to apply for 2026 intake immediately! Please schedule a counsellor call.",
        "question": "Could you provide details about the campus placement percentage and average salary?",
        "not_now": "I am still discussing with my family, will decide next month.",
        "stop": "Please STOP sending me messages, remove my phone number."
    }

    # Dynamically keyed text area to prevent Streamlit state sticking glitch
    reply_text = st.text_area(
        "Simulated Student Message",
        value=default_msgs[reply_type],
        height=100,
        key=f"sim_reply_txt_{reply_type}"
    )

    if st.button("📩 Process Simulated Reply", use_container_width=True):
        res = process_nurture_reply(selected_lead_id, reply_type, reply_text)
        if res["success"]:
            if res.get("promoted"):
                st.success(f"🎉 **Lead Promoted to High!** Rule: `{res['rule']}` | New Score: `{res['new_score']}/100`")
                st.info("Lead transitioned to **S8_Handoff_Approval**. Navigate to **05_Counsellor_Approvals** to confirm handoff.")
            elif res.get("action") == "Opted Out":
                st.error(f"🛑 Student opted out under Rule `{res['rule']}`. All subsequent communication suppressed.")
            else:
                st.info(f"Reply recorded under Rule `{res['rule']}`.")
            st.rerun()
        else:
            st.error(res.get("error"))

st.markdown("---")

# Message conversation history
st.subheader("📜 Complete Conversation Log for this Case")
conn = get_db_connection()
msgs_df = pd.read_sql_query("SELECT * FROM messages WHERE lead_id = ? ORDER BY timestamp ASC;", conn, params=(selected_lead_id,))
conn.close()

if len(msgs_df) > 0:
    for _, msg in msgs_df.iterrows():
        with st.chat_message("user" if msg["direction"] == "incoming" else "assistant"):
            st.caption(f"{msg['timestamp']} | Channel: {msg['channel']} | Type: {msg['message_type']}")
            st.write(msg["content"])
else:
    st.info("No recorded messages for this case yet.")
