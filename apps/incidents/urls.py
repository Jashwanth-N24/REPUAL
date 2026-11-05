from django.urls import path

from apps.incidents import views


app_name = 'incidents'
urlpatterns = [
    path('', views.incident_list_view, name='list'),
    path('create/<int:inspection_id>/', views.incident_create_view, name='create'),
    path('<uuid:incident_id>/', views.incident_detail_view, name='detail'),
    path('<uuid:incident_id>/review/', views.incident_review_view, name='review'),
]
