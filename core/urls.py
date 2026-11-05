from django.urls import include, path
from rest_framework.routers import DefaultRouter

from core.views import (
    AssistantViewSet,
    MachineViewSet,
    ManualViewSet,
    QuestionHistoryViewSet,
    current_user_view,
    admin_overview_view,
    admin_update_user_role,
    admin_create_user,
    admin_delete_user,
    admin_toggle_ai_access,
)

router = DefaultRouter()
router.register(r'machines', MachineViewSet, basename='machine')
router.register(r'manuals', ManualViewSet, basename='manual')
router.register(r'assistant', AssistantViewSet, basename='assistant')
router.register(r'history', QuestionHistoryViewSet, basename='history')

urlpatterns = [
    path('current-user/', current_user_view, name='current-user'),
    path('admin-overview/', admin_overview_view, name='admin-overview'),
    path('admin-update-role/', admin_update_user_role, name='admin-update-role'),
    path('admin-create-user/', admin_create_user, name='admin-create-user'),
    path('admin-delete-user/', admin_delete_user, name='admin-delete-user'),
    path('admin-toggle-ai-access/', admin_toggle_ai_access, name='admin-toggle-ai-access'),
    path('', include(router.urls)),
]
