from django.urls import path
from . import views

urlpatterns = [
    path('hospital/', views.create_hospital, name='create_hospital'),  # Create a new hospital
    path('hospitals/', views.get_hospitals, name='get_hospitals'),  # Get all hospitals or a single hospital by ID
    path('hospital/update/', views.update_hospital, name='update_hospital'),  # Update hospital
    path('hospital/delete/', views.delete_hospital, name='delete_hospital'),  # Delete a hospital
]