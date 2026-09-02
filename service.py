from dataclasses import replace

from .repository import (
    DuplicateEmailError, Page, User, UserNotFoundError,
    UserRepository, get_user_repository,
)


class UserService:

    def __init__(self, users: UserRepository | None = None):
        self._users = users or get_user_repository()

    def list_active(self, limit: int = 20, offset: int = 0) -> Page:
        return self._users.list_active(limit, offset)

    def get(self, user_id: int) -> User:
        user = self._users.get_by_id(user_id)
        if user is None:
            raise UserNotFoundError(user_id)
        return user

    def register(self, email: str, name: str) -> User:
        if self._users.find_by_email(email):
            raise DuplicateEmailError(email)

        with self._users.atomic():
            return self._users.create(
                User(id=None, email=email, name=name, is_active=True)
            )

    def deactivate(self, user_id: int) -> User:
        user = self.get(user_id)
        with self._users.atomic():
            return self._users.update(replace(user, is_active=False))
