# leads/tests.py

from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from django.urls import reverse
from django.contrib.auth import get_user_model
from hospital.models import Hospital
from patients.models import Patient, Condition
from .models import Lead, LeadCriteria

User = get_user_model()


# ─────────────────────────────────────────────────────────────────────────────
# BASE SETUP
# ─────────────────────────────────────────────────────────────────────────────

class LeadBaseSetup(APITestCase):
    """Shared setup for all lead test cases."""

    def setUp(self):
        self.client = APIClient()

        # Create two hospitals
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

        # Admin in Hospital A
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

        # Admin in Hospital B
        self.admin_b = User.objects.create_user(
            username='admin_b_test',
            email='admin_b@test.com',
            password='Admin@12345',
            role='Admin',
            hospital=self.hospital_b
        )

        # Create patient in Hospital A with a condition
        self.patient = Patient.objects.create(
            hospital=self.hospital_a,
            first_name='John',
            last_name='Doe',
            dob='1960-03-15',
            email='john.doe@test.com',
            contact_info='03001112222',
            is_chronic=True
        )

        # Add a condition to the patient
        self.condition = Condition.objects.create(
            patient=self.patient,
            name='diabetes',
            severity='severe',
            diagnosed_on='2020-01-15'
        )

        # Create patient in Hospital B
        self.patient_b = Patient.objects.create(
            hospital=self.hospital_b,
            first_name='Sara',
            last_name='Khan',
            dob='1970-07-22',
            email='sara.khan@test.com',
            contact_info='03003334444',
            is_chronic=False
        )

        # Create a criteria for Hospital A
        self.criteria = LeadCriteria.objects.create(
            hospital=self.hospital_a,
            name='Diabetic Seniors',
            criteria={'condition': 'diabetes', 'is_chronic': True},
            is_active=True,
            created_by=self.admin
        )

        # Create a lead for Hospital A
        self.lead = Lead.objects.create(
            patient=self.patient,
            hospital=self.hospital_a,
            criteria=self.criteria,
            status='new'
        )

        # URLs
        self.create_criteria_url  = reverse('create_criteria')
        self.list_criteria_url    = reverse('list_criteria')
        self.generate_url         = reverse('trigger_lead_generation')
        self.list_leads_url       = reverse('list_leads')

    def authenticate(self, user, password):
        """Helper — logs in and sets auth header."""
        response = self.client.post(reverse('login'), {
            'username': user.username,
            'password': password
        })
        token = response.data['access']
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

    def get_criteria_url(self, criteria_id, action=''):
        if action == 'update':
            return reverse('update_criteria', args=[criteria_id])
        elif action == 'delete':
            return reverse('delete_criteria', args=[criteria_id])
        return reverse('update_criteria', args=[criteria_id])

    def get_lead_url(self, lead_id, action=''):
        if action == 'update':
            return reverse('update_lead_status', args=[lead_id])
        elif action == 'assign':
            return reverse('assign_lead', args=[lead_id])
        return reverse('get_lead_by_id', args=[lead_id])


# ─────────────────────────────────────────────────────────────────────────────
# 1. POSITIVE TEST CASES
# ─────────────────────────────────────────────────────────────────────────────

class LeadPositiveTests(LeadBaseSetup):

    def test_admin_can_create_criteria(self):
        """Admin can create a new lead criteria rule."""
        self.authenticate(self.admin, 'Admin@12345')
        response = self.client.post(self.create_criteria_url, {
            'name':     'Hypertension Patients',
            'criteria': {'condition': 'hypertension', 'severity': 'severe'},
            'is_active': True
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['name'], 'Hypertension Patients')

    def test_admin_can_list_criteria(self):
        """Admin can list all criteria for their hospital."""
        self.authenticate(self.admin, 'Admin@12345')
        response = self.client.get(self.list_criteria_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(response.data), 1)

    def test_admin_can_update_criteria(self):
        """Admin can update an existing criteria rule."""
        self.authenticate(self.admin, 'Admin@12345')
        url = self.get_criteria_url(self.criteria.id, 'update')
        response = self.client.patch(url, {
            'name': 'Updated Criteria Name'
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['name'], 'Updated Criteria Name')

    def test_admin_can_soft_delete_criteria(self):
        """Admin can deactivate a criteria rule."""
        self.authenticate(self.admin, 'Admin@12345')
        url = self.get_criteria_url(self.criteria.id, 'delete')
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.criteria.refresh_from_db()
        self.assertFalse(self.criteria.is_active)

    def test_admin_can_trigger_lead_generation(self):
        """Admin can manually trigger lead generation."""
        self.authenticate(self.admin, 'Admin@12345')
        response = self.client.post(self.generate_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('leads_created', response.data)

    def test_admin_can_list_all_leads(self):
        """Admin can see all leads for their hospital."""
        self.authenticate(self.admin, 'Admin@12345')
        response = self.client.get(self.list_leads_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(response.data), 1)

    def test_admin_can_get_lead_by_id(self):
        """Admin can get full lead details by ID."""
        self.authenticate(self.admin, 'Admin@12345')
        url = self.get_lead_url(self.lead.id)
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'new')

    def test_admin_can_update_lead_status(self):
        """Admin can update lead status."""
        self.authenticate(self.admin, 'Admin@12345')
        url = self.get_lead_url(self.lead.id, 'update')
        response = self.client.patch(url, {
            'status': 'contacted'
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'contacted')

    def test_admin_can_assign_lead_to_doctor(self):
        """Admin can assign a lead to a doctor in the same hospital."""
        self.authenticate(self.admin, 'Admin@12345')
        url = self.get_lead_url(self.lead.id, 'assign')
        response = self.client.patch(url, {
            'doctor_id': self.doctor.id
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('assigned_to', response.data)

    def test_doctor_sees_only_assigned_leads(self):
        """Doctor only sees leads assigned to them."""
        # Assign lead to doctor first
        self.lead.assigned_to = self.doctor
        self.lead.save()

        self.authenticate(self.doctor, 'Doctor@12345')
        response = self.client.get(self.list_leads_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        for lead in response.data:
            self.assertEqual(
                lead['assigned_to_username'],
                self.doctor.username
            )

    def test_filter_leads_by_status(self):
        """Can filter leads by status."""
        self.authenticate(self.admin, 'Admin@12345')
        response = self.client.get(f'{self.list_leads_url}?status=new')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        for lead in response.data:
            self.assertEqual(lead['status'], 'new')

    def test_lead_generation_creates_leads_for_matching_patients(self):
        """Lead generation creates leads for patients matching criteria."""
        self.authenticate(self.admin, 'Admin@12345')
        # Delete existing lead to test fresh creation
        Lead.objects.all().delete()
        response = self.client.post(self.generate_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreater(response.data['leads_created'], 0)

    def test_criteria_auto_assigned_to_hospital(self):
        """Criteria is auto assigned to admin's hospital on create."""
        self.authenticate(self.admin, 'Admin@12345')
        response = self.client.post(self.create_criteria_url, {
            'name':     'Auto Hospital Test',
            'criteria': {'is_chronic': True},
            'is_active': True
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['hospital'], self.hospital_a.id)


# ─────────────────────────────────────────────────────────────────────────────
# 2. NEGATIVE TEST CASES
# ─────────────────────────────────────────────────────────────────────────────

class LeadNegativeTests(LeadBaseSetup):

    def test_doctor_cannot_create_criteria(self):
        """Doctor role is blocked from creating criteria."""
        self.authenticate(self.doctor, 'Doctor@12345')
        response = self.client.post(self.create_criteria_url, {
            'name':     'Unauthorized Criteria',
            'criteria': {'condition': 'diabetes'},
            'is_active': True
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_create_criteria_empty_criteria_json_fails(self):
        """Creating criteria with empty JSON is rejected."""
        self.authenticate(self.admin, 'Admin@12345')
        response = self.client.post(self.create_criteria_url, {
            'name':     'Empty Criteria',
            'criteria': {},
            'is_active': True
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_criteria_invalid_json_keys_fails(self):
        """Creating criteria with invalid JSON keys is rejected."""
        self.authenticate(self.admin, 'Admin@12345')
        response = self.client.post(self.create_criteria_url, {
            'name':     'Bad Keys',
            'criteria': {'invalid_key': 'value'},
            'is_active': True
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_get_nonexistent_lead_returns_404(self):
        """Getting a lead that does not exist returns 404."""
        self.authenticate(self.admin, 'Admin@12345')
        url = self.get_lead_url(99999)
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_generate_leads_no_criteria_fails(self):
        """Lead generation fails when no active criteria exist."""
        # Deactivate all criteria
        LeadCriteria.objects.all().update(is_active=False)
        self.authenticate(self.admin, 'Admin@12345')
        response = self.client.post(self.generate_url)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_assign_lead_to_wrong_hospital_doctor_fails(self):
        """Cannot assign lead to doctor from different hospital."""
        # Create doctor in Hospital B
        other_doctor = User.objects.create_user(
            username='other_doctor',
            email='other@test.com',
            password='Doctor@12345',
            role='Doctor',
            hospital=self.hospital_b  # different hospital
        )
        self.authenticate(self.admin, 'Admin@12345')
        url = self.get_lead_url(self.lead.id, 'assign')
        response = self.client.patch(url, {
            'doctor_id': other_doctor.id
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_doctor_cannot_update_unassigned_lead(self):
        """Doctor cannot update a lead not assigned to them."""
        self.authenticate(self.doctor, 'Doctor@12345')
        url = self.get_lead_url(self.lead.id, 'update')
        response = self.client.patch(url, {
            'status': 'contacted'
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_unauthenticated_cannot_list_leads(self):
        """Unauthenticated requests to lead list are rejected."""
        response = self.client.get(self.list_leads_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


# ─────────────────────────────────────────────────────────────────────────────
# 3. TENANT ISOLATION TEST CASES
# ─────────────────────────────────────────────────────────────────────────────

class LeadTenantIsolationTests(LeadBaseSetup):

    def test_admin_cannot_see_other_hospital_leads(self):
        """Admin from Hospital A cannot see Hospital B leads."""
        # Create lead in Hospital B
        lead_b = Lead.objects.create(
            patient=self.patient_b,
            hospital=self.hospital_b,
            status='new'
        )
        self.authenticate(self.admin, 'Admin@12345')
        response = self.client.get(self.list_leads_url)
        lead_ids = [l['id'] for l in response.data]
        self.assertNotIn(lead_b.id, lead_ids)

    def test_admin_cannot_access_other_hospital_lead_by_id(self):
        """Admin cannot access a lead from a different hospital."""
        lead_b = Lead.objects.create(
            patient=self.patient_b,
            hospital=self.hospital_b,
            status='new'
        )
        self.authenticate(self.admin, 'Admin@12345')
        url = self.get_lead_url(lead_b.id)
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_admin_cannot_see_other_hospital_criteria(self):
        """Admin from Hospital A cannot see Hospital B criteria."""
        criteria_b = LeadCriteria.objects.create(
            hospital=self.hospital_b,
            name='Hospital B Criteria',
            criteria={'condition': 'hypertension'},
            is_active=True,
            created_by=self.admin_b
        )
        self.authenticate(self.admin, 'Admin@12345')
        response = self.client.get(self.list_criteria_url)
        criteria_ids = [c['id'] for c in response.data]
        self.assertNotIn(criteria_b.id, criteria_ids)