from django.contrib.auth import login
from django.contrib.auth.models import User
from django.contrib.auth.views import (
    LoginView as DjangoLoginView,
    LogoutView as DjangoLogoutView,
)
from django.shortcuts import get_object_or_404, redirect, render

from .forms import ProfileEditForm, RegisterForm
from .models import Profile

from posts.models import Post


class LoginView(DjangoLoginView):
    template_name = "accounts/login.html"


class LogoutView(DjangoLogoutView):
    next_page = "posts:feed"


def register(request):
    if request.user.is_authenticated:
        return redirect("posts:feed")
    if request.method == "POST":
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            Profile.objects.get_or_create(user=user)
            login(request, user)
            return redirect("posts:feed")
    else:
        form = RegisterForm()
    return render(request, "accounts/register.html", {"form": form})


def profile_edit(request):
    if not request.user.is_authenticated:
        return redirect("accounts:login")
    profile, _ = Profile.objects.get_or_create(user=request.user)
    if request.method == "POST":
        form = ProfileEditForm(request.POST, request.FILES, instance=profile)
        if form.is_valid():
            form.save()
            return redirect("accounts:profile_detail", username=request.user.username)
    else:
        form = ProfileEditForm(instance=profile)
    return render(request, "accounts/profile_edit.html", {"form": form})


def profile_detail(request, username):
    user = get_object_or_404(User, username=username)
    profile, _ = Profile.objects.get_or_create(user=user)
    posts = Post.objects.filter(author=user).order_by("-created_at")[:20]
    return render(
        request,
        "accounts/profile_detail.html",
        {"profile_user": user, "profile": profile, "posts": posts},
    )
