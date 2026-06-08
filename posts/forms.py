import bleach
import re
from bleach.css_sanitizer import ALLOWED_CSS_PROPERTIES, CSSSanitizer
from django import forms
from django.conf import settings
from django.utils.html import strip_tags

from .models import Category, Post, Tag

_EXTRA_CSS = frozenset(
    {
        "max-width",
        "max-height",
        "min-width",
        "min-height",
        "margin",
        "margin-top",
        "margin-right",
        "margin-bottom",
        "margin-left",
        "padding",
        "padding-top",
        "padding-right",
        "padding-bottom",
        "padding-left",
        "border",
        "border-collapse",
        "border-spacing",
        "border-color",
        "border-width",
        "border-style",
        "border-top",
        "border-right",
        "border-bottom",
        "border-left",
        "box-sizing",
        "background",
        "background-image",
        "list-style",
        "list-style-type",
    }
)

_CSS_SANITIZER = CSSSanitizer(
    allowed_css_properties=ALLOWED_CSS_PROPERTIES | _EXTRA_CSS,
)

_MAX_GALLERY_FILES = 3
_MAX_IMAGE_BYTES = 5 * 1024 * 1024
_ALLOWED_IMAGE_TYPES = frozenset({"image/jpeg", "image/png", "image/gif", "image/webp"})

# Django 5+ CheckboxSelectMultiple 外層是 div>div>label（非 ul/li），樣式集中寫在 widget 外層 class。
_TAGS_CHECKBOX_OUTER_CLASS = (
    "flex flex-wrap gap-3 "
    "[&>div]:m-0 [&>div]:p-0 "
    "[&>div>label]:inline-flex [&>div>label]:max-w-full [&>div>label]:cursor-pointer [&>div>label]:items-center [&>div>label]:gap-2 "
    "[&>div>label]:rounded-full [&>div>label]:border [&>div>label]:border-slate-200 [&>div>label]:bg-white [&>div>label]:px-3 [&>div>label]:py-2 "
    "[&>div>label]:text-sm [&>div>label]:font-medium [&>div>label]:text-slate-700 [&>div>label]:shadow-sm [&>div>label]:transition-colors "
    "hover:[&>div>label]:border-sky-300 hover:[&>div>label]:bg-sky-50 "
    "[&>div>label:has(input:checked)]:border-sky-500 [&>div>label:has(input:checked)]:bg-sky-50 [&>div>label:has(input:checked)]:text-sky-800 "
    "[&_input]:h-4 [&_input]:w-4 [&_input]:shrink-0 [&_input]:rounded [&_input]:border-slate-300 [&_input]:accent-sky-500 "
    "[&_input]:focus:ring-2 [&_input]:focus:ring-sky-400 [&_input]:focus:ring-offset-0"
)


class MultiImageInput(forms.FileInput):
    """讓同一個欄位名稱可收到瀏覽器 multiple 上傳的多個檔案。"""

    allow_multiple_selected = True

    def value_from_datadict(self, data, files, name):
        if files is not None:
            return files.getlist(name)
        return []


class MultiImageField(forms.Field):
    """非 Model 欄位：整理成 UploadedFile 清單並做數量／型別檢查。"""

    widget = MultiImageInput

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("required", False)
        super().__init__(*args, **kwargs)

    def clean(self, data):
        if not data:
            return []
        files = [f for f in data if f and getattr(f, "name", "")]
        if len(files) > _MAX_GALLERY_FILES:
            raise forms.ValidationError(f"最多只能上傳 {_MAX_GALLERY_FILES} 張圖片。")
        for f in files:
            if f.size > _MAX_IMAGE_BYTES:
                raise forms.ValidationError("單張圖片請勿超過 5MB。")
            ct = (getattr(f, "content_type", "") or "").lower()
            if ct and ct not in _ALLOWED_IMAGE_TYPES:
                raise forms.ValidationError("只支援 JPEG、PNG、GIF、WebP 圖檔。")
        return files


class PostForm(forms.ModelForm):
    gallery = MultiImageField(
        label="貼文附圖（可選，按住 Ctrl / Shift 可一次選最多 3 張）",
        widget=MultiImageInput(
            attrs={
                "multiple": True,
                "accept": "image/*",
                "class": "block w-full cursor-pointer rounded-lg border border-slate-300 text-sm text-slate-600 file:mr-4 file:rounded-lg file:border-0 file:bg-slate-100 file:px-4 file:py-2 file:text-slate-700 hover:file:bg-slate-200",
            }
        ),
    )

    class Meta:
        model = Post
        fields = ("content",)

    def clean_content(self):
        value = self.cleaned_data.get("content") or ""
        text_only = strip_tags(value).replace("\xa0", " ").strip()
        if not text_only:
            raise forms.ValidationError("請輸入貼文內容。")
        return bleach.clean(
            value,
            tags=getattr(settings, "BLEACH_ALLOWED_TAGS", None),
            attributes=getattr(settings, "BLEACH_ALLOWED_ATTRIBUTES", None),
            protocols=getattr(settings, "BLEACH_ALLOWED_PROTOCOLS", None),
            css_sanitizer=_CSS_SANITIZER,
            strip=True,
        )

    def save(self, commit=True):
        post = super().save(commit=False)
        files = self.cleaned_data.get("gallery") or []
        if files:
            post.image = files[0]
            post.image2 = files[1] if len(files) > 1 else None
            post.image3 = files[2] if len(files) > 2 else None
            if len(files) < 2:
                post.image2 = None
            if len(files) < 3:
                post.image3 = None
        if commit:
            post.save()
        return post


class PostEditForm(PostForm):
    new_category = forms.CharField(
        required=False,
        label="新增分類",
        widget=forms.TextInput(
            attrs={
                "class": "min-h-11 w-full rounded-lg border border-slate-300 px-3 py-2 text-base outline-none ring-sky-200 focus:ring sm:text-sm",
                "placeholder": "想不到分類？直接輸入新增",
            }
        ),
    )
    new_tags = forms.CharField(
        required=False,
        label="新增標籤",
        widget=forms.TextInput(
            attrs={
                "class": "min-h-11 w-full rounded-lg border border-slate-300 px-3 py-2 text-base outline-none ring-sky-200 focus:ring sm:text-sm",
                "placeholder": "用逗號分隔，例如：辣, 便宜, Comfort Food",
            }
        ),
        help_text="可輸入多個，使用逗號分隔（可包含空白）",
    )

    class Meta:
        model = Post
        fields = ("title", "category", "visibility", "tags", "content")
        widgets = {
            "title": forms.TextInput(
                attrs={
                    "class": "min-h-11 w-full rounded-lg border border-slate-300 px-3 py-2 text-base outline-none ring-sky-200 focus:ring sm:text-sm",
                    "placeholder": "標題（可留空）",
                }
            ),
            "category": forms.Select(
                attrs={
                    "class": "min-h-11 w-full rounded-lg border border-slate-300 px-3 py-2 text-base outline-none ring-sky-200 focus:ring sm:text-sm",
                }
            ),
            "visibility": forms.Select(
                attrs={
                    "class": "min-h-11 w-full rounded-lg border border-slate-300 px-3 py-2 text-base outline-none ring-sky-200 focus:ring sm:text-sm",
                }
            ),
            "tags": forms.CheckboxSelectMultiple(attrs={"class": _TAGS_CHECKBOX_OUTER_CLASS}),
        }

    def clean_new_category(self):
        value = (self.cleaned_data.get("new_category") or "").strip()
        return value

    def clean_new_tags(self):
        value = (self.cleaned_data.get("new_tags") or "").strip()
        return value

    def _parse_new_tags(self, raw: str):
        # Split by comma and keep unique order; allow spaces inside tag names.
        parts = [p.strip() for p in raw.split(",") if p.strip()]
        seen = set()
        out = []
        for p in parts:
            key = p.lower()
            if key in seen:
                continue
            seen.add(key)
            out.append(p)
        return out

    def save(self, commit=True):
        post = super().save(commit=False)

        new_category = self.cleaned_data.get("new_category") or ""
        if new_category:
            category_obj, _ = Category.objects.get_or_create(name=new_category)
            post.category = category_obj

        if commit:
            post.save()
            self.save_m2m()

            new_tags_raw = self.cleaned_data.get("new_tags") or ""
            if new_tags_raw:
                tag_names = self._parse_new_tags(new_tags_raw)
                tag_objs = [Tag.objects.get_or_create(name=name)[0] for name in tag_names]
                post.tags.add(*tag_objs)

        return post


class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ("name",)
        widgets = {
            "name": forms.TextInput(
                attrs={
                    "class": "min-h-11 w-full rounded-lg border border-slate-300 px-3 py-2 text-base outline-none ring-sky-200 focus:ring sm:text-sm",
                    "placeholder": "例如：中式",
                }
            )
        }


class TagForm(forms.ModelForm):
    class Meta:
        model = Tag
        fields = ("name",)
        widgets = {
            "name": forms.TextInput(
                attrs={
                    "class": "min-h-11 w-full rounded-lg border border-slate-300 px-3 py-2 text-base outline-none ring-sky-200 focus:ring sm:text-sm",
                    "placeholder": "例如：健康",
                }
            )
        }
