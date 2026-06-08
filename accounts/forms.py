from django import forms
from django.contrib.auth import authenticate
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import (
    AuthenticationForm,
    UserCreationForm,
    UsernameField,
)

from .forms_security import AuthSecurityFieldsMixin
from .models import Profile

_SAAS_INPUT_CLASS = "saas-input min-h-11 w-full border px-3 py-2 text-base sm:text-sm"

User = get_user_model()


class RegisterForm(AuthSecurityFieldsMixin, UserCreationForm):
    email = forms.EmailField(required=True)

    class Meta:
        model = User
        fields = ("username", "email", "password1", "password2")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name in ("username", "email", "password1", "password2"):
            self.fields[name].widget.attrs.setdefault("class", _SAAS_INPUT_CLASS)
        self.fields["captcha"].widget.attrs.setdefault(
            "class", "saas-input min-h-11 w-36 border px-3 py-2 text-base sm:text-sm"
        )

    def clean_email(self):
        email = (self.cleaned_data.get("email") or "").strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("此 Email 已被註冊。")
        return email


class UsernameOrEmailAuthenticationForm(AuthSecurityFieldsMixin, AuthenticationForm):
    """
    必須使用 Django 的 UsernameField（NFKC Unicode 正規化），與註冊表單一致；
    若用一般 CharField，部分帳號會永遠無法登入。
    """

    username = UsernameField(
        label="帳號或 Email",
        widget=forms.TextInput(
            attrs={
                "autofocus": True,
                "autocomplete": "username",
                "class": _SAAS_INPUT_CLASS,
            },
        ),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["password"].widget.attrs.setdefault("class", _SAAS_INPUT_CLASS)
        self.fields["captcha"].widget.attrs.setdefault(
            "class", "saas-input min-h-11 w-36 border px-3 py-2 text-base sm:text-sm"
        )

    error_messages = {
        "invalid_login": "帳號/Email 或密碼錯誤，請再試一次。",
        "inactive": "此帳號已停用。",
    }

    def clean(self):
        identity = self.cleaned_data.get("username")
        password = self.cleaned_data.get("password")
        if identity is not None and password:
            username = identity
            if "@" in identity:
                matched_user = User.objects.filter(email__iexact=identity).first()
                if matched_user:
                    username = matched_user.username
            else:
                matched_user = User.objects.filter(username__iexact=identity).first()
                if matched_user:
                    username = matched_user.username
            self.user_cache = authenticate(
                self.request,
                username=username,
                password=password,
            )
            if self.user_cache is None:
                raise self.get_invalid_login_error()
            self.confirm_login_allowed(self.user_cache)
        return self.cleaned_data


class ProfileEditForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ("bio", "dietary_preference", "avatar")
