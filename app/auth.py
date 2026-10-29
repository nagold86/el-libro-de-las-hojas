"""Autenticación de operadores: contraseñas, sesiones firmadas y permisos.

El login vive en la base (ADR-017): sin ``DATABASE_URL`` no hay usuarios y la
aplicación queda abierta, que es el modo demo del almacén de archivos.

- Contraseñas: ``scrypt`` de la biblioteca estándar, con sal por usuario. El
  formato guardado es ``scrypt$n$r$p$sal$hash``, así que subir el costo más
  adelante no invalida las claves viejas.
- Sesiones: cookie firmada con HMAC-SHA256. No hay tabla de sesiones, así que
  cada acceso no escribe nada y el esquema no crece con el tráfico.
- El único módulo de ``app`` que conoce ``users``; el resto pide un ``User``.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import secrets
import time
from collections.abc import Iterator
from contextlib import closing, contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import lru_cache
from typing import Any
from uuid import uuid4

from app.db.connection import connect

logger = logging.getLogger("fellowship.auth")

COOKIE_NAME = "fellowship_session"
HASH_PREFIX = "scrypt"
SCRYPT_N = 2**14
SCRYPT_R = 8
SCRYPT_P = 1
SALT_BYTES = 16
KEY_BYTES = 32
MIN_PASSWORD_LENGTH = 8
MAX_PASSWORD_LENGTH = 256
DEFAULT_SESSION_HOURS = 12
ROLES = ("admin", "operador")

USERS_COLUMNS = "id, username, display_name, role, is_active, created_at, last_login_at"

SELECT_BY_USERNAME = f"SELECT {USERS_COLUMNS}, password_hash FROM users WHERE username = %s"
SELECT_BY_ID = f"SELECT {USERS_COLUMNS} FROM users WHERE id = %s"
SELECT_ALL = f"SELECT {USERS_COLUMNS} FROM users ORDER BY created_at"
INSERT_USER = """
INSERT INTO users (id, username, display_name, password_hash, role)
VALUES (%s, %s, %s, %s, %s)
RETURNING id, username, display_name, role, is_active, created_at, last_login_at
"""


class AuthError(Exception):
    """Falla de autenticación con su traducción HTTP pegada."""

    status_code = 401
    code = "NO_AUTENTICADO"

    def __init__(self, message: str) -> None:
        super().__init__(message)


class InvalidCredentials(AuthError):
    status_code = 401
    code = "CREDENCIALES_INVALIDAS"


class InactiveUser(AuthError):
    status_code = 403
    code = "USUARIO_INACTIVO"


class NotAllowed(AuthError):
    status_code = 403
    code = "SIN_PERMISO"


class DuplicateUser(AuthError):
    status_code = 409
    code = "USUARIO_EXISTENTE"


class WeakPassword(AuthError):
    status_code = 422
    code = "CLAVE_INVALIDA"


class InvalidUsername(AuthError):
    status_code = 422
    code = "USUARIO_INVALIDO"


class UserNotFound(AuthError):
    status_code = 404
    code = "USUARIO_NO_ENCONTRADO"


@dataclass(frozen=True)
class User:
    """Operador con sesión. Nunca lleva el hash: eso queda en la base."""

    id: str
    username: str
    display_name: str
    role: str = "operador"
    is_active: bool = True
    created_at: datetime | None = None
    last_login_at: datetime | None = None

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "username": self.username,
            "display_name": self.display_name,
            "role": self.role,
            "is_active": self.is_active,
            "created_at": self.created_at,
            "last_login_at": self.last_login_at,
        }

    def as_owner(self) -> dict[str, Any]:
        """Lo que viaja dentro del payload de una inspección."""
        return {
            "id": self.id,
            "username": self.username,
            "display_name": self.display_name,
        }


# -- contraseñas ---------------------------------------------------------


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _unb64(text: str) -> bytes:
    padded = text + "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode(padded.encode("ascii"))


def validate_password(password: str) -> None:
    if len(password) < MIN_PASSWORD_LENGTH:
        raise WeakPassword(
            f"La contraseña necesita al menos {MIN_PASSWORD_LENGTH} caracteres."
        )
    if len(password) > MAX_PASSWORD_LENGTH:
        raise WeakPassword(f"La contraseña no puede superar {MAX_PASSWORD_LENGTH} caracteres.")


def hash_password(password: str) -> str:
    """Deriva ``scrypt`` con sal nueva. El costo queda escrito en el hash."""
    validate_password(password)
    salt = secrets.token_bytes(SALT_BYTES)
    digest = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=SCRYPT_N,
        r=SCRYPT_R,
        p=SCRYPT_P,
        dklen=KEY_BYTES,
    )
    return f"{HASH_PREFIX}${SCRYPT_N}${SCRYPT_R}${SCRYPT_P}${_b64(salt)}${_b64(digest)}"


def verify_password(password: str, stored: str) -> bool:
    """Compara en tiempo constante contra un hash guardado."""
    try:
        prefix, raw_n, raw_r, raw_p, raw_salt, raw_key = stored.split("$")
        if prefix != HASH_PREFIX:
            return False
        salt = _unb64(raw_salt)
        expected = _unb64(raw_key)
        digest = hashlib.scrypt(
            password.encode("utf-8"),
            salt=salt,
            n=int(raw_n),
            r=int(raw_r),
            p=int(raw_p),
            dklen=len(expected),
        )
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(digest, expected)


@lru_cache(maxsize=1)
def _dummy_hash() -> str:
    """Hash descartable: un usuario inexistente cuesta lo mismo que uno real."""
    return hash_password("contrasena-que-nadie-usa")


# -- sesiones ------------------------------------------------------------


class SessionSigner:
    """Cookie firmada: ``payload.firma``, ambos en base64url."""

    def __init__(self, secret: str, hours: int = DEFAULT_SESSION_HOURS) -> None:
        if not secret:
            # Sin secreto las sesiones se caen en cada reinicio del proceso: es
            # preferible a aceptar cookies firmadas con una clave conocida.
            logger.warning(
                "FELLOWSHIP_SECRET_KEY vacía: se genera una por proceso y las "
                "sesiones no sobreviven al reinicio."
            )
            secret = secrets.token_urlsafe(32)
        self._secret = secret.encode("utf-8")
        self.hours = max(1, int(hours))

    @property
    def max_age_seconds(self) -> int:
        return self.hours * 3600

    def _sign(self, payload: bytes) -> str:
        return _b64(hmac.new(self._secret, payload, hashlib.sha256).digest())

    def issue(self, user_id: str) -> str:
        body = {"sub": user_id, "exp": int(time.time()) + self.max_age_seconds}
        payload = _b64(json.dumps(body, separators=(",", ":")).encode("utf-8"))
        return f"{payload}.{self._sign(payload.encode('ascii'))}"

    def verify(self, token: str | None) -> str | None:
        """Devuelve el ``sub`` si la firma y la expiración son válidas."""
        if not token or "." not in token:
            return None
        payload, signature = token.rsplit(".", 1)
        if not hmac.compare_digest(self._sign(payload.encode("ascii")), signature):
            return None
        try:
            body = json.loads(_unb64(payload))
        except (ValueError, json.JSONDecodeError):
            return None
        subject = body.get("sub")
        expires = body.get("exp")
        if not isinstance(subject, str) or not isinstance(expires, int):
            return None
        if expires < int(time.time()):
            return None
        return subject


# -- servicio ------------------------------------------------------------


def _row_to_user(row: dict[str, Any]) -> User:
    return User(
        id=str(row["id"]),
        username=str(row["username"]),
        display_name=str(row["display_name"]),
        role=str(row["role"]),
        is_active=bool(row["is_active"]),
        created_at=row.get("created_at"),
        last_login_at=row.get("last_login_at"),
    )


class AuthService:
    """Usuarios en Postgres y sesiones firmadas en memoria del proceso."""

    def __init__(
        self,
        dsn: str,
        secret: str,
        hours: int = DEFAULT_SESSION_HOURS,
        use_pool: bool = True,
        pool_size: int = 4,
    ) -> None:
        if not dsn:
            raise ValueError("AuthService necesita una cadena de conexión.")
        self.dsn = dsn
        self.signer = SessionSigner(secret, hours)
        self._use_pool = use_pool
        self._pool_size = pool_size
        self._pool: Any = None

    # -- infraestructura -------------------------------------------------
    def _ensure_pool(self) -> Any:
        if self._pool is None:
            from psycopg.rows import dict_row
            from psycopg_pool import ConnectionPool

            self._pool = ConnectionPool(
                self.dsn,
                min_size=1,
                max_size=self._pool_size,
                kwargs={"row_factory": dict_row},
                open=True,
            )
        return self._pool

    @contextmanager
    def _session(self) -> Iterator[Any]:
        if self._use_pool:
            with self._ensure_pool().connection() as connection:
                yield connection
        else:
            with closing(connect(self.dsn)) as connection, connection:
                yield connection

    def close(self) -> None:
        if self._pool is not None:
            self._pool.close()
            self._pool = None

    # -- contraseñas y sesiones -------------------------------------------
    def login(self, username: str, password: str) -> tuple[User, str]:
        """Verifica la clave, marca el acceso y devuelve ``(usuario, cookie)``."""
        normalized = username.strip().lower()
        if not normalized or not password:
            raise InvalidCredentials("Usuario o contraseña incorrectos.")

        with self._session() as connection:
            row = connection.execute(SELECT_BY_USERNAME, (normalized,)).fetchone()
            if row is None:
                # Mismo costo que un usuario real, para no delatar cuál existe.
                verify_password(password, _dummy_hash())
                raise InvalidCredentials("Usuario o contraseña incorrectos.")
            if not verify_password(password, str(row["password_hash"])):
                raise InvalidCredentials("Usuario o contraseña incorrectos.")

            user = _row_to_user(row)
            if not user.is_active:
                raise InactiveUser("El usuario está desactivado.")
            updated = connection.execute(
                f"UPDATE users SET last_login_at = now() WHERE id = %s RETURNING {USERS_COLUMNS}",
                (user.id,),
            ).fetchone()

        user = _row_to_user(updated or row)
        logger.info("Acceso de %s", user.username)
        return user, self.signer.issue(user.id)

    def authenticate(self, token: str | None) -> User | None:
        """Usuario dueño de la cookie, o ``None`` si no hay sesión válida."""
        user_id = self.signer.verify(token)
        if user_id is None:
            return None
        with self._session() as connection:
            row = connection.execute(SELECT_BY_ID, (user_id,)).fetchone()
        if row is None:
            return None
        user = _row_to_user(row)
        return user if user.is_active else None

    # -- usuarios --------------------------------------------------------
    def list_users(self) -> list[User]:
        with self._session() as connection:
            rows = connection.execute(SELECT_ALL).fetchall()
        return [_row_to_user(row) for row in rows]

    def count_users(self) -> int:
        with self._session() as connection:
            row = connection.execute("SELECT count(*) AS total FROM users").fetchone()
        return int(row["total"] if row else 0)

    def create_user(
        self,
        username: str,
        password: str,
        display_name: str = "",
        role: str = "operador",
    ) -> User:
        normalized = self._normalize_username(username)
        if role not in ROLES:
            raise NotAllowed(f"Rol desconocido: {role!r}.")
        password_hash = hash_password(password)
        try:
            with self._session() as connection:
                row = connection.execute(
                    INSERT_USER,
                    (
                        uuid4().hex,
                        normalized,
                        (display_name or normalized).strip(),
                        password_hash,
                        role,
                    ),
                ).fetchone()
        except Exception as exc:  # psycopg.errors.UniqueViolation sin importar el driver
            if "users_username_key" in str(exc) or "duplicate key" in str(exc):
                raise DuplicateUser(f"Ya existe el usuario {normalized!r}.") from exc
            raise
        logger.info("Usuario creado: %s (%s)", normalized, role)
        return _row_to_user(row)

    def delete_user(self, user_id: str, actor: User) -> None:
        """Da de baja una cuenta. Sus hojas quedan sin dueño (ADR-018).

        Nadie puede borrarse a sí mismo: así siempre queda un administrador vivo
        y no hay forma de dejar la aplicación cerrada sin puerta.
        """
        if actor.id == user_id:
            raise NotAllowed("No podés eliminar tu propia cuenta.")
        with self._session() as connection:
            removed = connection.execute(
                "DELETE FROM users WHERE id = %s", (user_id,)
            ).rowcount
        if not removed:
            raise UserNotFound(f"No existe el usuario {user_id}.")
        # La sesión del dado de baja muere sola: ``authenticate`` busca la fila
        # en cada pedido y ya no está.
        logger.info("Usuario eliminado: %s (por %s)", user_id, actor.username)

    def change_password(self, user_id: str, current: str, new: str) -> None:
        with self._session() as connection:
            row = connection.execute(
                "SELECT password_hash FROM users WHERE id = %s", (user_id,)
            ).fetchone()
            if row is None:
                raise InvalidCredentials("El usuario ya no existe.")
            if not verify_password(current, str(row["password_hash"])):
                raise InvalidCredentials("La contraseña actual no coincide.")
            connection.execute(
                "UPDATE users SET password_hash = %s WHERE id = %s",
                (hash_password(new), user_id),
            )

    def bootstrap_admin(self, username: str, password: str) -> User | None:
        """Crea el primer administrador si la tabla está vacía. Idempotente."""
        if not username or not password:
            return None
        if self.count_users() > 0:
            return None
        user = self.create_user(username, password, username, role="admin")
        logger.info("Administrador inicial creado: %s", user.username)
        return user

    @staticmethod
    def _normalize_username(username: str) -> str:
        normalized = (username or "").strip().lower()
        if not 3 <= len(normalized) <= 32:
            raise InvalidUsername("El usuario debe tener entre 3 y 32 caracteres.")
        if not all(character.isalnum() or character in "._-" for character in normalized):
            raise InvalidUsername("El usuario solo admite letras, números, punto, guion y guion bajo.")
        return normalized


def now_utc() -> datetime:
    """Marca de tiempo con zona, para payloads y pruebas."""
    return datetime.now(timezone.utc)
