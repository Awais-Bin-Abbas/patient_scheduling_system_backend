# hospital/urls.py

from django.urls import path
from . import views

urlpatterns = [
    # Create a new hospital — Admin only
    path('create/', views.create_hospital, name='create_hospital'),

    # List hospitals — Admin sees all, Doctor sees own only
    path('list/', views.get_hospitals, name='get_hospitals'),

    # Get single hospital by ID — Admin only
    path('<int:hospital_id>/', views.get_hospital_by_id, name='get_hospital_by_id'),

    # Update hospital details — Admin only
    path('<int:hospital_id>/update/', views.update_hospital, name='update_hospital'),

    # Soft delete hospital — Admin only
    path('<int:hospital_id>/delete/', views.delete_hospital, name='delete_hospital'),

    # Restore deactivated hospital — Admin only
    path('<int:hospital_id>/restore/', views.restore_hospital, name='restore_hospital'),

    # Hospital stats for dashboard — Admin only
    path('stats/', views.hospital_stats, name='hospital_stats'),
]