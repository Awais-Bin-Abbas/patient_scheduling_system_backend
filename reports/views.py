# reports/views.py

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.core.cache import cache
from django.db.models import Count
from datetime import date
from authentication.permissions import IsAdmin
from hospital.mixins import TenantMixin
from patients.models import Patient
from leads.models import Lead
from .models import Report
from .serializers import ReportSerializer, ReportListSerializer
from .tasks import generate_hospital_report


# ─── TRIGGER REPORT ───────────────────────────────────────────────────────────

@api_view(['POST'])
@permission_classes([IsAuthenticated, IsAdmin])
def trigger_report(request):
    """
    Trigger background report generation.
    Returns task_id immediately — does not wait for completion.
    Frontend polls /status/<task_id>/ to check progress.
    """
    # Resolve hospital after JWT auth
    hospital, error = TenantMixin.resolve_hospital(request)
    if error:
        return error

    # Create a pending report record in DB
    report = Report.objects.create(
        hospital=hospital,
        generated_by=request.user,
        status='pending'
    )

    # Dispatch Celery task asynchronously
    task = generate_hospital_report.delay(report.id)

    # Save task ID to report for polling
    report.task_id = task.id
    report.save()

    return Response({
        'message':   'Report generation started.',
        'report_id': report.id,
        'task_id':   task.id,
        'status':    'pending'
    }, status=status.HTTP_202_ACCEPTED)


# ─── REPORT STATUS ────────────────────────────────────────────────────────────

@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdmin])
def report_status(request, report_id):
    """
    Check the current status of a report.
    Frontend polls this every 3 seconds until status is complete.
    """
    # Resolve hospital after JWT auth
    hospital, error = TenantMixin.resolve_hospital(request)
    if error:
        return error

    report = Report.objects.filter(
        id=report_id,
        hospital=hospital
    ).first()

    if not report:
        return Response(
            {'error': 'Report not found.'},
            status=status.HTTP_404_NOT_FOUND
        )

    return Response({
        'report_id': report.id,
        'status':    report.status,
        'task_id':   report.task_id,
        'created_at': report.created_at,
        'completed_at': report.completed_at,
    }, status=status.HTTP_200_OK)


# ─── GET REPORT RESULT ────────────────────────────────────────────────────────

@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdmin])
def get_report(request, report_id):
    """
    Retrieve the full completed report data.
    Returns 400 if report is not yet complete.
    """
    # Resolve hospital after JWT auth
    hospital, error = TenantMixin.resolve_hospital(request)
    if error:
        return error

    report = Report.objects.filter(
        id=report_id,
        hospital=hospital
    ).first()

    if not report:
        return Response(
            {'error': 'Report not found.'},
            status=status.HTTP_404_NOT_FOUND
        )

    if report.status != 'complete':
        return Response(
            {
                'error':  'Report is not ready yet.',
                'status': report.status
            },
            status=status.HTTP_400_BAD_REQUEST
        )

    serializer = ReportSerializer(report)
    return Response(serializer.data, status=status.HTTP_200_OK)


# ─── REPORT HISTORY ───────────────────────────────────────────────────────────

@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdmin])
def report_history(request):
    """
    List all reports for the requesting admin's hospital.
    Shows report status and timestamps — not full data.
    """
    # Resolve hospital after JWT auth
    hospital, error = TenantMixin.resolve_hospital(request)
    if error:
        return error

    reports    = Report.objects.filter(hospital=hospital)
    serializer = ReportListSerializer(reports, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)


# ─── DASHBOARD SUMMARY ────────────────────────────────────────────────────────

# reports/views.py — updated dashboard view

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def dashboard(request):
    """
    Return dashboard summary statistics.
    Cached in Redis for 5 minutes.
    Falls back to direct DB query if cache is unavailable.
    """
    hospital, error = TenantMixin.resolve_hospital(request)
    if error:
        return error

    cache_key = f'dashboard:{hospital.id}'

    # Try cache first — fall back gracefully if Redis is down
    try:
        cached = cache.get(cache_key)
        if cached:
            cached['from_cache'] = True
            return Response(cached, status=status.HTTP_200_OK)
    except Exception:
        # Redis not available — skip cache and go straight to DB
        pass

    # Run DB aggregation queries
    today = date.today()

    total_patients   = Patient.objects.filter(hospital=hospital).count()
    chronic_patients = Patient.objects.filter(hospital=hospital, is_chronic=True).count()
    total_leads      = Lead.objects.filter(hospital=hospital).count()

    leads_this_month = Lead.objects.filter(
        hospital=hospital,
        lead_date__year=today.year,
        lead_date__month=today.month
    ).count()

    converted_leads  = Lead.objects.filter(
        hospital=hospital,
        status='converted'
    ).count()

    conversion_rate  = round(
        (converted_leads / total_leads * 100) if total_leads > 0 else 0, 2
    )

    leads_by_status  = list(
        Lead.objects.filter(hospital=hospital)
        .values('status')
        .annotate(count=Count('id'))
    )

    patients_by_condition = list(
        Patient.objects.filter(hospital=hospital)
        .values('conditions__name')
        .annotate(count=Count('id'))
        .exclude(conditions__name=None)
        .order_by('-count')[:5]
    )

    data = {
        'hospital':              hospital.name,
        'total_patients':        total_patients,
        'chronic_patients':      chronic_patients,
        'total_leads':           total_leads,
        'leads_this_month':      leads_this_month,
        'converted_leads':       converted_leads,
        'conversion_rate':       f'{conversion_rate}%',
        'leads_by_status':       leads_by_status,
        'patients_by_condition': patients_by_condition,
        'from_cache':            False
    }

    # Try to cache — skip if Redis is down
    try:
        cache.set(cache_key, data, timeout=300)
    except Exception:
        pass

    return Response(data, status=status.HTTP_200_OK)

# ─── ALL HOSPITALS STATS (Super Admin) ───────────────────────────────────────

@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdmin])
def all_hospitals_stats(request):
    """
    Return summary statistics for ALL hospitals.
    Used for system-wide overview on the admin dashboard.
    """
    from hospital.models import Hospital

    hospitals = Hospital.objects.filter(is_active=True)
    stats     = []

    for hosp in hospitals:
        total_patients = Patient.objects.filter(hospital=hosp).count()
        total_leads    = Lead.objects.filter(hospital=hosp).count()
        converted      = Lead.objects.filter(hospital=hosp, status='converted').count()
        rate           = round(
            (converted / total_leads * 100) if total_leads > 0 else 0, 2
        )

        stats.append({
            'hospital_id':      hosp.id,
            'hospital_name':    hosp.name,
            'total_patients':   total_patients,
            'total_leads':      total_leads,
            'converted_leads':  converted,
            'conversion_rate':  f'{rate}%',
            'is_active':        hosp.is_active,
        })

    return Response(stats, status=status.HTTP_200_OK)