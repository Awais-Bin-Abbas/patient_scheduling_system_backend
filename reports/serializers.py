# reports/serializers.py

from rest_framework import serializers
from .models import Report


class ReportSerializer(serializers.ModelSerializer):
    """Full report serializer including generated data."""

    # Show hospital name instead of ID
    hospital_name    = serializers.CharField(
        source='hospital.name',
        read_only=True
    )

    # Show generator username
    generated_by_username = serializers.CharField(
        source='generated_by.username',
        read_only=True
    )

    class Meta:
        model  = Report
        fields = [
            'id', 'hospital', 'hospital_name',
            'generated_by', 'generated_by_username',
            'data', 'status', 'task_id',
            'created_at', 'completed_at'
        ]
        read_only_fields = [
            'id', 'hospital', 'hospital_name',
            'generated_by', 'generated_by_username',
            'data', 'status', 'task_id',
            'created_at', 'completed_at'
        ]


class ReportListSerializer(serializers.ModelSerializer):
    """Lightweight report serializer for list view."""

    hospital_name = serializers.CharField(
        source='hospital.name',
        read_only=True
    )

    class Meta:
        model  = Report
        fields = [
            'id', 'hospital_name', 'status',
            'created_at', 'completed_at'
        ]