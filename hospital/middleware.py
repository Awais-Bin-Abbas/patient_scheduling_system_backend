# hospital/middleware.py

from django.utils.deprecation import MiddlewareMixin

class TenantMiddleware(MiddlewareMixin):
    """
    Middleware that automatically attaches the current user's hospital
    to every request object. This allows all views to access
    request.hospital for tenant-level data filtering without
    repeating the logic in every single view.
    """

    def process_request(self, request):
        # Only process authenticated users who have a hospital assigned
        if hasattr(request, 'user') and request.user.is_authenticated:
            # Attach hospital to request so all views can use request.hospital
            request.hospital = getattr(request.user, 'hospital', None)
        else:
            # Unauthenticated requests have no hospital context
            request.hospital = None