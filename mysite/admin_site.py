from django.contrib import admin
from django.contrib.auth.admin import GroupAdmin
from django.contrib.auth.models import Group

from mysite.admin_dashboard import get_dashboard_stats


class EatWhatAdminSite(admin.AdminSite):
    site_header = "等等吃啥 管理後台"
    site_title = "等等吃啥 Admin"
    index_title = "儀表板"
    index_template = "admin/eatwhat_index.html"
    empty_value_display = "—"

    def index(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context["dashboard"] = get_dashboard_stats()
        return super().index(request, extra_context)


eatwhat_admin = EatWhatAdminSite(name="eatwhat")
eatwhat_admin.register(Group, GroupAdmin)
