"""Deterministic policy engine implementing rules R1 through R15 with strict autonomy levels."""

from typing import Dict, Any, Optional, Tuple
from src.models import PolicyDecision, ScoreBreakdown, ExtractedFields, LeadRecord


def evaluate_policy(
    lead: LeadRecord,
    extracted: Optional[ExtractedFields] = None,
    score: Optional[ScoreBreakdown] = None,
    similarity_score: Optional[float] = None,
    is_exact_duplicate: bool = False,
    is_potential_duplicate: bool = False,
    opt_out_requested: bool = False,
    is_timeout_or_tool_failure: bool = False,
    capacity_exceeded: bool = False,
    unanswered_nurture_count: int = 0,
    reply_promoted_to_high: bool = False
) -> PolicyDecision:
    """
    Evaluates system and lead state against the 15 deterministic policy rules.
    Returns the selected PolicyDecision with rule ID, actions, autonomy level, and approval status.
    """
    prior_state = f"{lead.current_stage}:{lead.current_status}"

    # Rule R13: LLM timeout, invalid structured output, or empty retrieval after retries
    if is_timeout_or_tool_failure:
        return PolicyDecision(
            rule_id="R13",
            rule_name="Tool / Model Failure Recovery",
            trigger_condition="LLM timeout, invalid structured output or tool failure detected.",
            prior_state=prior_state,
            action_selected="Pause automation; hold case at last valid state; alert human exception desk.",
            result_state="Exception_Desk:Paused",
            autonomy_level="Act then report",
            requires_approval=False,
            explanation="Automation safely paused to prevent hallucination or data corruption; preserves last known valid state."
        )

    # Rule R6: Opt-out request
    if opt_out_requested or lead.opt_out_status:
        return PolicyDecision(
            rule_id="R6",
            rule_name="Opt-Out Enforcement",
            trigger_condition="Student requested to stop receiving messages or opted out.",
            prior_state=prior_state,
            action_selected="Immediately terminate nurture journey; mark opt_out_status=1; suppress all future contact.",
            result_state="Closed:Opted_Out",
            autonomy_level="Act then report",
            requires_approval=False,
            explanation="Student privacy and consent respected immediately. Nurture simulator blocked from further dispatch."
        )

    # Rule R7: Exact duplicate
    if is_exact_duplicate:
        return PolicyDecision(
            rule_id="R7",
            rule_name="Exact Duplicate Resolution",
            trigger_condition="Exact phone number or email address matches an active case in database.",
            prior_state=prior_state,
            action_selected="Link enquiry to existing case; suppress second independent journey; log notification.",
            result_state=f"Merged:{lead.duplicate_of or 'Existing_Case'}",
            autonomy_level="Act then report",
            requires_approval=False,
            explanation="Exact match prevents duplicate outbound communication and unified case history is maintained."
        )

    # Rule R8: Potential duplicate
    if is_potential_duplicate:
        return PolicyDecision(
            rule_id="R8",
            rule_name="Potential Duplicate Review",
            trigger_condition="Name and supporting background fields match an existing applicant with high similarity.",
            prior_state=prior_state,
            action_selected="Place lead on hold; route to human admissions queue for merge confirmation.",
            result_state="Lead_Desk:Hold_For_Verification",
            autonomy_level="Approve",
            requires_approval=True,
            explanation="Fuzzy matches must not merge records automatically without human confirmation."
        )

    # Rule R15: Nurture reply increases score >= 70 or requests counsellor
    if reply_promoted_to_high or (extracted and extracted.wants_counsellor and lead.current_stage == "S7_Nurturing"):
        return PolicyDecision(
            rule_id="R15",
            rule_name="Nurture-to-High Promotion",
            trigger_condition="Student nurture reply requested counsellor or improved qualifications yielding score >= 70.",
            prior_state=prior_state,
            action_selected="Promote case from nurture to High-lead counsellor allocation; compute slot and request approval.",
            result_state="S8_Handoff_Approval:Awaiting_Approval",
            autonomy_level="Approve",
            requires_approval=True,
            explanation="Lead demonstrated application readiness through nurturing interaction and is promoted to human handoff."
        )

    # Rule R14: Two consecutive unanswered nurture follow-ups
    if unanswered_nurture_count >= 2 and lead.current_stage == "S7_Nurturing":
        return PolicyDecision(
            rule_id="R14",
            rule_name="Nurture Non-Response Deprioritization",
            trigger_condition="Two consecutive simulated nurture follow-ups received no student response.",
            prior_state=prior_state,
            action_selected="Move lead to Low information track; schedule single Day-14 re-engagement message.",
            result_state="S7_Low_Track:Dormant",
            autonomy_level="Act then report",
            requires_approval=False,
            explanation="Suppresses spamming unresponsive prospects while preserving a scheduled Day-14 re-engagement touchpoint."
        )

    # Rule R3: Required fields missing after 2 requests
    if lead.clarification_count >= 2 and (not lead.programme_interest or not lead.education):
        return PolicyDecision(
            rule_id="R3",
            rule_name="Clarification Limit Exhaustion",
            trigger_condition="Essential qualifying fields remain missing after 2 automated clarification prompts.",
            prior_state=prior_state,
            action_selected="Mark classification as Uncertain; escalate case to admissions desk with context.",
            result_state="Exception_Desk:Uncertain_Escalated",
            autonomy_level="Act then report",
            requires_approval=False,
            explanation="Stops automated loop to avoid annoying the student; requires human admissions outreach."
        )

    # Rule R2: Required fields missing and fewer than 2 requests made
    if extracted and extracted.missing_fields and lead.clarification_count < 2 and not extracted.wants_counsellor:
        missing_desc = ", ".join(extracted.missing_fields)
        return PolicyDecision(
            rule_id="R2",
            rule_name="Targeted Clarification Request",
            trigger_condition=f"Crucial information missing ({missing_desc}) and clarification count ({lead.clarification_count}) < 2.",
            prior_state=prior_state,
            action_selected=f"Send polite clarification asking only for: {missing_desc}; increment clarification count.",
            result_state="Awaiting_Clarification",
            autonomy_level="Act then report",
            requires_approval=False,
            explanation="Gathers missing academic background or intended intake before running scoring and assignment."
        )

    # Rule R5: Unsupported question / complaint / exception
    if (extracted and extracted.message_type == "complaint") or (similarity_score is not None and similarity_score < 0.60 and extracted and extracted.message_type == "factual_question"):
        return PolicyDecision(
            rule_id="R5",
            rule_name="Out-of-Domain / Complaint Escalation",
            trigger_condition=f"Factual question similarity ({similarity_score or 0.0:.2f}) < 0.60 threshold or complaint detected.",
            prior_state=prior_state,
            action_selected="Inform student of team handoff; do not hallucinate answer; route case to Exception Desk.",
            result_state="Exception_Desk:Open_Exception",
            autonomy_level="Act then report",
            requires_approval=False,
            explanation="Strict anti-hallucination barrier. Questions not substantiated by approved knowledge base are escalated."
        )

    # Rule R4: Factual question with retrieval similarity >= 0.60
    if similarity_score is not None and similarity_score >= 0.60:
        return PolicyDecision(
            rule_id="R4",
            rule_name="Grounded Knowledge Answering",
            trigger_condition=f"Question matched approved knowledge base with similarity {similarity_score:.2f} >= 0.60.",
            prior_state=prior_state,
            action_selected="Generate grounded response using retrieved verified document; cite source URL.",
            result_state="Answered:Grounded",
            autonomy_level="Act then report",
            requires_approval=False,
            explanation="Direct factual answer synthesized strictly from approved institutional documentation with citation."
        )

    # Rule R12: Counsellors at capacity
    if capacity_exceeded and score and score.classification == "High":
        return PolicyDecision(
            rule_id="R12",
            rule_name="Capacity Saturation Re-Planning",
            trigger_condition="All eligible counsellors have reached their 8-lead capacity cap or no slot exists in 24h SLA.",
            prior_state=prior_state,
            action_selected="Execute re-planning: search next-day slots; place on high-priority waitlist; alert admissions manager.",
            result_state="Counsellor_Desk:Waitlisted_Capacity",
            autonomy_level="Suggest",
            requires_approval=True,
            explanation="Prevents counsellor overload and ensures manager oversight when capacity SLA is breached."
        )

    # Rule R9: High classification (Score >= 70, Eligibility > 0, No Escalation)
    if score and score.classification == "High":
        return PolicyDecision(
            rule_id="R9",
            rule_name="High-Intent Counsellor Proposal",
            trigger_condition="Total score >= 70, basic eligibility met, and zero escalation flags.",
            prior_state=prior_state,
            action_selected="Run Hungarian optimizer; propose best-fit counsellor and appointment slot; request human approval.",
            result_state="S8_Handoff_Approval:Awaiting_Approval",
            autonomy_level="Approve",
            requires_approval=True,
            explanation="High-intent applicants receive immediate counsellor matching subject to human approval before confirmation."
        )

    # Rule R10: Medium classification (Score 40-69)
    if score and score.classification == "Medium":
        return PolicyDecision(
            rule_id="R10",
            rule_name="Automated Nurture Sequence Enrollment",
            trigger_condition="Total score between 40 and 69 with no escalation flags.",
            prior_state=prior_state,
            action_selected="Enroll in multi-day nurturing journey (Stage N1 Day 0); send initial relevant programme information.",
            result_state="S7_Nurturing:Active",
            autonomy_level="Act then report",
            requires_approval=False,
            explanation="Prospect is interested but undecided or awaiting final qualifications; enters structured nurture track."
        )

    # Rule R11: Low classification (Score < 40 or zero eligibility)
    if score and score.classification == "Low":
        return PolicyDecision(
            rule_id="R11",
            rule_name="Low-Information Track Routing",
            trigger_condition="Total score below 40 or basic eligibility not met.",
            prior_state=prior_state,
            action_selected="Provide supported general information brochure link; place in low-frequency broadcast track.",
            result_state="S7_Low_Track:Active",
            autonomy_level="Act then report",
            requires_approval=False,
            explanation="Preserves counsellor bandwidth while keeping applicant informed via automated low-frequency updates."
        )

    # Rule R1: Default New enquiry received
    return PolicyDecision(
        rule_id="R1",
        rule_name="New Lead Intake & AI Disclosure",
        trigger_condition="New student enquiry received through active channel.",
        prior_state=prior_state,
        action_selected="Create case record; send automated greeting with mandatory AI disclosure; start qualification.",
        result_state="S2_Extraction:Processing",
        autonomy_level="Fully autonomous",
        requires_approval=False,
        explanation="Standard intake protocol with mandatory transparency regarding AI assistance."
    )
