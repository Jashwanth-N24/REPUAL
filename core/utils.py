import os
import re
from django.conf import settings
from core.models import Manual

try:
    import pymupdf as fitz
except ImportError:
    import fitz


STOP_WORDS = {
    'what', 'is', 'are', 'the', 'a', 'an', 'of', 'in', 'to', 'for', 'on', 'with', 
    'at', 'by', 'from', 'how', 'do', 'does', 'did', 'can', 'could', 'should', 
    'would', 'tell', 'me', 'about', 'please', 'why', 'which', 'when', 'where', 
    'who', 'whom', 'this', 'that', 'these', 'those', 'it', 'its', 'there', 
    'their', 'and', 'or', 'but', 'so', 'if', 'be', 'been', 'has', 'have', 'had',
    'i', 'you', 'we', 'they', 'he', 'she', 'my', 'your', 'our', 'his', 'her'
}

SYNONYMS = {
    'error': ['alarm', 'fault', 'code', 'warning', 'trip'],
    'alarm': ['error', 'fault', 'warning', 'code'],
    'fault': ['error', 'alarm', 'issue'],
    'fix': ['response', 'troubleshoot', 'inspection', 'maintenance', 'checks', 'action'],
    'resolve': ['response', 'troubleshoot', 'inspection', 'maintenance', 'action'],
    'troubleshoot': ['troubleshooting', 'inspection', 'checks', 'review', 'escalation'],
    'temperature': ['temp', 'degrees', 'celsius', 'cooling', 'heat', 'overheat'],
    'pressure': ['bar', 'psi', 'hydraulic', 'outlet'],
    'oil': ['lubricant', 'fluid', 'h46', 'reservoir'],
    'filter': ['restriction', 'return-filter', 'inlet-filter', 'rf-20', 'af-10'],
    'leak': ['leakage', 'external'],
    'guard': ['interlock', 'guard-open'],
    'level': ['sight-glass', 'min', 'max', 'low', 'high'],
}


def retrieve_manual_chunks(machine_id, query=""):
    """
    Retrieves text chunks strictly isolated to the selected machine_id,
    with block-level semantic extraction, synonym expansion, and cross-machine
    contamination guardrail detection.
    """
    allowed_manuals = Manual.objects.filter(machine__machine_id=machine_id)
    matched_chunks = []
    is_security_violation = False

    # Cross-machine guardrail detection:
    query_lower = query.lower() if query else ""
    if machine_id == "M-HP200" and any(
        k in query_lower for k in ["compressor", "psi", "air tank", "ac-90", "ac90", "m-ac90"]
    ):
        is_security_violation = True
    elif machine_id == "M-AC90" and any(
        k in query_lower for k in ["hydraulic", "bar pressure", "forming press", "hp-200", "hp200", "m-hp200"]
    ):
        is_security_violation = True

    if is_security_violation or not query:
        return matched_chunks, is_security_violation

    # Extract alphanumeric tokens, codes, and meaningful keywords (stopwords removed)
    raw_tokens = re.findall(r'[a-zA-Z0-9_\-]+', query)
    tokens = [t.lower() for t in raw_tokens]
    codes = [t for t in tokens if re.match(r'^[a-z]\d+$|^[a-z]+-\d+$', t)]
    meaningful = [t for t in tokens if t not in STOP_WORDS and len(t) > 1]

    # Expand terms with domain-specific synonyms
    expanded_terms = set(meaningful)
    for m in meaningful:
        if m in SYNONYMS:
            expanded_terms.update(SYNONYMS[m])

    for manual in allowed_manuals:
        pdf_path = ""
        pdf_url = ""
        try:
            if manual.pdf_file:
                pdf_path = manual.pdf_file.path
                pdf_url = manual.pdf_file.url
        except Exception:
            pdf_path = ""
            pdf_url = ""

        if not pdf_url and manual.pdf_file:
            pdf_url = f"/media/manuals/{os.path.basename(str(manual.pdf_file))}"

        if not pdf_path or not os.path.exists(pdf_path):
            candidates = [
                os.path.join(settings.BASE_DIR, "Manuals", os.path.basename(str(manual.pdf_file))),
                os.path.join(settings.BASE_DIR, "media", "manuals", os.path.basename(str(manual.pdf_file))),
            ]
            for cand in candidates:
                if os.path.exists(cand):
                    pdf_path = cand
                    break

        if not pdf_path or not os.path.exists(pdf_path):
            continue

        doc = fitz.open(pdf_path)
        for page_idx in range(len(doc)):
            page = doc[page_idx]
            page_num = page_idx + 1
            blocks = page.get_text("blocks")

            for b in blocks:
                b_text = b[4].strip()
                if not b_text or len(b_text) < 15:
                    continue

                # Filter out raw page headers and footers
                if re.match(r'^[A-Z0-9\-]+\s*\|\s*Rev\s*\d+\.\d+\s*\|\s*Page\s*\d+$', b_text):
                    continue

                lower_b = b_text.lower()
                score = 0
                has_code_match = False

                # 1. Exact code / alarm ID match (e.g., E17, E08, AC-90, RF-20)
                for c in codes:
                    if re.search(r'\b' + re.escape(c) + r'\b', lower_b):
                        score += 50
                        has_code_match = True
                        # Bonus if block defines the code or starts with it
                        if lower_b.startswith(c) or f'interpreting {c}' in lower_b or f'pressure or {c}' in lower_b or f'temperature or {c}' in lower_b:
                            score += 35

                # 2. Meaningful domain keywords
                for term in meaningful:
                    if re.search(r'\b' + re.escape(term) + r'\b', lower_b):
                        score += 15

                # 3. Expanded domain synonyms
                for exp in expanded_terms:
                    if exp not in meaningful and re.search(r'\b' + re.escape(exp) + r'\b', lower_b):
                        score += 7

                if score > 0:
                    matched_chunks.append({
                        "machine_id": machine_id,
                        "document_id": manual.document_id,
                        "revision": manual.revision,
                        "page_number": page_num,
                        "pdf_url": pdf_url,
                        "text": b_text,
                        "score": score,
                        "relevance_score": score,
                        "has_code_match": has_code_match,
                    })

    matched_chunks.sort(key=lambda x: x["score"], reverse=True)
    return matched_chunks, is_security_violation


def calculate_confidence_score(query, text_chunks):
    """
    Calculates RAG retrieval confidence score (0.0% to 98.5%) based on:
    - Exact match of alarm / equipment / document code IDs
    - Coverage of key meaningful terms (stop words excluded)
    - Presence of direct answers, definitions, or documented actions
    """
    if not text_chunks:
        return 0.0

    raw_tokens = re.findall(r'[a-zA-Z0-9_\-]+', query)
    tokens = [t.lower() for t in raw_tokens]
    codes = [t for t in tokens if re.match(r'^[a-z]\d+$|^[a-z]+-\d+$', t)]
    meaningful = [t for t in tokens if t not in STOP_WORDS and len(t) > 1]

    top_chunk = text_chunks[0]
    top_text = top_chunk.get("text", "").lower()

    if codes:
        code_matched = any(re.search(r'\b' + re.escape(c) + r'\b', top_text) for c in codes)
        if code_matched:
            conf = 92.0
            if any(w in top_text for w in ["meaning", "response", "documented response", "generated when", "trigger", "range", "inspection", "checks"]):
                conf += 4.5
            matched_meaningful = [m for m in meaningful if re.search(r'\b' + re.escape(m) + r'\b', top_text)]
            if len(matched_meaningful) >= 2:
                conf += 2.0
            return min(round(conf, 1), 98.5)
        else:
            return 35.0

    if not meaningful:
        return 50.0

    matched_meaningful = [m for m in meaningful if re.search(r'\b' + re.escape(m) + r'\b', top_text)]
    coverage = len(matched_meaningful) / len(meaningful)

    if coverage >= 0.8:
        conf = 90.0 + (coverage * 6.0)
    elif coverage >= 0.5:
        conf = 75.0 + (coverage * 15.0)
    elif coverage > 0:
        conf = 50.0 + (coverage * 20.0)
    else:
        return 0.0

    return min(round(conf, 1), 97.0)


def retrieve_chunks_from_sop_documents(documents, query):
    """Reuse the manual RAG block retrieval against an explicit SOP allowlist.

    `documents` must already be resolved from the exact product mapping. This
    function never searches the machine-manual table or any other SOP file.
    """
    raw_tokens = re.findall(r'[a-zA-Z0-9_\-]+', query or '')
    tokens = [token.lower() for token in raw_tokens]
    meaningful = [token for token in tokens if token not in STOP_WORDS and len(token) > 1]
    expanded = set(meaningful)
    for token in meaningful:
        expanded.update(SYNONYMS.get(token, []))

    results = []
    for source in documents:
        with fitz.open(source['path']) as pdf:
            for page_idx, page in enumerate(pdf):
                for block in page.get_text('blocks'):
                    block_text = block[4].strip()
                    if len(block_text) < 15:
                        continue
                    score = 0
                    lower = block_text.lower()
                    for term in meaningful:
                        if re.search(r'\b' + re.escape(term) + r'\b', lower):
                            score += 15
                    for term in expanded - set(meaningful):
                        if re.search(r'\b' + re.escape(term) + r'\b', lower):
                            score += 7
                    if score:
                        results.append({
                            'document_id': source['document_id'],
                            'revision': source['revision'],
                            'page_number': page_idx + 1,
                            'text': block_text,
                            'score': score,
                        })

    results.sort(key=lambda chunk: chunk['score'], reverse=True)
    return results
