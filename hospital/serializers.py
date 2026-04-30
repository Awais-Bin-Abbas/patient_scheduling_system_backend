# hospital/serializers.py

from rest_framework import serializers
from .models import Hospital

class HospitalSerializer(serializers.ModelSerializer):
    """Full serializer for creating and updating hospital records."""

    # Show owner username as read-only instead of just the ID
    owner_username = serializers.CharField(
        source='owner.username',
        read_only=True
    )

    class Meta:
        model = Hospital
        fields = [
            'id', 'name', 'slug', 'address',
            'contact_info', 'owner', 'owner_username',
            'is_active', 'created_at', 'updated_at'
        ]
        # These fields are auto-managed — never set by the user
        read_only_fields = ['id', 'slug', 'created_at', 'updated_at', 'owner_username']

    def validate_name(self, value):
        # Prevent duplicate hospital names (case-insensitive check)
        qs = Hospital.objects.filter(name__iexact=value)
        # On update, exclude the current instance from the check
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("A hospital with this name already exists.")
        return value

    def validate_contact_info(self, value):
        # Basic length check for contact info field
        if len(value) < 7:
            raise serializers.ValidationError("Contact info must be at least 7 characters.")
        return value


class HospitalListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for listing hospitals — fewer fields for performance."""

    class Meta:
        model = Hospital
        fields = ['id', 'name', 'slug', 'address', 'contact_info', 'is_active']