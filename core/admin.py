from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DefaultUserAdmin
from core.models import User, Machine, Manual, QuestionHistory


@admin.register(User)
class UserAdmin(DefaultUserAdmin):
    list_display = ('username', 'email', 'role', 'is_staff', 'is_superuser')
    list_filter = ('role', 'is_staff', 'is_superuser')
    fieldsets = DefaultUserAdmin.fieldsets + (
        ('Role Information', {'fields': ('role',)}),
    )


@admin.register(Machine)
class MachineAdmin(admin.ModelAdmin):
    list_display = ('machine_id', 'name', 'description')
    search_fields = ('machine_id', 'name')


@admin.register(Manual)
class ManualAdmin(admin.ModelAdmin):
    list_display = ('document_id', 'machine', 'title', 'revision', 'uploaded_at')
    list_filter = ('machine', 'revision')
    search_fields = ('document_id', 'title')


@admin.register(QuestionHistory)
class QuestionHistoryAdmin(admin.ModelAdmin):
    list_display = ('id', 'engineer', 'machine', 'status', 'confidence_score', 'security_flag', 'timestamp')
    list_filter = ('security_flag', 'status', 'machine', 'timestamp')
    search_fields = ('question', 'answer')
    readonly_fields = ('timestamp',)
