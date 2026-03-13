from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    # 之後會實作對應的 view
    path("register/", views.register, name="register"),
    path("login/", views.LoginView.as_view(), name="login"),
    path("logout/", views.LogoutView.as_view(), name="logout"),
    path("profile/edit/", views.profile_edit, name="profile_edit"),
    path("@<str:username>/", views.profile_detail, name="profile_detail"),
]

