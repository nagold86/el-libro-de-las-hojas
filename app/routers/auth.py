"""Login, sesión y alta de usuarios (ADR-017).

Las rutas de datos se protegen en ``app/main.py``; este router es el único
público y el único que escribe la cookie.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from app.auth import COOKIE_NAME, AuthError, AuthService, User
from app.schemas import LoginIn, MeOut, PasswordChangeIn, UserCreateIn, UserOut
from app.security import auth_service, current_user, require_admin, require_user

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _service(request: Request) -> AuthService:
    service = auth_service(request)
    if service is None:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "SIN_AUTENTICACION",
                "message": "El login necesita base de datos: configurá DATABASE_URL.",
            },
        )
    return service


def _http(exc: AuthError) -> HTTPException:
    return HTTPException(
        status_code=exc.status_code,
        detail={"code": exc.code, "message": str(exc)},
    )


def _remember(response: Response, token: str, service: AuthService, request: Request) -> None:
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        max_age=service.signer.max_age_seconds,
        httponly=True,
        samesite="lax",
        # ``Secure`` según el esquema del pedido, no según el entorno: en Vercel
        # el proxy siempre llega por HTTPS, y en local (o en el TestClient) un
        # http:// descartaría la cookie y la sesión nunca arrancaría.
        secure=request.url.scheme == "https",
        path="/",
    )


@router.post("/login", response_model=UserOut, summary="Inicia sesión")
def login(payload: LoginIn, request: Request, response: Response) -> UserOut:
    service = _service(request)
    try:
        user, token = service.login(payload.username, payload.password)
    except AuthError as exc:
        raise _http(exc) from exc
    _remember(response, token, service, request)
    return UserOut.model_validate(user.as_dict())


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Cierra la sesión",
)
def logout(response: Response) -> None:
    response.delete_cookie(COOKIE_NAME, path="/")


@router.get("/me", response_model=MeOut, summary="Quién está en sesión")
def me(request: Request) -> MeOut:
    user = current_user(request)
    return MeOut(
        user=UserOut.model_validate(user.as_dict()) if user else None,
        auth_required=request.app.state.settings.auth_required,
    )


@router.post(
    "/password",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Cambia la contraseña propia",
)
def change_password(
    payload: PasswordChangeIn,
    request: Request,
    user: User = Depends(require_user),
) -> None:
    try:
        _service(request).change_password(user.id, payload.current, payload.new)
    except AuthError as exc:
        raise _http(exc) from exc


@router.get("/users", response_model=list[UserOut], summary="Lista los usuarios")
def list_users(request: Request, _admin: User = Depends(require_admin)) -> list[UserOut]:
    return [
        UserOut.model_validate(item.as_dict()) for item in _service(request).list_users()
    ]


@router.post(
    "/users",
    response_model=UserOut,
    status_code=status.HTTP_201_CREATED,
    summary="Da de alta un usuario",
    responses={409: {"description": "El usuario ya existe"}},
)
def create_user(
    payload: UserCreateIn,
    request: Request,
    _admin: User = Depends(require_admin),
) -> UserOut:
    try:
        user = _service(request).create_user(
            payload.username,
            payload.password,
            payload.display_name,
            payload.role,
        )
    except AuthError as exc:
        raise _http(exc) from exc
    return UserOut.model_validate(user.as_dict())


@router.delete(
    "/users/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Da de baja un usuario",
    responses={
        403: {"description": "Es tu propia cuenta"},
        404: {"description": "El usuario no existe"},
    },
)
def delete_user(
    user_id: str,
    request: Request,
    admin: User = Depends(require_admin),
) -> None:
    """Borra la cuenta: sus hojas quedan en el almanaque sin dueño (ADR-018)."""
    try:
        _service(request).delete_user(user_id, admin)
    except AuthError as exc:
        raise _http(exc) from exc
