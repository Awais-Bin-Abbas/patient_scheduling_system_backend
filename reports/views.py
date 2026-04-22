from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from leads.models import Lead
from leads.serializers import LeadSerializer

@api_view(['GET'])
@permission_classes([IsAuthenticated])  # Any authenticated user can generate reports
def generate_leads_report(request):
    """
    Generate and return a report for leads.
    """
    leads = Lead.objects.all()
    serializer = LeadSerializer(leads, many=True)
    return Response(serializer.data)