# hospital/tests.py

from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from django.urls import reverse
from django.contrib.auth import get_user_model
from .models import Hospital

User = get_user_model()


# ─────────────────────────────────────────────────────────────────────────────
# BASE SETUP
# ─────────────────────────────────────────────────────────────────────────────

class HospitalBaseSetup(APITestCase):
    """Shared setup for all hospital test cases."""

    def setUp(self):
        self.client = APIClient()

        # Create two hospitals to test tenant isolation between them
        self.hospital_a = Hospital.objects.create(
            name="Hospital Alpha",
            address="123 Alpha Street",
            contact_info="03001234567"
        )
        self.hospital_b = Hospital.objects.create(
            name="Hospital Beta",
            address="456 Beta Avenue",
            contact_info="03009876543"
        )

        # Admin user — belongs to Hospital A, can manage all hospitals
        self.admin = User.objects.create_user(
            username='admin_test',
            email='admin@test.com',
            password='Admin@12345',
            role='Admin',
            hospital=self.hospital_a
        )

        # Doctor user — belongs to Hospital A, limited access
        self.doctor = User.objects.create_user(
            username='doctor_test',
            email='doctor@test.com',
            password='Doctor@12345',
            role='Doctor',
            hospital=self.hospital_a
        )

        # Doctor in Hospital B — to test cross-tenant isolation
        self.doctor_b = User.objects.create_user(
            username='doctor_b_test',
            email='doctor_b@test.com',
            password='Doctor@12345',
            role='Doctor',
            hospital=self.hospital_b
        )

        # User with no hospital assigned — edge case
        self.unassigned_user = User.objects.create_user(
            username='unassigned_test',
            email='unassigned@test.com',
            password='User@12345',
            role='User',
            hospital=None
        )

        # URL definitions
        self.create_url = reverse('create_hospital')
        self.list_url = reverse('get_hospitals')
        self.stats_url = reverse('hospital_stats')

    def authenticate(self, user, password):
        """Helper — logs in and sets auth header for given user."""
        response = self.client.post(reverse('login'), {
            'username': user.username,
            'password': password
        })
        token = response.data['access']
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

    def get_detail_url(self, hospital_id, action=''):
        """Helper — builds hospital detail URLs dynamically."""
        if action == 'update':
            return reverse('update_hospital', args=[hospital_id])
        elif action == 'delete':
            return reverse('delete_hospital', args=[hospital_id])
        elif action == 'restore':
            return reverse('restore_hospital', args=[hospital_id])
        return reverse('get_hospital_by_id', args=[hospital_id])


# ─────────────────────────────────────────────────────────────────────────────
# 1. POSITIVE TEST CASES
# ─────────────────────────────────────────────────────────────────────────────

class HospitalPositiveTests(HospitalBaseSetup):
    """Tests for expected successful scenarios."""

    def test_admin_can_create_hospital(self):
        """Admin successfully creates a new hospital."""
        self.authenticate(self.admin, 'Admin@12345')
        response = self.client.post(self.create_url, {
            'name': 'New City Hospital',
            'address': '789 City Road',
            'contact_info': '03111234567'
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['name'], 'New City Hospital')

    def test_hospital_slug_auto_generated(self):
        """Slug is automatically generated from hospital name on creation."""
        self.authenticate(self.admin, 'Admin@12345')
        response = self.client.post(self.create_url, {
            'name': 'Sunrise Medical Center',
            'address': '10 Sunrise Blvd',
            'contact_info': '03001112222'
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        # Slug must be auto-generated from name
        self.assertEqual(response.data['slug'], 'sunrise-medical-center')

    def test_admin_can_list_all_hospitals(self):
        """Admin can retrieve the full list of all active hospitals."""
        self.authenticate(self.admin, 'Admin@12345')
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Admin must see both hospitals
        self.assertGreaterEqual(len(response.data), 2)

    def test_doctor_sees_only_own_hospital(self):
        """Doctor only sees their own hospital — not others."""
        self.authenticate(self.doctor, 'Doctor@12345')
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Doctor should only see Hospital A
        self.assertEqual(response.data['name'], 'Hospital Alpha')

    def test_admin_can_update_hospital(self):
        """Admin can update hospital details partially."""
        self.authenticate(self.admin, 'Admin@12345')
        url = self.get_detail_url(self.hospital_a.id, 'update')
        response = self.client.patch(url, {'address': 'Updated Address 999'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['address'], 'Updated Address 999')

    def test_admin_can_soft_delete_hospital(self):
        """Admin can deactivate a hospital — data is preserved."""
        self.authenticate(self.admin, 'Admin@12345')
        url = self.get_detail_url(self.hospital_b.id, 'delete')
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Verify it's marked inactive in the database
        self.hospital_b.refresh_from_db()
        self.assertFalse(self.hospital_b.is_active)

    def test_admin_can_restore_hospital(self):
        """Admin can reactivate a deactivated hospital."""
        # First deactivate it
        self.hospital_b.is_active = False
        self.hospital_b.save()

        self.authenticate(self.admin, 'Admin@12345')
        url = self.get_detail_url(self.hospital_b.id, 'restore')
        response = self.client.patch(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.hospital_b.refresh_from_db()
        self.assertTrue(self.hospital_b.is_active)

    def test_admin_can_view_hospital_stats(self):
        """Admin can retrieve stats summary for all hospitals."""
        self.authenticate(self.admin, 'Admin@12345')
        response = self.client.get(self.stats_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Response must be a list of hospital stat objects
        self.assertIsInstance(response.data, list)
        # Each stat object must have these keys
        if len(response.data) > 0:
            stat = response.data[0]
            self.assertIn('hospital_id', stat)
            self.assertIn('hospital_name', stat)
            self.assertIn('total_patients', stat)
            self.assertIn('total_leads', stat)
            self.assertIn('is_active', stat)

    def test_owner_auto_assigned_on_create(self):
        """Hospital owner is automatically set to the creating admin."""
        self.authenticate(self.admin, 'Admin@12345')
        response = self.client.post(self.create_url, {
            'name': 'Admin Owned Hospital',
            'address': '1 Admin Lane',
            'contact_info': '03001234000'
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        # Owner must be the admin who created it
        self.assertEqual(response.data['owner'], self.admin.id)


# ─────────────────────────────────────────────────────────────────────────────
# 2. NEGATIVE TEST CASES
# ─────────────────────────────────────────────────────────────────────────────

class HospitalNegativeTests(HospitalBaseSetup):
    """Tests for scenarios the system should correctly reject."""

    def test_doctor_cannot_create_hospital(self):
        """Doctor role is blocked from creating hospitals."""
        self.authenticate(self.doctor, 'Doctor@12345')
        response = self.client.post(self.create_url, {
            'name': 'Unauthorized Hospital',
            'address': 'Some Address',
            'contact_info': '03001234567'
        })
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_unauthenticated_cannot_create_hospital(self):
        """Unauthenticated requests to create hospital are rejected."""
        response = self.client.post(self.create_url, {
            'name': 'Ghost Hospital',
            'address': 'Nowhere',
            'contact_info': '03001234567'
        })
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_doctor_cannot_update_hospital(self):
        """Doctor role is blocked from updating hospital details."""
        self.authenticate(self.doctor, 'Doctor@12345')
        url = self.get_detail_url(self.hospital_a.id, 'update')
        response = self.client.patch(url, {'address': 'Hacked Address'})
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_doctor_cannot_delete_hospital(self):
        """Doctor role is blocked from deleting hospitals."""
        self.authenticate(self.doctor, 'Doctor@12345')
        url = self.get_detail_url(self.hospital_a.id, 'delete')
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_get_nonexistent_hospital_returns_404(self):
        """Requesting a hospital that doesn't exist returns 404."""
        self.authenticate(self.admin, 'Admin@12345')
        url = self.get_detail_url(99999)
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_duplicate_hospital_name_fails(self):
        """Creating a hospital with an existing name is rejected."""
        self.authenticate(self.admin, 'Admin@12345')
        response = self.client.post(self.create_url, {
            'name': 'Hospital Alpha',  # Already exists in setUp
            'address': 'Different Address',
            'contact_info': '03001234567'
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_unassigned_user_gets_error_on_list(self):
        """User with no hospital assigned gets a clear error message."""
        self.authenticate(self.unassigned_user, 'User@12345')
        response = self.client.get(self.list_url)
        # Returns 400 because user has no hospital assigned
        # TenantMixin returns 400 with clear error message
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('error', response.data)

    def test_restore_already_active_hospital_fails(self):
        """Restoring an already active hospital returns 400."""
        self.authenticate(self.admin, 'Admin@12345')
        url = self.get_detail_url(self.hospital_a.id, 'restore')
        response = self.client.patch(url)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


# ─────────────────────────────────────────────────────────────────────────────
# 3. EDGE TEST CASES
# ─────────────────────────────────────────────────────────────────────────────

class HospitalEdgeTests(HospitalBaseSetup):
    """Tests for boundary and unusual input scenarios."""

    def test_create_hospital_missing_name_fails(self):
        """Hospital creation fails when name field is missing."""
        self.authenticate(self.admin, 'Admin@12345')
        response = self.client.post(self.create_url, {
            'address': 'Some Address',
            'contact_info': '03001234567'
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_hospital_short_contact_info_fails(self):
        """Hospital creation fails when contact info is too short."""
        self.authenticate(self.admin, 'Admin@12345')
        response = self.client.post(self.create_url, {
            'name': 'Short Contact Hospital',
            'address': 'Some Address',
            'contact_info': '123'  # Too short
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_hospital_missing_address_fails(self):
        """Hospital creation fails when address field is missing."""
        self.authenticate(self.admin, 'Admin@12345')
        response = self.client.post(self.create_url, {
            'name': 'No Address Hospital',
            'contact_info': '03001234567'
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_update_nonexistent_hospital_returns_404(self):
        """Updating a hospital that doesn't exist returns 404."""
        self.authenticate(self.admin, 'Admin@12345')
        url = self.get_detail_url(99999, 'update')
        response = self.client.patch(url, {'address': 'New Address'})
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_delete_nonexistent_hospital_returns_404(self):
        """Deleting a hospital that doesn't exist returns 404."""
        self.authenticate(self.admin, 'Admin@12345')
        url = self.get_detail_url(99999, 'delete')
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_hospital_name_case_insensitive_duplicate_check(self):
        """Duplicate name check is case-insensitive."""
        self.authenticate(self.admin, 'Admin@12345')
        response = self.client.post(self.create_url, {
            'name': 'hospital alpha',  # Lowercase version of existing
            'address': 'Different Address',
            'contact_info': '03001234567'
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


# ─────────────────────────────────────────────────────────────────────────────
# 4. TENANT ISOLATION TEST CASES
# ─────────────────────────────────────────────────────────────────────────────

class TenantIsolationTests(HospitalBaseSetup):
    """Tests that verify multi-tenant data isolation between hospitals."""

    def test_doctor_a_cannot_see_hospital_b_data(self):
        """Doctor from Hospital A only sees Hospital A — never Hospital B."""
        self.authenticate(self.doctor, 'Doctor@12345')
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Must be Hospital A data only
        self.assertEqual(response.data['name'], 'Hospital Alpha')
        self.assertNotEqual(response.data['name'], 'Hospital Beta')

    def test_doctor_b_cannot_see_hospital_a_data(self):
        """Doctor from Hospital B only sees Hospital B — never Hospital A."""
        self.authenticate(self.doctor_b, 'Doctor@12345')
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['name'], 'Hospital Beta')
        self.assertNotEqual(response.data['name'], 'Hospital Alpha')

    def test_admin_sees_all_hospitals(self):
        """Admin has cross-tenant visibility and sees all hospitals."""
        self.authenticate(self.admin, 'Admin@12345')
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Admin sees multiple hospitals
        self.assertGreaterEqual(len(response.data), 2)

    def test_deactivated_hospital_hidden_from_list(self):
        """Deactivated hospitals do not appear in the active list."""
        # Deactivate Hospital B
        self.hospital_b.is_active = False
        self.hospital_b.save()

        self.authenticate(self.admin, 'Admin@12345')
        response = self.client.get(self.list_url)
        # Get all names in the response
        names = [h['name'] for h in response.data]
        self.assertNotIn('Hospital Beta', names)