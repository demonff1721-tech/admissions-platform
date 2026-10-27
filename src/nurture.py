"""Multi-day nurture journey simulator with stateful progression, reply handling, and re-scoring."""

import json
import uuid
from datetime import datetime
from typing import Dict, Any, Optional, Tuple, List
from src.database import get_db_connection
from src.security import is_contact_permitted
from src.scoring import score_lead
from src.models import ExtractedFields, ScoreBreakdown, LeadRecord
from src.policy_engine import evaluate_policy
from src.audit import log_audit_event
from src.counsellor_optimizer import propose_counsellor_for_lead
from src.exception_handler import raise_exception
from src.extraction import extract_information


NURTURE_STAGES = [
    {
        "stage": "N1_Day0",
        "day": 0,
        "title": "N1: Programme Overview",
        "template": (
            "Hi {name}, thank you for your interest in Alliance University's {programme} program. "
            "Our curriculum is designed with industry leaders to give you real-world exposure and career acceleration. "
            "Explore our program curriculum here: https://www.alliance.edu.in/programmes"
        )
    },
    {
        "stage": "N2_Day2",
        "day": 2,
        "title": "N2: Eligibility & Qualification Confirmation",
        "template": (
            "Hi {name}, for admission to {programme}, the published eligibility criteria requires a recognized degree/qualifying exam "
            "with minimum 50% aggregate marks. Have you received your final results, or are you appearing for your final semester?"
        )
    },
    {
        "stage": "N3_Day4",
        "day": 4,
        "title": "N3: Application Steps & Upcoming Deadlines",
        "template": (
            "Hello {name}, admissions for the 2026 intake at Alliance University are now actively open! "
            "The upcoming application deadline for Round 1 is approaching. You can complete your online form in under 15 minutes: "
            "https://apply.alliance.edu.in"
        )
    },
    {
        "stage": "N4_Day7",
        "day": 7,
        "title": "N4: Application Intent & Counsellor Check",
        "template": (
            "Hi {name}, would you like to speak directly with an Alliance University admissions faculty counsellor this week? "
            "Our counsellors can help review your profile, answer questions regarding scholarships, and guide you through the interview process."
        )
    },
    {
        "stage": "N5_Readiness",
        "day": 10,
        "title": "N5: Final Readiness Route",
        "template": (
            "Hi {name}, we noticed you are exploring our {programme} program for 2026. "
            "Would you like us to schedule a personalized 1-on-1 consultation session with our department head?"
        )
    }
]


def send_next_nurture_message(lead_id: str, db_path: Optional[str] = None) -> Tuple[bool, str, Optional[str]]:
    """
    Simulates sending the next sequential nurture message according to rules:
    - Verifies contact permitted (consent=1, opt_out=0, sent < 5)
    - Enforces max 1 message/day
    - Updates lead stage and increments message count
    """
    permitted, reason = is_contact_permitted(lead_id, db_path)
    if not permitted:
        return False, reason, None

    conn = get_db_connection(db_path)
    cur = conn.cursor()
    cur.execute("""
    SELECT lead_id, name, programme_interest, nurture_stage, nurture_messages_sent, current_stage, channel
    FROM leads WHERE lead_id = ?;
    """, (lead_id,))
    lead = cur.fetchone()

    if not lead:
        conn.close()
        return False, "Lead record not found.", None

    sent_count = lead["nurture_messages_sent"]
    if sent_count >= len(NURTURE_STAGES):
        conn.close()
        return False, "Nurture sequence complete. Maximum 5 touchpoints sent.", None

    next_touchpoint = NURTURE_STAGES[sent_count]
    now_iso = datetime.now().isoformat()
    content = next_touchpoint["template"].format(
        name=lead["name"],
        programme=lead["programme_interest"] or "Management"
    )

    # Insert outgoing message
    msg_id = f"MSG-NURTURE-{lead_id}-{sent_count + 1}"
    cur.execute("""
    INSERT INTO messages (message_id, lead_id, timestamp, direction, channel, message_type, content, content_source, delivery_status)
    VALUES (?, ?, ?, 'outgoing', ?, 'nurture', ?, 'template', 'Delivered');
    """, (msg_id, lead_id, now_iso, lead["channel"], content))

    # Update lead record
    cur.execute("""
    UPDATE leads
    SET nurture_stage = ?,
        nurture_messages_sent = nurture_messages_sent + 1,
        last_contact_at = ?,
        current_stage = 'S7_Nurturing',
        current_status = 'In Nurture',
        updated_at = ?
    WHERE lead_id = ?;
    """, (next_touchpoint["stage"], now_iso, now_iso, lead_id))

    conn.commit()
    conn.close()

    log_audit_event(
        lead_id=lead_id,
        workflow_stage="S7_Nurturing",
        action=f"Dispatched {next_touchpoint['title']}",
        autonomy_level="Act then report",
        rule_id="R10",
        inputs={"stage": next_touchpoint["stage"], "sent_count": sent_count + 1},
        outputs={"message_id": msg_id, "content_preview": content[:60]},
        tool_invoked="nurture_dispatcher",
        db_path=db_path
    )

    return True, f"Successfully sent {next_touchpoint['title']}", content


def process_nurture_reply(
    lead_id: str,
    reply_type: str,  # "interested", "question", "objection", "not_now", "stop"
    reply_message: str,
    db_path: Optional[str] = None
) -> Dict[str, Any]:
    """
    Handles student reply in nurture stage:
    - Verifies opt-out status safeguard
    - Performs idempotency check on duplicate replies
    - Records incoming message
    - Evaluates intent and credential changes
    - Re-scores lead and checks safeguards
    - If promoted to High (R15), invokes Hungarian counsellor allocation and creates pending approval record
    - If counsellors saturated, triggers E6 / R12 capacity exception path
    - Preserves human approval pause (S8_Handoff_Approval)
    """
    conn = get_db_connection(db_path)
    cur = conn.cursor()
    cur.execute("SELECT * FROM leads WHERE lead_id = ?;", (lead_id,))
    row = cur.fetchone()
    if not row:
        conn.close()
        return {"success": False, "error": "Lead not found"}

    now_iso = datetime.now().isoformat()

    # 1. Safeguard: Block contact if lead has opted out
    if bool(row["opt_out_status"]) and reply_type != "stop":
        conn.close()
        return {
            "success": False,
            "error": "Contact blocked: Student opted out of communication (Rule R6)",
            "action": "Blocked",
            "rule": "R6",
            "promoted": False
        }

    # 2. Idempotency check: Avoid duplicate reply insertions within 2 seconds
    cur.execute("""
    SELECT message_id, timestamp FROM messages
    WHERE lead_id = ? AND direction = 'incoming' AND content = ?
    ORDER BY timestamp DESC LIMIT 1;
    """, (lead_id, reply_message))
    recent_msg = cur.fetchone()
    if recent_msg:
        try:
            prev_time = datetime.fromisoformat(recent_msg["timestamp"])
            if (datetime.fromisoformat(now_iso) - prev_time).total_seconds() < 2.0:
                if row["current_stage"] == "S8_Handoff_Approval":
                    conn.close()
                    return {
                        "success": True,
                        "action": "Already Promoted to High",
                        "rule": "R15",
                        "new_score": row["total_score"],
                        "promoted": True,
                        "assigned_counsellor": row["assigned_counsellor"],
                        "proposed_slot": row["proposed_slot"]
                    }
        except Exception:
            pass

    msg_id = f"MSG-REPLY-{lead_id}-{uuid.uuid4().hex[:6]}"

    # Record incoming message
    cur.execute("""
    INSERT INTO messages (message_id, lead_id, timestamp, direction, channel, message_type, content, content_source)
    VALUES (?, ?, ?, 'incoming', ?, ?, ?, 'student');
    """, (msg_id, lead_id, now_iso, row["channel"], reply_type, reply_message))

    # 3. Handle Opt-out
    if reply_type == "stop" or "stop" in reply_message.lower():
        cur.execute("""
        UPDATE leads 
        SET opt_out_status = 1, current_stage = 'Closed', current_status = 'Opted Out', updated_at = ? 
        WHERE lead_id = ?;
        """, (now_iso, lead_id))
        conn.commit()
        conn.close()
        log_audit_event(lead_id, "S7_Nurturing", "Student opted out; nurture closed", "Act then report", "R6", db_path=db_path)
        return {"success": True, "action": "Opted Out", "rule": "R6", "promoted": False}

    # 4. Handle Promotion to High
    elif reply_type in ["interested", "counsellor_request"] or "counsellor" in reply_message.lower():
        # Extract any updated credentials from the reply message
        reply_ext = extract_information(reply_message)
        edu_val = reply_ext.education if reply_ext.education else row["education"]
        prog_val = reply_ext.programme_interest if reply_ext.programme_interest else row["programme_interest"]

        extracted = ExtractedFields(
            programme_interest=prog_val,
            education=edu_val,
            work_experience=row["work_experience"],
            intended_intake="2026",
            application_readiness="Ready to apply",
            primary_concern="counsellor",
            wants_counsellor=True,
            message_type="interest"
        )
        new_score = score_lead(extracted)

        # Safeguard: if lead qualifications are uncertain or ineligible, route appropriately
        if new_score.is_uncertain:
            exc_reason = f"E2: Incomplete or uncertain credentials during nurture promotion ({'; '.join(new_score.uncertain_reasons)})"
            cur.execute("""
            UPDATE leads
            SET total_score = ?, classification = 'Uncertain', score_breakdown_json = ?,
                current_stage = 'Exception_Desk', current_status = 'Open Exception',
                escalation_flag = 1, escalation_reason = ?, updated_at = ?
            WHERE lead_id = ?;
            """, (new_score.total_score, new_score.model_dump_json(), exc_reason, now_iso, lead_id))
            conn.commit()
            conn.close()
            log_audit_event(lead_id, "S7_Nurturing", f"Reply caused uncertain classification: {exc_reason}", "Act then report", "R3", db_path=db_path)
            return {"success": True, "action": "Escalated Uncertain", "rule": "R3", "new_score": new_score.total_score, "promoted": False, "exception": "E2"}

        if new_score.classification != "High":
            cur.execute("""
            UPDATE leads
            SET total_score = ?, classification = ?, score_breakdown_json = ?, updated_at = ?
            WHERE lead_id = ?;
            """, (new_score.total_score, new_score.classification, new_score.model_dump_json(), now_iso, lead_id))
            conn.commit()
            conn.close()
            log_audit_event(lead_id, "S7_Nurturing", f"Reply logged; score updated to {new_score.total_score} ({new_score.classification})", "Act then report", "R10", db_path=db_path)
            return {"success": True, "action": "Reply logged", "rule": "R10", "new_score": new_score.total_score, "promoted": False}

        # Lead qualifies as High -> Invoke Hungarian counsellor allocation optimizer
        lead_dict = dict(row)
        lead_dict["programme_interest"] = prog_val
        lead_dict["education"] = edu_val
        lead_dict["intended_intake"] = "2026"
        lead_dict["application_readiness"] = "Ready to apply"
        lead_dict["total_score"] = new_score.total_score
        lead_dict["classification"] = "High"
        lead_rec = LeadRecord(**lead_dict)

        proposal = propose_counsellor_for_lead(lead_rec, student_language="English", db_path=db_path)

        if not proposal:
            # Capacity saturation exception path (E6 / R12)
            exc_reason = "E6: Counsellor Unavailable or at Capacity - All counsellors at capacity (R12)"
            cur.execute("""
            UPDATE leads
            SET intended_intake = '2026',
                application_readiness = 'Ready to apply',
                total_score = ?,
                classification = ?,
                score_breakdown_json = ?,
                current_stage = 'Counsellor_Desk',
                current_status = 'Waitlisted Capacity',
                escalation_flag = 1,
                escalation_reason = ?,
                updated_at = ?
            WHERE lead_id = ?;
            """, (new_score.total_score, new_score.classification, new_score.model_dump_json(), exc_reason, now_iso, lead_id))
            conn.commit()
            conn.close()

            raise_exception(
                lead_id=lead_id,
                exception_type="E6",
                explanation="All counsellors at capacity (R12) during nurture promotion",
                last_valid_state="S7_Nurturing",
                db_path=db_path
            )

            log_audit_event(
                lead_id=lead_id,
                workflow_stage="S7_Nurturing",
                action=f"Reply promoted score to {new_score.total_score} (High), but counsellors at capacity; waitlisted under R12",
                autonomy_level="Suggest",
                rule_id="R12",
                db_path=db_path
            )

            return {
                "success": True,
                "action": "Waitlisted Capacity",
                "rule": "R12",
                "new_score": new_score.total_score,
                "promoted": False,
                "exception": "E6"
            }

        # Proposal generated successfully: Update lead and create pending approval record
        approval_id = f"APP-{lead_id}-{uuid.uuid4().hex[:6]}"
        proposed_action = f"Allocate {proposal.counsellor_name} ({proposal.proposed_slot})"
        approval_comment = f"Promoted to High from nurture (Score: {new_score.total_score}). Hungarian cost: {proposal.cost}."

        cur.execute("""
        UPDATE leads
        SET intended_intake = '2026',
            application_readiness = 'Ready to apply',
            total_score = ?,
            classification = ?,
            score_breakdown_json = ?,
            assigned_counsellor = ?,
            proposed_slot = ?,
            current_stage = 'S8_Handoff_Approval',
            current_status = 'Awaiting Approval',
            updated_at = ?
        WHERE lead_id = ?;
        """, (
            new_score.total_score, new_score.classification, new_score.model_dump_json(),
            proposal.counsellor_name, proposal.proposed_slot, now_iso, lead_id
        ))

        cur.execute("""
        INSERT OR REPLACE INTO approvals 
        (approval_id, lead_id, proposed_action, decision, approving_person, comments, timestamp, previous_state, updated_state)
        VALUES (?, ?, ?, 'Pending', NULL, ?, ?, 'S7_Nurturing', 'S8_Handoff_Approval');
        """, (approval_id, lead_id, proposed_action, approval_comment, now_iso))

        conn.commit()
        conn.close()

        log_audit_event(
            lead_id=lead_id,
            workflow_stage="S7_Nurturing",
            action=f"Reply promoted lead to High (Score: {new_score.total_score}); proposed {proposal.counsellor_name} ({proposal.proposed_slot})",
            autonomy_level="Approve",
            rule_id="R15",
            approval_ref=approval_id,
            inputs={"reply_type": reply_type, "reply_message": reply_message},
            outputs={
                "new_score": new_score.total_score,
                "classification": new_score.classification,
                "counsellor": proposal.counsellor_name,
                "slot": proposal.proposed_slot,
                "cost": proposal.cost
            },
            db_path=db_path
        )

        return {
            "success": True,
            "action": "Promoted to High",
            "rule": "R15",
            "new_score": new_score.total_score,
            "promoted": True,
            "proposal": proposal.model_dump(),
            "assigned_counsellor": proposal.counsellor_name,
            "proposed_slot": proposal.proposed_slot,
            "approval_id": approval_id
        }

    else:
        # General question or objection
        cur.execute("UPDATE leads SET updated_at = ? WHERE lead_id = ?;", (now_iso, lead_id))
        conn.commit()
        conn.close()
        return {"success": True, "action": "Reply logged", "rule": "R10", "promoted": False}
