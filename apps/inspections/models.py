import uuid
from django.db import models
from django.conf import settings
from apps.products.models import Product

class Batch(models.Model):
    STATUS_QUEUED = 'queued'
    STATUS_PROCESSING = 'processing'
    STATUS_COMPLETED = 'completed'
    STATUS_PARTIAL_FAILED = 'partial_failed'
    STATUS_FAILED = 'failed'

    STATUS_CHOICES = [
        (STATUS_QUEUED, 'Queued'),
        (STATUS_PROCESSING, 'Processing'),
        (STATUS_COMPLETED, 'Completed'),
        (STATUS_PARTIAL_FAILED, 'Completed with Failures'),
        (STATUS_FAILED, 'Failed'),
    ]

    batch_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    submitter = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='batches')
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name='batches')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_QUEUED)
    total_items = models.PositiveIntegerField(default=0)
    completed_items = models.PositiveIntegerField(default=0)
    failed_items = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Inspection Batch'
        verbose_name_plural = 'Inspection Batches'

    def update_progress(self):
        """Recalculates batch state from related inspections."""
        inspections = self.inspections.all()
        self.total_items = inspections.count()
        self.completed_items = inspections.filter(status=Inspection.STATUS_COMPLETED).count()
        self.failed_items = inspections.filter(status=Inspection.STATUS_FAILED).count()
        
        finished = self.completed_items + self.failed_items
        if finished == 0:
            self.status = self.STATUS_QUEUED
        elif finished < self.total_items:
            self.status = self.STATUS_PROCESSING
        else:
            if self.failed_items == 0:
                self.status = self.STATUS_COMPLETED
            elif self.completed_items == 0:
                self.status = self.STATUS_FAILED
            else:
                self.status = self.STATUS_PARTIAL_FAILED
        self.save(update_fields=['total_items', 'completed_items', 'failed_items', 'status', 'updated_at'])

    @property
    def progress_percentage(self):
        if self.total_items == 0:
            return 0
        return int(((self.completed_items + self.failed_items) / self.total_items) * 100)

    def __str__(self):
        return f"Batch {str(self.batch_id)[:8]} ({self.status}) - {self.completed_items}/{self.total_items} done"


class Inspection(models.Model):
    STATUS_QUEUED = 'queued'
    STATUS_PROCESSING = 'processing'
    STATUS_COMPLETED = 'completed'
    STATUS_FAILED = 'failed'

    STATUS_CHOICES = [
        (STATUS_QUEUED, 'Queued'),
        (STATUS_PROCESSING, 'Processing'),
        (STATUS_COMPLETED, 'Completed'),
        (STATUS_FAILED, 'Failed'),
    ]

    CLASS_NORMAL = 'Normal'
    CLASS_DEFECTIVE = 'Defective'
    CLASS_CHOICES = [
        (CLASS_NORMAL, 'Normal'),
        (CLASS_DEFECTIVE, 'Defective'),
    ]

    REVIEW_PENDING = 'pending'
    REVIEW_CONFIRMED = 'confirmed'
    REVIEW_CORRECTED = 'corrected'

    REVIEW_CHOICES = [
        (REVIEW_PENDING, 'Pending Review'),
        (REVIEW_CONFIRMED, 'Confirmed by Supervisor'),
        (REVIEW_CORRECTED, 'Corrected by Supervisor'),
    ]

    batch = models.ForeignKey(Batch, on_delete=models.SET_NULL, null=True, blank=True, related_name='inspections')
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name='inspections')
    submitter = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='inspections')
    
    # File details
    original_filename = models.CharField(max_length=255)
    image = models.FileField(upload_to='inspections/%Y/%m/%d/')
    file_size = models.PositiveIntegerField(help_text='File size in bytes')
    image_width = models.IntegerField(null=True, blank=True)
    image_height = models.IntegerField(null=True, blank=True)
    image_format = models.CharField(max_length=20, null=True, blank=True)

    # Execution status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_QUEUED)
    failure_reason = models.TextField(blank=True, help_text='Detailed readable reason if validation/inference fails')

    # IMMUTABLE Model Prediction
    original_predicted_class = models.CharField(max_length=20, choices=CLASS_CHOICES, null=True, blank=True)
    confidence = models.FloatField(null=True, blank=True, help_text='Confidence score of predicted class (0.0 to 1.0)')
    defect_probability = models.FloatField(null=True, blank=True, help_text='Probability of Defective class (0.0 to 1.0)')
    model_version = models.CharField(max_length=64, null=True, blank=True, help_text='Frozen classifier version string')

    # SEPARATE Supervisor Review
    review_status = models.CharField(max_length=20, choices=REVIEW_CHOICES, default=REVIEW_PENDING)
    reviewed_class = models.CharField(max_length=20, choices=CLASS_CHOICES, null=True, blank=True)
    reviewer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='reviewed_inspections')
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_comment = models.TextField(blank=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Visual Inspection'
        verbose_name_plural = 'Visual Inspections'

    @property
    def final_verdict(self):
        """Returns the effective classification (supervisor review if provided, else model prediction)."""
        if self.review_status in (self.REVIEW_CONFIRMED, self.REVIEW_CORRECTED) and self.reviewed_class:
            return self.reviewed_class
        return self.original_predicted_class

    @property
    def is_defective(self):
        return self.final_verdict == self.CLASS_DEFECTIVE

    def __str__(self):
        return f"Inspection #{self.id} ({self.original_filename}) - {self.status}: {self.original_predicted_class or self.failure_reason}"

