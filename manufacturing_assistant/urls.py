from django.contrib import admin
from django.urls import include, path
from django.conf import settings
from django.conf.urls.static import static

from core.views import dashboard_view, login_view, logout_view
from apps.metrics.views import metrics_api_view
from rest_framework.routers import DefaultRouter
from apps.products.views import ProductViewSet
from apps.inspections.views import InspectionViewSet, BatchViewSet
from apps.incidents.views import sop_pdf_view

quality_api = DefaultRouter()
quality_api.register(r'products', ProductViewSet, basename='quality-api-product')
quality_api.register(r'inspections', InspectionViewSet, basename='quality-api-inspection')
quality_api.register(r'batches', BatchViewSet, basename='quality-api-batch')

urlpatterns = [
    path('', dashboard_view, name='dashboard'),
    path('login/', login_view, name='login'),
    path('logout/', logout_view, name='logout'),
    path('admin/', admin.site.urls),
    path('quality/incidents/', include('apps.incidents.urls')),
    path('quality/sops/<str:document_id>/', sop_pdf_view, name='incident_sop_pdf'),
    path('api/', include('apps.incidents.api_urls')),
    path('api/', include('core.urls')),
    path('quality/auth/', include('apps.accounts.urls')),
    path('quality/', include('apps.inspections.urls')),
    path('quality/products/', include('apps.products.urls')),
    path('quality/metrics/', include('apps.metrics.urls')),
    path('quality/api/', include(quality_api.urls)),
    path('quality/api/metrics/evaluate/', metrics_api_view, name='quality-api-metrics-evaluate'),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
