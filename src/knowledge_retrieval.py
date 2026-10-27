"""Approved institutional knowledge base retrieval engine with strict anti-hallucination guardrails."""

import re
import math
import io
from typing import List, Dict, Any, Optional, Tuple
from src.database import get_db_connection


DEFAULT_SIMILARITY_THRESHOLD = 0.60


def tokenize(text: str) -> List[str]:
    """Basic alphanumeric word tokenizer with lowercasing."""
    return re.findall(r'[a-zA-Z0-9]+', text.lower())


def compute_tf_idf_similarity(query: str, document_text: str, all_docs: List[str]) -> float:
    """
    Computes cosine similarity based on term frequency - inverse document frequency.
    Returns normalized similarity score in range [0.0, 1.0].
    """
    query_tokens = tokenize(query)
    doc_tokens = tokenize(document_text)

    if not query_tokens or not doc_tokens:
        return 0.0

    # Stopwords list
    stopwords = {"a", "an", "the", "in", "on", "of", "for", "with", "at", "by", "from", "up", "about", "into", "over", "after", "is", "are", "was", "were", "be", "been", "being", "have", "has", "had", "do", "does", "did", "to", "and", "or", "but", "if", "then", "else", "when", "up", "can", "could", "would", "should", "what", "which", "who", "whom", "how", "where", "why", "tell", "me", "please", "i", "you", "my", "your"}
    q_filtered = [t for t in query_tokens if t not in stopwords]
    if not q_filtered:
        q_filtered = query_tokens

    # Document frequency
    N = len(all_docs)
    df: Dict[str, int] = {}
    for term in set(q_filtered):
        count = sum(1 for d in all_docs if term in tokenize(d))
        df[term] = count if count > 0 else 1

    # Term weights for query
    q_weights: Dict[str, float] = {}
    for term in q_filtered:
        idf = math.log((N + 1) / (df.get(term, 1))) + 1.0
        q_weights[term] = q_weights.get(term, 0.0) + idf

    # Term weights for doc
    d_weights: Dict[str, float] = {}
    doc_token_set = set(doc_tokens)
    for term in q_filtered:
        if term in doc_token_set:
            tf = doc_tokens.count(term)
            idf = math.log((N + 1) / (df.get(term, 1))) + 1.0
            d_weights[term] = (1.0 + math.log(tf)) * idf

    dot_product = sum(q_weights[t] * d_weights.get(t, 0.0) for t in q_filtered)
    q_norm = math.sqrt(sum(w ** 2 for w in q_weights.values()))
    d_norm = math.sqrt(sum(w ** 2 for w in d_weights.values()))

    if not q_filtered or q_norm == 0.0 or d_norm == 0.0:
        return 0.0

    # High-value admissions entities
    domain_keywords = {
        "fee", "fees", "tuition", "cost", "installments", "hostel",
        "deadline", "deadlines", "date", "apply", "application", "steps",
        "eligibility", "criteria", "cat", "mat", "gmat", "amat", "interview", "admission",
        "placement", "placements", "package", "salary", "recruiters", "highest", "average",
        "mba", "btech", "cse", "law", "bba", "engineering", "management",
        "sports", "facilities", "campus", "swimming", "pool", "badminton",
        "exchange", "abroad", "tours"
    }

    # Keyword overlap bonus for high-precision admissions terms
    domain_overlap = [t for t in q_filtered if t in domain_keywords and t in doc_token_set]
    overlap_ratio = len([t for t in q_filtered if t in doc_token_set]) / max(1, len(q_filtered))
    base_sim = dot_product / (q_norm * d_norm)

    domain_bonus = 0.20 if len(domain_overlap) >= 2 else (0.10 if len(domain_overlap) == 1 else 0.0)

    # Blend cosine with overlap and domain bonus
    combined_score = (0.5 * base_sim) + (0.3 * overlap_ratio) + domain_bonus
    return min(1.0, round(combined_score, 3))


def retrieve_from_knowledge_base(
    query: str,
    threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
    programme_filter: Optional[str] = None,
    db_path: Optional[str] = None
) -> Dict[str, Any]:
    """
    Searches only approved knowledge documents (is_approved=1).
    Enforces the similarity threshold (default 0.60).
    If threshold is met, returns grounded answer with citation.
    If threshold is NOT met, returns found=False with similarity score, strictly preventing ungrounded generation.
    """
    conn = get_db_connection(db_path)
    cur = conn.cursor()

    cur.execute("""
    SELECT doc_id, title, programme, category, approved_content, official_source_url, last_verified_date
    FROM knowledge_documents
    WHERE is_approved = 1;
    """)
    rows = cur.fetchall()
    conn.close()

    if not rows:
        return {
            "found": False,
            "similarity": 0.0,
            "error": "No approved knowledge documents present in database."
        }

    all_contents = [f"{r['title']} {r['approved_content']}" for r in rows]
    
    scored_results = []
    for r, content in zip(rows, all_contents):
        # Program filter bonus
        prog_bonus = 0.0
        if programme_filter and (programme_filter.lower() in r["programme"].lower() or r["programme"] == "All Programmes"):
            prog_bonus = 0.05

        sim = compute_tf_idf_similarity(query, content, all_contents) + prog_bonus
        sim = min(1.0, round(sim, 3))
        scored_results.append({
            "doc_id": r["doc_id"],
            "title": r["title"],
            "programme": r["programme"],
            "category": r["category"],
            "content": r["approved_content"],
            "source_url": r["official_source_url"],
            "verified_date": r["last_verified_date"],
            "similarity": sim
        })

    scored_results.sort(key=lambda x: x["similarity"], reverse=True)
    top = scored_results[0]

    if top["similarity"] >= threshold:
        # Formulate grounded response strictly with citation
        grounded_answer = (
            f"{top['content']}\n\n"
            f"**Official Source:** [{top['title']}]({top['source_url']}) "
            f"(Verified: {top['verified_date']})"
        )
        return {
            "found": True,
            "similarity": top["similarity"],
            "threshold": threshold,
            "doc_id": top["doc_id"],
            "title": top["title"],
            "programme": top["programme"],
            "category": top["category"],
            "content": top["content"],
            "source_url": top["source_url"],
            "verified_date": top["verified_date"],
            "grounded_answer": grounded_answer,
            "all_ranked": scored_results[:3]
        }
    else:
        return {
            "found": False,
            "similarity": top["similarity"],
            "threshold": threshold,
            "top_match_title": top["title"],
            "source_url": top["source_url"],
            "grounded_answer": None,
            "explanation": f"Highest retrieval similarity ({top['similarity']:.2f}) fell below the policy threshold ({threshold:.2f}). Escalation required."
        }


def add_knowledge_document(
    doc_id: str,
    title: str,
    programme: str,
    category: str,
    content: str,
    source_url: str,
    verified_date: str,
    is_approved: bool = False,
    db_path: Optional[str] = None
) -> bool:
    """Inserts a new document. By default unapproved until explicitly reviewed."""
    conn = get_db_connection(db_path)
    cur = conn.cursor()
    from datetime import datetime
    now_date = datetime.now().strftime("%Y-%m-%d")

    cur.execute("""
    INSERT OR REPLACE INTO knowledge_documents
    (doc_id, title, programme, category, approved_content, official_source_url, retrieval_metadata, collection_date, last_verified_date, is_approved)
    VALUES (?, ?, ?, ?, ?, ?, '{}', ?, ?, ?);
    """, (doc_id, title, programme, category, content, source_url, now_date, verified_date, 1 if is_approved else 0))

    conn.commit()
    conn.close()
    return True


def approve_knowledge_document(doc_id: str, db_path: Optional[str] = None) -> bool:
    """Approves a document making it active in the RAG index."""
    conn = get_db_connection(db_path)
    cur = conn.cursor()
    cur.execute("UPDATE knowledge_documents SET is_approved = 1 WHERE doc_id = ?;", (doc_id,))
    conn.commit()
    conn.close()
    return True


def extract_text_from_pdf(file_bytes: bytes) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
    """
    Extracts plain text from PDF bytes using pypdf.
    Returns:
        (success: bool, text_or_error: str, metadata: Optional[Dict[str, Any]])
    Metadata includes: page_count, character_count, word_count.
    Gracefully handles empty files, encrypted PDFs, corrupted bytes, and non-extractable/scanned files.
    """
    if not file_bytes or len(file_bytes) == 0:
        return False, "Uploaded PDF file is empty (0 bytes).", None

    try:
        import pypdf
        reader = pypdf.PdfReader(io.BytesIO(file_bytes))

        if reader.is_encrypted:
            try:
                reader.decrypt("")
            except Exception:
                pass
            if reader.is_encrypted:
                return False, "PDF is password-protected or encrypted. Please decrypt the file before uploading.", None

        num_pages = len(reader.pages)
        if num_pages == 0:
            return False, "PDF contains 0 pages.", None

        page_texts = []
        for i, page in enumerate(reader.pages):
            text = page.extract_text() or ""
            if text.strip():
                page_texts.append(text.strip())

        full_text = "\n\n".join(page_texts).strip()
        if not full_text:
            return False, "PDF contains no extractable text (it may contain only scanned images or blank pages).", {
                "page_count": num_pages,
                "character_count": 0,
                "word_count": 0
            }

        words = full_text.split()
        metadata = {
            "page_count": num_pages,
            "character_count": len(full_text),
            "word_count": len(words)
        }
        return True, full_text, metadata

    except Exception as e:
        return False, f"Failed to parse PDF document: {str(e)}", None
