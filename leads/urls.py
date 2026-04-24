from django.urls import path
from . import views

urlpatterns = [
    # Lead Criteria CRUD
    path('criteria/create/', views.create_criteria, name='create_criteria'),
    path('criteria/list/', views.list_criteria, name='list_criteria'),
    path('criteria/<int:criteria_id>/update/', views.update_criteria, name='update_criteria'),
    path('criteria/<int:criteria_id>/delete/', views.delete_criteria, name='delete_criteria'),

    # Lead Generation — manual trigger
    path('generate/', views.trigger_lead_generation, name='trigger_lead_generation'),

    # Lead Management
    path('list/', views.list_leads, name='list_leads'),
    path('<int:lead_id>/', views.get_lead_by_id, name='get_lead_by_id'),
    path('<int:lead_id>/update/', views.update_lead_status, name='update_lead_status'),
    path('<int:lead_id>/assign/', views.assign_lead, name='assign_lead'),
]