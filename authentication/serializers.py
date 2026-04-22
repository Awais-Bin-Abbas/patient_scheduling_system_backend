# authentication/serializers.py

from rest_framework import serializers
from rest_framework.validators import UniqueValidator  # Built-in DRF unique validator
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_decode
from django.utils.encoding import force_str

User = get_user_model()

class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)

    # UniqueValidator runs during is_valid() — before create() is ever called
    # This prevents the IntegrityError from ever reaching the database
    email = serializers.EmailField(
        required=True,
        validators=[
            UniqueValidator(
                queryset=User.objects.all(),
                message="A user with this email already exists."
            )
        ]
    )

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'password', 'role', 'hospital']

    def create(self, validated_data):
        # Safe to access email directly now — UniqueValidator already confirmed it
        user = User.objects.create_user(
            username=validated_data['username'],
            email=validated_data['email'],
            password=validated_data['password'],
            role=validated_data.get('role', 'Doctor'),
            hospital=validated_data.get('hospital', None),
        )
        return user


class UserDetailSerializer(serializers.ModelSerializer):
    """Serializer to return user profile details — no password exposed."""
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'role', 'hospital', 'mfa_enabled']
        read_only_fields = ['id', 'username', 'role']


class ChangePasswordSerializer(serializers.Serializer):
    """Validates old password before allowing new password to be set."""
    old_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True, min_length=8)

    def validate_old_password(self, value):
        # Verify current password matches before allowing the change
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError("Old password is incorrect.")
        return value


class ForgotPasswordSerializer(serializers.Serializer):
    """Accepts email and verifies it belongs to a registered user."""
    email = serializers.EmailField()

    def validate_email(self, value):
        # Only proceed if the email exists in the system
        if not User.objects.filter(email=value).exists():
            raise serializers.ValidationError("No account found with this email address.")
        return value


class PasswordResetConfirmSerializer(serializers.Serializer):
    """Validates the reset token and uid from the password reset link."""
    uid = serializers.CharField()
    token = serializers.CharField()
    new_password = serializers.CharField(write_only=True, min_length=8)

    def validate(self, data):
        try:
            # Decode base64 uid back to user primary key
            uid = force_str(urlsafe_base64_decode(data['uid']))
            user = User.objects.get(pk=uid)
        except (User.DoesNotExist, ValueError):
            raise serializers.ValidationError("Invalid reset link.")

        # Check the token is valid and not expired
        if not default_token_generator.check_token(user, data['token']):
            raise serializers.ValidationError("Reset link has expired or is invalid.")

        # Attach user to validated data so the view can access it
        data['user'] = user
        return data