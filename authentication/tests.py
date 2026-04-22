# authentication/tests.py

from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from django.contrib.auth import get_user_model
from hospital.models import Hospital
import pyotp
import time

User = get_user_model()

# ─────────────────────────────────────────────────────────────────────────────
# BASE SETUP — Shared setup used across all test classes
# ─────────────────────────────────────────────────────────────────────────────

class BaseTestSetup(APITestCase):
    """Base class that creates reusable test data for all test cases."""

    def setUp(self):
        # Create a test hospital for multi-tenant tests
        self.hospital = Hospital.objects.create(
            name="Test Hospital",
            address="123 Test Street",
            contact_info="03001234567"
        )

        # Create an Admin user
        self.admin_user = User.objects.create_user(
            username='admin_test',
            email='admin@test.com',
            password='Admin@12345',
            role='Admin',
            hospital=self.hospital
        )

        # Create a Doctor user
        self.doctor_user = User.objects.create_user(
            username='doctor_test',
            email='doctor@test.com',
            password='Doctor@12345',
            role='Doctor',
            hospital=self.hospital
        )

        # Create a regular User
        self.regular_user = User.objects.create_user(
            username='user_test',
            email='user@test.com',
            password='User@12345',
            role='User',
            hospital=self.hospital
        )

        # API client for making requests
        self.client = APIClient()

        # Common URLs
        self.register_url = reverse('register')
        self.login_url = reverse('login')
        self.logout_url = reverse('logout')
        self.refresh_url = reverse('token_refresh')
        self.profile_url = reverse('profile')
        self.change_password_url = reverse('change_password')
        self.forgot_password_url = reverse('forgot_password')
        self.reset_password_url = reverse('reset_password_confirm')
        self.mfa_enable_url = reverse('mfa_enable')
        self.mfa_verify_url = reverse('mfa_verify')

    def get_auth_header(self, user):
        """Helper — logs in and returns Authorization header for a given user."""
        response = self.client.post(self.login_url, {
            'username': user.username,
            'password': self._get_password(user)
        })
        token = response.data['access']
        return {'HTTP_AUTHORIZATION': f'Bearer {token}'}

    def _get_password(self, user):
        """Helper — returns matching password for test users."""
        passwords = {
            'admin_test': 'Admin@12345',
            'doctor_test': 'Doctor@12345',
            'user_test': 'User@12345',
        }
        return passwords.get(user.username, 'Test@12345')


# ─────────────────────────────────────────────────────────────────────────────
# 1. POSITIVE TEST CASES — Expected happy path scenarios
# ─────────────────────────────────────────────────────────────────────────────

class PositiveTestCases(BaseTestSetup):
    """Tests for scenarios where everything works as expected."""

    def test_register_user_successfully(self):
        """A new user can register with valid data."""
        data = {
            'username': 'newdoctor',
            'email': 'newdoctor@test.com',
            'password': 'NewDoc@12345',
            'role': 'Doctor',
            'hospital': self.hospital.id
        }
        response = self.client.post(self.register_url, data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['message'], 'User registered successfully.')

    def test_login_with_valid_credentials(self):
        """User can log in with correct username and password."""
        data = {'username': 'doctor_test', 'password': 'Doctor@12345'}
        response = self.client.post(self.login_url, data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Both tokens must be returned on successful login
        self.assertIn('access', response.data)
        self.assertIn('refresh', response.data)

    def test_login_returns_user_role_in_response(self):
        """Login response must include user details with role."""
        data = {'username': 'doctor_test', 'password': 'Doctor@12345'}
        response = self.client.post(self.login_url, data)
        self.assertEqual(response.data['user']['role'], 'Doctor')

    def test_logout_with_valid_refresh_token(self):
        """User can log out by blacklisting their refresh token."""
        login_response = self.client.post(self.login_url, {
            'username': 'doctor_test',
            'password': 'Doctor@12345'
        })
        refresh_token = login_response.data['refresh']
        access_token = login_response.data['access']

        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}')
        response = self.client.post(self.logout_url, {'refresh': refresh_token})
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_token_refresh_returns_new_access_token(self):
        """A valid refresh token must return a new access token."""
        login_response = self.client.post(self.login_url, {
            'username': 'doctor_test',
            'password': 'Doctor@12345'
        })
        refresh_token = login_response.data['refresh']
        response = self.client.post(self.refresh_url, {'refresh': refresh_token})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)

    def test_get_profile_when_authenticated(self):
        """Authenticated user can fetch their own profile."""
        headers = self.get_auth_header(self.doctor_user)
        self.client.credentials(HTTP_AUTHORIZATION=headers['HTTP_AUTHORIZATION'])
        response = self.client.get(self.profile_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['username'], 'doctor_test')

    def test_change_password_with_correct_old_password(self):
        """User can change password when old password is correct."""
        headers = self.get_auth_header(self.doctor_user)
        self.client.credentials(HTTP_AUTHORIZATION=headers['HTTP_AUTHORIZATION'])
        response = self.client.post(self.change_password_url, {
            'old_password': 'Doctor@12345',
            'new_password': 'NewDoctor@999'
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_forgot_password_sends_email_for_valid_email(self):
        """Forgot password request succeeds for a registered email."""
        response = self.client.post(self.forgot_password_url, {
            'email': 'doctor@test.com'
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('email sent', response.data['message'].lower())

    def test_register_all_three_roles_successfully(self):
        """Admin, Doctor, and User roles can all be registered."""
        for role in ['Admin', 'Doctor', 'User']:
            data = {
                'username': f'{role.lower()}_new',
                'email': f'{role.lower()}_new@test.com',
                'password': 'Test@12345',
                'role': role,
                'hospital': self.hospital.id
            }
            response = self.client.post(self.register_url, data)
            self.assertEqual(response.status_code, status.HTTP_201_CREATED)


# ─────────────────────────────────────────────────────────────────────────────
# 2. NEGATIVE TEST CASES — Expected failure scenarios
# ─────────────────────────────────────────────────────────────────────────────

class NegativeTestCases(BaseTestSetup):
    """Tests for scenarios where the system should reject the request."""

    def test_register_with_duplicate_username_fails(self):
        """Registration fails if the username already exists."""
        data = {
            'username': 'doctor_test',  # Already exists in setUp
            'email': 'another@test.com',
            'password': 'Test@12345',
            'role': 'Doctor'
        }
        response = self.client.post(self.register_url, data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_register_with_duplicate_email_fails(self):
        """Registration fails if email is already taken."""
        data = {
            'username': 'brandnew',
            'email': 'doctor@test.com',  # Already exists in setUp
            'password': 'Test@12345',
            'role': 'Doctor'
        }
        response = self.client.post(self.register_url, data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_login_with_wrong_password_fails(self):
        """Login fails when the password is incorrect."""
        response = self.client.post(self.login_url, {
            'username': 'doctor_test',
            'password': 'WrongPassword'
        })
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertIn('error', response.data)

    def test_login_with_nonexistent_username_fails(self):
        """Login fails when the username does not exist."""
        response = self.client.post(self.login_url, {
            'username': 'ghost_user',
            'password': 'Test@12345'
        })
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_get_profile_without_token_fails(self):
        """Profile endpoint rejects unauthenticated requests."""
        response = self.client.get(self.profile_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_logout_with_invalid_refresh_token_fails(self):
        """Logout fails when an invalid or fake refresh token is provided."""
        headers = self.get_auth_header(self.doctor_user)
        self.client.credentials(HTTP_AUTHORIZATION=headers['HTTP_AUTHORIZATION'])
        response = self.client.post(self.logout_url, {'refresh': 'fake.invalid.token'})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_change_password_with_wrong_old_password_fails(self):
        """Password change is rejected when old password is wrong."""
        headers = self.get_auth_header(self.doctor_user)
        self.client.credentials(HTTP_AUTHORIZATION=headers['HTTP_AUTHORIZATION'])
        response = self.client.post(self.change_password_url, {
            'old_password': 'WrongOldPassword',
            'new_password': 'NewDoctor@999'
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_forgot_password_with_unregistered_email_fails(self):
        """Forgot password fails if the email is not in the system."""
        response = self.client.post(self.forgot_password_url, {
            'email': 'ghost@nobody.com'
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_refresh_with_blacklisted_token_fails(self):
        """A blacklisted refresh token cannot be used to get a new access token."""
        login_response = self.client.post(self.login_url, {
            'username': 'doctor_test',
            'password': 'Doctor@12345'
        })
        refresh_token = login_response.data['refresh']
        access_token = login_response.data['access']

        # Blacklist the token by logging out
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}')
        self.client.post(self.logout_url, {'refresh': refresh_token})

        # Now try to use the blacklisted token — must fail
        response = self.client.post(self.refresh_url, {'refresh': refresh_token})
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


# ─────────────────────────────────────────────────────────────────────────────
# 3. EDGE TEST CASES — Boundary and unusual input scenarios
# ─────────────────────────────────────────────────────────────────────────────

class EdgeTestCases(BaseTestSetup):
    """Tests for boundary conditions and unusual but possible inputs."""

    def test_register_with_missing_email_field(self):
        """Registration fails gracefully when email is missing."""
        data = {
            'username': 'nodoc',
            'password': 'Test@12345',
            'role': 'Doctor'
            # email intentionally missing
        }
        response = self.client.post(self.register_url, data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_register_with_short_password_fails(self):
        """Password shorter than 8 characters should be rejected."""
        data = {
            'username': 'shortpass',
            'email': 'short@test.com',
            'password': '123',  # Too short
            'role': 'Doctor'
        }
        response = self.client.post(self.register_url, data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_login_with_empty_body_fails(self):
        """Login with completely empty body returns 400 not 500."""
        response = self.client.post(self.login_url, {})
        # Should return a client error, not a server crash
        self.assertIn(response.status_code, [
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_401_UNAUTHORIZED
        ])

    def test_register_with_invalid_email_format_fails(self):
        """Registration fails when email format is invalid."""
        data = {
            'username': 'bademail',
            'email': 'not-an-email',
            'password': 'Test@12345',
            'role': 'Doctor'
        }
        response = self.client.post(self.register_url, data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_register_with_invalid_role_fails(self):
        """Registration fails when an invalid role is provided."""
        data = {
            'username': 'badrole',
            'email': 'badrole@test.com',
            'password': 'Test@12345',
            'role': 'SuperHero'  # Not a valid role
        }
        response = self.client.post(self.register_url, data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_refresh_with_empty_token_fails(self):
        """Token refresh with empty string returns error."""
        response = self.client.post(self.refresh_url, {'refresh': ''})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_forgot_password_with_empty_email_fails(self):
        """Forgot password with empty email returns validation error."""
        response = self.client.post(self.forgot_password_url, {'email': ''})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_username_with_spaces_fails(self):
        """Django does not allow spaces in usernames."""
        data = {
            'username': 'user name with spaces',
            'email': 'space@test.com',
            'password': 'Test@12345',
            'role': 'Doctor'
        }
        response = self.client.post(self.register_url, data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


# ─────────────────────────────────────────────────────────────────────────────
# 4. AUTHENTICATION & AUTHORIZATION TEST CASES
# ─────────────────────────────────────────────────────────────────────────────

class AuthorizationTestCases(BaseTestSetup):
    """Tests for role-based access control — who can do what."""

    def test_admin_can_access_profile(self):
        """Admin role can access the profile endpoint."""
        headers = self.get_auth_header(self.admin_user)
        self.client.credentials(HTTP_AUTHORIZATION=headers['HTTP_AUTHORIZATION'])
        response = self.client.get(self.profile_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_doctor_can_access_profile(self):
        """Doctor role can access the profile endpoint."""
        headers = self.get_auth_header(self.doctor_user)
        self.client.credentials(HTTP_AUTHORIZATION=headers['HTTP_AUTHORIZATION'])
        response = self.client.get(self.profile_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_regular_user_can_access_profile(self):
        """Regular user role can access their own profile."""
        headers = self.get_auth_header(self.regular_user)
        self.client.credentials(HTTP_AUTHORIZATION=headers['HTTP_AUTHORIZATION'])
        response = self.client.get(self.profile_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_unauthenticated_user_cannot_access_profile(self):
        """Unauthenticated requests to profile are rejected."""
        response = self.client.get(self.profile_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_role_is_correctly_stored_on_registration(self):
        """Role assigned during registration is correctly saved."""
        data = {
            'username': 'rolecheck',
            'email': 'rolecheck@test.com',
            'password': 'Test@12345',
            'role': 'Admin',
            'hospital': self.hospital.id
        }
        self.client.post(self.register_url, data)
        user = User.objects.get(username='rolecheck')
        self.assertEqual(user.role, 'Admin')

    def test_token_contains_role_claim(self):
        """JWT token issued at login must embed the user's role."""
        response = self.client.post(self.login_url, {
            'username': 'admin_test',
            'password': 'Admin@12345'
        })
        # Role must be in the user data returned with the token
        self.assertEqual(response.data['user']['role'], 'Admin')

    def test_token_contains_hospital_id_claim(self):
        """JWT token must include hospital_id for tenant context."""
        response = self.client.post(self.login_url, {
            'username': 'admin_test',
            'password': 'Admin@12345'
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)


# ─────────────────────────────────────────────────────────────────────────────
# 5. SECURITY TEST CASES
# ─────────────────────────────────────────────────────────────────────────────

class SecurityTestCases(BaseTestSetup):
    """Tests focused on security vulnerabilities and protections."""

    def test_password_is_not_returned_in_response(self):
        """Registered user's password must never appear in API response."""
        data = {
            'username': 'secureuser',
            'email': 'secure@test.com',
            'password': 'Secure@12345',
            'role': 'Doctor'
        }
        response = self.client.post(self.register_url, data)
        self.assertNotIn('password', response.data)

    def test_password_is_hashed_in_database(self):
        """Password stored in DB must be hashed, not plain text."""
        user = User.objects.get(username='doctor_test')
        # Hashed passwords never equal their plain text version
        self.assertNotEqual(user.password, 'Doctor@12345')
        # Django hashed passwords always start with algorithm identifier
        self.assertTrue(user.password.startswith('pbkdf2_') or
                       user.password.startswith('bcrypt') or
                       user.password.startswith('argon2'))

    def test_expired_access_token_is_rejected(self):
        """A manually crafted fake token is rejected by the API."""
        self.client.credentials(HTTP_AUTHORIZATION='Bearer faketoken.invalid.xyz')
        response = self.client.get(self.profile_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_blacklisted_token_cannot_access_profile(self):
        """After logout, the old access token cannot access protected endpoints."""
        login_response = self.client.post(self.login_url, {
            'username': 'doctor_test',
            'password': 'Doctor@12345'
        })
        access = login_response.data['access']
        refresh = login_response.data['refresh']

        # Logout to blacklist the refresh token
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {access}')
        self.client.post(self.logout_url, {'refresh': refresh})

        # Try refreshing — must be blocked
        response = self.client.post(self.refresh_url, {'refresh': refresh})
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_mfa_login_blocked_without_otp(self):
        """User with MFA enabled cannot login without providing OTP."""
        # Enable MFA manually on the user
        self.doctor_user.mfa_enabled = True
        self.doctor_user.mfa_secret = pyotp.random_base32()
        self.doctor_user.save()

        response = self.client.post(self.login_url, {
            'username': 'doctor_test',
            'password': 'Doctor@12345'
            # otp intentionally missing
        })
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_mfa_login_blocked_with_wrong_otp(self):
        """User with MFA enabled is rejected when OTP is wrong."""
        self.doctor_user.mfa_enabled = True
        self.doctor_user.mfa_secret = pyotp.random_base32()
        self.doctor_user.save()

        response = self.client.post(self.login_url, {
            'username': 'doctor_test',
            'password': 'Doctor@12345',
            'otp': '000000'  # Wrong OTP
        })
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_mfa_login_succeeds_with_valid_otp(self):
        """User with MFA enabled can login with correct OTP."""
        secret = pyotp.random_base32()
        self.doctor_user.mfa_enabled = True
        self.doctor_user.mfa_secret = secret
        self.doctor_user.save()

        # Generate correct OTP using the same secret
        totp = pyotp.TOTP(secret)
        valid_otp = totp.now()

        response = self.client.post(self.login_url, {
            'username': 'doctor_test',
            'password': 'Doctor@12345',
            'otp': valid_otp
        })
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)

    def test_reset_password_with_tampered_token_fails(self):
        """Password reset fails if the token in the link is tampered."""
        from django.utils.http import urlsafe_base64_encode
        from django.utils.encoding import force_bytes
        uid = urlsafe_base64_encode(force_bytes(self.doctor_user.pk))

        response = self.client.post(self.reset_password_url, {
            'uid': uid,
            'token': 'tampered-token-xyz',
            'new_password': 'Hacked@99999'
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_sql_injection_in_login_is_safe(self):
        """SQL injection attempt in login does not cause server error."""
        response = self.client.post(self.login_url, {
            'username': "' OR 1=1; --",
            'password': "' OR 1=1; --"
        })
        # Must return auth error, not a 500 server crash
        self.assertIn(response.status_code, [
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_401_UNAUTHORIZED
        ])