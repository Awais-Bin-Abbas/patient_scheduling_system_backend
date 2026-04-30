from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.db.models import Q
from django.core.cache import cache
from datetime import date
from authentication.permissions import IsAdmin, IsAdminOrDoctor
from hospital.mixins import TenantMixin
from patients.models import Patient
from .models import Lead, LeadCriteria
from .serializers import (
    LeadSerializer,
    LeadListSerializer,
    LeadCriteriaSerializer
)


# ─── LEAD CRITERIA CRUD ───────────────────────────────────────────────────────

@api_view(['POST'])
@permission_classes([IsAuthenticated, IsAdmin])
def create_criteria(request):
    """
    Create a new lead criteria rule.
    Admin only — criteria is linked to their hospital automatically.
    """
    hospital, error = TenantMixin.resolve_hospital(request)
    if error:
        return error

    serializer = LeadCriteriaSerializer(data=request.data)
    if serializer.is_valid():
        serializer.save(
            hospital=hospital,
            created_by=request.user
        )
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdmin])
def list_criteria(request):
    """
    List all lead criteria for the requesting admin's hospital.
    Tenant filtered — only sees own hospital's criteria.
    """
    hospital, error = TenantMixin.resolve_hospital(request)
    if error:
        return error

    criteria = LeadCriteria.objects.filter(hospital=hospital)
    serializer = LeadCriteriaSerializer(criteria, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(['PATCH'])
@permission_classes([IsAuthenticated, IsAdmin])
def update_criteria(request, criteria_id):
    """
    Update a lead criteria rule.
    Admin only — tenant filtered.
    """
    hospital, error = TenantMixin.resolve_hospital(request)
    if error:
        return error

    criteria = LeadCriteria.objects.filter(
        id=criteria_id,
        hospital=hospital
    ).first()

    if not criteria:
        return Response(
            {'error': 'Criteria not found.'},
            status=status.HTTP_404_NOT_FOUND
        )

    serializer = LeadCriteriaSerializer(criteria, data=request.data, partial=True)
    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated, IsAdmin])
def delete_criteria(request, criteria_id):
    """
    Soft delete a criteria by setting is_active=False.
    Admin only — tenant filtered.
    """
    hospital, error = TenantMixin.resolve_hospital(request)
    if error:
        return error

    criteria = LeadCriteria.objects.filter(
        id=criteria_id,
        hospital=hospital
    ).first()

    if not criteria:
        return Response(
            {'error': 'Criteria not found.'},
            status=status.HTTP_404_NOT_FOUND
        )

    criteria.is_active = False
    criteria.save()
    return Response(
        {'message': f"Criteria '{criteria.name}' has been deactivated."},
        status=status.HTTP_200_OK
    )


# ─── LEAD GENERATION ──────────────────────────────────────────────────────────

@api_view(['POST'])
@permission_classes([IsAuthenticated, IsAdmin])
def trigger_lead_generation(request):
    """
    Manually trigger lead generation for this hospital.
    Runs all active criteria against patient table immediately.
    """
    hospital, error = TenantMixin.resolve_hospital(request)
    if error:
        return error

    active_criteria = LeadCriteria.objects.filter(
        hospital=hospital,
        is_active=True
    )

    if not active_criteria.exists():
        return Response(
            {'error': 'No active criteria found for your hospital. Create criteria first.'},
            status=status.HTTP_400_BAD_REQUEST
        )

    total_created = 0
    total_skipped = 0

    for criteria_rule in active_criteria:
        criteria = criteria_rule.criteria

        q = Q(hospital=hospital)

        if 'condition' in criteria:
            q &= Q(conditions__name__icontains=criteria['condition'])

        if 'severity' in criteria:
            q &= Q(conditions__severity=criteria['severity'])

        if 'is_chronic' in criteria:
            q &= Q(is_chronic=criteria['is_chronic'])

        if 'min_age' in criteria:
            min_dob = date.today().replace(
                year=date.today().year - criteria['min_age']
            )
            q &= Q(dob__lte=min_dob)

        if 'max_age' in criteria:
            max_dob = date.today().replace(
                year=date.today().year - criteria['max_age']
            )
            q &= Q(dob__gte=max_dob)

        matching_patients = Patient.objects.filter(q).distinct()

        for patient in matching_patients:
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

    # Invalidate dashboard cache after lead generation
    try:
        cache.delete(f'dashboard:{hospital.id}')
    except Exception:
        pass

    return Response({
        'message':       'Lead generation completed.',
        'leads_created': total_created,
        'leads_skipped': total_skipped,
    }, status=status.HTTP_200_OK)


# ─── LEAD CRUD ────────────────────────────────────────────────────────────────

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_leads(request):
    """
    List leads with tenant isolation.
    Admin sees all leads for their hospital.
    Doctor sees only leads assigned to them.
    Supports filtering by status.
    """
    hospital, error = TenantMixin.resolve_hospital(request)
    if error:
        return error

    if request.user.role == 'Admin':
        leads = Lead.objects.filter(hospital=hospital)
    else:
        leads = Lead.objects.filter(
            hospital=hospital,
            assigned_to=request.user
        )

    lead_status = request.query_params.get('status', None)
    if lead_status:
        leads = leads.filter(status=lead_status)

    criteria_id = request.query_params.get('criteria', None)
    if criteria_id:
        leads = leads.filter(criteria__id=criteria_id)

    serializer = LeadListSerializer(leads, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_lead_by_id(request, lead_id):
    """
    Get full lead details by ID.
    Tenant filtered — cannot access other hospital leads.
    """
    hospital, error = TenantMixin.resolve_hospital(request)
    if error:
        return error

    lead = Lead.objects.filter(
        id=lead_id,
        hospital=hospital
    ).first()

    if not lead:
        return Response(
            {'error': 'Lead not found.'},
            status=status.HTTP_404_NOT_FOUND
        )

    serializer = LeadSerializer(lead)
    return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(['PATCH'])
@permission_classes([IsAuthenticated, IsAdminOrDoctor])
def update_lead_status(request, lead_id):
    """
    Update lead status and notes.
    Admin and Doctor can update status.
    Doctor can only update leads assigned to them.
    """
    hospital, error = TenantMixin.resolve_hospital(request)
    if error:
        return error

    if request.user.role == 'Admin':
        lead = Lead.objects.filter(
            id=lead_id,
            hospital=hospital
        ).first()
    else:
        lead = Lead.objects.filter(
            id=lead_id,
            hospital=hospital,
            assigned_to=request.user
        ).first()

    if not lead:
        return Response(
            {'error': 'Lead not found.'},
            status=status.HTTP_404_NOT_FOUND
        )

    serializer = LeadSerializer(lead, data=request.data, partial=True)
    if serializer.is_valid():
        serializer.save()
        # Invalidate dashboard cache so converted_leads updates immediately
        try:
            cache.delete(f'dashboard:{hospital.id}')
        except Exception:
            pass
        return Response(serializer.data, status=status.HTTP_200_OK)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsAdmin])
def create_lead(request):
    """
    Manually create a lead for a specific patient.
    Admin only — patient must belong to the same hospital.
    """
    hospital, error = TenantMixin.resolve_hospital(request)
    if error:
        return error

    patient_id = request.data.get('patient_id')
    if not patient_id:
        return Response(
            {'error': 'patient_id is required.'},
            status=status.HTTP_400_BAD_REQUEST
        )

    patient = Patient.objects.filter(
        id=patient_id,
        hospital=hospital
    ).first()

    if not patient:
        return Response(
            {'error': 'Patient not found in your hospital.'},
            status=status.HTTP_404_NOT_FOUND
        )

    if Lead.objects.filter(patient=patient, hospital=hospital).exists():
        return Response(
            {'error': 'A lead already exists for this patient.'},
            status=status.HTTP_400_BAD_REQUEST
        )

    serializer = LeadSerializer(data=request.data)
    if serializer.is_valid():
        serializer.save(
            patient=patient,
            hospital=hospital
        )
        # Invalidate dashboard cache after new lead creation
        try:
            cache.delete(f'dashboard:{hospital.id}')
        except Exception:
            pass
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['PATCH'])
@permission_classes([IsAuthenticated, IsAdmin])
def assign_lead(request, lead_id):
    """
    Assign a lead to a specific doctor.
    Admin only — doctor must belong to the same hospital.
    """
    hospital, error = TenantMixin.resolve_hospital(request)
    if error:
        return error

    lead = Lead.objects.filter(
        id=lead_id,
        hospital=hospital
    ).first()

    if not lead:
        return Response(
            {'error': 'Lead not found.'},
            status=status.HTTP_404_NOT_FOUND
        )

    doctor_id = request.data.get('doctor_id')
    if not doctor_id:
        return Response(
            {'error': 'doctor_id is required.'},
            status=status.HTTP_400_BAD_REQUEST
        )

    from authentication.models import CustomUser
    doctor = CustomUser.objects.filter(
        id=doctor_id,
        role='Doctor',
        hospital=hospital
    ).first()

    if not doctor:
        return Response(
            {'error': 'Doctor not found in your hospital.'},
            status=status.HTTP_404_NOT_FOUND
        )

    lead.assigned_to = doctor
    lead.save()

    return Response({
        'message': f'Lead assigned to Dr. {doctor.username} successfully.',
        'lead_id': lead.id,
        'assigned_to': doctor.username
    }, status=status.HTTP_200_OK)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated, IsAdmin])
def delete_lead(request, lead_id):
    """
    Delete a lead record.
    Admin only — tenant filtered.
    """
    hospital, error = TenantMixin.resolve_hospital(request)
    if error:
        return error

    lead = Lead.objects.filter(
        id=lead_id,
        hospital=hospital
    ).first()

    if not lead:
        return Response(
            {'error': 'Lead not found.'},
            status=status.HTTP_404_NOT_FOUND
        )

    lead.delete()

    # Invalidate dashboard cache after lead deletion
    try:
        cache.delete(f'dashboard:{hospital.id}')
    except Exception:
        pass

    return Response(
        {'message': 'Lead deleted successfully.'},
        status=status.HTTP_200_OK
    )