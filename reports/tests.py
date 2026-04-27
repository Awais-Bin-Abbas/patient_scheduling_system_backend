# reports/tests.py

from rest_framework.test import APITestCase, APIClient
from rest_framework import status
from django.urls import reverse
from django.contrib.auth import get_user_model
from unittest.mock import patch
from hospital.models import Hospital
from patients.models import Patient, Condition
from leads.models import Lead, LeadCriteria
from .models import Report

User = get_user_model()


# ─────────────────────────────────────────────────────────────────────────────
# BASE SETUP
# ─────────────────────────────────────────────────────────────────────────────

class ReportBaseSetup(APITestCase):

    def setUp(self):
        from django.core.cache import cache
        cache.clear()

        self.client = APIClient()

        # Create hospital
        self.hospital = Hospital.objects.create(
            name='Test Hospital',
            address='123 Test Street',
            contact_info='03001234567'
        )

        # Admin user
        self.admin = User.objects.create_user(
            username='admin_test',
            email='admin@test.com',
            password='Admin@12345',
            role='Admin',
            hospital=self.hospital
        )

        # Doctor user
        self.doctor = User.objects.create_user(
            username='doctor_test',
            email='doctor@test.com',
            password='Doctor@12345',
            role='Doctor',
            hospital=self.hospital
        )

        # Create patients
        self.patient1 = Patient.objects.create(
            hospital=self.hospital,
            first_name='John',
            last_name='Doe',
            dob='1960-01-15',
            email='john@test.com',
            contact_info='03001111111',
            is_chronic=True
        )

        self.patient2 = Patient.objects.create(
            hospital=self.hospital,
            first_name='Sara',
            last_name='Khan',
            dob='1980-07-22',
            email='sara@test.com',
            contact_info='03002222222',
            is_chronic=False
        )

        # Add condition to patient1
        Condition.objects.create(
            patient=self.patient1,
            name='diabetes',
            severity='severe',
            diagnosed_on='2020-01-15'
        )

        # Create criteria
        self.criteria = LeadCriteria.objects.create(
            hospital=self.hospital,
            name='Test Criteria',
            criteria={'condition': 'diabetes'},
            is_active=True,
            created_by=self.admin
        )

        # Create lead
        self.lead = Lead.objects.create(
            patient=self.patient1,
            hospital=self.hospital,
            criteria=self.criteria,
            status='new'
        )

        # Create completed report
        self.report = Report.objects.create(
            hospital=self.hospital,
            generated_by=self.admin,
            status='complete',
            data={
                'total_patients': 2,
                'total_leads': 1,
                'conversion_rate': '0%'
            }
        )

        # URLs
        self.dashboard_url   = reverse('dashboard')
        self.all_stats_url   = reverse('all_hospitals_stats')
        self.trigger_url     = reverse('trigger_report')
        self.history_url     = reverse('report_history')

    def authenticate(self, user, password):
        response = self.client.post(reverse('login'), {
            'username': user.username,
            'password': password
        })
        token = response.data['access']
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

    def get_report_url(self, report_id, action='status'):
        if action == 'result':
            return reverse('get_report', args=[report_id])
        return reverse('report_status', args=[report_id])


# ─────────────────────────────────────────────────────────────────────────────
# 1. POSITIVE TEST CASES
# ─────────────────────────────────────────────────────────────────────────────

class ReportPositiveTests(ReportBaseSetup):

    def test_admin_can_get_dashboard(self):
        """Admin can retrieve dashboard summary statistics."""
        self.authenticate(self.admin, 'Admin@12345')
        response = self.client.get(self.dashboard_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('total_patients', response.data)
        self.assertIn('total_leads', response.data)
        self.assertIn('conversion_rate', response.data)

    def test_doctor_can_get_dashboard(self):
        """Doctor can also retrieve their hospital dashboard."""
        self.authenticate(self.doctor, 'Doctor@12345')
        response = self.client.get(self.dashboard_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_dashboard_returns_correct_patient_count(self):
        """Dashboard returns correct total patient count."""
        self.authenticate(self.admin, 'Admin@12345')
        response = self.client.get(self.dashboard_url)
        self.assertEqual(response.data['total_patients'], 2)

    def test_dashboard_returns_correct_lead_count(self):
        """Dashboard returns correct total lead count."""
        self.authenticate(self.admin, 'Admin@12345')
        response = self.client.get(self.dashboard_url)
        self.assertEqual(response.data['total_leads'], 1)

    def test_dashboard_returns_leads_by_status(self):
        """Dashboard includes leads grouped by status."""
        self.authenticate(self.admin, 'Admin@12345')
        response = self.client.get(self.dashboard_url)
        self.assertIn('leads_by_status', response.data)
        self.assertIsInstance(response.data['leads_by_status'], list)

    def test_dashboard_returns_patients_by_condition(self):
        """Dashboard includes patients grouped by condition."""
        self.authenticate(self.admin, 'Admin@12345')
        response = self.client.get(self.dashboard_url)
        self.assertIn('patients_by_condition', response.data)

    @patch('reports.tasks.generate_hospital_report.delay')
    def test_admin_can_trigger_report(self, mock_task):
        """Admin can trigger background report generation."""
        mock_task.return_value.id = 'mock-task-id-123'
        self.authenticate(self.admin, 'Admin@12345')
        response = self.client.post(self.trigger_url)
        self.assertEqual(response.status_code, status.HTTP_202_ACCEPTED)
        self.assertIn('report_id', response.data)
        self.assertIn('task_id', response.data)
        self.assertEqual(response.data['status'], 'pending')

    def test_admin_can_check_report_status(self):
        """Admin can check the status of a report."""
        self.authenticate(self.admin, 'Admin@12345')
        url = self.get_report_url(self.report.id, 'status')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('status', response.data)

    def test_admin_can_get_completed_report(self):
        """Admin can retrieve a completed report result."""
        self.authenticate(self.admin, 'Admin@12345')
        url = self.get_report_url(self.report.id, 'result')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('data', response.data)

    def test_admin_can_list_report_history(self):
        """Admin can list all reports for their hospital."""
        self.authenticate(self.admin, 'Admin@12345')
        response = self.client.get(self.history_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(response.data), 1)

    def test_admin_can_get_all_hospitals_stats(self):
        """Admin can get stats across all hospitals."""
        self.authenticate(self.admin, 'Admin@12345')
        response = self.client.get(self.all_stats_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsInstance(response.data, list)
        self.assertIn('hospital_name', response.data[0])
        self.assertIn('total_patients', response.data[0])
        self.assertIn('conversion_rate', response.data[0])

    def test_dashboard_is_cached_on_second_request(self):
        """Second dashboard request returns cached data."""
        from django.core.cache import cache

        # Clear cache before test to ensure fresh start
        cache.clear()

        self.authenticate(self.admin, 'Admin@12345')

        # First request — hits DB and stores in cache
        response1 = self.client.get(self.dashboard_url)
        self.assertEqual(response1.status_code, status.HTTP_200_OK)
        self.assertFalse(response1.data.get('from_cache', False))

        # Second request — should come from cache now
        response2 = self.client.get(self.dashboard_url)
        self.assertEqual(response2.status_code, status.HTTP_200_OK)
        self.assertTrue(response2.data.get('from_cache', False))

# ─────────────────────────────────────────────────────────────────────────────
# 2. NEGATIVE TEST CASES
# ─────────────────────────────────────────────────────────────────────────────

class ReportNegativeTests(ReportBaseSetup):

    def test_unauthenticated_cannot_get_dashboard(self):
        """Unauthenticated request to dashboard is rejected."""
        response = self.client.get(self.dashboard_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_doctor_cannot_trigger_report(self):
        """Doctor role cannot trigger report generation."""
        self.authenticate(self.doctor, 'Doctor@12345')
        response = self.client.post(self.trigger_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_get_nonexistent_report_returns_404(self):
        """Getting a report that does not exist returns 404."""
        self.authenticate(self.admin, 'Admin@12345')
        url = self.get_report_url(99999, 'result')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_get_pending_report_result_returns_400(self):
        """Getting result of a pending report returns 400."""
        # Create a pending report
        pending = Report.objects.create(
            hospital=self.hospital,
            generated_by=self.admin,
            status='pending'
        )
        self.authenticate(self.admin, 'Admin@12345')
        url = self.get_report_url(pending.id, 'result')
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_doctor_cannot_trigger_report_generation(self):
        """Doctor cannot access report generation endpoint."""
        self.authenticate(self.doctor, 'Doctor@12345')
        response = self.client.post(self.trigger_url)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_unauthenticated_cannot_list_report_history(self):
        """Unauthenticated request to history is rejected."""
        response = self.client.get(self.history_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)