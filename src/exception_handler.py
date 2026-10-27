"""Central exception desk and recovery manager covering all 7 exception paths (E1-E7)."""

import json
from datetime import datetime
from typing import Dict, Any, Optional, List
from src.database import get_db_connection
from src.audit import log_audit_event


EXCEPTION_DEFINITIONS = {
    "E1": {
        "title": "Unsupported Question / Complaint / Special Category",
        "severity": "Medium",
        "detection_rule": "R5",
        "recommended_action": "Review student query, consult admissions faculty, and draft manual grounded response."
    },
    "E2": {
        "title": "Contradictory or Missing Information",
        "severity": "Low",
        "detection_rule": "R3",
        "recommended_action": "Contact applicant via phone/email to verify qualifying credentials or intake."
    },
    "E3": {
        "title": "Duplicate Lead Detection",
        "severity": "Medium",
        "detection_rule": "R8",
        "recommended_action": "Review case histories and confirm whether records should be merged."
    },
    "E4": {
        "title": "Opt-Out Request",
        "severity": "High",
        "detection_rule": "R6",
        "recommended_action": "Confirm contact suppression across all channels and close lead journey."
    },
    "E5": {
        "title": "Non-Response / Nurture Exhaustion",
        "severity": "Low",
        "detection_rule": "R14",
        "recommended_action": "Place lead in low-frequency broadcast track or schedule Day-14 follow-up."
    },
    "E6": {
        "title": "Counsellor Unavailable or at Capacity",
        "severity": "High",
        "detection_rule": "R12",
        "recommended_action": "Review waitlist, allocate next-day slot, or assign overflow counsellor."
    },
    "E7": {
        "title": "Tool or Model Failure",
        "severity": "Critical",
        "detection_rule": "R13",
        "recommended_action": "Inspect last valid workflow state, verify inputs, and resume pipeline manually."
    }
}


def raise_exception(
    lead_id: str,
    exception_type: str,  # E1 to E7
    explanation: str,
    last_valid_state: str,
    owner_queue: str = "Admissions Operations",
    db_path: Optional[str] = None
) -> str:
    """Marks lead with escalation flag and records exception event."""
    conn = get_db_connection(db_path)
    cur = conn.cursor()

    defn = EXCEPTION_DEFINITIONS.get(exception_type, {
        "title": "General Admissions Exception",
        "severity": "Medium",
        "detection_rule": "R5",
        "recommended_action": "Manual review required."
    })

    full_reason = f"{exception_type}: {defn['title']} - {explanation}"
    now_iso = datetime.now().isoformat()

    cur.execute("""
    UPDATE leads
    SET escalation_flag = 1,
        escalation_reason = ?,
        classification = 'Uncertain',
        current_stage = 'Exception_Desk',
        current_status = 'Open Exception',
        updated_at = ?
    WHERE lead_id = ?;
    """, (full_reason, now_iso, lead_id))

    conn.commit()
    conn.close()

    log_audit_event(
        lead_id=lead_id,
        workflow_stage="Exception_Desk",
        action=f"Raised {exception_type}: {defn['title']}",
        autonomy_level="Act then report",
        rule_id=defn["detection_rule"],
        inputs={"last_valid_state": last_valid_state, "severity": defn["severity"]},
        outputs={"escalation_reason": full_reason, "queue": owner_queue},
        error_details=explanation,
        db_path=db_path
    )

    return full_reason


def resolve_exception(
    lead_id: str,
    resolution_action: str,  # "Resolved & Resume Workflow", "Resolved", "Resumed", "Merged", "Closed", "Reassigned"
    resolution_notes: str,
    operator: str,
    target_stage: Optional[str] = None,
    db_path: Optional[str] = None,
    resume_workflow: Optional[bool] = None
) -> bool:
    """
    Resolves an open exception with strict policy validation and recovery:
    - Validates that resolution is permitted for the exception type (e.g. blocks resuming opted-out students under R6)
    - Retains original exception details in case_summary and audit trail
    - Provides idempotency to prevent duplicate resolution actions or duplicate side effects
    - Re-dispatches workflow from the designated stage without repeating completed actions
    """
    conn = get_db_connection(db_path)
    cur = conn.cursor()

    cur.execute("""
    SELECT lead_id, escalation_flag, escalation_reason, case_summary, opt_out_status, current_stage, current_status
    FROM leads
    WHERE lead_id = ?;
    """, (lead_id,))
    lead = cur.fetchone()

    if not lead:
        conn.close()
        return False

    now_iso = datetime.now().isoformat()

    # Determine whether workflow resumption is requested
    if resume_workflow is None:
        should_resume = "resume" in resolution_action.lower()
    else:
        should_resume = bool(resume_workflow)

    orig_reason = lead["escalation_reason"] or ""
    exc_type = orig_reason[:2] if orig_reason[:2] in EXCEPTION_DEFINITIONS else ""
    if not exc_type:
        for code in EXCEPTION_DEFINITIONS.keys():
            if code in orig_reason:
                exc_type = code
                break
    if not exc_type:
        exc_type = "E1"

    # 1. Validation for Exception Type: E4 (Opt-Out Request - Rule R6) cannot be resumed into active pipeline
    if exc_type == "E4" or bool(lead["opt_out_status"]):
        is_resume_attempt = should_resume or (target_stage and target_stage not in ["Closed", "Exception_Desk"])
        permitted_optout_actions = ["Closed", "Close Case (Ineligible / Out-of-Domain)", "Suppressed", "Confirm Opt-Out"]
        
        if is_resume_attempt and resolution_action not in permitted_optout_actions:
            cur.execute("""
            UPDATE leads
            SET current_status = 'Review: Cannot Resume Opted-Out Lead',
                case_summary = CASE 
                    WHEN case_summary IS NULL OR case_summary = '' 
                    THEN 'Resolution rejected: Cannot resume opted-out student (Rule R6)'
                    ELSE case_summary || ' | Resolution rejected: Cannot resume opted-out student (Rule R6)' 
                END,
                updated_at = ?
            WHERE lead_id = ?;
            """, (now_iso, lead_id))
            conn.commit()
            conn.close()

            log_audit_event(
                lead_id=lead_id,
                workflow_stage="Exception_Desk",
                action="Exception Resolution Rejected: Opt-Out Safeguard",
                autonomy_level="Reject",
                rule_id="R6",
                inputs={"operator": operator, "resolution_action": resolution_action, "original_exception": orig_reason},
                error_details="Cannot resume workflow for opted-out student (Rule R6). Contact suppression active.",
                db_path=db_path
            )
            return False

    # 2. Idempotency check: if already resolved and not in Open Exception state, no-op safely
    if lead["escalation_flag"] == 0 and lead["current_status"] != "Open Exception":
        conn.close()
        return True

    # Determine target stage & status
    if resolution_action in ["Closed", "Close Case (Ineligible / Out-of-Domain)"]:
        new_stage = "Closed"
        new_status = "Closed"
    else:
        new_stage = target_stage or "S5_Scoring"
        new_status = "In Progress"

    # Retain original exception details alongside resolution entry in case_summary
    orig_summary = lead["case_summary"] or ""
    resolution_entry = f"Exception [{orig_reason}] resolved by {operator} via '{resolution_action}': {resolution_notes}"
    new_summary = f"{orig_summary} | {resolution_entry}" if orig_summary else resolution_entry

    cur.execute("""
    UPDATE leads
    SET escalation_flag = 0,
        current_stage = ?,
        current_status = ?,
        case_summary = ?,
        updated_at = ?
    WHERE lead_id = ?;
    """, (new_stage, new_status, new_summary, now_iso, lead_id))

    conn.commit()
    conn.close()

    log_audit_event(
        lead_id=lead_id,
        workflow_stage="Exception_Desk",
        action=f"Exception Resolved: {resolution_action}",
        autonomy_level="Approve",
        inputs={"operator": operator, "resolution_notes": resolution_notes, "original_exception": orig_reason},
        outputs={"resumed_stage": new_stage, "new_status": new_status},
        db_path=db_path
    )

    # 3. Resume workflow from target stage if requested and not closed
    if should_resume and new_stage != "Closed":
        from src.agent_graph import resume_admissions_workflow
        resume_admissions_workflow(lead_id=lead_id, resume_from_stage=new_stage, db_path=db_path)

    return True


def list_open_exceptions(db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """Retrieves all leads with active escalation flags."""
    conn = get_db_connection(db_path)
    cur = conn.cursor()
    cur.execute("""
    SELECT lead_id, name, channel, programme_interest, total_score, classification,
           escalation_reason, current_stage, current_status, created_at, updated_at
    FROM leads
    WHERE escalation_flag = 1
    ORDER BY updated_at DESC;
    """)
    rows = cur.fetchall()
    conn.close()

    exceptions = []
    for r in rows:
        reason = r["escalation_reason"] or ""
        exc_type = reason[:2] if reason[:2] in EXCEPTION_DEFINITIONS else "E1"
        defn = EXCEPTION_DEFINITIONS.get(exc_type, EXCEPTION_DEFINITIONS["E1"])
        
        exceptions.append({
            "lead_id": r["lead_id"],
            "name": r["name"],
            "channel": r["channel"],
            "programme": r["programme_interest"],
            "score": r["total_score"],
            "classification": r["classification"],
            "exception_type": exc_type,
            "title": defn["title"],
            "severity": defn["severity"],
            "detection_rule": defn["detection_rule"],
            "explanation": reason,
            "recommended_action": defn["recommended_action"],
            "updated_at": r["updated_at"]
        })
    return exceptions
