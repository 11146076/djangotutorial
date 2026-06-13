from django.urls import path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from .jwt_serializers import EatWhatTokenObtainPairSerializer

app_name = "accounts_api"


class EatWhatTokenObtainPairView(TokenObtainPairView):
    serializer_class = EatWhatTokenObtainPairSerializer


urlpatterns = [
    path("token/", EatWhatTokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
]
