from __future__ import annotations

from django.contrib.auth import authenticate
from django.utils.functional import SimpleLazyObject


class ApiKeyAuthMiddleware:
    """若 Session 未登入，嘗試以 X-API-Key 認證（並存於帳密登入）。"""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if hasattr(request, "user") and not request.user.is_authenticated:
            api_key = request.headers.get("X-API-Key") or request.META.get("HTTP_X_API_KEY", "")
            api_key = (api_key or "").strip()
            if api_key:
                user = authenticate(request, api_key=api_key)
                if user:
                    request.user = user
                    request._api_key_authenticated = True
        return self.get_response(request)
