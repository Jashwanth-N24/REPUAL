from django.urls import path
from . import views

app_name = 'metrics'

urlpatterns = [
    path('', views.metrics_dashboard_view, name='benchmark'),
    path('api/', views.metrics_api_view, name='api'),
]

