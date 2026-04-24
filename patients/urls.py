# patients/urls.py

from django.urls import path
from . import views

urlpatterns = [
    # Patient CRUD
    path('create/', views.create_patient, name='create_patient'),
    path('list/', views.get_patients, name='get_patients'),
    path('<int:patient_id>/', views.get_patient_by_id, name='get_patient_by_id'),
    path('<int:patient_id>/update/', views.update_patient, name='update_patient'),
    path('<int:patient_id>/delete/', views.delete_patient, name='delete_patient'),

    # Condition management
    path('<int:patient_id>/conditions/', views.get_patient_conditions, name='get_patient_conditions'),
    path('<int:patient_id>/conditions/add/', views.add_condition, name='add_condition'),
    path('<int:patient_id>/conditions/<int:condition_id>/remove/', views.remove_condition, name='remove_condition'),
]