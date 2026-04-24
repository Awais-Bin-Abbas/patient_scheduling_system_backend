# leads/tasks.py

from celery import shared_task
from django.db.models import Q
from datetime import date


@shared_task
def apply_lead_criteria():
    """
    Background Celery task that runs all active lead criteria
    against the patient table and creates leads for matches.
    Scheduled to run nightly at midnight via Celery Beat.
    Can also be triggered manually via the API endpoint.
    """
    from hospital.models import Hospital
    from patients.models import Patient
    from leads.models import Lead, LeadCriteria

    # Get all active criteria across all hospitals
    all_criteria = LeadCriteria.objects.filter(
        is_active=True
    ).select_related('hospital')

    total_created = 0
    total_skipped = 0

    for criteria_rule in all_criteria:
        criteria = criteria_rule.criteria
        hospital = criteria_rule.hospital

        # Start with patients from this hospital only
        q = Q(hospital=hospital)

        # Build Q objects dynamically from stored criteria JSON
        if 'condition' in criteria:
            q &= Q(conditions__name__icontains=criteria['condition'])

        if 'severity' in criteria:
            q &= Q(conditions__severity=criteria['severity'])

        if 'is_chronic' in criteria:
            q &= Q(is_chronic=criteria['is_chronic'])

        if 'min_age' in criteria:
            # Calculate minimum DOB from minimum age
            min_dob = date.today().replace(
                year=date.today().year - criteria['min_age']
            )
            q &= Q(dob__lte=min_dob)

        if 'max_age' in criteria:
            # Calculate maximum DOB from maximum age
            max_dob = date.today().replace(
                year=date.today().year - criteria['max_age']
            )
            q &= Q(dob__gte=max_dob)

        # Get all matching patients for this criteria
        matching_patients = Patient.objects.filter(q).distinct()

        for patient in matching_patients:
            # get_or_create prevents duplicate leads
            lead, created = Lead.objects.get_or_create(
                patient=patient,
                hospital=hospital,
                defaults={
                    'criteria': criteria_rule,
                    'status':   'new'
                }
            )
            if created:
                total_created += 1
            else:
                total_skipped += 1

    return f'Done. Created: {total_created} | Skipped: {total_skipped}'