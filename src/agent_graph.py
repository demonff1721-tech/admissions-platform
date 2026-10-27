"""Stateful LangGraph workflow orchestrating the 9 lifecycle stages (S1-S9) with human-in-the-loop interrupts."""

from typing import Dict, Any, Optional, TypedDict, List
from datetime import datetime
import json

from langgraph.graph import StateGraph, END

from src.database import get_db_connection
from src.models import ExtractedFields, ScoreBreakdown, LeadRecord, PolicyDecision
from src.extraction import extract_information
from src.knowledge_retrieval import retrieve_from_knowledge_base
from src.security import check_for_duplicates, AI_DISCLOSURE_TEXT
from src.scoring import score_lead
from src.policy_engine import evaluate_policy
from src.counsellor_optimizer import propose_counsellor_for_lead
from src.exception_handler import raise_exception
from src.audit import log_audit_event


class AdmissionsState(TypedDict, total=False):
    """LangGraph state representation passed through nodes."""
    lead_id: str
    channel: str
    name: str
    phone: Optional[str]
    email: Optional[str]
    student_message: str
    extracted: Optional[Dict[str, Any]]
    rag_result: Optional[Dict[str, Any]]
    score: Optional[Dict[str, Any]]
    policy_decision: Optional[Dict[str, Any]]
    proposal: Optional[Dict[str, Any]]
    current_stage: str
    current_status: str
    clarification_count: int
    escalation_flag: bool
    escalation_reason: Optional[str]
    requires_approval: bool
    is_paused: bool
    error: Optional[str]
    db_path: Optional[str]


# Node 1: S1 Trigger & Case Creation
def node_s1_trigger(state: AdmissionsState) -> Dict[str, Any]:
    lead_id = state["lead_id"]
    db_path = state.get("db_path")
    now_iso = datetime.now().isoformat()
    
    conn = get_db_connection(db_path)
    cur = conn.cursor()
    cur.execute("""
    INSERT OR REPLACE INTO leads 
    (lead_id, created_at, updated_at, channel, student_message, name, phone, email, current_stage, current_status)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'S1_Trigger', 'Created');
    """, (lead_id, now_iso, now_iso, state.get("channel", "Web Chat"), state["student_message"], state["name"], state.get("phone"), state.get("email")))
    
    # Simulated AI disclosure message
    msg_id = f"MSG-DISCLOSURE-{lead_id}"
    cur.execute("""
    INSERT OR REPLACE INTO messages (message_id, lead_id, timestamp, direction, channel, message_type, content, content_source)
    VALUES (?, ?, ?, 'outgoing', ?, 'disclosure', ?, 'template');
    """, (msg_id, lead_id, now_iso, state.get("channel", "Web Chat"), AI_DISCLOSURE_TEXT))
    
    conn.commit()
    conn.close()

    log_audit_event(
        lead_id=lead_id,
        workflow_stage="S1_Trigger",
        action="Case created and AI disclosure sent",
        autonomy_level="Fully autonomous",
        rule_id="R1",
        db_path=db_path
    )

    return {
        "current_stage": "S1_Trigger",
        "current_status": "Created"
    }


# Node 2: S2 Extraction
def node_s2_extraction(state: AdmissionsState) -> Dict[str, Any]:
    lead_id = state["lead_id"]
    db_path = state.get("db_path")
    extracted = extract_information(state["student_message"])
    
    conn = get_db_connection(db_path)
    cur = conn.cursor()
    cur.execute("""
    UPDATE leads
    SET programme_interest = ?,
        education = ?,
        work_experience = ?,
        intended_intake = ?,
        application_readiness = ?,
        intent = ?,
        extracted_fields_json = ?,
        extraction_confidence = ?,
        current_stage = 'S2_Extraction',
        current_status = 'Information Extracted',
        updated_at = ?
    WHERE lead_id = ?;
    """, (
        extracted.programme_interest, extracted.education, extracted.work_experience,
        extracted.intended_intake, extracted.application_readiness, extracted.primary_concern,
        extracted.model_dump_json(), extracted.overall_confidence, datetime.now().isoformat(), lead_id
    ))
    conn.commit()
    conn.close()

    log_audit_event(
        lead_id=lead_id,
        workflow_stage="S2_Extraction",
        action=f"Extracted fields with confidence {extracted.overall_confidence}",
        autonomy_level="Fully autonomous",
        inputs={"message": state["student_message"]},
        outputs=extracted.model_dump(),
        db_path=db_path
    )

    return {
        "extracted": extracted.model_dump(),
        "current_stage": "S2_Extraction",
        "current_status": "Information Extracted"
    }


# Node 3: S3 Grounded RAG
def node_s3_grounded_rag(state: AdmissionsState) -> Dict[str, Any]:
    lead_id = state["lead_id"]
    db_path = state.get("db_path")
    msg = state["student_message"]
    extracted_dict = state.get("extracted") or {}
    prog = extracted_dict.get("programme_interest")

    rag = retrieve_from_knowledge_base(msg, programme_filter=prog, db_path=db_path)
    now_iso = datetime.now().isoformat()

    conn = get_db_connection(db_path)
    cur = conn.cursor()

    if rag["found"]:
        # Record grounded answer message
        msg_id = f"MSG-ANS-{lead_id}-{int(datetime.now().timestamp())}"
        cur.execute("""
        INSERT INTO messages (message_id, lead_id, timestamp, direction, channel, message_type, content, content_source)
        VALUES (?, ?, ?, 'outgoing', ?, 'answer', ?, 'knowledge_base');
        """, (msg_id, lead_id, now_iso, state.get("channel", "Web Chat"), rag["grounded_answer"]))
        conn.commit()
        conn.close()

        log_audit_event(
            lead_id=lead_id,
            workflow_stage="S3_RAG",
            action=f"Answered with verified citation ({rag['title']}, similarity {rag['similarity']})",
            autonomy_level="Act then report",
            rule_id="R4",
            inputs={"query": msg},
            outputs={"doc_id": rag["doc_id"], "similarity": rag["similarity"]},
            db_path=db_path
        )
        return {
            "rag_result": rag,
            "current_stage": "S3_RAG",
            "current_status": "Answered Grounded"
        }
    else:
        conn.close()
        # Only escalate to E1 if applicant is asking an unsupported factual question and does NOT want a counsellor
        is_pure_question = extracted_dict.get("message_type") == "factual_question" and not extracted_dict.get("wants_counsellor")
        
        if is_pure_question:
            raise_exception(
                lead_id=lead_id,
                exception_type="E1",
                explanation=rag.get("explanation", "Query could not be grounded in approved knowledge base"),
                last_valid_state="S2_Extraction",
                db_path=db_path
            )
            return {
                "rag_result": rag,
                "current_stage": "Exception_Desk",
                "current_status": "Open Exception",
                "escalation_flag": True,
                "escalation_reason": "E1: Unsupported question requiring admissions judgement"
            }
        else:
            # Lead expresses application interest; continue to qualification and counsellor matching
            return {
                "rag_result": rag,
                "current_stage": "S3_RAG",
                "current_status": "Qualification In Progress"
            }


# Node 4: S4 Duplicate & Consent Validation
def node_s4_validation(state: AdmissionsState) -> Dict[str, Any]:
    lead_id = state["lead_id"]
    db_path = state.get("db_path")
    extracted_dict = state.get("extracted") or {}
    
    # Check opt-out first
    if extracted_dict.get("message_type") == "stop":
        conn = get_db_connection(db_path)
        cur = conn.cursor()
        cur.execute("UPDATE leads SET opt_out_status = 1, current_stage = 'Closed', current_status = 'Opted Out' WHERE lead_id = ?;", (lead_id,))
        conn.commit()
        conn.close()
        log_audit_event(lead_id, "S4_Validation", "Opt-out processed", "Act then report", "R6", db_path=db_path)
        return {
            "current_stage": "Closed",
            "current_status": "Opted Out",
            "is_paused": True
        }

    is_exact, is_potential, existing_id, match_type = check_for_duplicates(
        phone=state.get("phone"),
        email=state.get("email"),
        name=state["name"],
        programme_interest=extracted_dict.get("programme_interest"),
        current_lead_id=lead_id,
        db_path=db_path
    )

    if is_exact:
        conn = get_db_connection(db_path)
        cur = conn.cursor()
        cur.execute("UPDATE leads SET duplicate_of = ?, current_stage = 'Merged', current_status = 'Exact Duplicate' WHERE lead_id = ?;", (existing_id, lead_id))
        conn.commit()
        conn.close()
        log_audit_event(lead_id, "S4_Validation", f"Linked exact duplicate to {existing_id}", "Act then report", "R7", db_path=db_path)
        return {
            "current_stage": "Merged",
            "current_status": "Exact Duplicate",
            "is_paused": True
        }
    elif is_potential:
        raise_exception(
            lead_id=lead_id,
            exception_type="E3",
            explanation=f"Potential duplicate of {existing_id} ({match_type})",
            last_valid_state="S3_RAG",
            db_path=db_path
        )
        return {
            "current_stage": "Lead_Desk",
            "current_status": "Hold For Duplicate Review",
            "escalation_flag": True,
            "requires_approval": True,
            "is_paused": True
        }

    return {
        "current_stage": "S4_Validation",
        "current_status": "Validated"
    }


# Node 5: S5 Deterministic Scoring
def node_s5_scoring(state: AdmissionsState) -> Dict[str, Any]:
    lead_id = state["lead_id"]
    db_path = state.get("db_path")
    extracted_dict = state.get("extracted") or {}
    extracted = ExtractedFields(**extracted_dict) if extracted_dict else ExtractedFields()
    
    score = score_lead(
        extracted=extracted,
        clarification_count=state.get("clarification_count", 0),
        contradiction_detected=bool(state.get("escalation_flag") and "E2" in (state.get("escalation_reason") or "")),
        unsupported_question=bool(state.get("escalation_flag") and "E1" in (state.get("escalation_reason") or ""))
    )

    now_iso = datetime.now().isoformat()
    conn = get_db_connection(db_path)
    cur = conn.cursor()
    cur.execute("""
    UPDATE leads
    SET score_breakdown_json = ?,
        total_score = ?,
        eligibility_score = ?,
        classification = ?,
        current_stage = 'S5_Scoring',
        current_status = ?,
        updated_at = ?
    WHERE lead_id = ?;
    """, (score.model_dump_json(), score.total_score, score.eligibility_score, score.classification, score.classification, now_iso, lead_id))
    conn.commit()
    conn.close()

    log_audit_event(
        lead_id=lead_id,
        workflow_stage="S5_Scoring",
        action=f"Scored lead {score.total_score}/100, Classified as {score.classification}",
        autonomy_level="Act then report",
        outputs=score.model_dump(),
        db_path=db_path
    )

    return {
        "score": score.model_dump(),
        "current_stage": "S5_Scoring",
        "current_status": score.classification
    }


# Node 6: S6 Policy & Allocation
def node_s6_allocation(state: AdmissionsState) -> Dict[str, Any]:
    lead_id = state["lead_id"]
    db_path = state.get("db_path")
    score_dict = state.get("score") or {}
    score = ScoreBreakdown(**score_dict) if score_dict else None
    
    conn = get_db_connection(db_path)
    cur = conn.cursor()
    cur.execute("SELECT * FROM leads WHERE lead_id = ?;", (lead_id,))
    lead_row = cur.fetchone()
    conn.close()

    if not lead_row:
        return {"error": "Lead row missing"}

    lead_rec = LeadRecord(**dict(lead_row))

    if score and score.classification == "High":
        proposal = propose_counsellor_for_lead(lead_rec, db_path=db_path)
        if proposal:
            conn = get_db_connection(db_path)
            cur = conn.cursor()
            cur.execute("""
            UPDATE leads
            SET assigned_counsellor = ?,
                proposed_slot = ?,
                current_stage = 'S8_Handoff_Approval',
                current_status = 'Awaiting Approval',
                updated_at = ?
            WHERE lead_id = ?;
            """, (proposal.counsellor_name, proposal.proposed_slot, datetime.now().isoformat(), lead_id))
            
            # Record pending approval with idempotency check
            cur.execute("SELECT approval_id FROM approvals WHERE lead_id = ? AND decision = 'Pending';", (lead_id,))
            existing_app = cur.fetchone()
            if existing_app:
                approval_id = existing_app["approval_id"]
                cur.execute("""
                UPDATE approvals 
                SET proposed_action = ?, comments = 'High lead awaiting counsellor desk approval', timestamp = ?, updated_state = 'S8_Handoff_Approval'
                WHERE approval_id = ?;
                """, (f"Allocate {proposal.counsellor_name} ({proposal.proposed_slot})", datetime.now().isoformat(), approval_id))
            else:
                approval_id = f"APP-{lead_id}-{int(datetime.now().timestamp())}"
                cur.execute("""
                INSERT INTO approvals 
                (approval_id, lead_id, proposed_action, decision, comments, timestamp, previous_state, updated_state)
                VALUES (?, ?, ?, 'Pending', 'High lead awaiting counsellor desk approval', ?, 'S6_Allocation', 'S8_Handoff_Approval');
                """, (approval_id, lead_id, f"Allocate {proposal.counsellor_name} ({proposal.proposed_slot})", datetime.now().isoformat()))
            
            conn.commit()
            conn.close()

            log_audit_event(
                lead_id=lead_id,
                workflow_stage="S6_Allocation",
                action=f"Proposed counsellor {proposal.counsellor_name} ({proposal.proposed_slot})",
                autonomy_level="Approve",
                rule_id="R9",
                approval_ref=approval_id,
                outputs=proposal.model_dump(),
                db_path=db_path
            )

            return {
                "proposal": proposal.model_dump(),
                "current_stage": "S8_Handoff_Approval",
                "current_status": "Awaiting Approval",
                "requires_approval": True,
                "is_paused": True
            }
        else:
            # Capacity exceeded -> R12
            raise_exception(lead_id, "E6", "All counsellors at capacity (R12)", "S5_Scoring", db_path=db_path)
            return {
                "current_stage": "Counsellor_Desk",
                "current_status": "Waitlisted Capacity",
                "escalation_flag": True,
                "requires_approval": True,
                "is_paused": True
            }

    elif score and score.classification == "Medium":
        conn = get_db_connection(db_path)
        cur = conn.cursor()
        cur.execute("""
        UPDATE leads
        SET current_stage = 'S7_Nurturing',
            current_status = 'In Nurture',
            nurture_stage = 'N1_Day0',
            nurture_messages_sent = 1,
            updated_at = ?
        WHERE lead_id = ?;
        """, (datetime.now().isoformat(), lead_id))
        conn.commit()
        conn.close()

        log_audit_event(lead_id, "S6_Allocation", "Enrolled in Nurturing (Stage N1)", "Act then report", "R10", db_path=db_path)
        return {
            "current_stage": "S7_Nurturing",
            "current_status": "In Nurture"
        }

    else:
        # Low classification
        conn = get_db_connection(db_path)
        cur = conn.cursor()
        cur.execute("""
        UPDATE leads
        SET current_stage = 'S7_Low_Track',
            current_status = 'Low Information Track',
            updated_at = ?
        WHERE lead_id = ?;
        """, (datetime.now().isoformat(), lead_id))
        conn.commit()
        conn.close()

        log_audit_event(lead_id, "S6_Allocation", "Routed to Low information track", "Act then report", "R11", db_path=db_path)
        return {
            "current_stage": "S7_Low_Track",
            "current_status": "Low Information Track"
        }


def build_admissions_graph() -> StateGraph:
    """Constructs the LangGraph state machine with conditional routing and approval interrupts."""
    builder = StateGraph(AdmissionsState)

    builder.add_node("s1_trigger", node_s1_trigger)
    builder.add_node("s2_extraction", node_s2_extraction)
    builder.add_node("s3_grounded_rag", node_s3_grounded_rag)
    builder.add_node("s4_validation", node_s4_validation)
    builder.add_node("s5_scoring", node_s5_scoring)
    builder.add_node("s6_allocation", node_s6_allocation)

    builder.set_entry_point("s1_trigger")
    builder.add_edge("s1_trigger", "s2_extraction")
    builder.add_edge("s2_extraction", "s3_grounded_rag")
    
    # Conditional edge from S3: If exception raised, end or route to Exception Desk
    def route_after_s3(state: AdmissionsState) -> str:
        if state.get("escalation_flag"):
            return END
        return "s4_validation"

    builder.add_conditional_edges("s3_grounded_rag", route_after_s3)

    # Conditional edge from S4: If paused or merged, end
    def route_after_s4(state: AdmissionsState) -> str:
        if state.get("is_paused") or state.get("current_stage") in ["Merged", "Closed", "Lead_Desk"]:
            return END
        return "s5_scoring"

    builder.add_conditional_edges("s4_validation", route_after_s4)
    builder.add_edge("s5_scoring", "s6_allocation")
    builder.add_edge("s6_allocation", END)

    return builder.compile()


def run_admissions_workflow(
    lead_id: str,
    student_message: str,
    name: str,
    phone: Optional[str] = None,
    email: Optional[str] = None,
    channel: str = "Web Chat",
    db_path: Optional[str] = None
) -> AdmissionsState:
    """Executes the admissions graph from trigger through qualification and routing."""
    graph = build_admissions_graph()
    
    initial_state: AdmissionsState = {
        "lead_id": lead_id,
        "channel": channel,
        "name": name,
        "phone": phone,
        "email": email,
        "student_message": student_message,
        "extracted": None,
        "rag_result": None,
        "score": None,
        "policy_decision": None,
        "proposal": None,
        "current_stage": "S1_Trigger",
        "current_status": "New",
        "clarification_count": 0,
        "escalation_flag": False,
        "escalation_reason": None,
        "requires_approval": False,
        "is_paused": False,
        "error": None,
        "db_path": db_path
    }

    final_state = graph.invoke(initial_state)
    return final_state


def resume_admissions_workflow(
    lead_id: str,
    resume_from_stage: str = "S5_Scoring",
    db_path: Optional[str] = None
) -> Optional[AdmissionsState]:
    """
    Safely resumes the admissions workflow from a designated stage without repeating completed actions.
    - Preserves confidence thresholds, eligibility rules, and human-approval gates.
    - Prevents duplicate S1 triggers, duplicate messages, and duplicate pending approvals.
    - Respects opt-out safeguards (refuses resumption if opted out).
    """
    conn = get_db_connection(db_path)
    cur = conn.cursor()
    cur.execute("SELECT * FROM leads WHERE lead_id = ?;", (lead_id,))
    lead_row = cur.fetchone()
    conn.close()

    if not lead_row:
        return None

    if lead_row["opt_out_status"]:
        # Rule R6: Opt-out student cannot be resumed in active pipeline
        return None

    extracted = {}
    if lead_row["extracted_fields_json"]:
        try:
            extracted = json.loads(lead_row["extracted_fields_json"])
        except Exception:
            extracted = {}

    score = None
    if lead_row["score_breakdown_json"]:
        try:
            score = json.loads(lead_row["score_breakdown_json"])
        except Exception:
            score = None

    state: AdmissionsState = {
        "lead_id": lead_id,
        "channel": lead_row["channel"] or "Web Chat",
        "name": lead_row["name"],
        "phone": lead_row["phone"],
        "email": lead_row["email"],
        "student_message": lead_row["student_message"],
        "extracted": extracted,
        "rag_result": None,
        "score": score,
        "policy_decision": None,
        "proposal": None,
        "current_stage": resume_from_stage,
        "current_status": "In Progress",
        "clarification_count": lead_row["clarification_count"] or 0,
        "escalation_flag": False,
        "escalation_reason": None,
        "requires_approval": False,
        "is_paused": False,
        "error": None,
        "db_path": db_path
    }

    # Sequence of lifecycle stages. S1_Trigger is NEVER executed during resumption.
    stages = ["S2_Extraction", "S3_RAG", "S4_Validation", "S5_Scoring", "S6_Allocation"]
    if resume_from_stage not in stages:
        resume_from_stage = "S5_Scoring"

    start_idx = stages.index(resume_from_stage)

    for stage in stages[start_idx:]:
        if stage == "S2_Extraction":
            out = node_s2_extraction(state)
            state.update(out)
        elif stage == "S3_RAG":
            out = node_s3_grounded_rag(state)
            state.update(out)
            if state.get("escalation_flag"):
                break
        elif stage == "S4_Validation":
            out = node_s4_validation(state)
            state.update(out)
            if state.get("is_paused") or state.get("current_stage") in ["Merged", "Closed", "Lead_Desk"]:
                break
        elif stage == "S5_Scoring":
            out = node_s5_scoring(state)
            state.update(out)
        elif stage == "S6_Allocation":
            out = node_s6_allocation(state)
            state.update(out)

    return state
