from __future__ import annotations

from functools import wraps

from django.contrib import messages
from django.shortcuts import redirect

from accounts.roles import role_level, user_has_role


def get_effective_role(user) -> str:
    if not user or not user.is_authenticated:
        return ""
    return getattr(user, "_api_key_role", None) or getattr(user, "role", "")


class _RoleProxy:
    def __init__(self, user):
        self.is_authenticated = True
        self.is_superuser = getattr(user, "is_superuser", False)
        self.role = get_effective_role(user)


def check_role(user, minimum_role: str) -> bool:
    if not user or not user.is_authenticated:
        return False
    return user_has_role(_RoleProxy(user), minimum_role)


def role_required(minimum_role: str, *, redirect_to: str = "posts:feed"):
    """View decorator：要求使用者角色達指定等級。"""

    def decorator(view_func):
        @wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect("accounts:login")
            if not check_role(request.user, minimum_role):
                messages.error(request, "權限不足，無法執行此操作。")
                return redirect(redirect_to)
            return view_func(request, *args, **kwargs)

        return _wrapped

    return decorator
