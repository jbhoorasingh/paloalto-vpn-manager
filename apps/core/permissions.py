import functools
import json

from django.contrib.auth.mixins import UserPassesTestMixin
from django.http import JsonResponse


def role_required(*roles):
    """Decorator for function-based views that checks user roles (M2M)."""
    def decorator(view_func):
        @functools.wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                if request.content_type == "application/json":
                    return JsonResponse({"error": "Authentication required"}, status=401)
                from django.shortcuts import redirect
                from django.conf import settings
                return redirect(settings.LOGIN_URL)
            user_roles = request.user.role_values
            if not user_roles.intersection(set(roles)) and "admin" not in user_roles:
                if request.content_type == "application/json":
                    return JsonResponse({"error": "Permission denied"}, status=403)
                from django.core.exceptions import PermissionDenied
                raise PermissionDenied
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator


class RoleRequiredMixin(UserPassesTestMixin):
    """Mixin for class-based views that checks user roles (M2M)."""
    required_roles = ()

    def test_func(self):
        user = self.request.user
        if not user.is_authenticated:
            return False
        user_roles = user.role_values
        return bool(user_roles.intersection(set(self.required_roles))) or "admin" in user_roles
