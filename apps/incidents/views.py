import json
from pathlib import Path

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import FileResponse, Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.incidents.models import Incident
from apps.incidents.services import apply_supervisor_review, create_incident_for_inspection, required_sops_for_product
from apps.inspections.models import Inspection


def _can_view_incident(user, incident):
    if user.role == 'supervisor':
        return True
    return user.role == 'engineer' and incident.creator_id == user.id


@login_required
def incident_list_view(request):
    if request.user.role == 'supervisor':
        incidents = Incident.objects.select_related('inspection', 'creator').all()
        inspections = Inspection.objects.none()
        is_supervisor = True
    elif request.user.role == 'engineer':
        incidents = Incident.objects.select_related('inspection', 'creator').filter(creator=request.user)
        inspections = Inspection.objects.select_related('product', 'batch').filter(
            submitter=request.user,
            status=Inspection.STATUS_COMPLETED,
        )
        is_supervisor = False
    else:
        return render(request, 'incidents/forbidden.html', status=403)

    return render(request, 'incidents/list.html', {
        'incidents': incidents,
        'inspections': inspections,
        'is_supervisor': is_supervisor,
    })


@login_required
@require_POST
def incident_create_view(request, inspection_id):
    if request.user.role != 'engineer':
        return render(request, 'incidents/forbidden.html', status=403)
    inspection = get_object_or_404(Inspection, pk=inspection_id, submitter=request.user)
    incident, created, error = create_incident_for_inspection(inspection)
    if error:
        messages.error(request, error)
        return redirect('incidents:list')
    if created and incident.evidence_status == Incident.EVIDENCE_INSUFFICIENT:
        messages.warning(request, 'Incident saved. Manual review is required because SOP evidence is insufficient.')
    elif created:
        messages.success(request, 'Quality incident created with cited SOP actions.')
    else:
        messages.info(request, 'This inspection already has an incident. Its saved recommendations and review were kept.')
    return redirect('incidents:detail', incident_id=incident.incident_id)


@login_required
def incident_detail_view(request, incident_id):
    incident = get_object_or_404(
        Incident.objects.select_related('inspection', 'inspection__product', 'inspection__submitter', 'creator', 'reviewer'),
        incident_id=incident_id,
    )
    if not _can_view_incident(request.user, incident):
        return render(request, 'incidents/forbidden.html', status=403)
    return render(request, 'incidents/detail.html', {
        'incident': incident,
        'can_review': request.user.role == 'supervisor',
    })


@login_required
@require_POST
def incident_review_view(request, incident_id):
    if request.user.role != 'supervisor':
        return render(request, 'incidents/forbidden.html', status=403)
    incident = get_object_or_404(Incident, incident_id=incident_id)
    error = apply_supervisor_review(
        incident,
        request.POST.get('decision'),
        request.POST.get('comment'),
        request.user,
    )
    if error:
        messages.error(request, error)
    else:
        messages.success(request, 'Supervisor decision saved.')
    return redirect('incidents:detail', incident_id=incident.incident_id)


@login_required
def sop_pdf_view(request, document_id):
    documents, error = required_sops_for_product('P-PLATE01')
    if error:
        raise Http404('The mapped SOP is currently unavailable.')
    source = next((doc for doc in documents if doc['document_id'] == document_id), None)
    if source is None:
        raise Http404('This SOP is not in the P-PLATE01 allowed reference set.')
    return FileResponse(
        open(source['path'], 'rb'),
        content_type='application/pdf',
        filename=Path(source['filename']).name,
    )


def _incident_data(incident):
    inspection = incident.inspection
    return {
        'incident_id': str(incident.incident_id),
        'inspection_reference': inspection.pk,
        'product_id': incident.product_id_snapshot,
        'original_model_result': incident.original_model_result,
        'model_version': incident.model_version,
        'summary': incident.summary,
        'actions': incident.actions,
        'evidence_status': incident.evidence_status,
        'evidence_reason': incident.evidence_reason or None,
        'status': incident.get_workflow_status_display(),
        'workflow_status': incident.workflow_status,
        'source_references': incident.source_references,
        'creator_username': incident.creator.username,
        'created_at': incident.created_at.isoformat(),
        'review_status': incident.review_status,
        'reviewer_username': incident.reviewer.username if incident.reviewer else None,
        'review_comment': incident.review_comment or None,
        'reviewed_at': incident.reviewed_at.isoformat() if incident.reviewed_at else None,
        'human_review': {
            'status': inspection.review_status,
            'class': inspection.reviewed_class,
            'comment': inspection.review_comment,
        },
    }


def incident_api_collection(request):
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Authentication is required.'}, status=401)
    if request.method == 'GET':
        if request.user.role == 'supervisor':
            incidents = Incident.objects.select_related('creator', 'inspection').all()
        elif request.user.role == 'engineer':
            incidents = Incident.objects.select_related('creator', 'inspection').filter(creator=request.user)
        else:
            return JsonResponse({'error': 'Your role cannot access quality incidents.'}, status=403)
        return JsonResponse({'results': [_incident_data(item) for item in incidents]})

    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed.'}, status=405)
    if request.user.role != 'engineer':
        return JsonResponse({'error': 'Only Engineers can create incidents for their own inspections.'}, status=403)
    try:
        payload = json.loads(request.body or '{}')
        inspection_reference = payload.get('inspection_reference')
    except (json.JSONDecodeError, AttributeError):
        return JsonResponse({'error': 'Provide a valid JSON inspection_reference.'}, status=400)
    if not isinstance(payload, dict):
        return JsonResponse({'error': 'Provide a valid JSON object.'}, status=400)
    if not inspection_reference:
        return JsonResponse({'error': 'inspection_reference is required.'}, status=400)
    inspection = Inspection.objects.select_related('product', 'submitter').filter(
        pk=inspection_reference, submitter=request.user,
    ).first()
    if inspection is None:
        return JsonResponse({'error': 'Inspection not found for this Engineer.'}, status=404)
    incident, created, error = create_incident_for_inspection(inspection)
    if error:
        return JsonResponse({'error': error}, status=400)
    return JsonResponse(
        {'incident': _incident_data(incident), 'created': created},
        status=201 if created else 200,
    )


def incident_api_detail(request, incident_id):
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Authentication is required.'}, status=401)
    if request.method != 'GET':
        return JsonResponse({'error': 'Method not allowed.'}, status=405)
    incident = Incident.objects.select_related('creator', 'inspection', 'reviewer').filter(
        incident_id=incident_id,
    ).first()
    if incident is None or not _can_view_incident(request.user, incident):
        return JsonResponse({'error': 'Incident not found.'}, status=404)
    return JsonResponse(_incident_data(incident))


def incident_api_review(request, incident_id):
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Authentication is required.'}, status=401)
    if request.method != 'PUT':
        return JsonResponse({'error': 'Method not allowed.'}, status=405)
    if request.user.role != 'supervisor':
        return JsonResponse({'error': 'Only Supervisors can review incidents.'}, status=403)
    incident = Incident.objects.filter(incident_id=incident_id).first()
    if incident is None:
        return JsonResponse({'error': 'Incident not found.'}, status=404)
    try:
        payload = json.loads(request.body or '{}')
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Provide valid JSON.'}, status=400)
    if not isinstance(payload, dict):
        return JsonResponse({'error': 'Provide a valid JSON object.'}, status=400)
    error = apply_supervisor_review(
        incident,
        payload.get('decision'),
        payload.get('comment'),
        request.user,
    )
    if error:
        return JsonResponse({'error': error}, status=400)
    incident.refresh_from_db()
    return JsonResponse(_incident_data(incident))
