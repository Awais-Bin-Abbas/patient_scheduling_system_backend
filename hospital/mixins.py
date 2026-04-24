# hospital/mixins.py

from rest_framework.response import Response
from rest_framework import status

class TenantMixin:
    """
    Resolves request.hospital from request.user after
    DRF JWT authentication has completed.
    Must be called at the start of every tenant-aware view.
    """

    @staticmethod
    def resolve_hospital(request):
        """
        Reads hospital from authenticated user and attaches to request.
        Returns (hospital, None) on success.
        Returns (None, error_response) on failure.
        """
        # Check user is authenticated
        if not request.user or not request.user.is_authenticated:
            return None, Response(
                {'error': 'Authentication required.'},
                status=status.HTTP_401_UNAUTHORIZED
            )

        # Get hospital from user
        hospital = getattr(request.user, 'hospital', None)

        # If no hospital assigned — return clear error for ALL roles
        # Admin must also be assigned to a hospital to create patients
        if not hospital:
            return None, Response(
                {
                    'error': 'You are not assigned to any hospital.',
                    'detail': 'Ask a superuser to assign you to a hospital in Django admin.'
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        # Attach hospital to request for use in views
        request.hospital = hospital
        return hospital, None