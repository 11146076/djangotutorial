from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from .models import Comment, Like, Post


@login_required(login_url=settings.LOGIN_URL)
def feed(request):
    posts = Post.objects.select_related("author").prefetch_related("likes", "comments").all()
    return render(request, "posts/feed.html", {"posts": posts})


def post_create(request):
    if not request.user.is_authenticated:
        return redirect(settings.LOGIN_URL)
    if request.method != "POST":
        return redirect("posts:feed")
    content = (request.POST.get("content") or "").strip()
    if not content:
        return redirect("posts:feed")
    Post.objects.create(author=request.user, content=content)
    return redirect("posts:feed")


def post_detail(request, pk):
    return HttpResponse(f"Post detail {pk} (to be implemented)")


@login_required(login_url=settings.LOGIN_URL)
def like_toggle(request, pk):
    post = get_object_or_404(Post, pk=pk)
    like = post.likes.filter(user=request.user).first()
    if like:
        like.delete()
    else:
        Like.objects.get_or_create(user=request.user, post=post)
    return redirect("posts:feed")


@login_required(login_url=settings.LOGIN_URL)
def comment_create(request, pk):
    post = get_object_or_404(Post, pk=pk)
    if request.method != "POST":
        return redirect("posts:feed")
    content = (request.POST.get("content") or "").strip()
    if content:
        Comment.objects.create(post=post, author=request.user, content=content)
    return redirect("posts:feed")

