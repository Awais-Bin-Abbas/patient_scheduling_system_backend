from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/auth/', include('authentication.urls')),
    path('api/hospital/', include('hospital.urls')),   
    path('api/patient/', include('patients.urls')),
    path('api/lead/', include('leads.urls')),
    path('api/reports/', include('reports.urls')),
]