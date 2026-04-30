# reports/urls.py

from django.urls import path
from . import views

urlpatterns = [
    # Dashboard
    path('dashboard/', views.dashboard, name='dashboard'),
    path('all-stats/', views.all_hospitals_stats, name='all_hospitals_stats'),

    # Report Generation
    path('generate/', views.trigger_report, name='trigger_report'),
    path('<int:report_id>/status/', views.report_status, name='report_status'),
    path('<int:report_id>/result/', views.get_report, name='get_report'),
    path('history/', views.report_history, name='report_history'),
    path('clear/', views.clear_all_reports, name='clear_all_reports'),
    path('<int:report_id>/delete/', views.delete_report, name='delete_report'),
]