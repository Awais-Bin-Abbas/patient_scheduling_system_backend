# reports/tasks.py

from celery import shared_task
from django.db.models import Count, Avg, Q
from django.utils import timezone
from datetime import date


@shared_task(bind=True, max_retries=3)
def generate_hospital_report(self, report_id):
    """
    Background Celery task for generating hospital reports.
    bind=True gives access to self for progress updates and retries.
    max_retries=3 means task retries up to 3 times on failure.
    """
    from reports.models import Report
    from patients.models import Patient
    from leads.models import Lead

    try:
        # Get report record from DB
        report = Report.objects.get(id=report_id)

        # Update status to processing
        report.status = 'processing'
        report.save()

        hospital = report.hospital

        # ── Patient Statistics ──────────────────────────────────────────────
        total_patients = Patient.objects.filter(
            hospital=hospital
        ).count()

        chronic_patients = Patient.objects.filter(
            hospital=hospital,
            is_chronic=True
        ).count()

        # Group patients by condition
        patients_by_condition = list(
            Patient.objects.filter(hospital=hospital)
            .values('conditions__name')
            .annotate(count=Count('id'))
            .exclude(conditions__name=None)
            .order_by('-count')
        )

        # Group patients by condition severity
        patients_by_severity = list(
            Patient.objects.filter(hospital=hospital)
            .values('conditions__severity')
            .annotate(count=Count('id'))
            .exclude(conditions__severity=None)
        )

        # ── Lead Statistics ─────────────────────────────────────────────────
        total_leads = Lead.objects.filter(
            hospital=hospital
        ).count()

        # Group leads by status
        leads_by_status = list(
            Lead.objects.filter(hospital=hospital)
            .values('status')
            .annotate(count=Count('id'))
        )

        # Leads created this month
        today          = date.today()
        leads_this_month = Lead.objects.filter(
            hospital=hospital,
            lead_date__year=today.year,
            lead_date__month=today.month
        ).count()

        # Lead conversion rate — converted leads / total leads
        converted_leads = Lead.objects.filter(
            hospital=hospital,
            status='converted'
        ).count()

        conversion_rate = round(
            (converted_leads / total_leads * 100) if total_leads > 0 else 0,
            2
        )

        # ── Compile Report Data ─────────────────────────────────────────────
        report_data = {
            'hospital':              hospital.name,
            'generated_at':          str(timezone.now()),
            'patients': {
                'total':             total_patients,
                'chronic':           chronic_patients,
                'by_condition':      patients_by_condition,
                'by_severity':       patients_by_severity,
            },
            'leads': {
                'total':             total_leads,
                'this_month':        leads_this_month,
                'by_status':         leads_by_status,
                'converted':         converted_leads,
                'conversion_rate':   f'{conversion_rate}%',
            }
        }

        # Save completed report to DB
        report.data         = report_data
        report.status       = 'complete'
        report.completed_at = timezone.now()
        report.save()

        return {'report_id': report.id, 'status': 'complete'}

    except Exception as exc:
        # Update report status to failed
        try:
            report         = Report.objects.get(id=report_id)
            report.status  = 'failed'
            report.save()
        except Exception:
            pass

        # Retry the task after 60 seconds
        raise self.retry(exc=exc, countdown=60)