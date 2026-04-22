from authentication.permissions import IsAdmin, IsDoctor  # Corrected import path
from rest_framework import status
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from .models import Hospital
from .serializers import HospitalSerializer

# POST: Create a new hospital (Only Admin can create hospitals)
@api_view(['POST'])
@permission_classes([IsAuthenticated, IsAdmin])  # Only Admin can create hospitals
def create_hospital(request):
    serializer = HospitalSerializer(data=request.data)
    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

# GET: Retrieve all hospitals or a single hospital by ID
@api_view(['GET'])
@permission_classes([IsAuthenticated])  # Any authenticated user can retrieve hospitals
def get_hospitals(request):
    hospital_id = request.query_params.get('id')  # Optional query parameter for hospital ID
    if hospital_id:
        hospital = Hospital.objects.filter(id=hospital_id).first()
        if not hospital:
            return Response({"error": "Hospital not found"}, status=status.HTTP_404_NOT_FOUND)
        serializer = HospitalSerializer(hospital)
        return Response(serializer.data, status=status.HTTP_200_OK)

    hospitals = Hospital.objects.all()  # If no ID, return all hospitals
    serializer = HospitalSerializer(hospitals, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)

# PATCH: Update hospital details (Only Admin can update)
@api_view(['PATCH'])
@permission_classes([IsAuthenticated, IsAdmin])  # Only Admin can update hospitals
def update_hospital(request):
    hospital_id = request.data.get('id')
    if not hospital_id:
        return Response({"error": "Hospital ID is required"}, status=status.HTTP_400_BAD_REQUEST)

    hospital = Hospital.objects.filter(id=hospital_id).first()
    if not hospital:
        return Response({"error": "Hospital not found"}, status=status.HTTP_404_NOT_FOUND)

    serializer = HospitalSerializer(hospital, data=request.data, partial=True)
    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

# DELETE: Delete a hospital entry (Only Admin can delete hospitals)
@api_view(['DELETE'])
@permission_classes([IsAuthenticated, IsAdmin])  # Only Admin can delete hospitals
def delete_hospital(request):
    hospital_id = request.data.get('id')
    if not hospital_id:
        return Response({"error": "Hospital ID is required"}, status=status.HTTP_400_BAD_REQUEST)

    hospital = Hospital.objects.filter(id=hospital_id).first()
    if not hospital:
        return Response({"error": "Hospital not found"}, status=status.HTTP_404_NOT_FOUND)

    hospital.delete()
    return Response({"success": "Hospital deleted successfully"}, status=status.HTTP_200_OK)