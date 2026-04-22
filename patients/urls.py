from django.urls import path
from . import views

urlpatterns = [
    path('patient/', views.create_patient, name='create_patient'),  # Create a new patient
    path('patients/', views.get_patients, name='get_patients'),  # Get all patients or a single patient by ID
    path('patient/update/', views.update_patient, name='update_patient'),  # Update a patient's details
    path('patient/delete/', views.delete_patient, name='delete_patient'),  # Delete a patient
]