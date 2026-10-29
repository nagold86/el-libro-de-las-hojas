"""Dependencias HTTP de seguridad: quién pide y qué puede (ADR-017, ADR-018).

Capa fina entre FastAPI y :class:`app.auth.AuthService`. Las rutas declaran
``Depends(require_user)`` y no saben nada de cookies ni de hashes. El alcance
por dueño también se decide acá: un operador solo ve lo suyo, el administrador
ve todo y la demo sin base no filtra nada.
"""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException, Request

from app.auth import AuthService, User, COOKIE_NAME

UNAUTHENTICATED = {"code": "NO_AUTENTICADO", "message": "Iniciá sesión para continuar."}
FORBIDDEN = {"code": "SIN_PERMISO", "message": "Esta acción requiere permisos de administrador."}


def auth_service(request: Request) -> AuthService | None:
    """Servicio de sesiones, o ``None`` si la app corre sin base (demo)."""
    return getattr(request.app.state, "auth", None)


def current_user(request: Request) -> User | None:
    """Usuario de la cookie, o ``None`` sin sesión válida (o sin login activo)."""
    service = auth_service(request)
    if service is None:
        return None
    return service.authenticate(request.cookies.get(COOKIE_NAME))


def require_user(request: Request) -> User:
    """Sesión obligatoria. Solo se registra como guard cuando hay base."""
    user = current_user(request)
    if user is None:
        raise HTTPException(status_code=401, detail=UNAUTHENTICATED)
    return user


def require_admin(request: Request) -> User:
    user = require_user(request)
    if not user.is_admin:
        raise HTTPException(status_code=403, detail=FORBIDDEN)
    return user


def owner_scope(user: User | None, requested: str | None = None) -> str | None:
    """Dueño por el que filtrar: ``None`` significa "todo el almanaque".

    El operador no elige: ve lo suyo aunque pida otro ``owner`` (ADR-018).
    """
    if user is None or user.is_admin:
        return requested
    return user.username


def can_see(record: dict[str, Any], user: User | None) -> bool:
    """¿Este usuario puede leer o borrar este registro?"""
    if user is None or user.is_admin:
        return True
    owner = record.get("owner") or {}
    return str(owner.get("username") or "") == user.username
