"""Aplica las migraciones de ``app/db/migrations`` en orden alfabético.

Uso::

    python -m app.db.migrate

La cadena se lee de ``DATABASE_URL`` (``app/config.py`` es el único que toca el
entorno). Cada archivo corre en su propia transacción y queda anotado en
``schema_migrations``: si el cuarto falla, los tres anteriores siguen aplicados.
"""

from __future__ import annotations

import logging
import sys
from contextlib import closing

from app.config import Settings
from app.db.connection import MIGRATIONS_DIR, DatabaseUnavailable, connect

logger = logging.getLogger("fellowship.db.migrate")

SCHEMA_TABLE = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    version    text        PRIMARY KEY,
    applied_at timestamptz NOT NULL DEFAULT now()
)
"""


def apply_migrations(connection) -> list[str]:
    """Aplica lo que falte y devuelve las versiones aplicadas en esta corrida.

    El ``SELECT`` va dentro de la primera transacción a propósito: fuera de ella
    abriría una transacción implícita y cada bloque siguiente quedaría como
    *savepoint* que nadie confirma, así que cerrar la conexión revertía todo el
    esquema. Cada archivo se confirma solo, así una migración fallida no se
    lleva las anteriores.
    """
    with connection.transaction():
        connection.execute(SCHEMA_TABLE)
        applied = {
            row["version"]
            for row in connection.execute("SELECT version FROM schema_migrations").fetchall()
        }

    applied_now: list[str] = []
    for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
        version = path.stem
        if version in applied:
            continue
        with connection.transaction():
            connection.execute(path.read_text(encoding="utf-8"))
            connection.execute(
                "INSERT INTO schema_migrations (version) VALUES (%s)", (version,)
            )
        applied_now.append(version)
        logger.info("Migración aplicada: %s", version)
    return applied_now


def main(argv: list[str] | None = None) -> int:
    settings = Settings.from_env()
    if not settings.database_url:
        print(
            "Falta DATABASE_URL. Por ejemplo:\n"
            "  $env:DATABASE_URL='postgresql://fellowship:fellowship@127.0.0.1:5433/fellowship'"
        )
        return 2

    try:
        with closing(connect(settings.database_url)) as connection:
            applied = apply_migrations(connection)
    except DatabaseUnavailable as exc:
        print(str(exc))
        return 2
    except Exception as exc:  # pragma: no cover - depende del servidor
        print(f"No se pudo migrar: {exc}")
        return 1

    if applied:
        print("Migraciones aplicadas: " + ", ".join(applied))
    else:
        print("El esquema ya estaba al día.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
