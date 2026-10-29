"""Conexión a Postgres. Único módulo que importa ``psycopg``.

El driver se importa dentro de las funciones a propósito: sin ``DATABASE_URL``
la aplicación funciona con el almacén de archivos y no necesita el paquete
instalado (ADR-016).
"""

from __future__ import annotations

import logging
from contextlib import closing
from pathlib import Path
from typing import Any

logger = logging.getLogger("fellowship.db")

MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"
CONNECT_TIMEOUT_SECONDS = 5
# Un ping de salud no puede colgar cinco segundos: si no contestó en dos, está
# caído para efectos de quien pregunta.
HEALTH_TIMEOUT_SECONDS = 2


class DatabaseUnavailable(RuntimeError):
    """Falta el driver o el servidor no responde."""


def connect(dsn: str, timeout: int = CONNECT_TIMEOUT_SECONDS) -> Any:
    """Conecta a Postgres y devuelve filas como diccionarios."""
    try:
        import psycopg
        from psycopg.rows import dict_row
    except ModuleNotFoundError as exc:
        raise DatabaseUnavailable(
            "Falta el driver de Postgres. Instalar con: pip install -e ."
        ) from exc
    return psycopg.connect(
        dsn,
        row_factory=dict_row,
        connect_timeout=timeout,
    )


def check(dsn: str, timeout: int = HEALTH_TIMEOUT_SECONDS) -> bool:
    """Ping corto. Lo usan ``/api/health`` y los tests para decidir si saltear."""
    try:
        with closing(connect(dsn, timeout=timeout)) as connection:
            connection.execute("SELECT 1").fetchone()
    except Exception as exc:  # cualquier falla significa lo mismo: no hay base
        logger.warning("Postgres no responde: %s", exc)
        return False
    return True
