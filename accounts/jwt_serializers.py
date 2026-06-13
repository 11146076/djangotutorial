from __future__ import annotations

from rest_framework_simplejwt.serializers import TokenObtainPairSerializer


class EatWhatTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token["username"] = user.username
        token["role"] = getattr(user, "role", "member")
        return token

    def validate(self, attrs):
        data = super().validate(attrs)
        data["username"] = self.user.username
        data["role"] = getattr(self.user, "role", "member")
        return data
