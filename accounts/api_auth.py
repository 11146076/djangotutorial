from __future__ import annotations

from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed

from accounts.auth_backends import ApiKeyBackend
from accounts.permissions import get_effective_role


class ApiKeyAuthentication(BaseAuthentication):
    """DRF：X-API-Key 並存認證。"""

    keyword = "X-API-Key"

    def authenticate(self, request):
        api_key = request.headers.get(self.keyword) or request.META.get("HTTP_X_API_KEY", "")
        api_key = (api_key or "").strip()
        if not api_key:
            return None
        user = ApiKeyBackend().authenticate(request, api_key=api_key)
        if not user:
            raise AuthenticationFailed("Invalid API key.")
        return (user, None)


class MinimumRolePermission:
    """DRF permission：依 effective role 檢查最低角色。"""

    minimum_role = "member"

    def has_permission(self, request, view):
        from accounts.permissions import check_role

        minimum = getattr(view, "minimum_role", self.minimum_role)
        return check_role(request.user, minimum)
