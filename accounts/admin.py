from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.db.models import Count

from mysite.admin_site import eatwhat_admin

from .models import Profile, User


class ProfileInline(admin.StackedInline):
    model = Profile
    can_delete = False
    extra = 0
    fields = ("avatar", "bio", "dietary_preference")


class UserAdmin(DjangoUserAdmin):
    inlines = (ProfileInline,)
    list_display = ("username", "email", "role", "post_count", "is_staff", "is_active", "created_at")
    list_filter = ("role", "is_staff", "is_superuser", "is_active", "date_joined")
    search_fields = ("username", "email", "role")
    ordering = ("-created_at",)
    list_select_related = ("profile",)
    show_full_result_count = False

    fieldsets = DjangoUserAdmin.fieldsets + (
        ("等等吃啥", {"fields": ("role", "created_at")}),
    )
    readonly_fields = ("created_at",)
    add_fieldsets = DjangoUserAdmin.add_fieldsets

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(_post_count=Count("posts", distinct=True))

    @admin.display(description="貼文數", ordering="_post_count")
    def post_count(self, obj):
        return obj._post_count


class ProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "dietary_preference", "has_avatar")
    search_fields = ("user__username", "user__email", "dietary_preference", "bio")
    autocomplete_fields = ("user",)
    list_select_related = ("user",)

    @admin.display(description="有大頭貼", boolean=True)
    def has_avatar(self, obj):
        return bool(obj.avatar)


eatwhat_admin.register(User, UserAdmin)
eatwhat_admin.register(Profile, ProfileAdmin)
