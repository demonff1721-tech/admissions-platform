"""Knowledge Base: Institutional document repository, RAG search tester, and document verification desk."""

import sys
from pathlib import Path
_ROOT_DIR = Path(__file__).resolve().parent.parent
if str(_ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(_ROOT_DIR))


import streamlit as st
import pandas as pd
from datetime import datetime

from src.database import get_db_connection
from src.knowledge_retrieval import (
    retrieve_from_knowledge_base,
    add_knowledge_document,
    approve_knowledge_document,
    extract_text_from_pdf
)
from src.security import validate_uploaded_file
from src.ui import render_page_header, render_sidebar_info, render_kpi_card, inject_custom_css

st.set_page_config(page_title="Knowledge Base | Alliance Admissions", layout="wide")
inject_custom_css()
render_sidebar_info()

render_page_header(
    title="Verified Institutional Knowledge Base",
    subtitle="Approved Alliance University documentation, strict citation verification, and interactive RAG retrieval threshold tester.",
    icon="📚",
    badge="Institutional Truth Repository"
)

tab_docs, tab_test, tab_upload = st.tabs(["📄 Approved Documents Repository", "🔍 Grounded RAG Search Tester", "📤 Upload & Verify New Document"])

with tab_docs:
    st.subheader("Approved Knowledge Documents (Used by RAG Engine)")
    st.caption("Anti-hallucination policy: Only documents marked Approved (is_approved=1) are accessible to student queries.")

    conn = get_db_connection()
    docs_df = pd.read_sql_query("SELECT * FROM knowledge_documents ORDER BY is_approved DESC, doc_id ASC;", conn)
    conn.close()

    if len(docs_df) > 0:
        # Search & Filter
        d_col1, d_col2 = st.columns([1.2, 0.8])
        with d_col1:
            search_doc = st.text_input("Filter Documents by Title or Keyword", "")
        with d_col2:
            prog_filter = st.selectbox("Filter Programme", ["All Programmes"] + [p for p in docs_df["programme"].unique() if p != "All Programmes"])

        display_docs = docs_df.copy()
        if search_doc:
            display_docs = display_docs[
                display_docs["title"].str.lower().str.contains(search_doc.lower(), na=False) |
                display_docs["approved_content"].str.lower().str.contains(search_doc.lower(), na=False)
            ]
        if prog_filter != "All Programmes":
            display_docs = display_docs[display_docs["programme"] == prog_filter]

        st.dataframe(
            display_docs[["doc_id", "title", "programme", "category", "official_source_url", "last_verified_date", "is_approved"]],
            use_container_width=True
        )

        for _, doc in display_docs.iterrows():
            with st.expander(f"📑 [{doc['doc_id']}] {doc['title']} — {'✅ Approved' if doc['is_approved'] else '⏳ Pending Review'}"):
                st.markdown(f"**Programme:** `{doc['programme']}` | **Category:** `{doc['category']}` | **Verified:** `{doc['last_verified_date']}`")
                st.markdown(f"**Source URL:** [{doc['official_source_url']}]({doc['official_source_url']})")
                st.info(doc["approved_content"])
                
                if not doc["is_approved"]:
                    if st.button(f"✅ Approve Document {doc['doc_id']}", key=f"app_{doc['doc_id']}"):
                        approve_knowledge_document(doc["doc_id"])
                        st.success(f"Document {doc['doc_id']} approved for live RAG retrieval!")
                        st.rerun()

with tab_test:
    st.subheader("Interactive Grounded Retrieval Tester")
    st.caption("Test retrieval scores against the 0.60 similarity threshold and inspect generated citations.")

    col_q, col_thresh = st.columns([1.2, 0.8])
    with col_q:
        test_query = st.text_input("Enter Student Query", value="What is the tuition fee for the regular MBA program?")
        prog_opt = st.selectbox("Programme Scope", ["All Programmes", "MBA", "B.Tech", "Law", "BBA"])
    with col_thresh:
        thresh_val = st.slider("Similarity Threshold ($R_4$ vs $R_5$)", min_value=0.30, max_value=0.90, value=0.60, step=0.05)

    if st.button("🔍 Execute Knowledge Retrieval", use_container_width=True):
        res = retrieve_from_knowledge_base(
            query=test_query,
            threshold=thresh_val,
            programme_filter=None if prog_opt == "All Programmes" else prog_opt
        )

        sim_score = res["similarity"]
        st.markdown(f"**Measured Similarity:** `{sim_score:.2f}` (Threshold: `{thresh_val:.2f}`)")
        st.progress(min(1.0, max(0.0, sim_score)))

        if res["found"]:
            st.success(f"✅ **Matched Approved Document with Similarity: {sim_score:.2f}** (Threshold: {thresh_val:.2f})")
            st.markdown("#### 📜 Grounded Answer Generated (Rule R4):")
            st.markdown(f"""
            <div class="callout-box" style="border-left-color: #10B981;">
                {res['grounded_answer']}
            </div>
            """, unsafe_allow_html=True)
        else:
            st.error(f"🛑 **Similarity ({sim_score:.2f}) Below Anti-Hallucination Threshold ({thresh_val:.2f})**")
            st.warning(f"**Anti-Hallucination Barrier Active (Rule R5 / E1):** No speculative answer generated. Escalated to Admissions Desk.")

with tab_upload:
    st.subheader("Add or Upload Institutional Knowledge Document")
    st.caption("Newly uploaded documents enter 'Pending Review' state until explicitly verified and approved.")

    with st.form("upload_kb_form"):
        doc_id = st.text_input("Document ID", f"KB_DOC_{datetime.now().strftime('%Y%m%d%H%M')}")
        title = st.text_input("Document Title", "Alliance University International Hostel Policy 2026")
        prog = st.selectbox("Target Programme", ["All Programmes", "MBA", "B.Tech", "Law", "BBA"])
        cat = st.selectbox("Category", ["Fees", "Eligibility", "Programmes", "Placements", "Application Steps", "Hostel & Facilities"])
        source_url = st.text_input("Verified Public Source URL", "https://www.alliance.edu.in/hostel-policy")
        content = st.text_area("Approved Document Content", "All international hostel rooms are twin-sharing with attached bathrooms and meal plans included.", height=120)
        uploaded_file = st.file_uploader("Or Upload Document (PDF, DOCX, TXT, CSV)", type=["pdf", "docx", "txt", "csv"])
        
        submit_doc = st.form_submit_button("📤 Submit for Verification & Approval", use_container_width=True)

    if submit_doc:
        final_content = content.strip()
        if uploaded_file:
            bytes_data = uploaded_file.read()
            valid, msg = validate_uploaded_file(uploaded_file.name, bytes_data)
            if not valid:
                st.error(f"❌ Upload validation failed: {msg}")
                st.stop()
            
            ext = uploaded_file.name.lower().split(".")[-1]
            if ext == "pdf":
                success, extracted_text, meta = extract_text_from_pdf(bytes_data)
                if not success:
                    st.error(f"❌ PDF Text Extraction Failed: {extracted_text}")
                    st.stop()
                st.info(f"📄 Successfully extracted text from '{uploaded_file.name}' ({meta['character_count']} characters, {meta['word_count']} words, {meta['page_count']} pages).")
                final_content = f"{final_content}\n\n{extracted_text}".strip() if final_content else extracted_text
            elif ext in ["txt", "csv"]:
                extracted_text = bytes_data.decode("utf-8", errors="replace").strip()
                if not extracted_text:
                    st.error("❌ Uploaded file is empty.")
                    st.stop()
                st.info(f"📄 Successfully extracted {len(extracted_text)} characters from '{uploaded_file.name}'.")
                final_content = f"{final_content}\n\n{extracted_text}".strip() if final_content else extracted_text
            elif ext == "docx":
                st.warning("⚠️ Direct text extraction from DOCX is not supported in this runtime environment. Please upload as PDF or TXT.")
                st.stop()

        if not final_content:
            st.error("❌ Document content cannot be empty. Please provide text or upload a valid document.")
            st.stop()

        add_knowledge_document(
            doc_id=doc_id,
            title=title,
            programme=prog,
            category=cat,
            content=final_content,
            source_url=source_url,
            verified_date=datetime.now().strftime("%Y-%m-%d"),
            is_approved=False
        )
        st.success(f"Document **{doc_id}** submitted! Currently pending approval in the repository.")
        st.rerun()
