from rest_framework.permissions import BasePermission, SAFE_METHODS


class IsAuthorOrReadOnly(BasePermission):
    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        if request.method in SAFE_METHODS:
            return True
        author = getattr(obj, "author", None)
        return author is not None and author_id_matches(author, request.user)


def author_id_matches(author, user) -> bool:
    if not user or not user.is_authenticated:
        return False
    author_id = getattr(author, "id", author)
    return author_id == user.id


class IsNotificationRecipient(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        return request.user.is_authenticated and obj.recipient_id == request.user.id


class IsStaffOrReadOnly(BasePermission):
    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        return bool(request.user and request.user.is_authenticated and request.user.is_staff)
