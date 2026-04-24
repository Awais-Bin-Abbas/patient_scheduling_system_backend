# patients/views.py

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.db.models import Q
from authentication.permissions import IsAdmin, IsAdminOrDoctor
from hospital.mixins import TenantMixin
from .models import Patient, Condition
from .serializers import (
    PatientSerializer,
    PatientListSerializer,
    ConditionSerializer
)


# ─── CREATE ───────────────────────────────────────────────────────────────────

@api_view(['POST'])
@permission_classes([IsAuthenticated, IsAdminOrDoctor])
def create_patient(request):
    """
    Create a new patient.
    Hospital is auto assigned from the requesting user via TenantMixin.
    Admin and Doctor roles can create patients.
    """
    # Resolve hospital after JWT auth has completed
    hospital, error = TenantMixin.resolve_hospital(request)
    if error:
        return error

    serializer = PatientSerializer(data=request.data)
    if serializer.is_valid():
        # Auto assign hospital from middleware — ensures tenant isolation
        serializer.save(hospital=hospital)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ─── READ ─────────────────────────────────────────────────────────────────────

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_patients(request):
    """
    List all patients for the requesting user's hospital.
    Supports:
      - Search by name or email (?search=John)
      - Filter by condition name (?condition=diabetes)
      - Filter by chronic status (?is_chronic=true)
      - Filter by condition severity (?severity=severe)
    All results are tenant filtered to the requesting user's hospital.
    """
    # Resolve hospital after JWT auth has completed
    hospital, error = TenantMixin.resolve_hospital(request)
    if error:
        return error

    # Start with all patients from this hospital only — tenant isolation
    patients = Patient.objects.filter(
        hospital=hospital
    ).prefetch_related('conditions')

    # Search by first name, last name, or email
    search = request.query_params.get('search', None)
    if search:
        patients = patients.filter(
            Q(first_name__icontains=search) |
            Q(last_name__icontains=search)  |
            Q(email__icontains=search)
        )

    # Filter by condition name
    condition = request.query_params.get('condition', None)
    if condition:
        patients = patients.filter(
            conditions__name__icontains=condition
        ).distinct()

    # Filter by chronic status
    is_chronic = request.query_params.get('is_chronic', None)
    if is_chronic is not None:
        patients = patients.filter(
            is_chronic=is_chronic.lower() == 'true'
        )

    # Filter by condition severity
    severity = request.query_params.get('severity', None)
    if severity:
        patients = patients.filter(
            conditions__severity=severity
        ).distinct()

    serializer = PatientListSerializer(patients, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_patient_by_id(request, patient_id):
    """
    Get full patient details including all conditions and calculated age.
    Tenant filtered — cannot access patients from other hospitals.
    """
    # Resolve hospital after JWT auth has completed
    hospital, error = TenantMixin.resolve_hospital(request)
    if error:
        return error

    # Filter by both patient id AND hospital — prevents cross-tenant access
    patient = Patient.objects.filter(
        id=patient_id,
        hospital=hospital
    ).prefetch_related('conditions').first()

    if not patient:
        return Response(
            {'error': 'Patient not found.'},
            status=status.HTTP_404_NOT_FOUND
        )

    serializer = PatientSerializer(patient)
    return Response(serializer.data, status=status.HTTP_200_OK)


# ─── UPDATE ───────────────────────────────────────────────────────────────────

@api_view(['PATCH'])
@permission_classes([IsAuthenticated, IsAdminOrDoctor])
def update_patient(request, patient_id):
    """
    Update patient details partially.
    Admin and Doctor roles can update patients.
    Tenant filtered — cannot update patients from other hospitals.
    """
    # Resolve hospital after JWT auth has completed
    hospital, error = TenantMixin.resolve_hospital(request)
    if error:
        return error

    # Filter by both patient id AND hospital — prevents cross-tenant updates
    patient = Patient.objects.filter(
        id=patient_id,
        hospital=hospital
    ).first()

    if not patient:
        return Response(
            {'error': 'Patient not found.'},
            status=status.HTTP_404_NOT_FOUND
        )

    # partial=True allows updating only the fields that are provided
    serializer = PatientSerializer(patient, data=request.data, partial=True)
    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ─── DELETE ───────────────────────────────────────────────────────────────────

@api_view(['DELETE'])
@permission_classes([IsAuthenticated, IsAdmin])
def delete_patient(request, patient_id):
    """
    Delete a patient record.
    Admin only — data is removed from the system.
    Tenant filtered — cannot delete patients from other hospitals.
    """
    # Resolve hospital after JWT auth has completed
    hospital, error = TenantMixin.resolve_hospital(request)
    if error:
        return error

    # Filter by both patient id AND hospital — prevents cross-tenant deletion
    patient = Patient.objects.filter(
        id=patient_id,
        hospital=hospital
    ).first()

    if not patient:
        return Response(
            {'error': 'Patient not found.'},
            status=status.HTTP_404_NOT_FOUND
        )

    patient_name = f'{patient.first_name} {patient.last_name}'
    patient.delete()

    return Response(
        {'message': f'Patient {patient_name} deleted successfully.'},
        status=status.HTTP_200_OK
    )


# ─── CONDITIONS ───────────────────────────────────────────────────────────────

@api_view(['POST'])
@permission_classes([IsAuthenticated, IsAdminOrDoctor])
def add_condition(request, patient_id):
    """
    Add a medical condition to a specific patient.
    Admin and Doctor roles can add conditions.
    Auto sets patient.is_chronic=True if severity is severe.
    Tenant filtered — cannot add conditions to other hospital patients.
    """
    # Resolve hospital after JWT auth has completed
    hospital, error = TenantMixin.resolve_hospital(request)
    if error:
        return error

    # Filter by both patient id AND hospital — prevents cross-tenant access
    patient = Patient.objects.filter(
        id=patient_id,
        hospital=hospital
    ).first()

    if not patient:
        return Response(
            {'error': 'Patient not found.'},
            status=status.HTTP_404_NOT_FOUND
        )

    serializer = ConditionSerializer(data=request.data)
    if serializer.is_valid():
        # Link the condition to this specific patient on save
        serializer.save(patient=patient)

        # Auto set is_chronic flag when a severe condition is added
        if serializer.validated_data.get('severity') == 'severe':
            patient.is_chronic = True
            patient.save()

        return Response(serializer.data, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated, IsAdminOrDoctor])
def remove_condition(request, patient_id, condition_id):
    """
    Remove a specific condition from a patient.
    Admin and Doctor roles can remove conditions.
    Tenant filtered — cannot remove conditions from other hospital patients.
    """
    # Resolve hospital after JWT auth has completed
    hospital, error = TenantMixin.resolve_hospital(request)
    if error:
        return error

    # Filter through patient__hospital to enforce tenant isolation
    condition = Condition.objects.filter(
        id=condition_id,
        patient__id=patient_id,
        patient__hospital=hospital
    ).first()

    if not condition:
        return Response(
            {'error': 'Condition not found.'},
            status=status.HTTP_404_NOT_FOUND
        )

    condition.delete()
    return Response(
        {'message': 'Condition removed successfully.'},
        status=status.HTTP_200_OK
    )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_patient_conditions(request, patient_id):
    """
    Get all conditions for a specific patient.
    Any authenticated user from the same hospital can view conditions.
    Tenant filtered — cannot view conditions of other hospital patients.
    """
    # Resolve hospital after JWT auth has completed
    hospital, error = TenantMixin.resolve_hospital(request)
    if error:
        return error

    # Filter by both patient id AND hospital — prevents cross-tenant access
    patient = Patient.objects.filter(
        id=patient_id,
        hospital=hospital
    ).first()

    if not patient:
        return Response(
            {'error': 'Patient not found.'},
            status=status.HTTP_404_NOT_FOUND
        )

    # Get all conditions linked to this patient
    conditions = patient.conditions.all()
    serializer = ConditionSerializer(conditions, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)