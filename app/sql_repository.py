"""Registro de inspecciones en Postgres (ADR-016).

Guarda metadatos y el PNG original. El overlay y las capas no se guardan: el
pipeline es determinista y ``app/media.py`` las regenera cuando alguien las pide.

El payload completo viaja como ``jsonb`` y es la fuente de verdad del contrato;
las columnas tipadas se derivan de él al insertar para poder consultar, ordenar
y agrupar sin abrir el JSON.
"""

from __future__ import annotations

import hashlib
import json
import logging
from collections.abc import Iterable
from contextlib import closing, contextmanager
from datetime import datetime, timezone
from typing import Any

from app.db.connection import DatabaseUnavailable, connect
from app.store import ID_PATTERN, media_urls, record_id
from core.exceptions import InspectionNotFound
from core.pipeline import method_fingerprint
from core.version import __version__

logger = logging.getLogger("fellowship.sql")

# Las URLs no se guardan: se recalculan al leer, así cambiar el prefijo de media
# no obliga a migrar filas.
URL_KEYS = ("result_url", "original_url", "layer_urls")

# ``user_id`` se resuelve en la misma sentencia: si el dueño ya no existe —un
# registro importado o reenviado— la columna queda NULL en vez de romper el
# guardado, y el nombre sigue viajando en el payload (ADR-017).
INSERT = """
INSERT INTO inspections (
    id, created_at, method_version, app_version, user_id, image_sha256,
    filename, width, height, format, lesion_count, area_fraction,
    chlorosis_fraction, payload, original_png
) VALUES (
    %s, %s, %s, %s, (SELECT id FROM users WHERE id = %s), %s, %s, %s, %s, %s,
    %s, %s, %s, %s, %s
) ON CONFLICT (id) DO NOTHING
"""

# Una fila por versión publicada (ADR-017). La huella se actualiza por si la
# misma versión se recompiló con otro método: lo que manda es la última vista.
REGISTER_VERSION = """
INSERT INTO software_versions (version, method_version)
VALUES (%s, %s)
ON CONFLICT (version) DO UPDATE
SET last_seen = now(), method_version = EXCLUDED.method_version
"""

VERSIONS_SQL = """
SELECT v.version, v.method_version, v.notes, v.first_seen, v.last_seen,
       count(i.id) AS inspections
FROM software_versions v
LEFT JOIN inspections i ON i.app_version = v.version
GROUP BY v.version, v.method_version, v.notes, v.first_seen, v.last_seen
ORDER BY v.first_seen DESC
"""


def _versions(record: dict[str, Any]) -> tuple[str, str]:
    """Versión publicada y huella de método, con respaldo en la build actual."""
    version = str(record.get("app_version") or __version__)
    method = str(record.get("method_version") or method_fingerprint())
    return version, method



def _timestamp(record: dict[str, Any]) -> datetime:
    raw = record.get("created_at")
    if isinstance(raw, datetime):
        return raw
    if isinstance(raw, str) and raw:
        try:
            return datetime.fromisoformat(raw)
        except ValueError:
            pass
    return datetime.now(timezone.utc)


def _layer_keys(record: dict[str, Any]) -> list[str]:
    """Claves de capa en orden de ejecución, tal como las publica la traza."""
    trace = record.get("trace") or {}
    layers = trace.get("layers") or []
    return [
        str(layer["key"])
        for layer in layers
        if isinstance(layer, dict) and layer.get("key")
    ]


def _with_urls(record: dict[str, Any], media_prefix: str) -> dict[str, Any]:
    return {
        **record,
        **media_urls(str(record.get("id", "")), _layer_keys(record), media_prefix),
    }


def _columns(record: dict[str, Any], original_png: bytes) -> tuple[Any, ...]:
    """Deriva las columnas consultables del registro. Único punto de verdad."""
    image = record.get("image") or {}
    lesions = record.get("lesions") or {}
    chlorosis = record.get("chlorosis") or {}
    owner = record.get("owner") or {}
    version, method = _versions(record)
    payload = {key: value for key, value in record.items() if key not in URL_KEYS}
    return (
        record["id"],
        _timestamp(record),
        method,
        version,
        str(owner.get("id")) if owner.get("id") else None,
        hashlib.sha256(original_png).hexdigest(),
        str(image.get("filename", "")),
        int(image.get("width") or 0),
        int(image.get("height") or 0),
        str(image.get("format", "")),
        int(lesions.get("count") or 0),
        float(lesions.get("area_fraction") or 0.0),
        float(chlorosis.get("area_fraction") or 0.0),
        json.dumps(payload, ensure_ascii=False),
        original_png,
    )


class SqlInspectionRepository:
    """Implementación de :class:`app.store.InspectionStore` sobre Postgres."""

    def __init__(
        self,
        dsn: str,
        media_prefix: str = "/media",
        pool_size: int = 4,
        use_pool: bool = True,
    ) -> None:
        if not dsn:
            raise ValueError("SqlInspectionRepository necesita una cadena de conexión.")
        self.dsn = dsn
        self.media_prefix = media_prefix.rstrip("/")
        self._pool_size = pool_size
        self._use_pool = use_pool
        self._pool: Any = None

    # -- infraestructura -------------------------------------------------
    def _ensure_pool(self) -> Any:
        if self._pool is None:
            try:
                from psycopg.rows import dict_row
                from psycopg_pool import ConnectionPool
            except ModuleNotFoundError as exc:
                raise DatabaseUnavailable(
                    "Falta el pool de Postgres. Instalar con: pip install -e ."
                ) from exc
            self._pool = ConnectionPool(
                self.dsn,
                min_size=1,
                max_size=self._pool_size,
                kwargs={"row_factory": dict_row},
                open=True,
            )
        return self._pool

    @contextmanager
    def _session(self):
        """Sesión con transacción. En serverless se abre y cierra por request."""
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

    # -- contrato --------------------------------------------------------
    def save(
        self,
        original_png: bytes,
        result_png: bytes,
        payload: dict[str, Any],
        layers: Iterable[tuple[str, bytes]] = (),
    ) -> dict[str, Any]:
        """Inserta el registro.

        ``result_png`` y las capas se reciben por compatibilidad con el
        contrato pero se descartan: se regeneran desde el original.
        """
        identifier = record_id()
        keys = [key for key, _ in layers]
        record = {
            **payload,
            "id": identifier,
            **media_urls(identifier, keys, self.media_prefix),
        }
        with self._session() as connection:
            connection.execute(INSERT, _columns(record, original_png))
            version, method = _versions(record)
            connection.execute(REGISTER_VERSION, (version, method))
        return record

    def get(self, identifier: str) -> dict[str, Any]:
        self._validate_id(identifier)
        with self._session() as connection:
            row = connection.execute(
                "SELECT payload FROM inspections WHERE id = %s", (identifier,)
            ).fetchone()
        if row is None:
            raise InspectionNotFound(f"No existe la inspección {identifier}.")
        return _with_urls(row["payload"], self.media_prefix)

    def update(
        self,
        record: dict[str, Any],
        *,
        result_png: bytes | None = None,
        layers: Iterable[tuple[str, bytes]] | None = None,
    ) -> dict[str, Any]:
        """Actualiza las medidas consultables y el payload JSON en una transacción."""
        identifier = str(record.get("id", ""))
        self._validate_id(identifier)
        payload = {key: value for key, value in record.items() if key not in URL_KEYS}
        lesions = record.get("lesions") or {}
        chlorosis = record.get("chlorosis") or {}
        with self._session() as connection:
            updated = connection.execute(
                """UPDATE inspections
                   SET lesion_count = %s, area_fraction = %s, chlorosis_fraction = %s,
                       payload = %s::jsonb
                   WHERE id = %s""",
                (
                    int(lesions.get("count") or 0),
                    float(lesions.get("area_fraction") or 0.0),
                    float(chlorosis.get("area_fraction") or 0.0),
                    json.dumps(payload, ensure_ascii=False),
                    identifier,
                ),
            ).rowcount
        if not updated:
            raise InspectionNotFound(f"No existe la inspección {identifier}.")
        return _with_urls(payload, self.media_prefix)

    def list(
        self,
        limit: int | None = None,
        offset: int = 0,
        *,
        app_version: str | None = None,
        owner: str | None = None,
        unassigned: bool = False,
        since: datetime | None = None,
        until: datetime | None = None,
        query: str | None = None,
    ) -> list[dict[str, Any]]:
        """Historial con filtros (ADR-017). Todo por columnas, sin abrir el JSON."""
        conditions: list[str] = []
        params: list[Any] = []
        if app_version:
            conditions.append("app_version = %s")
            params.append(app_version)
        if owner:
            conditions.append("payload -> 'owner' ->> 'username' = %s")
            params.append(owner)
        if unassigned:
            # Sin fila de usuario detrás: nunca hubo dueño o su cuenta se dio de
            # baja (ON DELETE SET NULL, ADR-018). Usa el índice de user_id.
            conditions.append("user_id IS NULL")
        if since is not None:
            conditions.append("created_at >= %s")
            params.append(since)
        if until is not None:
            conditions.append("created_at < %s")
            params.append(until)
        if query:
            conditions.append("filename ILIKE %s")
            params.append(f"%{query}%")

        sql = "SELECT payload FROM inspections"
        if conditions:
            sql += " WHERE " + " AND ".join(conditions)
        sql += " ORDER BY created_at DESC"
        if limit is not None:
            sql += " LIMIT %s"
            params.append(limit)
        if offset:
            sql += " OFFSET %s"
            params.append(offset)
        with self._session() as connection:
            rows = connection.execute(sql, params).fetchall()
        return [_with_urls(row["payload"], self.media_prefix) for row in rows]

    def versions(self) -> list[dict[str, Any]]:
        with self._session() as connection:
            rows = connection.execute(VERSIONS_SQL).fetchall()
        return [
            {
                "version": row["version"],
                "method_version": row["method_version"],
                "notes": row["notes"],
                "inspections": int(row["inspections"]),
                "first_seen": row["first_seen"],
                "last_seen": row["last_seen"],
            }
            for row in rows
        ]

    def delete(self, identifier: str) -> None:
        self._validate_id(identifier)
        with self._session() as connection:
            deleted = connection.execute(
                "DELETE FROM inspections WHERE id = %s", (identifier,)
            ).rowcount
        if not deleted:
            raise InspectionNotFound(f"No existe la inspección {identifier}.")

    def clear(
        self,
        *,
        owner: str | None = None,
        unassigned: bool = False,
    ) -> int:
        """Borra todo, lo de un dueño o lo que quedó sin cuenta (ADR-018)."""
        sql = "DELETE FROM inspections"
        conditions: list[str] = []
        params: list[Any] = []
        if owner:
            conditions.append("payload -> 'owner' ->> 'username' = %s")
            params.append(owner)
        if unassigned:
            conditions.append("user_id IS NULL")
        if conditions:
            sql += " WHERE " + " AND ".join(conditions)
        with self._session() as connection:
            return connection.execute(sql, params).rowcount

    def original_bytes(self, identifier: str) -> bytes:
        self._validate_id(identifier)
        with self._session() as connection:
            row = connection.execute(
                "SELECT original_png FROM inspections WHERE id = %s", (identifier,)
            ).fetchone()
        if row is None:
            raise InspectionNotFound(f"No existe la inspección {identifier}.")
        return bytes(row["original_png"])

    def _validate_id(self, identifier: str) -> None:
        if not ID_PATTERN.fullmatch(identifier):
            raise InspectionNotFound(f"Identificador inválido: {identifier!r}.")
