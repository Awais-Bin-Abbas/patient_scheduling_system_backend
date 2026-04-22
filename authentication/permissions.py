# authentication/permissions.py

from rest_framework.permissions import BasePermission

# ─── Role-Based Permissions ────────────────────────────────────────────────────

class IsAdmin(BasePermission):
    """Allow access only to users with the 'Admin' role."""
    def has_permission(self, request, view):
        # Check role field directly — fixes the old is_staff bug
        return request.user.is_authenticated and request.user.role == 'Admin'


class IsDoctor(BasePermission):
    """Allow access only to users with the 'Doctor' role."""
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role == 'Doctor'


class IsAdminOrDoctor(BasePermission):
    """Allow access to both Admin and Doctor roles."""
    def has_permission(self, request, view):
        return request.user.is_authenticated and request.user.role in ['Admin', 'Doctor']


class IsOwnerOrAdmin(BasePermission):
    """Allow object access only to its owner or an Admin (object-level permission)."""
    def has_object_permission(self, request, view, obj):
        # Admin can access any object
        if request.user.role == 'Admin':
            return True
        # Owner can only access their own object
        return obj == request.user


class IsSameHospital(BasePermission):
    """Allow access only if the user belongs to the same hospital as the object."""
    def has_object_permission(self, request, view, obj):
        # Admin bypasses tenant check
        if request.user.role == 'Admin':
            return True
        # Check if the object's hospital matches the requesting user's hospital
        return obj.hospital == request.user.hospital