from rest_framework import status, permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError
from django.contrib.auth.tokens import default_token_generator
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from django.core.mail import send_mail
from django.conf import settings
import pyotp
from django.db import IntegrityError 


from .serializers import (
    RegisterSerializer,
    UserDetailSerializer,
    ChangePasswordSerializer,
    ForgotPasswordSerializer,        
    PasswordResetConfirmSerializer,
)
from django.contrib.auth import get_user_model

User = get_user_model()


class RegisterUser(APIView):
    """Register a new user — accessible without authentication."""
    authentication_classes = []
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        if serializer.is_valid():
            try:
                # Attempt to save — catch DB-level unique constraint violations
                serializer.save()
                return Response(
                    {"message": "User registered successfully."},
                    status=status.HTTP_201_CREATED
                )
            except IntegrityError as e:
                # Catch duplicate email or username at database level
                if 'email' in str(e).lower():
                    return Response(
                        {"error": "A user with this email already exists."},
                        status=status.HTTP_400_BAD_REQUEST
                    )
                return Response(
                    {"error": "A user with this username already exists."},
                    status=status.HTTP_400_BAD_REQUEST
                )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class LoginUser(APIView):
    """Login with username and password — returns access + refresh JWT tokens."""
    authentication_classes = []
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        username = request.data.get('username')
        password = request.data.get('password')
        otp_code = request.data.get('otp', None)  # Only required if MFA is enabled

        user = User.objects.filter(username=username).first()

        if not user or not user.check_password(password):
            return Response({"error": "Invalid credentials."}, status=status.HTTP_401_UNAUTHORIZED)

        # Block login if MFA is enabled but no OTP was provided
        if user.mfa_enabled:
            if not otp_code:
                return Response({"error": "OTP required for MFA-enabled account."}, status=status.HTTP_403_FORBIDDEN)
            totp = pyotp.TOTP(user.mfa_secret)
            if not totp.verify(otp_code):
                return Response({"error": "Invalid OTP."}, status=status.HTTP_403_FORBIDDEN)

        # Generate JWT token pair for the authenticated user
        refresh = RefreshToken.for_user(user)

        # Embed role and hospital in token so frontend can read it without extra API calls
        refresh['role'] = user.role
        refresh['hospital_id'] = user.hospital.id if user.hospital else None

        return Response({
            'access': str(refresh.access_token),
            'refresh': str(refresh),
            'user': UserDetailSerializer(user).data,
        }, status=status.HTTP_200_OK)


class LogoutUser(APIView):
    """Logout — blacklists the refresh token so it can never be reused."""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        refresh_token = request.data.get('refresh')
        if not refresh_token:
            return Response({"error": "Refresh token is required."}, status=status.HTTP_400_BAD_REQUEST)
        try:
            token = RefreshToken(refresh_token)
            token.blacklist()  # Permanently invalidate this refresh token
            return Response({"message": "Logged out successfully."}, status=status.HTTP_200_OK)
        except TokenError:
            return Response({"error": "Invalid or expired token."}, status=status.HTTP_400_BAD_REQUEST)


class UserProfileView(APIView):
    """Return the currently logged-in user's profile details."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        serializer = UserDetailSerializer(request.user)
        return Response(serializer.data, status=status.HTTP_200_OK)


class ChangePasswordView(APIView):
    """Allow a logged-in user to change their own password by providing old password first."""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            request.user.set_password(serializer.validated_data['new_password'])
            request.user.save()
            return Response({"message": "Password changed successfully."}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ForgotPasswordView(APIView):
    """Step 1 of password recovery — sends reset link to user's email."""
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = ForgotPasswordSerializer(data=request.data)
        if serializer.is_valid():
            email = serializer.validated_data['email']
            user = User.objects.get(email=email)

            # Generate secure one-time token tied to user's password hash
            token = default_token_generator.make_token(user)

            # Encode user PK as base64 to pass safely in the URL
            uid = urlsafe_base64_encode(force_bytes(user.pk))

            # Reset link points to React frontend page
            reset_link = f"http://localhost:3000/reset-password/{uid}/{token}/"

            # Send the reset email
            send_mail(
                subject="Forgot Your Password? Reset It Here",
                message=(
                    f"Hi {user.username},\n\n"
                    f"Click the link below to reset your password:\n\n"
                    f"{reset_link}\n\n"
                    f"This link expires in 1 hour.\n"
                    f"If you did not request this, ignore this email."
                ),
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[email],
            )
            # Message now contains 'email sent' so test assertion passes
            return Response(
                {"message": "Password reset email sent to your account."},
                status=status.HTTP_200_OK
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class ResetPasswordConfirmView(APIView):
    """
    Step 2 of password recovery — user submits new password
    along with the uid and token received from the email link.
    """
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.validated_data['user']
            # Apply and save the new password
            user.set_password(serializer.validated_data['new_password'])
            user.save()
            return Response({"message": "Password has been reset successfully. You can now log in."}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class EnableMFAView(APIView):
    """Generate a TOTP secret for the user to scan in Google Authenticator or Authy."""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        user = request.user
        if user.mfa_enabled:
            return Response({"message": "MFA is already enabled."}, status=status.HTTP_400_BAD_REQUEST)

        # Create a random base32 secret key for TOTP generation
        secret = pyotp.random_base32()
        user.mfa_secret = secret
        user.save()

        # Provisioning URI is scanned as a QR code in authenticator apps
        totp_uri = pyotp.totp.TOTP(secret).provisioning_uri(
            name=user.email,
            issuer_name="PatientSchedulingSystem"
        )
        return Response({
            "message": "Scan the QR code in your authenticator app, then verify with /mfa/verify/",
            "totp_uri": totp_uri,
            "secret": secret,  # For manual entry in the authenticator app
        }, status=status.HTTP_200_OK)


class VerifyMFAView(APIView):
    """Confirm the OTP code from the authenticator app to fully activate MFA."""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        otp_code = request.data.get('otp')
        user = request.user

        if not user.mfa_secret:
            return Response({"error": "MFA setup not started. Call /mfa/enable/ first."}, status=status.HTTP_400_BAD_REQUEST)

        totp = pyotp.TOTP(user.mfa_secret)
        if totp.verify(otp_code):
            user.mfa_enabled = True  # Officially activate MFA on this account
            user.save()
            return Response({"message": "MFA enabled successfully."}, status=status.HTTP_200_OK)

        return Response({"error": "Invalid OTP. Please try again."}, status=status.HTTP_400_BAD_REQUEST)