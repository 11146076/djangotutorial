"""使用者角色與授權分級。"""

from __future__ import annotations

ROLE_MEMBER = "member"
ROLE_EDITOR = "editor"
ROLE_MODERATOR = "moderator"
ROLE_ADMIN = "admin"

ROLE_CHOICES = (
    (ROLE_MEMBER, "一般會員"),
    (ROLE_EDITOR, "編輯"),
    (ROLE_MODERATOR, "版主"),
    (ROLE_ADMIN, "管理員"),
)

ROLE_LEVEL = {
    ROLE_MEMBER: 0,
    ROLE_EDITOR: 10,
    ROLE_MODERATOR: 20,
    ROLE_ADMIN: 30,
}


def role_level(role: str) -> int:
    return ROLE_LEVEL.get(role or ROLE_MEMBER, 0)


def user_has_role(user, minimum_role: str) -> bool:
    if not user or not getattr(user, "is_authenticated", False):
        return False
    if getattr(user, "is_superuser", False):
        return True
    return role_level(getattr(user, "role", ROLE_MEMBER)) >= role_level(minimum_role)
