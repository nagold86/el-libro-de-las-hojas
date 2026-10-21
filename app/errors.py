"""Mapeo declarativo de errores de dominio a HTTP.

Un solo lugar decide el status y el código. El router no conoce ninguno de los
dos y el core no sabe qué es un 422.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from core.exceptions import (
    InspectionNotFound,
    InvalidImage,
    LeafError,
    NotALeaf,
    UnusableImage,
    UploadTooLarge,
)

logger = logging.getLogger("fellowship.errors")

CORE_ERRORS: dict[type[LeafError], tuple[int, str]] = {
    InvalidImage: (400, "INVALID_FILE"),
    UploadTooLarge: (413, "FILE_TOO_LARGE"),
    UnusableImage: (422, "IMAGE_UNUSABLE"),
    NotALeaf: (422, "IMAGE_NOT_A_LEAF"),
    InspectionNotFound: (404, "INSPECTION_NOT_FOUND"),
    LeafError: (400, "LEAF_ERROR"),
}


def resolve(exc: LeafError) -> tuple[int, str]:
    for error_type in type(exc).__mro__:
        if error_type in CORE_ERRORS:
            return CORE_ERRORS[error_type]
    return 400, "LEAF_ERROR"


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(LeafError)
    async def handle_leaf_error(request: Request, exc: LeafError) -> JSONResponse:
        status_code, code = resolve(exc)
        logger.warning(
            "%s %s -> %s %s: %s",
            request.method,
            request.url.path,
            status_code,
            code,
            exc,
        )
        return JSONResponse(
            status_code=status_code,
            content={"detail": {"code": code, "message": str(exc)}},
        )
