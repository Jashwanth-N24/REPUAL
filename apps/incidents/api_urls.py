from django.urls import re_path

from apps.incidents.views import incident_api_collection, incident_api_detail, incident_api_review


urlpatterns = [
    re_path(r'^incidents/?$', incident_api_collection, name='incident-api-list-create'),
    re_path(r'^incidents/(?P<incident_id>[0-9a-fA-F-]{36})/?$', incident_api_detail, name='incident-api-detail'),
    re_path(r'^incidents/(?P<incident_id>[0-9a-fA-F-]{36})/review/?$', incident_api_review, name='incident-api-review'),
]
