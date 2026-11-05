from rest_framework import serializers
from core.models import User, Machine, Manual, QuestionHistory


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ('id', 'username', 'role')


class MachineSerializer(serializers.ModelSerializer):
    class Meta:
        model = Machine
        fields = ('id', 'machine_id', 'name', 'description')


class ManualSerializer(serializers.ModelSerializer):
    machine_id = serializers.CharField(source='machine.machine_id', read_only=True)

    class Meta:
        model = Manual
        fields = (
            'id',
            'machine',
            'machine_id',
            'document_id',
            'title',
            'revision',
            'pdf_file',
            'uploaded_at',
        )


class QuestionHistorySerializer(serializers.ModelSerializer):
    engineer_name = serializers.CharField(
        source='engineer.username', read_only=True
    )
    machine_code = serializers.CharField(source='machine.machine_id', read_only=True)

    class Meta:
        model = QuestionHistory
        fields = (
            'id',
            'engineer_name',
            'machine_code',
            'question',
            'answer',
            'source_references',
            'status',
            'security_flag',
            'confidence_score',
            'timestamp',
        )
