"""Persistent SQLite database manager for leads, messages, approvals, audit events, and counsellors."""

import os
import json
import sqlite3
from datetime import datetime
from typing import Dict, Any, List, Optional
from pathlib import Path


DEFAULT_DB_DIR = Path(__file__).resolve().parent.parent / "data"
DEFAULT_DB_PATH = DEFAULT_DB_DIR / "admissions.db"


def get_db_connection(db_path: Optional[str] = None) -> sqlite3.Connection:
    """Creates a sqlite3 connection with dict-like row access and WAL mode."""
    target_path = Path(db_path) if db_path else Path(DEFAULT_DB_PATH)
    target_path.parent.mkdir(parents=True, exist_ok=True)
    
    conn = sqlite3.connect(str(target_path), timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn


def init_database(db_path: Optional[str] = None):
    """Initializes tables and indices in SQLite if they do not exist."""
    conn = get_db_connection(db_path)
    cur = conn.cursor()

    # 1. Leads Table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS leads (
        lead_id TEXT PRIMARY KEY,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        channel TEXT DEFAULT 'Web Chat',
        student_message TEXT NOT NULL,
        name TEXT NOT NULL,
        phone TEXT,
        email TEXT,
        consent_status INTEGER DEFAULT 1,
        opt_out_status INTEGER DEFAULT 0,
        programme_interest TEXT,
        education TEXT,
        work_experience TEXT,
        intended_intake TEXT,
        application_readiness TEXT,
        intent TEXT,
        extracted_fields_json TEXT DEFAULT '{}',
        extraction_confidence REAL DEFAULT 1.0,
        clarification_count INTEGER DEFAULT 0,
        score_breakdown_json TEXT DEFAULT '{}',
        total_score INTEGER DEFAULT 0,
        eligibility_score INTEGER DEFAULT 0,
        classification TEXT DEFAULT 'Uncertain',
        current_stage TEXT DEFAULT 'S1_Trigger',
        current_status TEXT DEFAULT 'New',
        escalation_flag INTEGER DEFAULT 0,
        escalation_reason TEXT,
        assigned_counsellor TEXT,
        proposed_slot TEXT,
        approved_by TEXT,
        nurture_stage TEXT,
        nurture_messages_sent INTEGER DEFAULT 0,
        last_contact_at TEXT,
        duplicate_of TEXT,
        case_summary TEXT
    );
    """)

    # 2. Messages Table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS messages (
        message_id TEXT PRIMARY KEY,
        lead_id TEXT NOT NULL,
        timestamp TEXT NOT NULL,
        direction TEXT NOT NULL, -- incoming / outgoing
        channel TEXT DEFAULT 'Web Chat',
        message_type TEXT NOT NULL, -- greeting, clarification, answer, nurture, handoff, disclosure
        content TEXT NOT NULL,
        content_source TEXT, -- knowledge_base, policy, template, student
        delivery_status TEXT DEFAULT 'Delivered',
        FOREIGN KEY(lead_id) REFERENCES leads(lead_id) ON DELETE CASCADE
    );
    """)

    # 3. Approvals Table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS approvals (
        approval_id TEXT PRIMARY KEY,
        lead_id TEXT NOT NULL,
        proposed_action TEXT NOT NULL,
        decision TEXT DEFAULT 'Pending', -- Pending, Approved, Rejected
        approving_person TEXT,
        comments TEXT,
        timestamp TEXT NOT NULL,
        previous_state TEXT,
        updated_state TEXT,
        FOREIGN KEY(lead_id) REFERENCES leads(lead_id) ON DELETE CASCADE
    );
    """)

    # 4. Audit Events Table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS audit_events (
        event_id TEXT PRIMARY KEY,
        timestamp TEXT NOT NULL,
        lead_id TEXT NOT NULL,
        workflow_stage TEXT NOT NULL,
        rule_id TEXT,
        action TEXT NOT NULL,
        inputs TEXT,
        output TEXT,
        tool_invoked TEXT,
        autonomy_level TEXT NOT NULL,
        approval_ref TEXT,
        error_details TEXT
    );
    """)

    # 5. Counsellors Table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS counsellors (
        counsellor_id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        specialisations TEXT NOT NULL, -- JSON list
        languages TEXT NOT NULL, -- JSON list
        active_high_leads INTEGER DEFAULT 0,
        capacity INTEGER DEFAULT 8,
        available_slots TEXT NOT NULL, -- JSON list
        is_available INTEGER DEFAULT 1
    );
    """)

    # 6. Knowledge Documents Table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS knowledge_documents (
        doc_id TEXT PRIMARY KEY,
        title TEXT NOT NULL,
        programme TEXT NOT NULL,
        category TEXT NOT NULL,
        approved_content TEXT NOT NULL,
        official_source_url TEXT NOT NULL,
        retrieval_metadata TEXT DEFAULT '{}',
        collection_date TEXT NOT NULL,
        last_verified_date TEXT NOT NULL,
        is_approved INTEGER DEFAULT 1
    );
    """)

    # 7. Evaluation Runs Table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS evaluation_runs (
        run_id TEXT PRIMARY KEY,
        timestamp TEXT NOT NULL,
        case_id TEXT NOT NULL,
        expected_outcome TEXT NOT NULL,
        actual_outcome TEXT NOT NULL,
        extracted_fields TEXT,
        scores TEXT,
        routing_correctness INTEGER DEFAULT 1,
        exception_correctness INTEGER DEFAULT 1,
        processing_time_ms REAL DEFAULT 0.0,
        passed INTEGER DEFAULT 1,
        errors TEXT
    );
    """)

    # 8. Manual Baseline Metrics Table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS manual_baseline (
        metric_key TEXT PRIMARY KEY,
        metric_name TEXT NOT NULL,
        as_is_value REAL NOT NULL,
        unit TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );
    """)

    # Indices for performance
    cur.execute("CREATE INDEX IF NOT EXISTS idx_leads_phone ON leads(phone);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_leads_email ON leads(email);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_leads_status ON leads(current_status);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_leads_classification ON leads(classification);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_messages_lead ON messages(lead_id);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_audit_lead ON audit_events(lead_id);")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_approvals_lead ON approvals(lead_id);")

    conn.commit()
    conn.close()


def seed_default_counsellors(db_path: Optional[str] = None):
    """Seeds the synthetic roster of 5 Alliance University counsellors."""
    conn = get_db_connection(db_path)
    cur = conn.cursor()

    counsellors = [
        {
            "counsellor_id": "C1",
            "name": "Prof. Rajesh Nair",
            "specialisations": json.dumps(["MBA", "Executive MBA", "Management"]),
            "languages": json.dumps(["English", "Hindi"]),
            "active_high_leads": 3,
            "capacity": 8,
            "available_slots": json.dumps(["Today 11:00 AM", "Today 03:00 PM", "Tomorrow 10:00 AM"]),
            "is_available": 1
        },
        {
            "counsellor_id": "C2",
            "name": "Dr. Ananya Sharma",
            "specialisations": json.dumps(["B.Tech", "Engineering", "Data Science", "Computer Science"]),
            "languages": json.dumps(["English", "Kannada", "Hindi"]),
            "active_high_leads": 5,
            "capacity": 8,
            "available_slots": json.dumps(["Today 02:00 PM", "Tomorrow 11:30 AM", "Tomorrow 04:00 PM"]),
            "is_available": 1
        },
        {
            "counsellor_id": "C3",
            "name": "Prof. S. Venkatesh",
            "specialisations": json.dumps(["Law", "BBA LLB", "BA LLB", "LLM"]),
            "languages": json.dumps(["English", "Tamil"]),
            "active_high_leads": 2,
            "capacity": 8,
            "available_slots": json.dumps(["Today 12:00 PM", "Tomorrow 02:30 PM"]),
            "is_available": 1
        },
        {
            "counsellor_id": "C4",
            "name": "Priya Menon",
            "specialisations": json.dumps(["MBA", "BBA", "Commerce", "Economics"]),
            "languages": json.dumps(["English", "Malayalam", "Hindi"]),
            "active_high_leads": 4,
            "capacity": 8,
            "available_slots": json.dumps(["Today 04:00 PM", "Tomorrow 09:30 AM", "Tomorrow 01:00 PM"]),
            "is_available": 1
        },
        {
            "counsellor_id": "C5",
            "name": "Vikram Das",
            "specialisations": json.dumps(["Engineering", "General"]),
            "languages": json.dumps(["English", "Telugu", "Hindi"]),
            "active_high_leads": 1,
            "capacity": 8,
            "available_slots": json.dumps(["Today 10:00 AM", "Today 01:30 PM", "Tomorrow 03:00 PM"]),
            "is_available": 1
        }
    ]

    for c in counsellors:
        cur.execute("""
        INSERT OR REPLACE INTO counsellors 
        (counsellor_id, name, specialisations, languages, active_high_leads, capacity, available_slots, is_available)
        VALUES (:counsellor_id, :name, :specialisations, :languages, :active_high_leads, :capacity, :available_slots, :is_available);
        """, c)

    conn.commit()
    conn.close()


def seed_default_knowledge_documents(db_path: Optional[str] = None):
    """Seeds verified public Alliance University knowledge documents."""
    conn = get_db_connection(db_path)
    cur = conn.cursor()

    docs = [
        {
            "doc_id": "KB_MBA_01",
            "title": "Alliance School of Business: Master of Business Administration (MBA) Overview",
            "programme": "MBA",
            "category": "Programmes",
            "approved_content": (
                "Alliance University's flagship Master of Business Administration (MBA) is a two-year, full-time program "
                "accredited by IACBE (USA). Specialisations include Marketing, Financial Management, Human Resource Management, "
                "Operations Management, and International Business & Analytics. The curriculum blends case method learning, industry "
                "immersion, and international exchange partnerships. Foreign study tours, international exchange programs, and semester abroad options "
                "are offered through partner universities across Europe and North America. Intake is scheduled for July 2026."
            ),
            "official_source_url": "https://www.alliance.edu.in/programmes/school-of-business/master-of-business-administration",
            "retrieval_metadata": json.dumps({"keywords": ["mba", "specialisations", "marketing", "finance", "foreign study tours", "semester abroad", "international exchange", "iacbe", "curriculum"]}),
            "collection_date": "2026-01-15",
            "last_verified_date": "2026-10-01",
            "is_approved": 1
        },
        {
            "doc_id": "KB_MBA_ELIG_02",
            "title": "Alliance University MBA Eligibility Criteria & Admission Process",
            "programme": "MBA",
            "category": "Eligibility",
            "approved_content": (
                "MBA Eligibility Requirements: Bachelor's degree in any discipline with a minimum of 50% aggregate marks (45% for SC/ST candidates) "
                "from a recognized university. Candidates must have a valid test score in national entrance exams: CAT, MAT, XAT, NMAT, CMAT, GMAT, "
                "or the Alliance Management Aptitude Test (AMAT). The admission process involves Oral Presentation, Personal Interview, and evaluation "
                "of academic record and work experience. Upcoming Application Deadline: Round 1 closes 30th April 2026."
            ),
            "official_source_url": "https://www.alliance.edu.in/admissions/eligibility/mba",
            "retrieval_metadata": json.dumps({"keywords": ["eligibility", "50 percent", "graduation", "cat", "mat", "gmat", "amat", "interview"]}),
            "collection_date": "2026-01-15",
            "last_verified_date": "2026-10-01",
            "is_approved": 1
        },
        {
            "doc_id": "KB_FEE_MBA_03",
            "title": "Alliance School of Business MBA Fee Structure 2026-28",
            "programme": "MBA",
            "category": "Fees",
            "approved_content": (
                "The total tuition fee for the two-year regular MBA program (Batch 2026-2028) is INR 15,00,000 (Rupees Fifteen Lakhs) payable in "
                "four semester installments. Registration fee is INR 50,000. Hostel and mess fees range from INR 1,20,000 to INR 1,80,000 per year "
                "depending on occupancy. Merit scholarships covering up to 50% tuition waiver are available for candidates scoring 90+ percentile in CAT/GMAT."
            ),
            "official_source_url": "https://www.alliance.edu.in/admissions/fees/mba",
            "retrieval_metadata": json.dumps({"keywords": ["fees", "tuition", "15 lakhs", "installments", "hostel", "scholarships", "cost"]}),
            "collection_date": "2026-02-10",
            "last_verified_date": "2026-10-01",
            "is_approved": 1
        },
        {
            "doc_id": "KB_PLACEMENTS_04",
            "title": "Alliance University Career Outcomes & Placements Report",
            "programme": "All Programmes",
            "category": "Placements",
            "approved_content": (
                "Alliance University Office of Career Advancement has reported over 600+ recruitment partners. For the recent graduating batch: "
                "The highest international package reached INR 60.1 LPA, and the highest domestic package reached INR 21.6 LPA. The overall average "
                "package across management programs stood at INR 8.5 LPA. Key recruiters include Amazon, Deloitte, KPMG, Cisco, Ernst & Young, "
                "Bosch, HCL, and Aditya Birla Group."
            ),
            "official_source_url": "https://www.alliance.edu.in/placements/statistics",
            "retrieval_metadata": json.dumps({"keywords": ["placements", "salary", "average package", "highest package", "recruiters", "60.1 lpa", "8.5 lpa"]}),
            "collection_date": "2026-02-12",
            "last_verified_date": "2026-10-01",
            "is_approved": 1
        },
        {
            "doc_id": "KB_BTECH_05",
            "title": "Alliance College of Engineering and Design: B.Tech Programs",
            "programme": "B.Tech",
            "category": "Programmes",
            "approved_content": (
                "Alliance College of Engineering offers four-year B.Tech degrees in Computer Science & Engineering (with specialisations in AI & ML, "
                "Data Science, Cloud Computing), Electronics & Communication, Aerospace, and Mechanical Engineering. Eligibility requires 10+2 with "
                "Physics and Mathematics along with Chemistry/Biotechnology/Computer Science with minimum 50% aggregate marks. Accepted entrance tests: "
                "JEE Main, COMED-K, KCET, or Alliance University Scholastic Aptitude Test (AUSAT)."
            ),
            "official_source_url": "https://www.alliance.edu.in/programmes/college-of-engineering/b-tech",
            "retrieval_metadata": json.dumps({"keywords": ["btech", "engineering", "cse", "artificial intelligence", "jee", "kcet", "ausat"]}),
            "collection_date": "2026-01-20",
            "last_verified_date": "2026-10-01",
            "is_approved": 1
        },
        {
            "doc_id": "KB_LAW_06",
            "title": "Alliance School of Law: BBA LLB (Hons.) and BA LLB (Hons.)",
            "programme": "Law",
            "category": "Programmes",
            "approved_content": (
                "Alliance School of Law offers 5-year integrated BBA LLB (Hons.) and BA LLB (Hons.) degrees approved by the Bar Council of India (BCI). "
                "Eligibility requires 10+2 or equivalent with minimum 45% aggregate marks (40% for SC/ST). Candidates are selected based on CLAT, LSAT India, "
                "or AUSAT scores, followed by a personal interview."
            ),
            "official_source_url": "https://www.alliance.edu.in/programmes/school-of-law",
            "retrieval_metadata": json.dumps({"keywords": ["law", "bba llb", "ba llb", "clat", "lsat", "bar council", "5 years"]}),
            "collection_date": "2026-01-25",
            "last_verified_date": "2026-10-01",
            "is_approved": 1
        },
        {
            "doc_id": "KB_ADMISSIONS_STEPS_07",
            "title": "Step-by-Step Admissions Application Process",
            "programme": "General",
            "category": "Application Steps",
            "approved_content": (
                "Application steps at Alliance University: 1. Submit online application at apply.alliance.edu.in with application fee (INR 1,000). "
                "2. Upload academic transcripts, entrance score card, and ID proof. 3. Participate in the evaluation process (Oral Presentation/Essay & PI). "
                "4. Selected candidates receive provisional offer letter via email within 5 working days. 5. Pay registration deposit to secure seat."
            ),
            "official_source_url": "https://www.alliance.edu.in/admissions/how-to-apply",
            "retrieval_metadata": json.dumps({"keywords": ["how to apply", "application steps", "documents", "process", "portal", "registration"]}),
            "collection_date": "2026-01-10",
            "last_verified_date": "2026-10-01",
            "is_approved": 1
        },
        {
            "doc_id": "KB_FEE_BBA_08",
            "title": "Alliance School of Business BBA Fee Structure & Installment Options",
            "programme": "BBA",
            "category": "Fees",
            "approved_content": (
                "The total tuition fee for the three-year regular Bachelor of Business Administration (BBA) program is INR 9,00,000 "
                "payable in six semester installments (INR 1,50,000 per semester). Registration fee is INR 25,000. Hostel fees range from "
                "INR 1,20,000 to INR 1,80,000 per year."
            ),
            "official_source_url": "https://www.alliance.edu.in/admissions/fees/bba",
            "retrieval_metadata": json.dumps({"keywords": ["bba", "fees", "tuition", "installments", "semester", "fee structure", "bachelor of business administration"]}),
            "collection_date": "2026-02-15",
            "last_verified_date": "2026-10-01",
            "is_approved": 1
        },
        {
            "doc_id": "KB_CAMPUS_FACILITIES_09",
            "title": "Alliance University Campus Life, Sports Facilities & Amenities",
            "programme": "All Programmes",
            "category": "Campus Life",
            "approved_content": (
                "Alliance University's sprawling 60-acre green campus in Bengaluru provides world-class infrastructure including an "
                "Olympic-size swimming pool, indoor badminton and squash courts, basketball and tennis courts, modern gymnasium, "
                "student activity centre, multi-cuisine food courts, and Wi-Fi enabled residential halls."
            ),
            "official_source_url": "https://www.alliance.edu.in/campus-life",
            "retrieval_metadata": json.dumps({"keywords": ["campus", "facilities", "sports", "swimming pool", "badminton", "gym", "amenities", "olympic"]}),
            "collection_date": "2026-02-15",
            "last_verified_date": "2026-10-01",
            "is_approved": 1
        }
    ]

    for doc in docs:
        cur.execute("""
        INSERT OR REPLACE INTO knowledge_documents
        (doc_id, title, programme, category, approved_content, official_source_url, retrieval_metadata, collection_date, last_verified_date, is_approved)
        VALUES (:doc_id, :title, :programme, :category, :approved_content, :official_source_url, :retrieval_metadata, :collection_date, :last_verified_date, :is_approved);
        """, doc)

    conn.commit()
    conn.close()


def seed_manual_baseline(db_path: Optional[str] = None):
    """Seeds the initial assumed manual baseline values as documented in proposal."""
    conn = get_db_connection(db_path)
    cur = conn.cursor()

    baselines = [
        ("first_response_time", "First-Response Time", 14400.0, "seconds"),  # 4 hours manual
        ("processing_time", "Agent Processing Time per Lead", 1800.0, "seconds"),  # 30 mins manual
        ("human_touchpoints", "Average Human Touchpoints", 4.5, "touchpoints"),
        ("cost_per_case", "Estimated Cost per Case", 150.0, "INR"),
        ("field_completeness", "Required-Field Completeness", 62.0, "percent"),
        ("intent_accuracy", "Intent & Extraction Accuracy", 70.0, "percent"),
        ("routing_accuracy", "Routing Accuracy on Normal Cases", 65.0, "percent"),
        ("stp_rate", "Straight-Through Processing Rate", 10.0, "percent"),
        ("automation_coverage", "Automation Coverage", 20.0, "percent"),
        ("human_intervention_rate", "Human Intervention Rate", 85.0, "percent"),
        ("exception_correctness", "Exception-Handling Correctness", 75.0, "percent"),
        ("followup_adherence", "Follow-Up Schedule Adherence", 50.0, "percent"),
        ("allocation_sla", "High-Lead Allocation within SLA", 58.0, "percent"),
        ("capacity_violations", "Capacity Violations", 4.0, "violations"),
        ("ungrounded_answers", "Ungrounded / Hallucinated Answers", 8.0, "incidents"),
        ("audit_completeness", "Audit Completeness", 40.0, "percent"),
        ("score_reproducibility", "Deterministic Scoring Reproducibility", 35.0, "percent")
    ]

    now_iso = datetime.now().isoformat()
    for key, name, val, unit in baselines:
        cur.execute("""
        INSERT OR REPLACE INTO manual_baseline (metric_key, metric_name, as_is_value, unit, updated_at)
        VALUES (?, ?, ?, ?, ?)
        """, (key, name, val, unit, now_iso))

    conn.commit()
    conn.close()


def seed_demo_leads(db_path: Optional[str] = None):
    """Preloads initial representative leads across various workflow stages."""
    conn = get_db_connection(db_path)
    cur = conn.cursor()

    demo_leads = [
        {
            "lead_id": "LEAD-2026-001",
            "created_at": "2026-10-18T10:15:00",
            "updated_at": "2026-10-18T10:20:00",
            "channel": "Web Chat",
            "student_message": "Hi, I graduated with B.Tech CSE (78%) and took CAT 2025 (88 percentile). Want to apply for MBA 2026 batch. How do I apply and can I speak with a counsellor?",
            "name": "Rohan Gupta",
            "phone": "+91 98765 43210",
            "email": "rohan.gupta@example.com",
            "consent_status": 1,
            "opt_out_status": 0,
            "programme_interest": "MBA",
            "education": "B.Tech CSE Graduate (78%)",
            "work_experience": "Fresher",
            "intended_intake": "2026",
            "application_readiness": "Ready to apply",
            "intent": "Apply and Request Counsellor",
            "extracted_fields_json": json.dumps({
                "programme_interest": "MBA", "education": "B.Tech", "intended_intake": "2026",
                "application_readiness": "Ready to apply", "primary_concern": "application process",
                "wants_counsellor": True, "message_type": "interest"
            }),
            "extraction_confidence": 0.98,
            "clarification_count": 0,
            "score_breakdown_json": json.dumps({
                "readiness_score": 25, "readiness_rationale": "Upcoming 2026 intake + graduated",
                "intent_score": 25, "intent_rationale": "Asks how to apply and requests counsellor",
                "fit_score": 20, "fit_rationale": "Names specific offered MBA program",
                "eligibility_score": 20, "eligibility_rationale": "78% graduation exceeds 50% min requirement",
                "engagement_score": 10, "engagement_rationale": "Provided complete information upfront",
                "total_score": 100, "classification": "High", "is_uncertain": False, "uncertain_reasons": []
            }),
            "total_score": 100,
            "eligibility_score": 20,
            "classification": "High",
            "current_stage": "S8_Handoff_Approval",
            "current_status": "Awaiting Approval",
            "escalation_flag": 0,
            "escalation_reason": None,
            "assigned_counsellor": "Prof. Rajesh Nair",
            "proposed_slot": "Today 03:00 PM",
            "approved_by": None,
            "nurture_stage": None,
            "nurture_messages_sent": 0,
            "last_contact_at": "2026-10-18T10:16:00",
            "duplicate_of": None,
            "case_summary": "High-intent MBA applicant with 78% B.Tech and 88 percentile CAT. Ready for 2026 intake. Matched with Prof. Rajesh Nair."
        },
        {
            "lead_id": "LEAD-2026-002",
            "created_at": "2026-10-18T11:30:00",
            "updated_at": "2026-10-18T11:32:00",
            "channel": "WhatsApp",
            "student_message": "Could you tell me the tuition fee and hostel charges for the MBA program?",
            "name": "Kavita Rao",
            "phone": "+91 98450 11223",
            "email": "kavita.rao@example.com",
            "consent_status": 1,
            "opt_out_status": 0,
            "programme_interest": "MBA",
            "education": "B.Com final year",
            "work_experience": "Fresher",
            "intended_intake": "Undecided",
            "application_readiness": "Exploratory",
            "intent": "Fees Enquiry",
            "extracted_fields_json": json.dumps({
                "programme_interest": "MBA", "education": "B.Com", "intended_intake": "Undecided",
                "application_readiness": "Exploratory", "primary_concern": "fees",
                "wants_counsellor": False, "message_type": "factual_question"
            }),
            "extraction_confidence": 0.92,
            "clarification_count": 0,
            "score_breakdown_json": json.dumps({
                "readiness_score": 5, "readiness_rationale": "Undecided intake",
                "intent_score": 15, "intent_rationale": "Asks about fees",
                "fit_score": 20, "fit_rationale": "Names specific MBA program",
                "eligibility_score": 10, "eligibility_rationale": "Final year results awaited",
                "engagement_score": 5, "engagement_rationale": "Partial profile provided",
                "total_score": 55, "classification": "Medium", "is_uncertain": False, "uncertain_reasons": []
            }),
            "total_score": 55,
            "eligibility_score": 10,
            "classification": "Medium",
            "current_stage": "S7_Nurturing",
            "current_status": "In Nurture",
            "escalation_flag": 0,
            "escalation_reason": None,
            "assigned_counsellor": None,
            "proposed_slot": None,
            "approved_by": None,
            "nurture_stage": "N1_Day0",
            "nurture_messages_sent": 1,
            "last_contact_at": "2026-10-18T11:31:00",
            "duplicate_of": None,
            "case_summary": "Medium-intent lead inquiring about MBA tuition. Currently in Nurture Stage N1."
        },
        {
            "lead_id": "LEAD-2026-003",
            "created_at": "2026-10-18T14:00:00",
            "updated_at": "2026-10-18T14:05:00",
            "channel": "Web Chat",
            "student_message": "Do you offer a PhD in Astrobiology with full funding and an on-campus observatory?",
            "name": "Arjun Sen",
            "phone": "+91 97110 99887",
            "email": "arjun.sen@example.com",
            "consent_status": 1,
            "opt_out_status": 0,
            "programme_interest": "PhD Astrobiology",
            "education": "M.Sc Physics",
            "work_experience": "Fresher",
            "intended_intake": "2026",
            "application_readiness": "Exploratory",
            "intent": "Special Program",
            "extracted_fields_json": json.dumps({
                "programme_interest": "PhD Astrobiology", "education": "M.Sc Physics",
                "intended_intake": "2026", "application_readiness": "Exploratory",
                "primary_concern": "programme availability", "wants_counsellor": False,
                "message_type": "factual_question"
            }),
            "extraction_confidence": 0.85,
            "clarification_count": 0,
            "score_breakdown_json": json.dumps({
                "readiness_score": 5, "readiness_rationale": "Exploratory",
                "intent_score": 5, "intent_rationale": "General inquiry",
                "fit_score": 0, "fit_rationale": "Program not offered by Alliance",
                "eligibility_score": 0, "eligibility_rationale": "No verified eligibility info for program",
                "engagement_score": 5, "engagement_rationale": "Partial details",
                "total_score": 15, "classification": "Uncertain", "is_uncertain": True,
                "uncertain_reasons": ["Unsupported question with retrieval similarity below 0.60"]
            }),
            "total_score": 15,
            "eligibility_score": 0,
            "classification": "Uncertain",
            "current_stage": "Exception_Desk",
            "current_status": "Open Exception",
            "escalation_flag": 1,
            "escalation_reason": "E1: Unsupported question regarding PhD Astrobiology (similarity 0.22 < 0.60 threshold)",
            "assigned_counsellor": None,
            "proposed_slot": None,
            "approved_by": None,
            "nurture_stage": None,
            "nurture_messages_sent": 0,
            "last_contact_at": "2026-10-18T14:01:00",
            "duplicate_of": None,
            "case_summary": "Exception E1: Student inquiring about unoffered Astrobiology program. Escalated to Admissions Desk."
        }
    ]

    for lead in demo_leads:
        cur.execute("""
        INSERT OR REPLACE INTO leads 
        (lead_id, created_at, updated_at, channel, student_message, name, phone, email, consent_status,
         opt_out_status, programme_interest, education, work_experience, intended_intake, application_readiness,
         intent, extracted_fields_json, extraction_confidence, clarification_count, score_breakdown_json,
         total_score, eligibility_score, classification, current_stage, current_status, escalation_flag,
         escalation_reason, assigned_counsellor, proposed_slot, approved_by, nurture_stage, nurture_messages_sent,
         last_contact_at, duplicate_of, case_summary)
        VALUES 
        (:lead_id, :created_at, :updated_at, :channel, :student_message, :name, :phone, :email, :consent_status,
         :opt_out_status, :programme_interest, :education, :work_experience, :intended_intake, :application_readiness,
         :intent, :extracted_fields_json, :extraction_confidence, :clarification_count, :score_breakdown_json,
         :total_score, :eligibility_score, :classification, :current_stage, :current_status, :escalation_flag,
         :escalation_reason, :assigned_counsellor, :proposed_slot, :approved_by, :nurture_stage, :nurture_messages_sent,
         :last_contact_at, :duplicate_of, :case_summary);
        """, lead)

    # Initial Messages
    cur.execute("""
    INSERT OR REPLACE INTO messages (message_id, lead_id, timestamp, direction, channel, message_type, content, content_source)
    VALUES 
    ('MSG-001-1', 'LEAD-2026-001', '2026-10-18T10:15:00', 'incoming', 'Web Chat', 'interest', 'Hi, I graduated with B.Tech CSE (78%) and took CAT 2025 (88 percentile). Want to apply for MBA 2026 batch. How do I apply and can I speak with a counsellor?', 'student'),
    ('MSG-001-2', 'LEAD-2026-001', '2026-10-18T10:15:02', 'outgoing', 'Web Chat', 'disclosure', 'Welcome to Alliance University Admissions Assistant. I am an automated AI agent designed to help answer your queries and connect you with our admissions team.', 'template'),
    ('MSG-002-1', 'LEAD-2026-002', '2026-10-18T11:30:00', 'incoming', 'WhatsApp', 'factual_question', 'Could you tell me the tuition fee and hostel charges for the MBA program?', 'student'),
    ('MSG-002-2', 'LEAD-2026-002', '2026-10-18T11:30:04', 'outgoing', 'WhatsApp', 'answer', 'The total tuition fee for the two-year regular MBA program (Batch 2026-2028) is INR 15,00,000 payable in installments. Hostel fees range from INR 1,20,000 to INR 1,80,000/yr. [Source: alliance.edu.in/admissions/fees/mba]', 'knowledge_base'),
    ('MSG-003-1', 'LEAD-2026-003', '2026-10-18T14:00:00', 'incoming', 'Web Chat', 'factual_question', 'Do you offer a PhD in Astrobiology with full funding and an on-campus observatory?', 'student'),
    ('MSG-003-2', 'LEAD-2026-003', '2026-10-18T14:00:03', 'outgoing', 'Web Chat', 'escalation', 'Thank you for your enquiry. We currently do not have verified admissions data matching your specific request. Your enquiry has been routed to our senior admissions team for personalised assistance.', 'template');
    """)

    # Initial Approvals
    cur.execute("""
    INSERT OR REPLACE INTO approvals (approval_id, lead_id, proposed_action, decision, approving_person, comments, timestamp, previous_state, updated_state)
    VALUES
    ('APP-001', 'LEAD-2026-001', 'Allocate Counsellor Prof. Rajesh Nair for Today 03:00 PM', 'Pending', NULL, 'High intent lead (Score 100). Awaiting counsellor desk sign-off.', '2026-10-18T10:20:00', 'S6_Allocation', 'S8_Handoff_Approval');
    """)

    # Initial Audit Events
    cur.execute("""
    INSERT OR REPLACE INTO audit_events (event_id, timestamp, lead_id, workflow_stage, rule_id, action, inputs, output, tool_invoked, autonomy_level, approval_ref)
    VALUES
    ('EVT-001', '2026-10-18T10:15:02', 'LEAD-2026-001', 'S1_Trigger', 'R1', 'Case created and AI disclosure sent', '{"channel": "Web Chat"}', '{"lead_id": "LEAD-2026-001"}', 'create_case', 'Fully autonomous', NULL),
    ('EVT-002', '2026-10-18T10:15:05', 'LEAD-2026-001', 'S5_Scoring', 'R9', 'Calculated score 100, classified High', '{"education": "B.Tech"}', '{"total_score": 100, "classification": "High"}', 'score_lead', 'Act then report', NULL),
    ('EVT-003', '2026-10-18T10:20:00', 'LEAD-2026-001', 'S6_Allocation', 'R9', 'Proposed counsellor allocation Prof. Rajesh Nair', '{"lead_id": "LEAD-2026-001"}', '{"counsellor_id": "C1", "slot": "Today 03:00 PM"}', 'counsellor_optimizer', 'Approve', 'APP-001'),
    ('EVT-004', '2026-10-18T14:00:03', 'LEAD-2026-003', 'S3_RAG', 'R5', 'Retrieved similarity 0.22 < 0.60, escalated E1', '{"query": "PhD Astrobiology"}', '{"escalation_flag": true}', 'knowledge_retriever', 'Act then report', NULL);
    """)

    conn.commit()
    conn.close()


def reset_database_to_demo(db_path: Optional[str] = None, confirm: bool = False):
    """Safely resets the database with seed data. Requires explicit confirm=True."""
    if not confirm:
        raise ValueError("Database reset requires explicit confirm=True.")
    
    target_path = Path(db_path) if db_path else Path(DEFAULT_DB_PATH)
    if target_path.exists():
        target_path.unlink()
    
    init_database(db_path)
    seed_default_counsellors(db_path)
    seed_default_knowledge_documents(db_path)
    seed_manual_baseline(db_path)
    seed_demo_leads(db_path)
