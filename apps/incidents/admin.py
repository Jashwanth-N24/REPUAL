from django.contrib import admin

from apps.incidents.models import Incident


@admin.register(Incident)
class IncidentAdmin(admin.ModelAdmin):
    list_display = (
        'incident_id', 'inspection', 'product_id_snapshot', 'evidence_status',
        'review_status', 'creator', 'created_at',
    )
    list_filter = ('evidence_status', 'review_status', 'created_at')
    search_fields = ('incident_id', 'inspection__id', 'product_id_snapshot', 'creator__username')
    readonly_fields = (
        'incident_id', 'inspection', 'product_id_snapshot', 'original_model_result',
        'model_version', 'summary', 'actions', 'evidence_status', 'evidence_reason',
        'workflow_status', 'source_references', 'creator', 'created_at',
        'review_status', 'reviewer', 'review_comment', 'reviewed_at',
    )
