from django.urls import path

from .views import AiChatAPIView

app_name = "posts_api"

urlpatterns = [
    path("ai-chat/", AiChatAPIView.as_view(), name="ai_chat"),
]
