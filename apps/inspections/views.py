import os
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST, require_GET
from django.core.exceptions import PermissionDenied
from django.http import JsonResponse, HttpResponseForbidden
from django.utils import timezone
from django.db.models import Count, Q
from django.core.paginator import Paginator
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser

from .models import Inspection, Batch
from .forms import (
    SingleInspectionUploadForm,
    BatchInspectionUploadForm,
    SupervisorReviewForm,
    HistoryFilterForm
)
from .serializers import InspectionSerializer, BatchSerializer, SupervisorReviewSerializer
from .tasks import execute_inspection_logic, enqueue_inspection, enqueue_batch
from .validators import validate_batch_size, validate_image_file
from apps.accounts.permissions import IsSupervisorRole, IsAdminRole, IsEngineerRole
from apps.products.models import Product


# ==========================================
# Web UI Views
# ==========================================

@login_required
def dashboard_view(request):
    """Manufacturing quality dashboard showing real-time statistics."""
    user = request.user
    
    if user.is_supervisor_role:
        inspections = Inspection.objects.all()
        batches = Batch.objects.all()[:5]
    else:
        inspections = Inspection.objects.filter(submitter=user)
        batches = Batch.objects.filter(submitter=user)[:5]

    total_count = inspections.count()
    completed_count = inspections.filter(status=Inspection.STATUS_COMPLETED).count()
    failed_count = inspections.filter(status=Inspection.STATUS_FAILED).count()
    
    defective_count = inspections.filter(
        status=Inspection.STATUS_COMPLETED,
        original_predicted_class=Inspection.CLASS_DEFECTIVE
    ).count()

    normal_count = inspections.filter(
        status=Inspection.STATUS_COMPLETED,
        original_predicted_class=Inspection.CLASS_NORMAL
    ).count()

    pending_review_count = Inspection.objects.filter(
        status=Inspection.STATUS_COMPLETED,
        review_status=Inspection.REVIEW_PENDING
    ).count()

    defect_rate = round((defective_count / completed_count * 100), 1) if completed_count > 0 else 0

    recent_inspections = inspections[:10]

    return render(request, 'inspections/dashboard.html', {
        'total_count': total_count,
        'completed_count': completed_count,
        'failed_count': failed_count,
        'defective_count': defective_count,
        'normal_count': normal_count,
        'defect_rate': defect_rate,
        'pending_review_count': pending_review_count,
        'recent_inspections': recent_inspections,
        'recent_batches': batches,
    })


@login_required
def single_inspect_view(request):
    """Handles single image inspection upload and immediate evaluation."""
    if request.method == 'POST':
        form = SingleInspectionUploadForm(request.POST, request.FILES)
        if form.is_valid():
            product = form.cleaned_data['product']
            image_file = form.cleaned_data['image']

            # Create queued inspection record
            inspection = Inspection.objects.create(
                product=product,
                submitter=request.user,
                original_filename=image_file.name,
                image=image_file,
                file_size=image_file.size,
                status=Inspection.STATUS_QUEUED
            )

            # Process inspection
            execute_inspection_logic(inspection.id)
            inspection.refresh_from_db()

            if inspection.status == Inspection.STATUS_COMPLETED:
                messages.success(request, f"Inspection completed! Classification: {inspection.original_predicted_class} (Confidence: {int(inspection.confidence * 100)}%)")
            else:
                messages.warning(request, f"Inspection rejected: {inspection.failure_reason}")

            return redirect('inspections:detail', pk=inspection.id)
        else:
            messages.error(request, "Please review the upload form errors.")
    else:
        form = SingleInspectionUploadForm()

    return render(request, 'inspections/single_upload.html', {'form': form})


@login_required
def batch_inspect_view(request):
    """Handles small batch upload (1 to 10 files) with background Celery/Redis queue."""
    if request.method == 'POST':
        form = BatchInspectionUploadForm(request.POST, request.FILES)
        raw_files = request.FILES.getlist('images')

        # Validate batch size strictly
        is_batch_valid, batch_err = validate_batch_size(len(raw_files))
        if not is_batch_valid:
            messages.error(request, batch_err)
            return render(request, 'inspections/batch_upload.html', {'form': form})

        if form.is_valid():
            product = form.cleaned_data['product']
            files = form.cleaned_data.get('images') or raw_files
            if not isinstance(files, list):
                files = [files]

            # Create Batch container
            batch = Batch.objects.create(
                submitter=request.user,
                product=product,
                status=Batch.STATUS_QUEUED,
                total_items=len(files)
            )

            # Persist each file item
            for f in files:
                Inspection.objects.create(
                    batch=batch,
                    product=product,
                    submitter=request.user,
                    original_filename=f.name,
                    image=f,
                    file_size=f.size,
                    status=Inspection.STATUS_QUEUED
                )

            # Dispatch batch asynchronously via Celery
            enqueue_batch(batch.batch_id)
            messages.success(request, f"Batch {str(batch.batch_id)[:8]} with {len(files)} items submitted for background processing.")
            return redirect('inspections:batch_detail', batch_id=batch.batch_id)
        else:
            messages.error(request, "Please check the batch upload errors.")
    else:
        form = BatchInspectionUploadForm()

    return render(request, 'inspections/batch_upload.html', {'form': form})


@login_required
def batch_detail_view(request, batch_id):
    """Live monitor for background batch processing with real-time status updates."""
    batch = get_object_or_404(Batch, batch_id=batch_id)
    
    # Non-supervisors can only view their own batches
    if not request.user.is_supervisor_role and batch.submitter != request.user:
        raise PermissionDenied("You are not authorized to view this batch.")

    inspections = batch.inspections.all()
    return render(request, 'inspections/batch_detail.html', {
        'batch': batch,
        'inspections': inspections,
    })


@login_required
@require_GET
def batch_status_api(request, batch_id):
    """AJAX endpoint for polling batch status and individual item progression."""
    batch = get_object_or_404(Batch, batch_id=batch_id)
    
    if not request.user.is_supervisor_role and batch.submitter != request.user:
        return JsonResponse({'error': 'Forbidden'}, status=403)

    items = []
    for insp in batch.inspections.all():
        items.append({
            'id': insp.id,
            'filename': insp.original_filename,
            'status': insp.status,
            'predicted_class': insp.original_predicted_class,
            'confidence': insp.confidence,
            'failure_reason': insp.failure_reason,
            'image_url': insp.image.url if insp.image else '',
        })

    return JsonResponse({
        'batch_id': str(batch.batch_id),
        'status': batch.status,
        'total_items': batch.total_items,
        'completed_items': batch.completed_items,
        'failed_items': batch.failed_items,
        'progress_percentage': batch.progress_percentage,
        'items': items,
    })


@login_required
def inspection_history_view(request):
    """
    Searchable, filterable inspection history table.
    Engineers see only their own inspections. Supervisors and Admins see all.
    """
    user = request.user
    if user.is_supervisor_role:
        queryset = Inspection.objects.all()
    else:
        queryset = Inspection.objects.filter(submitter=user)

    filter_form = HistoryFilterForm(request.GET)
    if filter_form.is_valid():
        prediction = filter_form.cleaned_data.get('prediction')
        review_status = filter_form.cleaned_data.get('review_status')
        status_filter = filter_form.cleaned_data.get('status')
        query = filter_form.cleaned_data.get('q')

        if prediction:
            queryset = queryset.filter(original_predicted_class=prediction)
        if review_status:
            queryset = queryset.filter(review_status=review_status)
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        if query:
            queryset = queryset.filter(
                Q(original_filename__icontains=query) |
                Q(id__icontains=query) |
                Q(product__product_id__icontains=query)
            )

    paginator = Paginator(queryset, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'inspections/history.html', {
        'page_obj': page_obj,
        'filter_form': filter_form,
        'total_filtered': queryset.count(),
    })


@login_required
def inspection_detail_view(request, pk):
    """Detailed view of an inspection with immutable prediction and supervisor review audit."""
    inspection = get_object_or_404(Inspection, pk=pk)

    # Permission check: Engineers can only see their own inspections
    if not request.user.is_supervisor_role and inspection.submitter != request.user:
        raise PermissionDenied("You can only view your own submitted inspections.")

    review_form = SupervisorReviewForm(initial={
        'reviewed_class': inspection.reviewed_class or inspection.original_predicted_class or 'Normal',
        'review_comment': inspection.review_comment
    })

    return render(request, 'inspections/detail.html', {
        'inspection': inspection,
        'review_form': review_form,
    })


@login_required
@require_POST
def supervisor_review_submit_view(request, pk):
    """
    Backend-enforced Supervisor review submission.
    Denies access with 403 Forbidden if called by an Engineer!
    Preserves original model prediction unchanged.
    """
    inspection = get_object_or_404(Inspection, pk=pk)

    # BACKEND AUTHORIZATION ENFORCEMENT
    if not request.user.is_supervisor_role:
        messages.error(request, "Permission Denied: Quality Engineers are strictly prohibited from reviewing or correcting inspection results.")
        raise PermissionDenied("Only Supervisors are authorized to submit reviews.")

    if inspection.status != Inspection.STATUS_COMPLETED:
        messages.error(request, "Cannot review an incomplete or failed inspection.")
        return redirect('inspections:detail', pk=pk)

    action = request.POST.get('review_action', 'confirm')
    reviewed_class = request.POST.get('reviewed_class')
    review_comment = request.POST.get('review_comment', '').strip()

    if reviewed_class not in [Inspection.CLASS_NORMAL, Inspection.CLASS_DEFECTIVE]:
        messages.error(request, "Invalid classification chosen.")
        return redirect('inspections:detail', pk=pk)

    # Update SEPARATE review fields only. Original model output remains immutable!
    inspection.reviewer = request.user
    inspection.reviewed_at = timezone.now()
    inspection.reviewed_class = reviewed_class
    inspection.review_comment = review_comment

    if action == 'confirm' or reviewed_class == inspection.original_predicted_class:
        inspection.review_status = Inspection.REVIEW_CONFIRMED
        messages.success(request, f"Supervisor confirmation recorded for Inspection #{inspection.id}.")
    else:
        inspection.review_status = Inspection.REVIEW_CORRECTED
        messages.warning(request, f"Supervisor corrected Inspection #{inspection.id} from {inspection.original_predicted_class} to {reviewed_class}.")

    inspection.save(update_fields=['review_status', 'reviewed_class', 'reviewer', 'reviewed_at', 'review_comment', 'updated_at'])

    return redirect('inspections:detail', pk=pk)


# ==========================================
# REST API ViewSets
# ==========================================

class InspectionViewSet(viewsets.ModelViewSet):
    """
    REST API for visual quality inspections.
    Enforces role permissions at the backend API layer.
    """
    serializer_class = InspectionSerializer
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_queryset(self):
        user = self.request.user
        if not user.is_authenticated:
            return Inspection.objects.none()
        if user.is_supervisor_role:
            return Inspection.objects.all()
        return Inspection.objects.filter(submitter=user)

    def perform_create(self, serializer):
        product_id = self.request.data.get('product')
        product = get_object_or_404(Product, pk=product_id)
        image_file = self.request.FILES.get('image')

        inspection = serializer.save(
            product=product,
            submitter=self.request.user,
            original_filename=image_file.name if image_file else 'uploaded_image',
            file_size=image_file.size if image_file else 0,
            status=Inspection.STATUS_QUEUED
        )
        execute_inspection_logic(inspection.id)
        inspection.refresh_from_db()

    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAuthenticated])
    def review(self, request, pk=None):
        """
        Supervisor review endpoint.
        Strictly returns 403 Forbidden if caller is an Engineer!
        """
        # STRICT SERVER-SIDE ROLE CHECK
        if not request.user.is_supervisor_role:
            return Response(
                {"detail": "Permission denied: Only Supervisors can review or correct inspection results."},
                status=status.HTTP_403_FORBIDDEN
            )

        inspection = self.get_object()
        if inspection.status != Inspection.STATUS_COMPLETED:
            return Response(
                {"error": "Cannot review uncompleted or failed inspection."},
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = SupervisorReviewSerializer(data=request.data)
        if serializer.is_valid():
            reviewed_class = serializer.validated_data['reviewed_class']
            review_comment = serializer.validated_data.get('review_comment', '')
            action_type = serializer.validated_data.get('action', 'confirm')

            inspection.reviewer = request.user
            inspection.reviewed_at = timezone.now()
            inspection.reviewed_class = reviewed_class
            inspection.review_comment = review_comment

            if action_type == 'confirm' or reviewed_class == inspection.original_predicted_class:
                inspection.review_status = Inspection.REVIEW_CONFIRMED
            else:
                inspection.review_status = Inspection.REVIEW_CORRECTED

            inspection.save(update_fields=['review_status', 'reviewed_class', 'reviewer', 'reviewed_at', 'review_comment', 'updated_at'])

            return Response(InspectionSerializer(inspection, context={'request': request}).data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class BatchViewSet(viewsets.ReadOnlyModelViewSet):
    """REST API for tracking inspection batches."""
    serializer_class = BatchSerializer

    def get_queryset(self):
        user = self.request.user
        if not user.is_authenticated:
            return Batch.objects.none()
        if user.is_supervisor_role:
            return Batch.objects.all()
        return Batch.objects.filter(submitter=user)
