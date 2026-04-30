# authentication/views.py

from rest_framework import status, permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
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
from .permissions import IsAdmin, IsAdminOrDoctor
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
                serializer.save()
                return Response(
                    {"message": "User registered successfully."},
                    status=status.HTTP_201_CREATED
                )
            except IntegrityError as e:
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
        otp_code = request.data.get('otp', None)

        user = User.objects.filter(username=username).first()

        if not user or not user.check_password(password):
            return Response(
                {"error": "Invalid credentials."},
                status=status.HTTP_401_UNAUTHORIZED
            )

        if user.mfa_enabled:
            if not otp_code:
                return Response(
                    {"error": "OTP required for MFA-enabled account."},
                    status=status.HTTP_403_FORBIDDEN
                )
            totp = pyotp.TOTP(user.mfa_secret)
            if not totp.verify(otp_code, valid_window=1):
                return Response(
                    {"error": "Invalid OTP."},
                    status=status.HTTP_403_FORBIDDEN
                )

        refresh = RefreshToken.for_user(user)
        refresh['role'] = user.role
        refresh['hospital_id'] = user.hospital.id if user.hospital else None

        return Response({
            'access':  str(refresh.access_token),
            'refresh': str(refresh),
            'user':    UserDetailSerializer(user).data,
        }, status=status.HTTP_200_OK)


class LogoutUser(APIView):
    """Logout — blacklists the refresh token."""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        refresh_token = request.data.get('refresh')
        if not refresh_token:
            return Response(
                {"error": "Refresh token is required."},
                status=status.HTTP_400_BAD_REQUEST
            )
        try:
            token = RefreshToken(refresh_token)
            token.blacklist()
            return Response(
                {"message": "Logged out successfully."},
                status=status.HTTP_200_OK
            )
        except TokenError:
            return Response(
                {"error": "Invalid or expired token."},
                status=status.HTTP_400_BAD_REQUEST
            )


class UserProfileView(APIView):
    """Return the currently logged-in user's profile details."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        serializer = UserDetailSerializer(request.user)
        return Response(serializer.data, status=status.HTTP_200_OK)


class ChangePasswordView(APIView):
    """Allow a logged-in user to change their own password."""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = ChangePasswordSerializer(
            data=request.data,
            context={'request': request}
        )
        if serializer.is_valid():
            request.user.set_password(serializer.validated_data['new_password'])
            request.user.save()
            return Response(
                {"message": "Password changed successfully."},
                status=status.HTTP_200_OK
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ForgotPasswordView(APIView):
    """Step 1 of password recovery — sends reset link to user's email."""
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = ForgotPasswordSerializer(data=request.data)
        if serializer.is_valid():
            email = serializer.validated_data['email']
            user  = User.objects.get(email=email)

            token = default_token_generator.make_token(user)
            uid   = urlsafe_base64_encode(force_bytes(user.pk))

            # Points to React frontend
            reset_link = f"http://localhost:3001/reset-password/{uid}/{token}/"

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
            return Response(
                {"message": "Password reset email sent to your account."},
                status=status.HTTP_200_OK
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ResetPasswordConfirmView(APIView):
    """Step 2 — user submits new password with uid and token from email."""
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.validated_data['user']
            user.set_password(serializer.validated_data['new_password'])
            user.save()
            return Response(
                {"message": "Password has been reset successfully. You can now log in."},
                status=status.HTTP_200_OK
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class EnableMFAView(APIView):
    """Generate a TOTP secret for the user to scan in Google Authenticator."""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        user = request.user
        if user.mfa_enabled:
            return Response(
                {"message": "MFA is already enabled."},
                status=status.HTTP_400_BAD_REQUEST
            )

        secret = pyotp.random_base32()
        user.mfa_secret = secret
        user.save()

        totp_uri = pyotp.totp.TOTP(secret).provisioning_uri(
            name=user.email,
            issuer_name="PatientSchedulingSystem"
        )
        return Response({
            "message": "Scan the QR code in your authenticator app, then verify with /mfa/verify/",
            "totp_uri": totp_uri,
            "secret":   secret,
        }, status=status.HTTP_200_OK)


class VerifyMFAView(APIView):
    """Confirm the OTP code to fully activate MFA."""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        otp_code = request.data.get('otp')
        user     = request.user

        if not user.mfa_secret:
            return Response(
                {"error": "MFA setup not started. Call /mfa/enable/ first."},
                status=status.HTTP_400_BAD_REQUEST
            )

        totp = pyotp.TOTP(user.mfa_secret)
        if totp.verify(otp_code, valid_window=1):
            user.mfa_enabled = True
            user.save()
            return Response(
                {"message": "MFA enabled successfully."},
                status=status.HTTP_200_OK
            )
        return Response(
            {"error": "Invalid OTP. Please try again."},
            status=status.HTTP_400_BAD_REQUEST
        )


# ─── NEW ENDPOINTS ─────────────────────────────────────────────────────────────

@api_view(['GET'])
@permission_classes([AllowAny])
def list_hospitals_public(request):
    """
    Public endpoint — returns list of active hospitals.
    Used on setup screen before user has a hospital assigned.
    No authentication required.
    """
    from hospital.models import Hospital
    hospitals = Hospital.objects.filter(is_active=True).values(
        'id', 'name', 'address'
    )
    return Response(list(hospitals), status=status.HTTP_200_OK)


@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def assign_hospital(request):
    """
    Allow authenticated user to assign themselves to a hospital.
    Used on first login when user has no hospital assigned yet.
    """
    hospital_id = request.data.get('hospital_id')

    if not hospital_id:
        return Response(
            {'error': 'hospital_id is required.'},
            status=status.HTTP_400_BAD_REQUEST
        )

    from hospital.models import Hospital
    hospital = Hospital.objects.filter(
        id=hospital_id,
        is_active=True
    ).first()

    if not hospital:
        return Response(
            {'error': 'Hospital not found.'},
            status=status.HTTP_404_NOT_FOUND
        )

    request.user.hospital = hospital
    request.user.save()

    return Response({
        'message':       f'Successfully assigned to {hospital.name}',
        'hospital_id':   hospital.id,
        'hospital_name': hospital.name,
    }, status=status.HTTP_200_OK)

class HospitalDoctorListView(APIView):
    """Return a list of all users with the 'Doctor' role in the current user's hospital."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        if not request.user.hospital:
            return Response(
                {"error": "User not assigned to a hospital."},
                status=status.HTTP_400_BAD_REQUEST
            )

        doctors = User.objects.filter(
            hospital=request.user.hospital,
            role='Doctor',
            is_active=True
        ).values('id', 'username', 'email')

        return Response(list(doctors), status=status.HTTP_200_OK)


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated, IsAdmin])
def hospital_staff_list(request):
    """
    GET: List all staff members (Admins, Doctors, Users) in the current hospital.
    POST: Create a new staff member for this hospital.
    """
    if not request.user.hospital:
        return Response({"error": "You are not assigned to a hospital."}, status=status.HTTP_400_BAD_REQUEST)

    if request.method == 'GET':
        staff = User.objects.filter(hospital=request.user.hospital).order_by('role', 'username')
        serializer = UserDetailSerializer(staff, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    if request.method == 'POST':
        # Reuse RegisterSerializer logic but auto-assign hospital
        serializer = RegisterSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            user.hospital = request.user.hospital
            user.save()
            return Response(UserDetailSerializer(user).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['DELETE', 'PATCH'])
@permission_classes([IsAuthenticated, IsAdmin])
def manage_staff_member(request, user_id):
    """
    DELETE: Soft-delete (deactivate) a staff member.
    PATCH: Update staff role or details.
    """
    if not request.user.hospital:
        return Response({"error": "Access denied."}, status=status.HTTP_403_FORBIDDEN)

    staff_member = User.objects.filter(id=user_id, hospital=request.user.hospital).first()
    if not staff_member:
        return Response({"error": "Staff member not found in your hospital."}, status=status.HTTP_404_NOT_FOUND)

    if request.user.id == staff_member.id:
        return Response({"error": "You cannot delete yourself."}, status=status.HTTP_400_BAD_REQUEST)

    if request.method == 'DELETE':
        staff_member.is_active = False
        staff_member.save()
        return Response({"message": "Staff member deactivated successfully."}, status=status.HTTP_200_OK)

    if request.method == 'PATCH':
        role = request.data.get('role')
        if role and role in dict(User.ROLE_CHOICES):
            staff_member.role = role
            staff_member.save()
            return Response(UserDetailSerializer(staff_member).data, status=status.HTTP_200_OK)
        return Response({"error": "Invalid role."}, status=status.HTTP_400_BAD_REQUEST)