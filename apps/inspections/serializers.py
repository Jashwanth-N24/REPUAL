from rest_framework import serializers
from .models import Inspection, Batch
from apps.products.models import Product

class InspectionSerializer(serializers.ModelSerializer):
    submitter_username = serializers.CharField(source='submitter.username', read_only=True)
    reviewer_username = serializers.CharField(source='reviewer.username', read_only=True, default=None)
    product_name = serializers.CharField(source='product.product_name', read_only=True)
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = Inspection
        fields = [
            'id', 'batch', 'product', 'product_name', 'submitter', 'submitter_username',
            'original_filename', 'image_url', 'file_size', 'image_width', 'image_height', 'image_format',
            'status', 'failure_reason',
            # Immutable original model predictions
            'original_predicted_class', 'confidence', 'defect_probability', 'model_version',
            # Supervisor review fields
            'review_status', 'reviewed_class', 'reviewer', 'reviewer_username', 'reviewed_at', 'review_comment',
            'final_verdict', 'is_defective',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'original_predicted_class', 'confidence', 'defect_probability', 'model_version',
            'status', 'failure_reason', 'review_status', 'reviewed_class', 'reviewer', 'reviewed_at',
            'created_at', 'updated_at'
        ]

    def get_image_url(self, obj):
        if obj.image:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.image.url)
            return obj.image.url
        return None


class SupervisorReviewSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=['confirm', 'correct'], required=False, default='confirm')
    reviewed_class = serializers.ChoiceField(choices=['Normal', 'Defective'], required=True)
    review_comment = serializers.CharField(required=False, allow_blank=True, default='')

    def validate(self, attrs):
        return attrs


class BatchSerializer(serializers.ModelSerializer):
    submitter_username = serializers.CharField(source='submitter.username', read_only=True)
    product_name = serializers.CharField(source='product.product_name', read_only=True)
    inspections = InspectionSerializer(many=True, read_only=True)
    progress_percentage = serializers.IntegerField(read_only=True)

    class Meta:
        model = Batch
        fields = [
            'batch_id', 'product', 'product_name', 'submitter', 'submitter_username',
            'status', 'total_items', 'completed_items', 'failed_items',
            'progress_percentage', 'created_at', 'updated_at', 'inspections'
        ]

