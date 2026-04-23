# hospital/views.py

from rest_framework import status
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from authentication.permissions import IsAdmin, IsAdminOrDoctor
from .models import Hospital
from .serializers import HospitalSerializer, HospitalListSerializer


# ─── CREATE ───────────────────────────────────────────────────────────────────

@api_view(['POST'])
@permission_classes([IsAuthenticated, IsAdmin])  # Only Admin can create hospitals
def create_hospital(request):
    """Create a new hospital — Admin only. Auto-assigns requester as owner."""
    serializer = HospitalSerializer(data=request.data)
    if serializer.is_valid():
        # Automatically set the creating admin as the hospital owner
        serializer.save(owner=request.user)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ─── READ ─────────────────────────────────────────────────────────────────────

@api_view(['GET'])
@permission_classes([IsAuthenticated])  # Any authenticated user can view hospitals
def get_hospitals(request):
    """
    Retrieve hospitals with tenant isolation:
    - Admin sees ALL hospitals
    - Doctor/User sees ONLY their own hospital
    """
    user = request.user

    if user.role == 'Admin':
        # Admins get the full list of all hospitals
        hospitals = Hospital.objects.filter(is_active=True)
        serializer = HospitalListSerializer(hospitals, many=True)
    else:
        # Non-admins can only see their own hospital
        if not user.hospital:
            return Response(
                {"error": "You are not assigned to any hospital."},
                status=status.HTTP_404_NOT_FOUND
            )
        serializer = HospitalSerializer(user.hospital)

    return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdmin])  # Only Admin can view any hospital by ID
def get_hospital_by_id(request, hospital_id):
    """Retrieve a specific hospital by its ID — Admin only."""
    hospital = Hospital.objects.filter(id=hospital_id).first()
    if not hospital:
        return Response(
            {"error": "Hospital not found."},
            status=status.HTTP_404_NOT_FOUND
        )
    serializer = HospitalSerializer(hospital)
    return Response(serializer.data, status=status.HTTP_200_OK)


# ─── UPDATE ───────────────────────────────────────────────────────────────────

@api_view(['PATCH'])
@permission_classes([IsAuthenticated, IsAdmin])  # Only Admin can update hospitals
def update_hospital(request, hospital_id):
    """Update hospital details — Admin only. Partial update supported."""
    hospital = Hospital.objects.filter(id=hospital_id).first()
    if not hospital:
        return Response(
            {"error": "Hospital not found."},
            status=status.HTTP_404_NOT_FOUND
        )

    # partial=True allows updating only the fields provided
    serializer = HospitalSerializer(hospital, data=request.data, partial=True)
    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated, IsAdmin])  # Only Admin can delete hospitals
def delete_hospital(request, hospital_id):
    """
    Soft-delete a hospital by marking it inactive.
    Data is preserved — hospital is just hidden from active lists.
    """
    hospital = Hospital.objects.filter(id=hospital_id).first()
    if not hospital:
        return Response(
            {"error": "Hospital not found."},
            status=status.HTTP_404_NOT_FOUND
        )

    hospital.is_active = False
    hospital.save()
    return Response(
        {"message": f"Hospital '{hospital.name}' has been deactivated."},
        status=status.HTTP_200_OK
    )


@api_view(['PATCH'])
@permission_classes([IsAuthenticated, IsAdmin])  # Only Admin can restore hospitals
def restore_hospital(request, hospital_id):
    """Restore a previously deactivated hospital — Admin only."""
    hospital = Hospital.objects.filter(id=hospital_id).first()
    if not hospital:
        return Response(
            {"error": "Hospital not found."},
            status=status.HTTP_404_NOT_FOUND
        )

    if hospital.is_active:
        return Response(
            {"message": "Hospital is already active."},
            status=status.HTTP_400_BAD_REQUEST
        )

    # Reactivate the hospital
    hospital.is_active = True
    hospital.save()
    return Response(
        {"message": f"Hospital '{hospital.name}' has been restored."},
        status=status.HTTP_200_OK
    )


# ─── STATS ────────────────────────────────────────────────────────────────────

@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdmin])
def hospital_stats(request):
    """Return summary statistics for all hospitals — Admin only."""
    from patients.models import Patient
    from leads.models import Lead

    hospitals = Hospital.objects.filter(is_active=True)
    stats = []

    for hospital in hospitals:
        # Count patients directly linked to this hospital
        total_patients = Patient.objects.filter(hospital=hospital).count()

        # Count leads by going through patient → hospital relationship
        # since Lead has no direct hospital FK yet (added in Phase 4)
        total_leads = Lead.objects.filter(
            patient__hospital=hospital  # traverse: Lead→Patient→Hospital
        ).count()

        stats.append({
            'hospital_id': hospital.id,
            'hospital_name': hospital.name,
            'total_patients': total_patients,
            'total_leads': total_leads,
            'is_active': hospital.is_active,
        })

    return Response(stats, status=status.HTTP_200_OK)