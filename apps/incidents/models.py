import uuid

from django.conf import settings
from django.db import models

from apps.inspections.models import Inspection


class Incident(models.Model):
    EVIDENCE_SUFFICIENT = 'Sufficient'
    EVIDENCE_INSUFFICIENT = 'Insufficient'
    EVIDENCE_CHOICES = (
        (EVIDENCE_SUFFICIENT, 'Sufficient'),
        (EVIDENCE_INSUFFICIENT, 'Insufficient'),
    )

    STATUS_READY = 'ready_for_follow_up'
    STATUS_MANUAL_REVIEW = 'manual_review_required'
    STATUS_CHOICES = (
        (STATUS_READY, 'Ready for Supervisor review'),
        (STATUS_MANUAL_REVIEW, 'Manual review required'),
    )

    REVIEW_PENDING = 'Pending'
    REVIEW_APPROVED = 'Approved for follow-up'
    REVIEW_NEEDS_INFO = 'Needs more information'
    REVIEW_CHOICES = (
        (REVIEW_PENDING, 'Pending'),
        (REVIEW_APPROVED, 'Approved for follow-up'),
        (REVIEW_NEEDS_INFO, 'Needs more information'),
    )

    incident_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    inspection = models.OneToOneField(
        Inspection, on_delete=models.PROTECT, related_name='quality_incident'
    )
    product_id_snapshot = models.CharField(max_length=64)
    original_model_result = models.CharField(max_length=20)
    model_version = models.CharField(max_length=64, blank=True)
    summary = models.TextField()
    actions = models.JSONField(default=list, blank=True)
    evidence_status = models.CharField(max_length=20, choices=EVIDENCE_CHOICES)
    evidence_reason = models.TextField(blank=True)
    workflow_status = models.CharField(max_length=40, choices=STATUS_CHOICES)
    source_references = models.JSONField(default=list, blank=True)
    creator = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='created_quality_incidents'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    review_status = models.CharField(
        max_length=32, choices=REVIEW_CHOICES, default=REVIEW_PENDING
    )
    reviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
        related_name='reviewed_quality_incidents'
    )
    review_comment = models.TextField(blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Quality incident'
        verbose_name_plural = 'Quality incidents'

    def __str__(self):
        return f'Incident {self.incident_id} for inspection {self.inspection_id}'
