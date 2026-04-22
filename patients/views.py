from rest_framework import status
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from .serializers import PatientSerializer
from authentication.permissions import IsAdmin, IsDoctor

# POST: Create a new patient (Admin/Doctor can create)
@api_view(['POST'])
@permission_classes([IsAuthenticated])  # Any authenticated user can create a patient
def create_patient(request):
    serializer = PatientSerializer(data=request.data)
    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

# PATCH: Update patient details (Doctor/Admin can update patients)
@api_view(['PATCH'])
@permission_classes([IsAuthenticated, IsDoctor])  # Only Doctor/Admin can update patients
def update_patient(request):
    patient_id = request.data.get('id')
    if not patient_id:
        return Response({"error": "Patient ID is required"}, status=status.HTTP_400_BAD_REQUEST)

    patient = Patient.objects.filter(id=patient_id).first()
    if not patient:
        return Response({"error": "Patient not found"}, status=status.HTTP_404_NOT_FOUND)

    serializer = PatientSerializer(patient, data=request.data, partial=True)
    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

# DELETE: Delete a patient entry (Only Admin can delete patients)
@api_view(['DELETE'])
@permission_classes([IsAuthenticated, IsAdmin])  # Only Admin can delete patients
def delete_patient(request):
    patient_id = request.data.get('id')
    if not patient_id:
        return Response({"error": "Patient ID is required"}, status=status.HTTP_400_BAD_REQUEST)

    patient = Patient.objects.filter(id=patient_id).first()
    if not patient:
        return Response({"error": "Patient not found"}, status=status.HTTP_404_NOT_FOUND)

    patient.delete()
    return Response({"success": "Patient deleted successfully"}, status=status.HTTP_200_OK)

# GET: Retrieve all patients or a single patient by ID
@api_view(['GET'])
@permission_classes([IsAuthenticated])  # Any authenticated user can retrieve patients
def get_patients(request):
    """
    Retrieve a list of all patients, or a single patient by ID.
    """
    patient_id = request.query_params.get('id')  # Optional query parameter for patient ID
    if patient_id:
        patient = Patient.objects.filter(id=patient_id).first()
        if not patient:
            return Response({"error": "Patient not found"}, status=status.HTTP_404_NOT_FOUND)
        serializer = PatientSerializer(patient)
        return Response(serializer.data, status=status.HTTP_200_OK)

    patients = Patient.objects.all()  # If no ID, return all patients
    serializer = PatientSerializer(patients, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)