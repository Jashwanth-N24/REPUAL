from django.contrib import admin
from .models import Batch, Inspection

class InspectionInline(admin.TabularInline):
    model = Inspection
    fields = ('id', 'original_filename', 'status', 'original_predicted_class', 'confidence', 'review_status')
    readonly_fields = fields
    extra = 0
    can_delete = False


@admin.register(Batch)
class BatchAdmin(admin.ModelAdmin):
    list_display = ('batch_id', 'product', 'submitter', 'status', 'completed_items', 'failed_items', 'total_items', 'created_at')
    list_filter = ('status', 'product', 'created_at')
    search_fields = ('batch_id', 'submitter__username')
    inlines = [InspectionInline]


@admin.register(Inspection)
class InspectionAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'original_filename', 'product', 'submitter', 'status',
        'original_predicted_class', 'confidence', 'review_status', 'reviewed_class', 'created_at'
    )
    list_filter = ('status', 'original_predicted_class', 'review_status', 'product', 'created_at')
    search_fields = ('original_filename', 'id', 'submitter__username', 'reviewer__username')
    readonly_fields = (
        'original_predicted_class', 'confidence', 'defect_probability', 'model_version',
        'file_size', 'image_width', 'image_height', 'image_format', 'created_at', 'updated_at'
    )

