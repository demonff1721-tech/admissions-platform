"""Append-only audit trail logging and compliance reporting."""

import json
from datetime import datetime
from typing import Dict, Any, Optional, List
import pandas as pd
from src.database import get_db_connection


def log_audit_event(
    lead_id: str,
    workflow_stage: str,
    action: str,
    autonomy_level: str,
    rule_id: Optional[str] = None,
    inputs: Optional[Dict[str, Any]] = None,
    outputs: Optional[Dict[str, Any]] = None,
    tool_invoked: Optional[str] = None,
    approval_ref: Optional[str] = None,
    error_details: Optional[str] = None,
    db_path: Optional[str] = None
) -> str:
    """
    Appends an immutable audit event to SQLite.
    Performs idempotency check to avoid duplicate events created by Streamlit page rerenders.
    """
    conn = get_db_connection(db_path)
    cur = conn.cursor()

    now_iso = datetime.now().isoformat()
    inp_str = json.dumps(inputs or {})
    out_str = json.dumps(outputs or {})

    # Check idempotency: If identical action on same lead in same stage happened in the last 2 seconds, reuse
    cur.execute("""
    SELECT event_id, timestamp FROM audit_events
    WHERE lead_id = ? AND workflow_stage = ? AND action = ?
    ORDER BY timestamp DESC LIMIT 1;
    """, (lead_id, workflow_stage, action))
    recent = cur.fetchone()

    if recent:
        try:
            prev_time = datetime.fromisoformat(recent["timestamp"])
            curr_time = datetime.fromisoformat(now_iso)
            if (curr_time - prev_time).total_seconds() < 2.0:
                conn.close()
                return recent["event_id"]
        except Exception:
            pass

    import uuid
    event_id = f"EVT-{datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6]}"

    cur.execute("""
    INSERT INTO audit_events 
    (event_id, timestamp, lead_id, workflow_stage, rule_id, action, inputs, output, tool_invoked, autonomy_level, approval_ref, error_details)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
    """, (
        event_id, now_iso, lead_id, workflow_stage, rule_id, action,
        inp_str, out_str, tool_invoked, autonomy_level, approval_ref, error_details
    ))

    conn.commit()
    conn.close()
    return event_id


def query_audit_trail(
    lead_id: Optional[str] = None,
    workflow_stage: Optional[str] = None,
    rule_id: Optional[str] = None,
    limit: int = 100,
    db_path: Optional[str] = None
) -> pd.DataFrame:
    """Queries audit events with optional filters, returning a pandas DataFrame."""
    conn = get_db_connection(db_path)
    
    query = "SELECT * FROM audit_events WHERE 1=1"
    params = []

    if lead_id:
        query += " AND lead_id = ?"
        params.append(lead_id)
    if workflow_stage and workflow_stage != "All":
        query += " AND workflow_stage = ?"
        params.append(workflow_stage)
    if rule_id and rule_id != "All":
        query += " AND rule_id = ?"
        params.append(rule_id)

    query += " ORDER BY timestamp DESC LIMIT ?;"
    params.append(limit)

    df = pd.read_sql_query(query, conn, params=params)
    conn.close()
    return df
