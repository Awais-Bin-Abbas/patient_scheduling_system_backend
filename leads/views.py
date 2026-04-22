from rest_framework import status
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from .serializers import LeadSerializer
from authentication.permissions import IsAdmin

# POST: Create a new lead (Admin/Doctor can create leads)
@api_view(['POST'])
@permission_classes([IsAuthenticated])  # Any authenticated user can create a lead
def create_lead(request):
    serializer = LeadSerializer(data=request.data)
    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

# PATCH: Update lead details (Only Admin can update)
@api_view(['PATCH'])
@permission_classes([IsAuthenticated, IsAdmin])  # Only Admin can update leads
def update_lead(request):
    lead_id = request.data.get('id')
    if not lead_id:
        return Response({"error": "Lead ID is required"}, status=status.HTTP_400_BAD_REQUEST)

    lead = Lead.objects.filter(id=lead_id).first()
    if not lead:
        return Response({"error": "Lead not found"}, status=status.HTTP_404_NOT_FOUND)

    serializer = LeadSerializer(lead, data=request.data, partial=True)
    if serializer.is_valid():
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

# DELETE: Delete a lead entry (Only Admin can delete leads)
@api_view(['DELETE'])
@permission_classes([IsAuthenticated, IsAdmin])  # Only Admin can delete leads
def delete_lead(request):
    lead_id = request.data.get('id')
    if not lead_id:
        return Response({"error": "Lead ID is required"}, status=status.HTTP_400_BAD_REQUEST)

    lead = Lead.objects.filter(id=lead_id).first()
    if not lead:
        return Response({"error": "Lead not found"}, status=status.HTTP_404_NOT_FOUND)

    lead.delete()
    return Response({"success": "Lead deleted successfully"}, status=status.HTTP_200_OK)


# GET: Retrieve all leads or a single lead by ID
@api_view(['GET'])
@permission_classes([IsAuthenticated])  # Any authenticated user can retrieve leads
def get_leads(request):
    """
    Retrieve a list of all leads, or a single lead by ID.
    """
    lead_id = request.query_params.get('id')  # Optional query parameter for lead ID
    if lead_id:
        lead = Lead.objects.filter(id=lead_id).first()
        if not lead:
            return Response({"error": "Lead not found"}, status=status.HTTP_404_NOT_FOUND)
        serializer = LeadSerializer(lead)
        return Response(serializer.data, status=status.HTTP_200_OK)

    leads = Lead.objects.all()  # If no ID, return all leads
    serializer = LeadSerializer(leads, many=True)
    return Response(serializer.data, status=status.HTTP_200_OK)