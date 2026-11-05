from rest_framework import permissions
from django.core.exceptions import PermissionDenied
from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages

class IsAdminRole(permissions.BasePermission):
    """Allows access only to Administrators."""
    message = "Only Administrators are authorized to perform this operation."

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_admin_role)


class IsSupervisorRole(permissions.BasePermission):
    """Allows access only to Inspection Supervisors (or Admins)."""
    message = "Only Supervisors are authorized to review or correct inspection results."

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_supervisor_role)


class IsEngineerRole(permissions.BasePermission):
    """Allows access only to Quality Engineers."""
    message = "Only Quality Engineers are authorized for this operation."

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and (request.user.is_engineer_role or request.user.is_admin_role))


class CanSubmitInspection(permissions.BasePermission):
    """Engineers and Admins can submit inspections."""
    message = "You do not have permission to submit inspections."

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)


def supervisor_required(view_func):
    """View decorator to enforce Supervisor role."""
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('accounts:login')
        if not request.user.is_supervisor_role:
            messages.error(request, "Permission denied: Only Supervisors can review or correct inspection results.")
            raise PermissionDenied("Only Supervisors are authorized to access this resource.")
        return view_func(request, *args, **kwargs)
    return _wrapped_view


def admin_required(view_func):
    """View decorator to enforce Administrator role."""
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('accounts:login')
        if not request.user.is_admin_role:
            messages.error(request, "Permission denied: Administrator role required.")
            raise PermissionDenied("Only Administrators can manage products and system configurations.")
        return view_func(request, *args, **kwargs)
    return _wrapped_view

