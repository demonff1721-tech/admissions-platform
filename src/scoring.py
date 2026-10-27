"""Deterministic lead scoring rubric and classification engine for Alliance University admissions."""

from typing import Dict, Any, List, Optional
from src.models import ScoreBreakdown, ExtractedFields


OFFERED_PROGRAMMES = {
    "mba": ["mba", "master of business administration", "executive mba", "pgdm"],
    "btech": ["b.tech", "btech", "b tech", "bachelor of technology", "b.tech cse", "cse", "computer science", "aerospace engineering", "ece"],
    "law": ["bba llb", "ba llb", "llb", "llm", "law"],
    "bba": ["bba", "bachelor of business administration"]
}

BROAD_DISCIPLINES = ["engineering", "management", "business", "law", "technology", "commerce", "science"]


def score_lead(
    extracted: ExtractedFields,
    clarification_count: int = 0,
    clarification_replied: bool = True,
    contradiction_detected: bool = False,
    unsupported_question: bool = False,
    missing_required_exhausted: bool = False
) -> ScoreBreakdown:
    """
    Computes deterministic score (0-100) across 5 fixed criteria:
    Criterion 1: Application readiness (0, 5, 15, 25)
    Criterion 2: Application intent (0, 5, 15, 25)
    Criterion 3: Programme fit (0, 10, 20)
    Criterion 4: Basic Eligibility (0, 10, 20)
    Criterion 5: Engagement (0, 5, 10)
    """
    uncertain_reasons: List[str] = []
    
    # Check mandatory escalation conditions first
    if contradiction_detected:
        uncertain_reasons.append("Contradictory applicant information detected.")
    if unsupported_question:
        uncertain_reasons.append("Unsupported question requiring human admissions judgement.")
    if missing_required_exhausted:
        uncertain_reasons.append("Required information remained missing after 2 clarification attempts.")

    # 1. Criterion 1: Application Readiness (Max 25)
    readiness_str = (extracted.application_readiness or "").lower()
    intake_str = (extracted.intended_intake or "").lower()
    edu_str = (extracted.education or "").lower()
    
    is_upcoming_intake = any(term in intake_str for term in ["2026", "upcoming", "immediate", "current", "this year", "july 2026"])
    is_undecided_or_later = any(term in intake_str for term in ["2027", "2028", "later", "undecided", "next year", "exploring"])
    has_completed_edu = any(term in edu_str for term in ["graduated", "graduate", "completed", "passed", "degree", "b.tech", "b.com", "b.sc", "bba", "ba"]) and not any(term in edu_str for term in ["awaiting", "final year", "pursuing", "pending", "appearing"])
    is_results_pending = any(term in edu_str for term in ["awaiting", "final year", "pursuing", "pending", "appearing", "results awaited"]) or "pending" in readiness_str or "awaiting" in readiness_str

    if "student" in edu_str or "pursuing" in edu_str or "appearing" in edu_str:
        is_results_pending = True
        has_completed_edu = False

    if is_upcoming_intake and has_completed_edu:
        c1_score = 25
        c1_rationale = "Intends to apply for upcoming intake (2026) and has completed required qualification."
    elif (is_upcoming_intake and is_results_pending) or "ready to apply" in readiness_str:
        if is_results_pending:
            c1_score = 15
            c1_rationale = "Intends to apply for upcoming intake, but final year results/experience are pending."
        else:
            c1_score = 25
            c1_rationale = "Intends to apply for upcoming intake and is ready to apply."
    elif is_undecided_or_later or "exploratory" in readiness_str:
        c1_score = 5
        c1_rationale = "Considering a later intake or undecided."
    elif not intake_str and not readiness_str:
        c1_score = 0
        c1_rationale = "Intended intake or readiness not stated."
    else:
        c1_score = 5
        c1_rationale = "Early exploratory inquiry."

    # 2. Criterion 2: Application Intent (Max 25)
    concern_str = (extracted.primary_concern or "").lower()
    wants_counsellor = extracted.wants_counsellor is True
    msg_type = (extracted.message_type or "").lower()

    high_intent_keywords = ["how to apply", "application deadline", "application process", "apply", "admission steps", "counsellor", "admission date", "last date"]
    medium_intent_keywords = ["fee", "fees", "tuition", "cost", "scholarship", "placement", "salary", "package", "hostel", "compare", "comparison"]
    general_keywords = ["info", "information", "brochure", "syllabus", "overview", "about"]

    if wants_counsellor or any(k in concern_str for k in ["application process", "apply", "deadline", "counsellor"]) or any(k in msg_type for k in ["counsellor", "apply"]):
        c2_score = 25
        c2_rationale = "Asks how to apply, application deadlines/steps, or explicitly requests a counsellor."
    elif any(k in concern_str for k in medium_intent_keywords):
        c2_score = 15
        c2_rationale = "Asks about fees, scholarships, placements or programme comparisons."
    elif any(k in concern_str for k in general_keywords) or msg_type == "factual_question":
        c2_score = 5
        c2_rationale = "Requests general information only."
    elif not concern_str and not wants_counsellor:
        c2_score = 0
        c2_rationale = "No evidence of application intent."
    else:
        c2_score = 5
        c2_rationale = "General exploratory enquiry."

    # 3. Criterion 3: Programme Fit (Max 20)
    prog_str = (extracted.programme_interest or "").lower()
    
    is_specific = False
    for group in OFFERED_PROGRAMMES.values():
        if any(p in prog_str for p in group):
            is_specific = True
            break
            
    is_broad = any(b in prog_str for b in BROAD_DISCIPLINES)

    if is_specific:
        c3_score = 20
        c3_rationale = f"Names specific offered programme ({extracted.programme_interest})."
    elif is_broad:
        c3_score = 10
        c3_rationale = f"Names a broad discipline ({extracted.programme_interest}) mapping to offered programmes."
    elif not prog_str or "unspecified" in prog_str or "not stated" in prog_str:
        c3_score = 0
        c3_rationale = "Programme interest is not stated."
    else:
        c3_score = 0
        c3_rationale = f"Requested programme ({extracted.programme_interest}) is not offered by Alliance University."

    # 4. Criterion 4: Basic Eligibility (Max 20)
    # Check if education meets basic thresholds
    # MBA: Graduation >= 50%
    # B.Tech: 10+2 PCM >= 50%
    # Law: 10+2 >= 45%
    meets_basic = False
    likely_meets = False
    ineligible = False

    # Extract percentage if present
    import re
    pct_match = re.search(r'(\d{2,3}(?:\.\d+)?)\s*%', edu_str)
    pct = float(pct_match.group(1)) if pct_match else None

    if "mba" in prog_str or "management" in prog_str:
        if any(deg in edu_str for deg in ["b.tech", "btech", "b.com", "bcom", "b.sc", "bsc", "bba", "ba", "bachelor", "degree", "graduate"]):
            if pct is not None:
                if pct >= 50.0:
                    meets_basic = True
                else:
                    ineligible = True
            elif is_results_pending:
                likely_meets = True
            else:
                meets_basic = True  # Graduate without stated pct assumed met basic degree
        elif "12th" in edu_str or "high school" in edu_str:
            ineligible = True
    elif "b.tech" in prog_str or "engineering" in prog_str or "cse" in prog_str:
        if any(h in edu_str for h in ["12th", "10+2", "puc", "inter", "intermediate", "high school"]):
            if pct is not None:
                if pct >= 50.0:
                    meets_basic = True
                else:
                    ineligible = True
            elif is_results_pending:
                likely_meets = True
            else:
                meets_basic = True
        elif any(deg in edu_str for deg in ["bachelor", "graduate", "diploma"]):
            meets_basic = True
    elif "law" in prog_str:
        if any(h in edu_str for h in ["12th", "10+2", "puc", "inter", "intermediate", "graduate", "degree"]):
            if pct is not None:
                if pct >= 45.0:
                    meets_basic = True
                else:
                    ineligible = True
            elif is_results_pending:
                likely_meets = True
            else:
                meets_basic = True
    else:
        # Generic check
        if any(k in edu_str for k in ["graduate", "bachelor", "completed", "degree"]):
            meets_basic = True
        elif is_results_pending:
            likely_meets = True

    if ineligible:
        c4_score = 0
        c4_rationale = f"Stated academic credentials ({extracted.education}) do not meet published minimum eligibility criteria."
    elif meets_basic:
        c4_score = 20
        c4_rationale = f"Stated education ({extracted.education}) meets basic eligibility published in knowledge base."
    elif likely_meets:
        c4_score = 10
        c4_rationale = f"Likely to meet eligibility, but final results/scores are currently awaited ({extracted.education})."
    else:
        c4_score = 0
        c4_rationale = "Stated education is insufficient or required information is not stated."

    # 5. Criterion 5: Engagement (Max 10)
    has_prog = bool(extracted.programme_interest and extracted.programme_interest.strip() and extracted.programme_interest.lower() not in ["undecided", "not stated"])
    has_edu = bool(extracted.education and extracted.education.strip() and extracted.education.lower() not in ["undecided", "not stated"])
    has_intake = bool(extracted.intended_intake and extracted.intended_intake.strip() and extracted.intended_intake.lower() not in ["undecided", "unknown", "not stated", "later"])

    if has_prog and has_edu and has_intake and c1_score >= 20 and c4_score >= 20:
        c5_score = 10
        c5_rationale = "Answered all required qualifying questions."
    elif has_prog or has_edu or has_intake:
        if clarification_count >= 2 and not clarification_replied:
            c5_score = 0
            c5_rationale = "Answers none after two clarification prompts."
        else:
            c5_score = 5
            c5_rationale = "Initiates contact with partial profile or answers some required questions."
    else:
        if clarification_count >= 2:
            c5_score = 0
            c5_rationale = "Answers none after two clarification prompts."
        else:
            c5_score = 5
            c5_rationale = "Initial enquiry provided minimal context."

    total_score = c1_score + c2_score + c3_score + c4_score + c5_score

    # Determine classification
    is_uncertain = len(uncertain_reasons) > 0
    if is_uncertain:
        classification = "Uncertain"
    elif total_score >= 70 and c4_score > 0:
        classification = "High"
    elif 40 <= total_score <= 69:
        classification = "Medium"
    else:
        classification = "Low"

    return ScoreBreakdown(
        readiness_score=c1_score,
        readiness_rationale=c1_rationale,
        intent_score=c2_score,
        intent_rationale=c2_rationale,
        fit_score=c3_score,
        fit_rationale=c3_rationale,
        eligibility_score=c4_score,
        eligibility_rationale=c4_rationale,
        engagement_score=c5_score,
        engagement_rationale=c5_rationale,
        total_score=total_score,
        classification=classification,
        is_uncertain=is_uncertain,
        uncertain_reasons=uncertain_reasons
    )
