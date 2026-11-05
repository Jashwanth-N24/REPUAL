import csv
import logging
import re
from pathlib import Path

import pymupdf
from django.conf import settings
from django.urls import reverse

from apps.incidents.models import Incident
from apps.inspections.models import Inspection
from core.utils import retrieve_chunks_from_sop_documents


logger = logging.getLogger(__name__)
ACTION_STARTS = (
    'record ', 'keep ', 'request ', 'confirm ', 'review ', 'read ', 'check ',
    'verify ', 'include ', 'link ', 'preserve ',
)
PLATE_REQUIRED_SOPS = {'Q-PLATE-01', 'Q-PLATE-02'}


def required_sops_for_product(product_id):
    """Read required SOPs from the supplied mapping, matching product IDs exactly."""
    mapping_path = Path(settings.BASE_DIR) / 'product_sop_mapping.csv'
    if not mapping_path.is_file():
        return [], 'The product-to-SOP mapping file is missing.'

    try:
        with mapping_path.open('r', encoding='utf-8-sig', newline='') as mapping_file:
            rows = [row for row in csv.DictReader(mapping_file)
                    if row.get('product_id', '').strip() == product_id
                    and row.get('required', '').strip().lower() == 'true']
    except (OSError, csv.Error):
        return [], 'The product-to-SOP mapping could not be read.'

    if not rows:
        return [], f'No required SOPs are mapped to product {product_id}.'
    if product_id == 'P-PLATE01':
        mapped_ids = {row.get('document_id', '').strip() for row in rows}
        if not PLATE_REQUIRED_SOPS.issubset(mapped_ids):
            return [], 'The mapping does not include both required P-PLATE01 procedures.'

    sops_root = (Path(settings.BASE_DIR) / 'SOPs').resolve()
    documents = []
    for row in rows:
        document_id = row.get('document_id', '').strip()
        revision = row.get('revision', '').strip()
        filename = row.get('pdf_filename', '').strip()
        if not document_id or not revision or not filename:
            return [], 'A required SOP mapping is missing its document ID, revision, or filename.'
        pdf_path = (sops_root / filename).resolve()
        if sops_root not in pdf_path.parents:
            return [], 'A required SOP mapping contains an invalid file path.'
        if not pdf_path.is_file():
            return [], f'Required SOP {document_id} revision {revision} is unavailable.'
        try:
            with pymupdf.open(pdf_path) as pdf:
                if not pdf.page_count or not any(page.get_text().strip() for page in pdf):
                    return [], f'Required SOP {document_id} revision {revision} has no readable text.'
        except Exception:
            return [], f'Required SOP {document_id} revision {revision} could not be read.'

        documents.append({
            'document_id': document_id,
            'revision': revision,
            'path': str(pdf_path),
            'filename': filename,
        })
    return documents, ''


def _incident_summary(inspection):
    version = inspection.model_version or 'Not recorded'
    confidence = (
        f' Model confidence: {inspection.confidence:.1%}.'
        if inspection.confidence is not None else ''
    )
    batch_text = f' Batch reference: {inspection.batch_id}.' if inspection.batch_id else ''
    return (
        f'Inspection {inspection.pk} for product {inspection.product.product_id} was completed '
        f'with an original model prediction of {inspection.original_predicted_class} '
        f'(model {version}).{confidence}{batch_text} The classifier result is a flag for '
        'Supervisor review; it does not establish a physical defect, defect type, cause, or severity.'
    )


def _action_candidates(chunks, document_id):
    candidates = []
    seen = set()
    for chunk in chunks:
        if chunk['document_id'] != document_id:
            continue
        text = chunk['text'].replace('\uf0b7', '\n')
        sentences = re.split(r'(?:(?<=[.!?])\s+|\n+)', text)
        for sentence in sentences:
            sentence = re.sub(r'^[\s•●▪\uf0b7\-*]+', '', sentence).strip()
            sentence = re.sub(r'\s+', ' ', sentence)
            if not sentence or not sentence.endswith(('.', '!', '?')):
                continue
            normalized = sentence.casefold()
            if normalized in seen or not normalized.startswith(ACTION_STARTS):
                continue
            seen.add(normalized)
            candidates.append({
                'action_text': sentence,
                'source_document_id': document_id,
                'revision': chunk['revision'],
                'pdf_page': chunk['page_number'],
                'supporting_passage': text,
                'source_link': reverse('incident_sop_pdf', kwargs={'document_id': document_id})
                              + f"#page={chunk['page_number']}",
                '_score': chunk['score'],
            })
    candidates.sort(key=lambda action: action['_score'], reverse=True)
    return candidates[:2]


def _generate_grounded_content(inspection):
    product_id = inspection.product.product_id
    documents, reason = required_sops_for_product(product_id)
    summary = _incident_summary(inspection)
    if reason:
        return summary, [], [], Incident.EVIDENCE_INSUFFICIENT, reason

    query = (
        'P-PLATE01 quality incident completed inspection original model prediction '
        'record item-level hold preserve image Supervisor review evidence confirm references '
        'review cited passages verify actions'
    )
    chunks = retrieve_chunks_from_sop_documents(documents, query)
    actions = []
    for document in documents:
        actions.extend(_action_candidates(chunks, document['document_id']))

    document_ids = [document['document_id'] for document in documents]
    cited_ids = {action['source_document_id'] for action in actions}
    if not chunks or not actions or cited_ids != set(document_ids):
        return (
            summary,
            [],
            [],
            Incident.EVIDENCE_INSUFFICIENT,
            'The required SOP set did not provide relevant, citable actions from every mapped document.',
        )

    for action in actions:
        action.pop('_score', None)
    return summary, actions, document_ids, Incident.EVIDENCE_SUFFICIENT, ''


def create_incident_for_inspection(inspection):
    """Create one incident per eligible inspection, preserving any existing review."""
    existing = Incident.objects.filter(inspection=inspection).first()
    if existing:
        return existing, False, ''

    if (inspection.status != Inspection.STATUS_COMPLETED or
            inspection.original_predicted_class != Inspection.CLASS_DEFECTIVE):
        return None, False, 'Only completed inspections with an original Defective model prediction can create an incident.'

    try:
        summary, actions, source_references, evidence_status, evidence_reason = (
            _generate_grounded_content(inspection)
        )
    except Exception:
        logger.exception('Quality incident evidence generation failed for inspection %s', inspection.pk)
        summary = _incident_summary(inspection)
        actions = []
        source_references = []
        evidence_status = Incident.EVIDENCE_INSUFFICIENT
        evidence_reason = 'The required SOP evidence could not be retrieved. Manual review is required.'

    incident, created = Incident.objects.get_or_create(
        inspection=inspection,
        defaults={
            'product_id_snapshot': inspection.product.product_id,
            'original_model_result': inspection.original_predicted_class,
            'model_version': inspection.model_version or '',
            'summary': summary,
            'actions': actions,
            'evidence_status': evidence_status,
            'evidence_reason': evidence_reason,
            'workflow_status': (
                Incident.STATUS_READY if evidence_status == Incident.EVIDENCE_SUFFICIENT
                else Incident.STATUS_MANUAL_REVIEW
            ),
            'source_references': source_references,
            'creator': inspection.submitter,
        },
    )
    return incident, created, ''


def apply_supervisor_review(incident, decision, comment, reviewer):
    comment = (comment or '').strip()
    allowed = {Incident.REVIEW_APPROVED, Incident.REVIEW_NEEDS_INFO}
    if decision not in allowed:
        return 'Choose Approved for follow-up or Needs more information.'
    if not comment:
        return 'A comment is required for every Supervisor review.'
    if (incident.evidence_status == Incident.EVIDENCE_INSUFFICIENT
            and decision != Incident.REVIEW_NEEDS_INFO):
        return 'Insufficient-evidence incidents cannot be approved for follow-up.'

    from django.utils import timezone
    incident.review_status = decision
    incident.review_comment = comment
    incident.reviewer = reviewer
    incident.reviewed_at = timezone.now()
    incident.save(update_fields=[
        'review_status', 'review_comment', 'reviewer', 'reviewed_at',
    ])
    return ''
