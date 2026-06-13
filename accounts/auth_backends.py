from __future__ import annotations

from django.contrib.auth.backends import ModelBackend

from accounts.models import ApiKey


class EmailUsernameModelBackend(ModelBackend):
    """Web 帳密登入（Django 預設 ModelBackend 擴充，保留 is_active 檢查）。"""


class ApiKeyBackend:
    """
    並存認證：HTTP Header `X-API-Key`。
    與 Session 帳密登入並行，供外部系統或腳本呼叫 API。
    """

    def authenticate(self, request, api_key=None, **kwargs):
        if not api_key:
            return None
        try:
            key_obj = (
                ApiKey.objects.select_related("user")
                .filter(key=api_key, is_active=True, user__is_active=True)
                .first()
            )
        except Exception:
            return None
        if not key_obj:
            return None
        key_obj.mark_used()
        user = key_obj.user
        user._api_key_role = key_obj.effective_role()  # noqa: SLF001
        return user

    def get_user(self, user_id):
        from django.contrib.auth import get_user_model

        User = get_user_model()
        try:
            return User.objects.get(pk=user_id, is_active=True)
        except User.DoesNotExist:
            return None
