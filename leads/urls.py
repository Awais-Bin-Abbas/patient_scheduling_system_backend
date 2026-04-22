from django.urls import path
from . import views

urlpatterns = [
    path('lead/', views.create_lead, name='create_lead'),  # Create a new lead
    path('leads/', views.get_leads, name='get_leads'),  # Get all leads or a single lead by ID
    path('lead/update/', views.update_lead, name='update_lead'),  # Update lead details
    path('lead/delete/', views.delete_lead, name='delete_lead'),  # Delete a lead
]