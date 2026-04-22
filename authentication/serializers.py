from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str

User = get_user_model()

class RegisterSerializer(serializers.ModelSerializer):
    """Serializer for registering a new user with role and hospital assignment."""
    password = serializers.CharField(write_only=True, min_length=8)

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'password', 'role', 'hospital']

    def create(self, validated_data):
        # Use create_user to ensure password is hashed properly
        user = User.objects.create_user(
            username=validated_data['username'],
            email=validated_data['email'],
            password=validated_data['password'],
            role=validated_data.get('role', 'Doctor'),
            hospital=validated_data.get('hospital', None),
        )
        return user


class UserDetailSerializer(serializers.ModelSerializer):
    """Serializer to return user profile details (read-only, no password)."""
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'role', 'hospital', 'mfa_enabled']
        read_only_fields = ['id', 'username', 'role']


class ChangePasswordSerializer(serializers.Serializer):
    """Serializer to handle authenticated password change."""
    old_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True, min_length=8)

    def validate_old_password(self, value):
        # Verify the current password is correct before allowing change
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError("Old password is incorrect.")
        return value


# authentication/serializers.py  — only the changed class shown

class ForgotPasswordSerializer(serializers.Serializer):
    """
    Step 1 — Accepts the user's email to initiate the forgot password flow.
    Validates that the email actually belongs to a registered user.
    """
    email = serializers.EmailField()

    def validate_email(self, value):
        # Ensure this email exists in our system before sending anything
        if not User.objects.filter(email=value).exists():
            raise serializers.ValidationError("No account found with this email address.")
        return value
    

class PasswordResetConfirmSerializer(serializers.Serializer):
    """Serializer to validate and apply the new password from reset link."""
    uid = serializers.CharField()       # Base64-encoded user ID from the reset link
    token = serializers.CharField()     # One-time token from the reset link
    new_password = serializers.CharField(write_only=True, min_length=8)

    def validate(self, data):
        try:
            # Decode the user ID from base64
            uid = force_str(urlsafe_base64_decode(data['uid']))
            user = User.objects.get(pk=uid)
        except (User.DoesNotExist, ValueError):
            raise serializers.ValidationError("Invalid reset link.")

        # Verify the token is still valid and matches the user
        if not default_token_generator.check_token(user, data['token']):
            raise serializers.ValidationError("Reset link has expired or is invalid.")

        # Attach user to validated data for use in the view
        data['user'] = user
        return data