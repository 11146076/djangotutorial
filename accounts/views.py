from django.contrib.auth import login
from django.contrib.auth import get_user_model
from django.contrib.auth.views import (
    LoginView as DjangoLoginView,
    LogoutView as DjangoLogoutView,
)
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render

from .forms import ProfileEditForm, RegisterForm, UsernameOrEmailAuthenticationForm
from .models import Profile

from posts.models import Follow, Post, PostComment

User = get_user_model()


class LoginView(DjangoLoginView):
    template_name = "accounts/login.html"
    authentication_form = UsernameOrEmailAuthenticationForm


class LogoutView(DjangoLogoutView):
    next_page = "accounts:login"


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


PROFILE_POSTS_PER_PAGE = 10
PROFILE_COMMENTS_PER_PAGE = 10


def _profile_header_context(request, username):
    user = get_object_or_404(User, username=username)
    profile, _ = Profile.objects.get_or_create(user=user)
    is_following = False
    if request.user.is_authenticated:
        is_following = Follow.objects.filter(follower=request.user, following=user).exists()
    follower_count = Follow.objects.filter(following=user).count()
    following_count = Follow.objects.filter(follower=user).count()
    return {
        "profile_user": user,
        "profile": profile,
        "is_following": is_following,
        "follower_count": follower_count,
        "following_count": following_count,
    }


def profile_detail(request, username):
    return redirect("accounts:profile_posts", username=username)


def profile_posts(request, username):
    base = _profile_header_context(request, username)
    post_qs = (
        Post.objects.filter(author=base["profile_user"])
        .select_related("author", "author__profile", "category")
        .prefetch_related("tags")
        .annotate(comment_count=Count("post_comments", distinct=True))
        .order_by("-created_at", "-id")
    )
    if request.user.id != base["profile_user"].id:
        post_qs = post_qs.filter(visibility=Post.VISIBILITY_PUBLIC)
    paginator = Paginator(post_qs, PROFILE_POSTS_PER_PAGE)
    page_obj = paginator.get_page(request.GET.get("page") or 1)

    return render(
        request,
        "accounts/profile_detail.html",
        {
            **base,
            "active_section": "posts",
            "page_obj": page_obj,
        },
    )


def profile_comments(request, username):
    base = _profile_header_context(request, username)
    comment_qs = (
        PostComment.objects.filter(author=base["profile_user"]).select_related("post").order_by("-created_at", "-id")
    )
    paginator = Paginator(comment_qs, PROFILE_COMMENTS_PER_PAGE)
    page_obj = paginator.get_page(request.GET.get("page") or 1)

    return render(
        request,
        "accounts/profile_detail.html",
        {
            **base,
            "active_section": "comments",
            "page_obj": page_obj,
        },
    )


@login_required(login_url="accounts:login")
def follow_toggle(request, username):
    if request.method != "POST":
        return redirect("accounts:profile_detail", username=username)
    target = get_object_or_404(User, username=username)
    if target == request.user:
        messages.error(request, "不能追蹤自己。")
        return redirect("accounts:profile_detail", username=target.username)

    relation = Follow.objects.filter(follower=request.user, following=target).first()
    if relation:
        relation.delete()
        messages.info(request, "已取消追蹤。")
    else:
        Follow.objects.get_or_create(follower=request.user, following=target)
        messages.success(request, "已追蹤。")
    next_url = request.POST.get("next", "").strip()
    if next_url:
        return redirect(next_url)
    return redirect("accounts:profile_detail", username=target.username)
