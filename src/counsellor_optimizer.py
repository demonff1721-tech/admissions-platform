"""Counsellor allocation optimizer using SciPy linear assignment (Hungarian method) and multi-factor cost."""

import json
import uuid
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
import numpy as np
from scipy.optimize import linear_sum_assignment
from src.models import CounsellorProposal, CounsellorRecord, LeadRecord
from src.database import get_db_connection


def calculate_assignment_cost(
    programme_interest: Optional[str],
    student_language: str,
    counsellor: CounsellorRecord
) -> Tuple[float, bool, bool]:
    """
    Computes cost = 10 * programme_mismatch + 3 * language_mismatch + 1 * active_high_leads.
    Returns (cost, specialisation_match, language_match).
    """
    prog = (programme_interest or "").lower().strip()
    
    # Check specialisation match
    spec_match = False
    for spec in counsellor.specialisations:
        spec_lower = spec.lower().strip()
        if spec_lower == prog or spec_lower in prog or prog in spec_lower:
            spec_match = True
            break
            
    # Check language match
    lang_match = any(student_language.lower() in l.lower() for l in counsellor.languages)
    
    prog_penalty = 0.0 if spec_match else 10.0
    lang_penalty = 0.0 if lang_match else 3.0
    load_penalty = float(counsellor.active_high_leads)
    
    total_cost = prog_penalty + lang_penalty + load_penalty
    return total_cost, spec_match, lang_match


def get_available_counsellors(db_path: Optional[str] = None) -> List[CounsellorRecord]:
    """Fetches counsellor roster from database."""
    conn = get_db_connection(db_path)
    cur = conn.cursor()
    cur.execute("""
    SELECT counsellor_id, name, specialisations, languages, active_high_leads, capacity, available_slots, is_available
    FROM counsellors
    ORDER BY counsellor_id ASC;
    """)
    rows = cur.fetchall()
    conn.close()

    counsellors = []
    for r in rows:
        counsellors.append(CounsellorRecord(
            counsellor_id=r["counsellor_id"],
            name=r["name"],
            specialisations=json.loads(r["specialisations"]),
            languages=json.loads(r["languages"]),
            active_high_leads=r["active_high_leads"],
            capacity=r["capacity"],
            available_slots=json.loads(r["available_slots"]),
            is_available=bool(r["is_available"])
        ))
    return counsellors


def propose_counsellor_for_lead(
    lead: LeadRecord,
    student_language: str = "English",
    db_path: Optional[str] = None
) -> Optional[CounsellorProposal]:
    """
    Finds the optimal counsellor for a single High-intent lead.
    Enforces capacity limit <= 8 and chooses next available 24h slot.
    Returns CounsellorProposal or None if all counsellors are at capacity (triggering R12).
    """
    counsellors = get_available_counsellors(db_path)
    
    # Filter counsellors that are available and under capacity limit (strictly < capacity)
    eligible = [
        c for c in counsellors 
        if c.is_available and c.active_high_leads < c.capacity and len(c.available_slots) > 0
    ]

    if not eligible:
        return None  # Triggers R12 capacity re-planning

    ranked = []
    for c in eligible:
        cost, spec_match, lang_match = calculate_assignment_cost(
            lead.programme_interest,
            student_language,
            c
        )
        ranked.append({
            "counsellor": c,
            "cost": cost,
            "spec_match": spec_match,
            "lang_match": lang_match,
            "slot": c.available_slots[0]
        })

    # Sort primarily by cost, secondarily by counsellor_id for deterministic tie breaking
    ranked.sort(key=lambda x: (x["cost"], x["counsellor"].counsellor_id))

    best = ranked[0]
    alternatives = [
        {
            "counsellor_id": item["counsellor"].counsellor_id,
            "name": item["counsellor"].name,
            "cost": item["cost"],
            "specialisation_match": item["spec_match"],
            "language_match": item["lang_match"],
            "active_leads": item["counsellor"].active_high_leads,
            "proposed_slot": item["slot"]
        }
        for item in ranked[1:]
    ]

    return CounsellorProposal(
        counsellor_id=best["counsellor"].counsellor_id,
        counsellor_name=best["counsellor"].name,
        cost=best["cost"],
        specialisation_match=best["spec_match"],
        language_match=best["lang_match"],
        current_load=best["counsellor"].active_high_leads,
        proposed_slot=best["slot"],
        alternative_counsellors=alternatives,
        status="Proposed"
    )


def batch_assign_counsellors(
    leads: List[LeadRecord],
    student_languages: Optional[List[str]] = None,
    db_path: Optional[str] = None
) -> Dict[str, Optional[CounsellorProposal]]:
    """
    Solves multi-lead global assignment using SciPy's Hungarian algorithm (linear_sum_assignment).
    Guarantees no double-booking of counsellor slots and minimizes overall system cost.
    """
    if not leads:
        return {}

    counsellors = get_available_counsellors(db_path)
    eligible_counsellors = [
        c for c in counsellors 
        if c.is_available and c.active_high_leads < c.capacity and len(c.available_slots) > 0
    ]

    if not eligible_counsellors:
        return {lead.lead_id: None for lead in leads}

    if len(leads) == 1:
        lang = student_languages[0] if student_languages else "English"
        return {leads[0].lead_id: propose_counsellor_for_lead(leads[0], lang, db_path)}

    # Build cost matrix: rows = leads, columns = eligible counsellors
    cost_matrix = np.zeros((len(leads), len(eligible_counsellors)))
    for i, lead in enumerate(leads):
        lang = student_languages[i] if student_languages and i < len(student_languages) else "English"
        for j, c in enumerate(eligible_counsellors):
            cost, _, _ = calculate_assignment_cost(lead.programme_interest, lang, c)
            cost_matrix[i, j] = cost

    row_ind, col_ind = linear_sum_assignment(cost_matrix)
    assignments: Dict[str, Optional[CounsellorProposal]] = {}

    assigned_slots: Dict[str, List[str]] = {}

    for r, c in zip(row_ind, col_ind):
        lead = leads[r]
        counsellor = eligible_counsellors[c]
        lang = student_languages[r] if student_languages and r < len(student_languages) else "English"
        cost, spec_match, lang_match = calculate_assignment_cost(lead.programme_interest, lang, counsellor)
        
        # Pick slot avoiding double-booking
        used_slots = assigned_slots.get(counsellor.counsellor_id, [])
        available = [s for s in counsellor.available_slots if s not in used_slots]
        
        if available:
            slot = available[0]
            assigned_slots.setdefault(counsellor.counsellor_id, []).append(slot)
            assignments[lead.lead_id] = CounsellorProposal(
                counsellor_id=counsellor.counsellor_id,
                counsellor_name=counsellor.name,
                cost=cost,
                specialisation_match=spec_match,
                language_match=lang_match,
                current_load=counsellor.active_high_leads,
                proposed_slot=slot,
                status="Proposed"
            )
        else:
            assignments[lead.lead_id] = None

    # Handle unassigned leads if leads > counsellors
    for lead in leads:
        if lead.lead_id not in assignments:
            assignments[lead.lead_id] = None

    return assignments


def execute_allocation_approval(
    lead_id: str,
    counsellor_id: str,
    slot: str,
    operator: str,
    decision: str,  # "Approved" or "Rejected"
    comments: Optional[str] = None,
    db_path: Optional[str] = None
) -> bool:
    """Records human operator approval/rejection for counsellor handoff, updates lead and roster, and logs audit event transactionally."""
    conn = get_db_connection(db_path)
    cur = conn.cursor()

    cur.execute("SELECT lead_id, current_stage, current_status, assigned_counsellor, proposed_slot FROM leads WHERE lead_id = ?;", (lead_id,))
    lead_row = cur.fetchone()
    if not lead_row:
        conn.close()
        return False

    now_iso = datetime.now().isoformat()

    # Idempotency check: prevent duplicate approvals/audits if retried within 2 seconds
    cur.execute("""
    SELECT approval_id, timestamp FROM approvals
    WHERE lead_id = ? AND decision = ? AND approving_person = ?
    ORDER BY timestamp DESC LIMIT 1;
    """, (lead_id, decision, operator))
    recent_app = cur.fetchone()
    if recent_app:
        try:
            prev_time = datetime.fromisoformat(recent_app["timestamp"])
            if (datetime.fromisoformat(now_iso) - prev_time).total_seconds() < 2.0:
                conn.close()
                return True
        except Exception:
            pass

    approval_id = f"APP-{lead_id}-{uuid.uuid4().hex[:6]}"
    event_id = f"EVT-{datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6]}"

    try:
        if decision == "Approved":
            # Lookup counsellor name
            cur.execute("SELECT name FROM counsellors WHERE counsellor_id = ?;", (counsellor_id,))
            c_row = cur.fetchone()
            counsellor_name = c_row["name"] if c_row else (lead_row["assigned_counsellor"] or counsellor_id)

            # 1. Update lead record
            cur.execute("""
            UPDATE leads
            SET current_stage = 'Confirmed_Handoff',
                current_status = 'Handoff Confirmed',
                assigned_counsellor = ?,
                proposed_slot = ?,
                approved_by = ?,
                updated_at = ?
            WHERE lead_id = ?;
            """, (counsellor_name, slot, operator, now_iso, lead_id))

            # 2. Increment active high leads on counsellor (only if not already confirmed)
            if lead_row["current_stage"] != "Confirmed_Handoff":
                cur.execute("""
                UPDATE counsellors
                SET active_high_leads = active_high_leads + 1
                WHERE counsellor_id = ?;
                """, (counsellor_id,))

            # 3. Insert approval record
            rationale = comments or "Handoff confirmed by counsellor desk"
            cur.execute("""
            INSERT INTO approvals (approval_id, lead_id, proposed_action, decision, approving_person, comments, timestamp, previous_state, updated_state)
            VALUES (?, ?, ?, 'Approved', ?, ?, ?, 'S8_Handoff_Approval', 'Confirmed_Handoff');
            """, (approval_id, lead_id, f"Allocate {counsellor_name} ({slot})", operator, rationale, now_iso))

            # 4. Insert audit event record in the same atomic transaction
            inp_data = {
                "counsellor_id": counsellor_id,
                "counsellor_name": counsellor_name,
                "slot": slot,
                "operator": operator,
                "decision": "Approved",
                "comments": rationale
            }
            out_data = {
                "updated_stage": "Confirmed_Handoff",
                "updated_status": "Handoff Confirmed",
                "assigned_counsellor": counsellor_name,
                "proposed_slot": slot
            }
            cur.execute("""
            INSERT INTO audit_events 
            (event_id, timestamp, lead_id, workflow_stage, rule_id, action, inputs, output, tool_invoked, autonomy_level, approval_ref, error_details)
            VALUES (?, ?, ?, 'S8_Handoff_Approval', 'R9', ?, ?, ?, 'counsellor_approval_desk', 'Approve', ?, NULL);
            """, (
                event_id, now_iso, lead_id,
                f"Handoff Allocation Approved: {counsellor_name} ({slot})",
                json.dumps(inp_data), json.dumps(out_data),
                approval_id
            ))

        else:
            # Rejection
            counsellor_name = lead_row["assigned_counsellor"] or counsellor_id
            rationale = comments or "Rejected by counsellor desk"

            # 1. Update lead record
            cur.execute("""
            UPDATE leads
            SET current_stage = 'S8_Handoff_Approval',
                current_status = 'Allocation Rejected',
                updated_at = ?
            WHERE lead_id = ?;
            """, (now_iso, lead_id))

            # 2. Insert approval record
            cur.execute("""
            INSERT INTO approvals (approval_id, lead_id, proposed_action, decision, approving_person, comments, timestamp, previous_state, updated_state)
            VALUES (?, ?, ?, 'Rejected', ?, ?, ?, 'S8_Handoff_Approval', 'Allocation Rejected');
            """, (approval_id, lead_id, f"Allocate {counsellor_name} ({slot})", operator, rationale, now_iso))

            # 3. Insert audit event record in the same atomic transaction
            inp_data = {
                "counsellor_id": counsellor_id,
                "slot": slot,
                "operator": operator,
                "decision": "Rejected",
                "comments": rationale
            }
            out_data = {
                "updated_stage": "S8_Handoff_Approval",
                "updated_status": "Allocation Rejected"
            }
            cur.execute("""
            INSERT INTO audit_events 
            (event_id, timestamp, lead_id, workflow_stage, rule_id, action, inputs, output, tool_invoked, autonomy_level, approval_ref, error_details)
            VALUES (?, ?, ?, 'S8_Handoff_Approval', 'R9', ?, ?, ?, 'counsellor_approval_desk', 'Approve', ?, ?);
            """, (
                event_id, now_iso, lead_id,
                f"Handoff Allocation Rejected: {counsellor_name} ({slot})",
                json.dumps(inp_data), json.dumps(out_data),
                approval_id,
                rationale
            ))

        conn.commit()
        return True
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
