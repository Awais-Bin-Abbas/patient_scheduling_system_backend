# hospital/views.py

from rest_framework import status
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from authentication.permissions import IsAdmin, IsAdminOrDoctor
from .models import Hospital
from .serializers import HospitalSerializer, HospitalListSerializer
from hospital.mixins import TenantMixin


# ─── CREATE ───────────────────────────────────────────────────────────────────

@api_view(['POST'])
@permission_classes([IsAuthenticated, IsAdmin])
def create_hospital(request):
    """
    Create a new hospital.
    Admin only — automatically assigns the requesting admin as owner.
    """
    serializer = HospitalSerializer(data=request.data)
    if serializer.is_valid():
        # Auto assign the creating admin as the hospital owner
        serializer.save(owner=request.user)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ─── READ ─────────────────────────────────────────────────────────────────────

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_hospitals(request):
    """
    List hospitals with tenant isolation.
    Admin sees all active hospitals.
    Doctor and User see only their assigned hospital.
    """
    user = request.user

    if user.role == 'Admin':
        # Admin bypasses tenant filter — sees all active hospitals
        hospitals = Hospital.objects.filter(is_active=True)
        serializer = HospitalListSerializer(hospitals, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    # Non-admin users — resolve hospital after JWT auth has completed
    hospital, error = TenantMixin.resolve_hospital(request)
    if error:
        return error

    # Return only the user's own hospital with full details
    serializer = HospitalSerializer(hospital)
    return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdmin])
def get_hospital_by_id(request, hospital_id):
    """
    Retrieve a specific hospital by its ID.
    Admin only — can access any hospital by ID.
    """
    hospital = Hospital.objects.filter(id=hospital_id).first()

    if not hospital:
        return Response(
            {'error': 'Hospital not found.'},
            status=status.HTTP_404_NOT_FOUND
        )

    serializer = HospitalSerializer(hospital)
    return Response(serializer.data, status=status.HTTP_200_OK)


# ─── UPDATE ───────────────────────────────────────────────────────────────────

@api_view(['PATCH'])
@permission_classes([IsAuthenticated, IsAdmin])
def update_hospital(request, hospital_id):
    """
    Update hospital details partially.
    Admin only — can update name, address, contact info.
    partial=True means only provided fields are updated.
    """
    hospital = Hospital.objects.filter(id=hospital_id).first()

    if not hospital:
        return Response(
            {'error': 'Hospital not found.'},
            status=status.HTTP_404_NOT_FOUND
        )

    # partial=True allows updating only the fields that are provided
    serializer = HospitalSerializer(hospital, data=request.data, partial=True)
    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ─── SOFT DELETE ──────────────────────────────────────────────────────────────

@api_view(['DELETE'])
@permission_classes([IsAuthenticated, IsAdmin])
def delete_hospital(request, hospital_id):
    """
    Soft delete a hospital by marking it as inactive.
    Admin only — data is preserved, hospital is just hidden from active lists.
    Hard delete is intentionally avoided to preserve patient and lead history.
    """
    hospital = Hospital.objects.filter(id=hospital_id).first()

    if not hospital:
        return Response(
            {'error': 'Hospital not found.'},
            status=status.HTTP_404_NOT_FOUND
        )

    # Soft delete — set inactive instead of removing from database
    hospital.is_active = False
    hospital.save()

    return Response(
        {'message': f"Hospital '{hospital.name}' has been deactivated."},
        status=status.HTTP_200_OK
    )


# ─── RESTORE ──────────────────────────────────────────────────────────────────

@api_view(['PATCH'])
@permission_classes([IsAuthenticated, IsAdmin])
def restore_hospital(request, hospital_id):
    """
    Restore a previously deactivated hospital.
    Admin only — sets is_active back to True.
    Returns 400 if hospital is already active.
    """
    hospital = Hospital.objects.filter(id=hospital_id).first()

    if not hospital:
        return Response(
            {'error': 'Hospital not found.'},
            status=status.HTTP_404_NOT_FOUND
        )

    # Cannot restore a hospital that is already active
    if hospital.is_active:
        return Response(
            {'message': 'Hospital is already active.'},
            status=status.HTTP_400_BAD_REQUEST
        )

    # Reactivate the hospital
    hospital.is_active = True
    hospital.save()

    return Response(
        {'message': f"Hospital '{hospital.name}' has been restored."},
        status=status.HTTP_200_OK
    )


# ─── STATS ────────────────────────────────────────────────────────────────────

@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdmin])
def hospital_stats(request):
    """
    Return summary statistics for all active hospitals.
    Admin only — shows patient count and lead count per hospital.
    Lead count is derived through patient relationship since Lead
    has no direct hospital FK yet (added in Phase 4).
    """
    from patients.models import Patient
    from leads.models import Lead

    hospitals = Hospital.objects.filter(is_active=True)
    stats = []

    for hospital in hospitals:
        # Count patients directly linked to this hospital
        total_patients = Patient.objects.filter(
            hospital=hospital
        ).count()

        # Count leads via patient relationship — Lead → Patient → Hospital
        total_leads = Lead.objects.filter(
            patient__hospital=hospital
        ).count()

        stats.append({
            'hospital_id':    hospital.id,
            'hospital_name':  hospital.name,
            'total_patients': total_patients,
            'total_leads':    total_leads,
            'is_active':      hospital.is_active,
        })

    return Response(stats, status=status.HTTP_200_OK)