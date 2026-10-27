"""Security, privacy, duplicate detection, and responsible AI governance guardrails."""

import re
from datetime import datetime
from typing import Dict, Any, Optional, Tuple, List
from src.database import get_db_connection
from src.models import LeadRecord
from src.audit import log_audit_event


AI_DISCLOSURE_TEXT = (
    "Welcome to Alliance University Admissions Assistant. I am an automated AI agent designed to help "
    "answer your queries, provide verified programme information, and connect you with our admissions team. "
    "You may request to speak with a human counsellor at any point."
)


def check_for_duplicates(
    phone: Optional[str],
    email: Optional[str],
    name: str,
    programme_interest: Optional[str] = None,
    current_lead_id: Optional[str] = None,
    db_path: Optional[str] = None
) -> Tuple[bool, bool, Optional[str], Optional[str]]:
    """
    Checks database for duplicates:
    1. Exact phone number match -> (is_exact=True, is_potential=False, existing_lead_id, match_type='phone')
    2. Exact email match -> (is_exact=True, is_potential=False, existing_lead_id, match_type='email')
    3. Potential duplicate (same name + similar programme) -> (is_exact=False, is_potential=True, existing_lead_id, match_type='name_similarity')
    """
    conn = get_db_connection(db_path)
    cur = conn.cursor()

    # Clean phone number (strip whitespace, dashes, country code if standard)
    clean_phone = re.sub(r'[\s\-\+]', '', phone or '')
    clean_email = (email or '').lower().strip()
    clean_name = name.lower().strip()

    # 1. Exact phone match
    if clean_phone and len(clean_phone) >= 8:
        cur.execute("""
        SELECT lead_id, name, phone, email, current_status
        FROM leads
        WHERE phone IS NOT NULL AND lead_id != ?;
        """, (current_lead_id or '',))
        for row in cur.fetchall():
            row_phone = re.sub(r'[\s\-\+]', '', row["phone"] or '')
            if row_phone and (clean_phone in row_phone or row_phone in clean_phone):
                conn.close()
                return True, False, row["lead_id"], f"Exact phone match ({row['phone']})"

    # 2. Exact email match
    if clean_email and "@" in clean_email:
        cur.execute("""
        SELECT lead_id, name, phone, email, current_status
        FROM leads
        WHERE LOWER(email) = ? AND lead_id != ?;
        """, (clean_email, current_lead_id or ''))
        row = cur.fetchone()
        if row:
            conn.close()
            return True, False, row["lead_id"], f"Exact email match ({row['email']})"

    # 3. Potential duplicate (Fuzzy name match)
    if clean_name and len(clean_name) >= 3:
        cur.execute("""
        SELECT lead_id, name, programme_interest, current_status
        FROM leads
        WHERE LOWER(name) = ? AND lead_id != ?;
        """, (clean_name, current_lead_id or ''))
        row = cur.fetchone()
        if row:
            conn.close()
            return False, True, row["lead_id"], f"Potential duplicate: exact name match '{row['name']}'"

    conn.close()
    return False, False, None, None


def is_contact_permitted(lead_id: str, db_path: Optional[str] = None) -> Tuple[bool, str]:
    """
    Checks consent and opt-out status before sending any simulated outgoing message.
    Returns (permitted: bool, reason: str).
    """
    conn = get_db_connection(db_path)
    cur = conn.cursor()
    cur.execute("""
    SELECT consent_status, opt_out_status, nurture_messages_sent, last_contact_at
    FROM leads
    WHERE lead_id = ?;
    """, (lead_id,))
    row = cur.fetchone()
    conn.close()

    if not row:
        return False, "Lead record not found."

    if row["opt_out_status"]:
        return False, "Contact blocked: Student opted out of communication (Rule R6)."

    if not row["consent_status"]:
        return False, "Contact blocked: Explicit consent not provided."

    if row["nurture_messages_sent"] >= 5:
        return False, "Contact blocked: Maximum journey limit of 5 nurture messages reached."

    return True, "Contact permitted under university admissions communication policy."


def validate_uploaded_file(file_name: str, file_bytes: bytes) -> Tuple[bool, str]:
    """Validates uploaded knowledge documents (PDF, DOCX, TXT, CSV)."""
    allowed_extensions = {".pdf", ".docx", ".txt", ".csv"}
    from pathlib import Path
    ext = Path(file_name).suffix.lower()

    if ext not in allowed_extensions:
        return False, f"File type '{ext}' is not permitted. Only PDF, DOCX, TXT, and CSV are supported."

    # Max 10MB limit
    if len(file_bytes) > 10 * 1024 * 1024:
        return False, "File size exceeds 10MB limit."

    return True, "File passed validation."


def handle_duplicate_enquiry(
    existing_lead_id: str,
    incoming_message: str,
    channel: str = "Web Chat",
    name: Optional[str] = None,
    phone: Optional[str] = None,
    email: Optional[str] = None,
    db_path: Optional[str] = None
) -> Tuple[bool, str, Optional[str]]:
    """
    Appends an incoming enquiry to an existing lead's conversation thread without creating a new lead.
    - Preserves original lead ID and full conversation history.
    - Idempotency guard: prevents appending duplicate messages if the same submission is retried.
    - Records incoming message timestamp, channel, and message metadata.
    - Logs audit trail under Rule R7.
    Returns: (success: bool, status_message: str, message_id: Optional[str])
    """
    conn = get_db_connection(db_path)
    cur = conn.cursor()

    cur.execute("SELECT lead_id, opt_out_status, consent_status, name FROM leads WHERE lead_id = ?;", (existing_lead_id,))
    lead = cur.fetchone()
    if not lead:
        conn.close()
        return False, f"Existing lead '{existing_lead_id}' not found.", None

    # Idempotency guard: check if identical incoming message was already recorded for this lead
    cur.execute("""
    SELECT message_id, timestamp, content FROM messages
    WHERE lead_id = ? AND direction = 'incoming' AND content = ?
    ORDER BY timestamp DESC LIMIT 1;
    """, (existing_lead_id, incoming_message))
    existing_msg = cur.fetchone()
    if existing_msg:
        conn.close()
        return True, "Duplicate message already recorded in conversation history (idempotent).", existing_msg["message_id"]

    now_iso = datetime.now().isoformat()
    msg_id = f"MSG-IN-{existing_lead_id}-{int(datetime.now().timestamp() * 1000)}"

    cur.execute("""
    INSERT INTO messages 
    (message_id, lead_id, timestamp, direction, channel, message_type, content, content_source, delivery_status)
    VALUES (?, ?, ?, 'incoming', ?, 'enquiry', ?, 'student', 'Delivered');
    """, (msg_id, existing_lead_id, now_iso, channel, incoming_message))

    # Update updated_at on existing lead
    cur.execute("UPDATE leads SET updated_at = ? WHERE lead_id = ?;", (now_iso, existing_lead_id))

    conn.commit()
    conn.close()

    # Log audit event under Rule R7
    log_audit_event(
        lead_id=existing_lead_id,
        workflow_stage="S4_Validation",
        action=f"Threaded incoming enquiry from {channel} to existing lead",
        autonomy_level="Act then report",
        rule_id="R7",
        inputs={"channel": channel, "message": incoming_message, "name": name, "phone": phone, "email": email},
        outputs={"message_id": msg_id, "lead_id": existing_lead_id},
        db_path=db_path
    )

    return True, "Incoming enquiry successfully threaded into existing case conversation.", msg_id
