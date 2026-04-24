# leads/serializers.py

from rest_framework import serializers
from .models import Lead, LeadCriteria


class LeadCriteriaSerializer(serializers.ModelSerializer):
    """
    Serializer for LeadCriteria model.
    Hospital and created_by are auto assigned in view — read only here.
    """

    # Show hospital name instead of just ID
    hospital_name  = serializers.CharField(
        source='hospital.name',
        read_only=True
    )

    # Show creator username instead of just ID
    created_by_username = serializers.CharField(
        source='created_by.username',
        read_only=True
    )

    class Meta:
        model  = LeadCriteria
        fields = [
            'id', 'hospital', 'hospital_name',
            'name', 'criteria', 'is_active',
            'created_by', 'created_by_username',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'hospital', 'hospital_name',
            'created_by', 'created_by_username',
            'created_at', 'updated_at'
        ]

    def validate_criteria(self, value):
        """
        Validate that criteria JSON contains at least one valid key.
        Supported keys: condition, min_age, max_age, severity, is_chronic
        """
        valid_keys = ['condition', 'min_age', 'max_age', 'severity', 'is_chronic']

        if not isinstance(value, dict):
            raise serializers.ValidationError(
                'Criteria must be a JSON object.'
            )

        if not value:
            raise serializers.ValidationError(
                'Criteria cannot be empty.'
            )

        # Check at least one valid key exists
        if not any(key in value for key in valid_keys):
            raise serializers.ValidationError(
                f'Criteria must contain at least one of: {valid_keys}'
            )

        return value


class LeadSerializer(serializers.ModelSerializer):
    """
    Full lead serializer with nested patient and criteria info.
    Hospital and criteria are set automatically — read only here.
    """

    # Show patient name for readability
    patient_name    = serializers.SerializerMethodField()

    # Show hospital name
    hospital_name   = serializers.CharField(
        source='hospital.name',
        read_only=True
    )

    # Show criteria name that generated this lead
    criteria_name   = serializers.CharField(
        source='criteria.name',
        read_only=True
    )

    # Show assigned doctor username
    assigned_to_username = serializers.CharField(
        source='assigned_to.username',
        read_only=True
    )

    class Meta:
        model  = Lead
        fields = [
            'id', 'patient', 'patient_name',
            'hospital', 'hospital_name',
            'criteria', 'criteria_name',
            'assigned_to', 'assigned_to_username',
            'status', 'notes',
            'lead_date', 'updated_at'
        ]
        read_only_fields = [
            'id', 'patient', 'patient_name',
            'hospital', 'hospital_name',
            'criteria', 'criteria_name',
            'lead_date', 'updated_at'
        ]

    def get_patient_name(self, obj):
        """Return full patient name."""
        return f'{obj.patient.first_name} {obj.patient.last_name}'


class LeadListSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for lead list view.
    Less data for better performance on large lists.
    """

    patient_name         = serializers.SerializerMethodField()
    assigned_to_username = serializers.CharField(
        source='assigned_to.username',
        read_only=True
    )
    criteria_name        = serializers.CharField(
        source='criteria.name',
        read_only=True
    )

    class Meta:
        model  = Lead
        fields = [
            'id', 'patient_name', 'status',
            'criteria_name', 'assigned_to_username',
            'lead_date'
        ]

    def get_patient_name(self, obj):
        return f'{obj.patient.first_name} {obj.patient.last_name}'