from django.urls import path
from . import views

app_name = 'inspections'

urlpatterns = [
    path('', views.dashboard_view, name='dashboard'),
    path('inspect/single/', views.single_inspect_view, name='single_inspect'),
    path('inspect/batch/', views.batch_inspect_view, name='batch_inspect'),
    path('batches/<uuid:batch_id>/', views.batch_detail_view, name='batch_detail'),
    path('batches/<uuid:batch_id>/status/', views.batch_status_api, name='batch_status_api'),
    path('history/', views.inspection_history_view, name='history'),
    path('inspections/<int:pk>/', views.inspection_detail_view, name='detail'),
    path('inspections/<int:pk>/review/', views.supervisor_review_submit_view, name='review_submit'),
]

