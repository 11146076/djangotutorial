from django.urls import path

from . import views

app_name = "posts"

urlpatterns = [
    path("", views.feed, name="feed"),
    path("create/", views.post_create, name="post_create"),
    path("<int:pk>/", views.post_detail, name="post_detail"),
    path("<int:pk>/like-toggle/", views.like_toggle, name="like_toggle"),
    path("<int:pk>/comment/", views.comment_create, name="comment_create"),
]

