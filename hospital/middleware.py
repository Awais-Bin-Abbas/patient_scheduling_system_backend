from django.utils.deprecation import MiddlewareMixin

class TenantMiddleware(MiddlewareMixin):
    """
    Middleware placeholder for tenant context.
    Hospital is resolved at view level after DRF JWT authentication runs.
    JWT authentication happens at view level not middleware level in DRF.
    """

    def process_request(self, request):
        # Set to None by default
        # Views will set request.hospital after JWT auth completes
        request.hospital = None