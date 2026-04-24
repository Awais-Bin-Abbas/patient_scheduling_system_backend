from django.test import TestCase

# Create your tests here.
# patients/tests.py

from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from django.urls import reverse
from django.contrib.auth import get_user_model
from .models import Patient, Condition
from hospital.models import Hospital

User = get_user_model()


# ─────────────────────────────────────────────────────────────────────────────
# BASE SETUP
# ─────────────────────────────────────────────────────────────────────────────

class PatientBaseSetup(APITestCase):
    """Shared setup for all patient test cases."""

    def setUp(self):
        self.client = APIClient()

        # Create two hospitals for tenant isolation tests
        self.hospital_a = Hospital.objects.create(
            name='Hospital Alpha',
            address='123 Alpha Street',
            contact_info='03001234567'
        )
        self.hospital_b = Hospital.objects.create(
            name='Hospital Beta',
            address='456 Beta Avenue',
            contact_info='03009876543'
        )

        # Admin user in Hospital A
        self.admin = User.objects.create_user(
            username='admin_test',
            email='admin@test.com',
            password='Admin@12345',
            role='Admin',
            hospital=self.hospital_a
        )

        # Doctor in Hospital A
        self.doctor = User.objects.create_user(
            username='doctor_test',
            email='doctor@test.com',
            password='Doctor@12345',
            role='Doctor',
            hospital=self.hospital_a
        )

        # Doctor in Hospital B — for tenant isolation
        self.doctor_b = User.objects.create_user(
            username='doctor_b_test',
            email='doctor_b@test.com',
            password='Doctor@12345',
            role='Doctor',
            hospital=self.hospital_b
        )

        # Create test patient in Hospital A
        self.patient = Patient.objects.create(
            hospital=self.hospital_a,
            first_name='John',
            last_name='Doe',
            dob='1985-03-15',
            email='john.doe@test.com',
            contact_info='03001112222',
            is_chronic=False
        )

        # Create test patient in Hospital B
        self.patient_b = Patient.objects.create(
            hospital=self.hospital_b,
            first_name='Sara',
            last_name='Khan',
            dob='1990-07-22',
            email='sara.khan@test.com',
            contact_info='03003334444',
            is_chronic=False
        )

        # Create test condition on patient
        self.condition = Condition.objects.create(
            patient=self.patient,
            name='diabetes',
            severity='moderate',
            diagnosed_on='2020-01-15'
        )

        # URLs
        self.create_url    = reverse('create_patient')
        self.list_url      = reverse('get_patients')

    def authenticate(self, user, password):
        """Helper — logs in and sets auth header."""
        response = self.client.post(reverse('login'), {
            'username': user.username,
            'password': password
        })
        token = response.data['access']
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

    def get_detail_url(self, patient_id, action=''):
        """Helper — builds patient detail URLs."""
        if action == 'update':
            return reverse('update_patient', args=[patient_id])
        elif action == 'delete':
            return reverse('delete_patient', args=[patient_id])
        elif action == 'conditions':
            return reverse('get_patient_conditions', args=[patient_id])
        elif action == 'add_condition':
            return reverse('add_condition', args=[patient_id])
        return reverse('get_patient_by_id', args=[patient_id])


# ─────────────────────────────────────────────────────────────────────────────
# 1. POSITIVE TEST CASES
# ─────────────────────────────────────────────────────────────────────────────

class PatientPositiveTests(PatientBaseSetup):
    """Tests for expected successful scenarios."""

    def test_doctor_can_create_patient(self):
        """Doctor can create a new patient in their hospital."""
        self.authenticate(self.doctor, 'Doctor@12345')
        response = self.client.post(self.create_url, {
            'first_name':   'New',
            'last_name':    'Patient',
            'dob':          '1990-05-10',
            'email':        'new.patient@test.com',
            'contact_info': '03005556666',
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['first_name'], 'New')

    def test_admin_can_create_patient(self):
        """Admin can create a new patient."""
        self.authenticate(self.admin, 'Admin@12345')
        response = self.client.post(self.create_url, {
            'first_name':   'Admin',
            'last_name':    'Created',
            'dob':          '1992-08-20',
            'email':        'admin.created@test.com',
            'contact_info': '03007778888',
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_patient_auto_assigned_to_hospital(self):
        """Patient is automatically assigned to the creating user's hospital."""
        self.authenticate(self.doctor, 'Doctor@12345')
        response = self.client.post(self.create_url, {
            'first_name':   'Auto',
            'last_name':    'Assigned',
            'dob':          '1988-11-30',
            'email':        'auto.assigned@test.com',
            'contact_info': '03009990000',
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        # Hospital must be auto-assigned from middleware
        self.assertEqual(response.data['hospital'], self.hospital_a.id)

    def test_list_patients_returns_own_hospital_only(self):
        """Patient list returns only patients from requesting user's hospital."""
        self.authenticate(self.doctor, 'Doctor@12345')
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # All returned patients must belong to Hospital A
        for patient in response.data:
            self.assertNotEqual(patient['id'], self.patient_b.id)

    def test_get_patient_by_id(self):
        """Can retrieve a specific patient by ID."""
        self.authenticate(self.doctor, 'Doctor@12345')
        url = self.get_detail_url(self.patient.id)
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['email'], 'john.doe@test.com')

    def test_patient_response_includes_conditions(self):
        """Patient detail response includes nested conditions."""
        self.authenticate(self.doctor, 'Doctor@12345')
        url = self.get_detail_url(self.patient.id)
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('conditions', response.data)
        self.assertEqual(len(response.data['conditions']), 1)

    def test_patient_response_includes_age(self):
        """Patient detail response includes calculated age."""
        self.authenticate(self.doctor, 'Doctor@12345')
        url = self.get_detail_url(self.patient.id)
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('age', response.data)
        self.assertGreater(response.data['age'], 0)

    def test_update_patient(self):
        """Doctor can update patient details."""
        self.authenticate(self.doctor, 'Doctor@12345')
        url = self.get_detail_url(self.patient.id, 'update')
        response = self.client.patch(url, {'contact_info': '03001119999'})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['contact_info'], '03001119999')

    def test_add_condition_to_patient(self):
        """Doctor can add a medical condition to a patient."""
        self.authenticate(self.doctor, 'Doctor@12345')
        url = self.get_detail_url(self.patient.id, 'add_condition')
        response = self.client.post(url, {
            'name':         'hypertension',
            'severity':     'mild',
            'diagnosed_on': '2021-06-10'
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['name'], 'hypertension')

    def test_severe_condition_sets_is_chronic(self):
        """Adding a severe condition automatically sets patient is_chronic to True."""
        self.authenticate(self.doctor, 'Doctor@12345')
        url = self.get_detail_url(self.patient.id, 'add_condition')
        self.client.post(url, {
            'name':         'diabetes',
            'severity':     'severe',
            'diagnosed_on': '2022-01-01'
        })
        self.patient.refresh_from_db()
        self.assertTrue(self.patient.is_chronic)

    def test_get_patient_conditions(self):
        """Can retrieve all conditions for a patient."""
        self.authenticate(self.doctor, 'Doctor@12345')
        url = self.get_detail_url(self.patient.id, 'conditions')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)

    def test_search_patients_by_name(self):
        """Can search patients by first name."""
        self.authenticate(self.doctor, 'Doctor@12345')
        response = self.client.get(f'{self.list_url}?search=John')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]['first_name'], 'John')

    def test_filter_patients_by_condition(self):
        """Can filter patients by medical condition name."""
        self.authenticate(self.doctor, 'Doctor@12345')
        response = self.client.get(f'{self.list_url}?condition=diabetes')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(response.data), 1)

    def test_filter_patients_by_is_chronic(self):
        """Can filter patients by chronic status."""
        self.patient.is_chronic = True
        self.patient.save()
        self.authenticate(self.doctor, 'Doctor@12345')
        response = self.client.get(f'{self.list_url}?is_chronic=true')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        for p in response.data:
            self.assertTrue(p['is_chronic'])

    def test_admin_can_delete_patient(self):
        """Admin can delete a patient."""
        self.authenticate(self.admin, 'Admin@12345')
        url = self.get_detail_url(self.patient.id, 'delete')
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)


# ─────────────────────────────────────────────────────────────────────────────
# 2. NEGATIVE TEST CASES
# ─────────────────────────────────────────────────────────────────────────────

class PatientNegativeTests(PatientBaseSetup):
    """Tests for scenarios the system should correctly reject."""

    def test_unauthenticated_cannot_list_patients(self):
        """Unauthenticated requests to patient list are rejected."""
        response = self.client.get(self.list_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_create_patient_missing_required_fields(self):
        """Patient creation fails when required fields are missing."""
        self.authenticate(self.doctor, 'Doctor@12345')
        response = self.client.post(self.create_url, {
            'first_name': 'Incomplete'
            # missing last_name, dob, email, contact_info
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_duplicate_patient_email_fails(self):
        """Creating a patient with existing email is rejected."""
        self.authenticate(self.doctor, 'Doctor@12345')
        response = self.client.post(self.create_url, {
            'first_name':   'Duplicate',
            'last_name':    'Email',
            'dob':          '1990-01-01',
            'email':        'john.doe@test.com',  # already exists
            'contact_info': '03001234567',
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_doctor_cannot_delete_patient(self):
        """Doctor role is blocked from deleting patients."""
        self.authenticate(self.doctor, 'Doctor@12345')
        url = self.get_detail_url(self.patient.id, 'delete')
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_get_nonexistent_patient_returns_404(self):
        """Requesting a patient that does not exist returns 404."""
        self.authenticate(self.doctor, 'Doctor@12345')
        url = self.get_detail_url(99999)
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_invalid_severity_on_condition_fails(self):
        """Adding a condition with invalid severity is rejected."""
        self.authenticate(self.doctor, 'Doctor@12345')
        url = self.get_detail_url(self.patient.id, 'add_condition')
        response = self.client.post(url, {
            'name':         'diabetes',
            'severity':     'critical',  # not in choices
            'diagnosed_on': '2022-01-01'
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


# ─────────────────────────────────────────────────────────────────────────────
# 3. TENANT ISOLATION TEST CASES
# ─────────────────────────────────────────────────────────────────────────────

class PatientTenantIsolationTests(PatientBaseSetup):
    """Tests that verify tenant isolation between hospitals."""

    def test_doctor_cannot_access_other_hospital_patient(self):
        """Doctor from Hospital A cannot access Hospital B patient."""
        self.authenticate(self.doctor, 'Doctor@12345')
        url = self.get_detail_url(self.patient_b.id)
        response = self.client.get(url)
        # Must return 404 — patient exists but not in this hospital
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_doctor_cannot_update_other_hospital_patient(self):
        """Doctor from Hospital A cannot update Hospital B patient."""
        self.authenticate(self.doctor, 'Doctor@12345')
        url = self.get_detail_url(self.patient_b.id, 'update')
        response = self.client.patch(url, {'contact_info': '03001234567'})
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_doctor_cannot_add_condition_to_other_hospital_patient(self):
        """Doctor from Hospital A cannot add condition to Hospital B patient."""
        self.authenticate(self.doctor, 'Doctor@12345')
        url = self.get_detail_url(self.patient_b.id, 'add_condition')
        response = self.client.post(url, {
            'name':         'diabetes',
            'severity':     'mild',
            'diagnosed_on': '2022-01-01'
        })
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_patient_list_does_not_include_other_hospital_patients(self):
        """Patient list never includes patients from other hospitals."""
        self.authenticate(self.doctor, 'Doctor@12345')
        response = self.client.get(self.list_url)
        patient_ids = [p['id'] for p in response.data]
        # Hospital B patient must not appear
        self.assertNotIn(self.patient_b.id, patient_ids)