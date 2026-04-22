from django.urls import path
from . import views

urlpatterns = [
    path('leads-report/', views.generate_leads_report, name='leads_report'),  # Generate leads report
]