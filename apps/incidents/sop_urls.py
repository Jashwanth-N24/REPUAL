from django.urls import path

from apps.incidents.views import sop_pdf_view


urlpatterns = [path('', sop_pdf_view, name='incident_sop_pdf')]
