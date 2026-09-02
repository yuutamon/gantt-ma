from abc import ABC, abstractmethod
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime

from django.conf import settings
from django.db import IntegrityError, transaction
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from .models import UserModel


# ---------- エンティティ / 例外 ----------

@dataclass(frozen=True)
class User:
    id: int | None
    email: str
    name: str
    is_active: bool
    created_at: datetime | None = None


@dataclass(frozen=True)
class Page:
    items: list[User]
    total: int


class UserNotFoundError(Exception):
    pass


class DuplicateEmailError(Exception):
    pass


# ---------- 抽象 ----------

class UserRepository(ABC):
    @abstractmethod
    def get_by_id(self, user_id: int) -> User | None: ...

    @abstractmethod
    def find_by_email(self, email: str) -> User | None: ...

    @abstractmethod
    def list_active(self, limit: int, offset: int) -> Page: ...

    @abstractmethod
    def create(self, user: User) -> User: ...

    @abstractmethod
    def update(self, user: User) -> User: ...

    @abstractmethod
    def atomic(self): ...


# ---------- 実装1: Django ORM ----------

class DjangoUserRepository(UserRepository):

    @staticmethod
    def _to_entity(row: UserModel) -> User:
        return User(
            id=row.id, email=row.email, name=row.name,
            is_active=row.is_active, created_at=row.created_at,
        )

    def atomic(self):
        return transaction.atomic()

    def get_by_id(self, user_id):
        row = UserModel.objects.filter(pk=user_id).first()
        return self._to_entity(row) if row else None

    def find_by_email(self, email):
        row = UserModel.objects.filter(email=email).first()
        return self._to_entity(row) if row else None

    def list_active(self, limit, offset):
        qs = UserModel.objects.filter(is_active=True).order_by("id")
        rows = qs[offset:offset + limit]
        return Page(items=[self._to_entity(r) for r in rows], total=qs.count())

    def create(self, user):
        try:
            row = UserModel.objects.create(
                email=user.email, name=user.name, is_active=user.is_active,
            )
        except IntegrityError as e:
            raise DuplicateEmailError(user.email) from e
        return self._to_entity(row)

    def update(self, user):
        affected = UserModel.objects.filter(pk=user.id).update(
            name=user.name, is_active=user.is_active,
        )
        if affected == 0:
            raise UserNotFoundError(user.id)
        return user


# ---------- 実装2: 外部データベース ----------

_pool = ConnectionPool(settings.EXTERNAL_DB_DSN, min_size=1, max_size=10, open=True)
_COLUMNS = "id, email, name, is_active, created_at"


class ExternalUserRepository(UserRepository):

    def __init__(self, pool: ConnectionPool = _pool):
        self._pool = pool
        self._tx_conn = None          # atomic中はこの接続を使い回す

    @staticmethod
    def _to_entity(row: dict) -> User:
        return User(**row)

    @contextmanager
    def _connection(self):
        if self._tx_conn is not None:
            yield self._tx_conn        # トランザクション中はコミットせず借りるだけ
            return
        with self._pool.connection() as conn:
            yield conn

    @contextmanager
    def atomic(self):
        if self._tx_conn is not None:  # ネストしても外側の境界に委ねる
            yield
            return
        with self._pool.connection() as conn:
            with conn.transaction():
                self._tx_conn = conn
                try:
                    yield
                finally:
                    self._tx_conn = None

    def _fetch_one(self, sql, params) -> User | None:
        with self._connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(sql, params)
                row = cur.fetchone()
        return self._to_entity(row) if row else None

    def get_by_id(self, user_id):
        return self._fetch_one(f"SELECT {_COLUMNS} FROM users WHERE id = %s", (user_id,))

    def find_by_email(self, email):
        return self._fetch_one(f"SELECT {_COLUMNS} FROM users WHERE email = %s", (email,))

    def list_active(self, limit, offset):
        with self._connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    f"SELECT {_COLUMNS} FROM users WHERE is_active "
                    "ORDER BY id LIMIT %s OFFSET %s", (limit, offset),
                )
                items = [self._to_entity(r) for r in cur.fetchall()]
                cur.execute("SELECT count(*) AS c FROM users WHERE is_active")
                total = cur.fetchone()["c"]
        return Page(items=items, total=total)

    def create(self, user):
        try:
            with self._connection() as conn:
                with conn.cursor(row_factory=dict_row) as cur:
                    cur.execute(
                        f"INSERT INTO users (email, name, is_active) "
                        f"VALUES (%s, %s, %s) RETURNING {_COLUMNS}",
                        (user.email, user.name, user.is_active),
                    )
                    return self._to_entity(cur.fetchone())
        except UniqueViolation as e:
            raise DuplicateEmailError(user.email) from e

    def update(self, user):
        with self._connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE users SET name = %s, is_active = %s WHERE id = %s",
                    (user.name, user.is_active, user.id),
                )
                if cur.rowcount == 0:
                    raise UserNotFoundError(user.id)
        return user


# ---------- ファクトリ ----------

def get_user_repository() -> UserRepository:
    if getattr(settings, "USER_STORE", "orm") == "external":
        return ExternalUserRepository()
    return DjangoUserRepository()
