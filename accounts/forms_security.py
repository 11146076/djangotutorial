"""登入／註冊共用的驗證欄位（圖片驗證碼 + 我不是機器人）。"""

from django import forms
from captcha.fields import CaptchaField


class AuthSecurityFieldsMixin(forms.Form):
    captcha = CaptchaField(
        label="圖片驗證碼",
        error_messages={"invalid": "驗證碼錯誤，請依圖片重新輸入。"},
    )
    not_robot = forms.BooleanField(
        label="我不是機器人",
        required=True,
        error_messages={"required": "請勾選「我不是機器人」。"},
        widget=forms.CheckboxInput(
            attrs={
                "class": "mt-1 h-4 w-4 shrink-0 rounded border-slate-300 text-brand-teal focus:ring-brand-mint",
            }
        ),
    )
