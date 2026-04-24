# patients/serializers.py

from rest_framework import serializers
from .models import Patient, Condition


class ConditionSerializer(serializers.ModelSerializer):
    """Serializer for individual medical conditions linked to a patient."""

    class Meta:
        model  = Condition
        fields = [
            'id', 'name', 'severity',
            'diagnosed_on', 'notes'
        ]


class PatientSerializer(serializers.ModelSerializer):
    """
    Full patient serializer with nested conditions and calculated age.
    Hospital is read-only — always auto-assigned from TenantMixin in view.
    """

    # Nested conditions — read only, managed via separate endpoints
    conditions = ConditionSerializer(many=True, read_only=True)

    # Computed age from dob — read only
    age = serializers.IntegerField(read_only=True)

    class Meta:
        model  = Patient
        fields = [
            'id', 'hospital', 'first_name', 'last_name',
            'dob', 'age', 'email', 'contact_info',
            'is_chronic', 'conditions',
            'created_at', 'updated_at'
        ]
        # Hospital is auto-assigned from middleware — never sent by client
        read_only_fields = [
            'id', 'hospital', 'created_at', 'updated_at', 'age'
        ]

    def validate_email(self, value):
        # Check email uniqueness on both create and update
        qs = Patient.objects.filter(email=value)
        if self.instance:
            # On update exclude the current patient from the check
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError(
                'A patient with this email already exists.'
            )
        return value


class PatientListSerializer(serializers.ModelSerializer):
    """
    Lightweight serializer for patient list view.
    Shows condition count instead of full nested list for performance.
    """

    # Show count instead of full nested conditions list
    condition_count = serializers.IntegerField(
        source='conditions.count',
        read_only=True
    )
    age = serializers.IntegerField(read_only=True)

    class Meta:
        model  = Patient
        fields = [
            'id', 'first_name', 'last_name',
            'age', 'email', 'contact_info',
            'is_chronic', 'condition_count'
        ]