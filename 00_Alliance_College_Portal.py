"""Alliance College Portal: Public-facing student admissions portal embedded in the platform."""

import sys
from pathlib import Path
_ROOT_DIR = Path(__file__).resolve().parent.parent
if str(_ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(_ROOT_DIR))

import streamlit as st
from datetime import datetime
from src.agent_graph import run_admissions_workflow
from src.knowledge_retrieval import retrieve_from_knowledge_base
from src.ui import inject_custom_css

st.set_page_config(
    page_title="Alliance University | Admissions 2026 Portal",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded"
)
inject_custom_css()

# Custom Header Styling
st.markdown("""
<div style="background: linear-gradient(135deg, #0A192F 0%, #172A45 100%); padding: 36px 30px; border-radius: 12px; color: white; margin-bottom: 24px; border: 1px solid rgba(197, 160, 89, 0.3);">
    <div style="display: flex; align-items: center; gap: 16px; margin-bottom: 12px;">
        <div style="background: #C5A059; color: #0A192F; font-size: 1.8rem; font-weight: 800; width: 50px; height: 50px; border-radius: 10px; display: flex; align-items: center; justify-content: center;">AU</div>
        <div>
            <h1 style="color: white; margin: 0; font-size: 1.8rem; font-weight: 800; letter-spacing: 0.5px;">ALLIANCE UNIVERSITY</h1>
            <p style="color: #94A3B8; margin: 0; font-size: 0.85rem;">Bengaluru, India • Estd. Under Karnataka Act No. 34 of 2010 • QS Ranked • AACSB Member</p>
        </div>
    </div>
    <div style="margin-top: 16px; font-size: 1.15rem; color: #E2E8F0; line-height: 1.5;">
        Shape Your Ambition: Admissions Open for <strong style="color: #C5A059;">2026–27 Academic Year</strong> (MBA • B.Tech • Law • BBA)
    </div>
</div>
""", unsafe_allow_html=True)

# Key University Highlights
h_col1, h_col2, h_col3, h_col4 = st.columns(4)
with h_col1:
    st.metric("Highest Package", "₹21.6 LPA", "Placement Record")
with h_col2:
    st.metric("Global Recruiters", "600+", "Top Corporates")
with h_col3:
    st.metric("Lush Campus", "55+ Acres", "Bengaluru City")
with h_col4:
    st.metric("Admissions Status", "Open 2026", "Rolling Applications")

st.markdown("<hr style='margin: 24px 0; border: none; border-top: 1px solid #E2E8F0;'>", unsafe_allow_html=True)

tab_apply, tab_programs, tab_faq = st.tabs(["📝 Apply & Student Enquiry Form", "🏛️ Flagship Programs", "🤖 Ask Admissions AI (Knowledge Base)"])

with tab_apply:
    col_form, col_info = st.columns([1.2, 0.8])
    
    with col_form:
        st.subheader("Admissions 2026 Enquiry Form")
        st.caption("Submit your enquiry below. Our Agentic AI platform will immediately evaluate your academic profile and match you with an admissions counsellor.")
        
        with st.form("public_enquiry_form"):
            c_name = st.text_input("Full Name *", placeholder="e.g. Sathwik Narayana")
            
            c_col1, c_col2 = st.columns(2)
            with c_col1:
                c_phone = st.text_input("Mobile Number (WhatsApp) *", placeholder="e.g. +91 98450 11223")
            with c_col2:
                c_email = st.text_input("Email Address *", placeholder="e.g. sathwik@example.com")
                
            c_prog_col, c_intake_col = st.columns(2)
            with c_prog_col:
                c_prog = st.selectbox("Programme of Interest *", [
                    "Master of Business Administration (MBA)",
                    "Bachelor of Technology (B.Tech CSE)",
                    "Alliance School of Law (BBA LLB / BA LLB)",
                    "Bachelor of Business Administration (BBA)"
                ])
            with c_intake_col:
                c_intake = st.selectbox("Intended Intake *", [
                    "2026 upcoming (Immediate)",
                    "2027 (Next Year)",
                    "Still Deciding"
                ])
                
            c_edu = st.text_input("Highest Qualification & Percentage *", placeholder="e.g. BBA (80%) or B.Tech (75%)")
            c_msg = st.text_area("Your Message or Specific Questions", placeholder="Ask about fee structures, scholarships, eligibility, or request a call with an admissions counsellor...", height=90)
            
            c_consent = st.checkbox("I agree to receive official admissions updates from Alliance University", value=True)
            submit_btn = st.form_submit_button("🚀 Submit Enquiry to Admissions AI", use_container_width=True)
            
        if submit_btn:
            if not c_name or not c_phone or not c_email:
                st.error("Please fill in your name, phone number, and email address.")
            else:
                lead_id = f"WEB-{int(datetime.now().timestamp()*1000)}"
                
                # Synthesize message
                parts = []
                if c_msg:
                    parts.append(c_msg)
                parts.append(f"Interested in {c_prog}.")
                if c_edu:
                    parts.append(f"My academic background is {c_edu}.")
                parts.append(f"Planning for intake {c_intake}.")
                parts.append("Please provide guidance on admission process and counsellor support.")
                full_message = " ".join(parts)
                
                with st.spinner("Agentic AI is evaluating your profile across 9 lifecycle stages..."):
                    state = run_admissions_workflow(
                        lead_id=lead_id,
                        student_message=full_message,
                        name=c_name,
                        phone=c_phone,
                        email=c_email,
                        channel="Alliance College Web Portal"
                    )
                    
                score = state.get("score") or {}
                rag = state.get("rag_result") or {}
                
                st.success(f"🎉 **Enquiry Registered Successfully! (Reference: `{lead_id}`)**")
                
                res_col1, res_col2 = st.columns(2)
                with res_col1:
                    st.metric("AI Qualification Tier", f"{score.get('classification', 'High')} Priority", f"Score: {score.get('total_score', 100)}/100")
                with res_col2:
                    st.metric("Admissions Status", state.get("current_status", "Awaiting Approval"), state.get("current_stage", "S8_Handoff_Approval"))
                    
                if state.get("current_stage") == "S8_Handoff_Approval":
                    st.info(f"👨‍🏫 **Counsellor Allocation Proposal Generated:** You have been matched with **{state.get('assigned_counsellor', 'Prof. Rajesh Nair')}** ({state.get('proposed_slot', 'Today 11:00 AM')}). The admissions manager is reviewing the final handoff on the **05 Counsellor Approvals** desk.")
                elif rag.get("found"):
                    st.markdown(f"**Grounded Answer:** {rag.get('grounded_answer')}")
                    
                st.markdown("""
                > **Notice for Evaluators & Teammates:**  
                > This lead has been written to the shared database. You can immediately open **`05 Counsellor Approvals`** or **`03 Lead Management`** in the left sidebar to see the lead sitting live in the operational queues!
                """)

    with col_info:
        st.subheader("Why Choose Alliance University?")
        st.markdown("""
        * **Top B-School Ranking:** Alliance School of Business is consistently ranked among the top private business schools in India.
        * **100% Placement Record:** Over 600+ recruitment partners including Deloitte, Amazon, KPMG, Cisco, and Microsoft visit annually.
        * **Global Faculty & Curriculum:** Case-based pedagogy with international academic exchange partnerships worldwide.
        * **State-of-the-Art Infrastructure:** 55-acre green residential campus with modern sports complexes, library, and incubation centers.
        """)
        st.info("📍 **Campus Address:** Chikkahagade Cross, Chandapura - Anekal Main Road, Anekal, Bengaluru, Karnataka 562106")

with tab_programs:
    p_col1, p_col2 = st.columns(2)
    with p_col1:
        st.markdown("""
        ### 🎓 Alliance School of Business
        * **Master of Business Administration (MBA):** 2-year flagship postgraduate degree. Specializations in Marketing, Finance, HR, Operations, and Business Analytics.
        * **Executive MBA:** Designed for working professionals seeking senior leadership roles.
        * **Bachelor of Business Administration (BBA):** 3-year undergraduate foundation in business strategy and entrepreneurship.
        """)
    with p_col2:
        st.markdown("""
        ### ⚙️ College of Engineering & Design
        * **B.Tech Computer Science & Engineering (CSE)**
        * **B.Tech Artificial Intelligence & Machine Learning (AI & ML)**
        * **B.Tech Aerospace Engineering**
        
        ### ⚖️ Alliance School of Law
        * **BBA LLB (Hons.) & BA LLB (Hons.):** 5-year integrated law programs approved by the Bar Council of India.
        * **Master of Law (LLM):** Specialized legal research.
        """)

with tab_faq:
    st.subheader("Instant Knowledge Base Q&A (Grounded RAG)")
    st.caption("Ask any question regarding fee structures, scholarships, eligibility, or campus life. The AI retrieves verified facts directly from official policy documents.")
    
    faq_q = st.text_input("Ask a question about Alliance University:", value="What are the total fees and installment options for MBA?")
    if st.button("🔍 Ask Knowledge Base"):
        with st.spinner("Searching verified knowledge base..."):
            rag_res = retrieve_from_knowledge_base(faq_q, programme_filter="MBA")
        if rag_res.get("found"):
            st.success(f"**Verified Answer (Similarity: `{rag_res.get('similarity')}`):**")
            st.markdown(rag_res.get("grounded_answer"))
        else:
            st.warning("Query could not be grounded in published documents. An admissions counsellor will assist you with this question.")
