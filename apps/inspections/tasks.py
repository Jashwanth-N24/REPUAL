import logging
from celery import shared_task
from django.conf import settings
from .models import Inspection, Batch
from .validators import validate_image_file
from Model.inference import predict

logger = logging.getLogger(__name__)

def execute_inspection_logic(inspection_id):
    """
    Core inspection execution:
    1. Validates content, dimensions (64-4096), size (<=5MB), format (JPEG/PNG).
    2. Persists invalid items as failed attempts without a prediction; NEVER passes them to the model.
    3. For valid files, invokes the frozen model inference pipeline.
    4. Updates batch counters.
    """
    try:
        inspection = Inspection.objects.get(id=inspection_id)
    except Inspection.DoesNotExist:
        logger.error(f"Inspection with id {inspection_id} not found.")
        return False

    inspection.status = Inspection.STATUS_PROCESSING
    inspection.save(update_fields=['status', 'updated_at'])

    image_path = inspection.image.path
    is_valid, error_reason, (width, height), detected_format = validate_image_file(image_path)

    if not is_valid:
        # Invalid file rejected before inference!
        inspection.status = Inspection.STATUS_FAILED
        inspection.failure_reason = error_reason
        inspection.original_predicted_class = None
        inspection.confidence = None
        inspection.defect_probability = None
        inspection.model_version = None
        if width and height:
            inspection.image_width = width
            inspection.image_height = height
        if detected_format:
            inspection.image_format = detected_format
        inspection.save()
        logger.warning(f"Inspection #{inspection_id} rejected: {error_reason}")
    else:
        # Valid file: proceed to model inference
        try:
            pred = predict(image_path)
            inspection.image_width = width
            inspection.image_height = height
            inspection.image_format = detected_format
            inspection.original_predicted_class = pred['predicted_class']
            inspection.confidence = round(pred['confidence'], 4)
            inspection.defect_probability = round(pred['defect_probability'], 4)
            inspection.model_version = pred['model_version']
            inspection.status = Inspection.STATUS_COMPLETED
            inspection.failure_reason = ""
            inspection.save()
            logger.info(f"Inspection #{inspection_id} completed: {inspection.original_predicted_class} ({inspection.confidence})")
        except Exception as exc:
            inspection.status = Inspection.STATUS_FAILED
            inspection.failure_reason = f"Inference execution error: {str(exc)}"
            inspection.save()
            logger.exception(f"Inference error on inspection #{inspection_id}")

    if inspection.batch:
        inspection.batch.update_progress()

    return True


@shared_task(name='apps.inspections.tasks.process_inspection_task')
def process_inspection_task(inspection_id):
    """Celery task to run inspection inference asynchronously."""
    return execute_inspection_logic(inspection_id)


@shared_task(name='apps.inspections.tasks.process_batch_task')
def process_batch_task(batch_id):
    """Celery task to coordinate batch processing items."""
    try:
        batch = Batch.objects.get(batch_id=batch_id)
    except Batch.DoesNotExist:
        logger.error(f"Batch {batch_id} not found.")
        return False

    batch.status = Batch.STATUS_PROCESSING
    batch.save(update_fields=['status', 'updated_at'])

    for inspection in batch.inspections.all():
        execute_inspection_logic(inspection.id)

    batch.update_progress()
    return True


def enqueue_inspection(inspection_id):
    """
    Enqueues the inspection task to Celery & Redis.
    Gracefully falls back to synchronous execution if Celery worker is not currently listening,
    ensuring robust execution in any testing scenario.
    """
    try:
        # Attempt Celery async dispatch
        process_inspection_task.delay(inspection_id)
    except Exception as exc:
        logger.warning(f"Celery dispatch failed ({exc}), running synchronously as fallback.")
        execute_inspection_logic(inspection_id)


def enqueue_batch(batch_id):
    """Enqueues batch processing to Celery & Redis with fallback."""
    try:
        process_batch_task.delay(batch_id)
    except Exception as exc:
        logger.warning(f"Celery batch dispatch failed ({exc}), running synchronously as fallback.")
        process_batch_task(batch_id)

