"""Persistencia de inspecciones en disco, detrás de una interfaz mínima.

Frodo gobierna este módulo. Es la implementación de archivos de
``app.store.InspectionStore``: se usa cuando no hay ``DATABASE_URL`` (ADR-016).
El JSON es el punto de commit: si existe, el resultado y el original también.
Toda escritura es atómica (``*.tmp`` + ``os.replace``) y los identificadores se
validan antes de tocar el sistema de archivos.
"""

from __future__ import annotations

import json
import logging
import os
from collections.abc import Iterable
from datetime import datetime
from pathlib import Path
from typing import Any

from app.store import ID_PATTERN, LAYER_SUFFIX, media_urls, record_id
from app.versions import summarize_records, timestamp_of
from core.exceptions import InspectionNotFound
from core.layers import LAYER_KEY_PATTERN

logger = logging.getLogger("fellowship.repository")


class InspectionRepository:
    def __init__(self, root: Path, media_prefix: str = "/media") -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.media_prefix = media_prefix.rstrip("/")

    def save(
        self,
        original_png: bytes,
        result_png: bytes,
        payload: dict[str, Any],
        layers: Iterable[tuple[str, bytes]] = (),
    ) -> dict[str, Any]:
        """Guarda original, resultado, capas y metadatos. Devuelve el registro.

        Las capas se escriben como PNG sueltos y el registro solo publica su URL:
        el JSON sigue siendo el punto de commit.
        """
        identifier = record_id()
        keys: list[str] = []
        for key, png in layers:
            if not LAYER_KEY_PATTERN.fullmatch(key):
                raise ValueError(f"Clave de capa inválida: {key!r}.")
            self._atomic_write(self._path(identifier, LAYER_SUFFIX.format(key=key)), png)
            keys.append(key)

        record = {
            **payload,
            "id": identifier,
            **media_urls(identifier, keys, self.media_prefix),
        }

        self._atomic_write(self._path(identifier, "-original.png"), original_png)
        self._atomic_write(self._path(identifier, "-result.png"), result_png)
        self._atomic_write(
            self._path(identifier, ".json"),
            json.dumps(record, ensure_ascii=False, indent=2).encode("utf-8"),
        )
        return record

    def get(self, record_id: str) -> dict[str, Any]:
        self._validate_id(record_id)
        path = self._path(record_id, ".json")
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise InspectionNotFound(f"No existe la inspección {record_id}.") from exc
        except (OSError, json.JSONDecodeError) as exc:
            raise InspectionNotFound(f"La inspección {record_id} no se puede leer.") from exc

    def update(
        self,
        record: dict[str, Any],
        *,
        result_png: bytes | None = None,
        layers: Iterable[tuple[str, bytes]] | None = None,
    ) -> dict[str, Any]:
        """Reemplaza medidas y artefactos, con el JSON como punto de commit."""
        identifier = str(record.get("id", ""))
        self._validate_id(identifier)
        path = self._path(identifier, ".json")
        if not path.is_file():
            raise InspectionNotFound(f"No existe la inspección {identifier}.")
        previous_keys = set((record.get("layer_urls") or {}).keys())
        if result_png is not None:
            self._atomic_write(self._path(identifier, "-result.png"), result_png)
        if layers is not None:
            keys: list[str] = []
            for key, png in layers:
                if not LAYER_KEY_PATTERN.fullmatch(key):
                    raise ValueError(f"Clave de capa inválida: {key!r}.")
                self._atomic_write(self._path(identifier, LAYER_SUFFIX.format(key=key)), png)
                keys.append(key)
            record = {**record, **media_urls(identifier, keys, self.media_prefix)}
        self._atomic_write(
            path,
            json.dumps(record, ensure_ascii=False, indent=2).encode("utf-8"),
        )
        if layers is not None:
            for key in previous_keys - set(keys):
                self._path(identifier, LAYER_SUFFIX.format(key=key)).unlink(missing_ok=True)
        return self.get(identifier)

    def original_bytes(self, record_id: str) -> bytes:
        """Original guardado, para servir la ruta de media sin exponer el disco."""
        self._validate_id(record_id)
        path = self._path(record_id, "-original.png")
        try:
            return path.read_bytes()
        except FileNotFoundError as exc:
            raise InspectionNotFound(f"No existe la inspección {record_id}.") from exc
        except OSError as exc:
            raise InspectionNotFound(
                f"El original de la inspección {record_id} no se puede leer."
            ) from exc

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
        """Historial con los mismos filtros que la base (ADR-017, ADR-018)."""
        needle = (query or "").strip().lower()
        records: list[dict[str, Any]] = []
        for path in sorted(self.root.glob("*.json")):
            try:
                record = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                logger.warning("Registro ilegible, se omite: %s", path, exc_info=True)
                continue
            if not isinstance(record, dict):
                continue
            if not self._matches(
                record, app_version, owner, unassigned, since, until, needle
            ):
                continue
            records.append(record)
        records.sort(key=lambda item: str(item.get("created_at", "")), reverse=True)
        # El recorte se hace después de ordenar: la página es la misma que
        # devolvería la base con LIMIT/OFFSET.
        if offset:
            records = records[offset:]
        if limit is not None:
            records = records[:limit]
        return records

    def versions(self) -> list[dict[str, Any]]:
        """Sin tabla de versiones: se agrega desde los propios registros."""
        return summarize_records(self.list())

    @staticmethod
    def _matches(
        record: dict[str, Any],
        app_version: str | None,
        owner: str | None,
        unassigned: bool,
        since: datetime | None,
        until: datetime | None,
        needle: str,
    ) -> bool:
        if app_version and str(record.get("app_version") or "") != app_version:
            return False
        # Sin cuentas no hay dueño: la hoja sin ``owner`` es la que no tiene
        # cuenta detrás (ADR-018).
        if unassigned and record.get("owner"):
            return False
        if owner:
            who = record.get("owner") or {}
            if str(who.get("username") or "") != owner:
                return False
        stamp = timestamp_of(record.get("created_at"))
        if since is not None and stamp < since:
            return False
        if until is not None and stamp >= until:
            return False
        if needle:
            image = record.get("image") or {}
            if needle not in str(image.get("filename") or "").lower():
                return False
        return True

    def delete(self, record_id: str) -> None:
        self.get(record_id)
        self._purge(record_id)

    def clear(
        self,
        *,
        owner: str | None = None,
        unassigned: bool = False,
    ) -> int:
        """Elimina todos los registros, los de un dueño o los sin dueño.

        Devuelve cuántos borró. Sin filtros vacía el almanaque (ADR-018).
        """
        removed = 0
        for path in sorted(self.root.glob("*.json")):
            record_id = path.stem
            if not ID_PATTERN.fullmatch(record_id):
                continue
            if (owner or unassigned) and not self._selected(path, owner, unassigned):
                continue
            self._purge(record_id)
            removed += 1
        return removed

    @staticmethod
    def _selected(path: Path, owner: str | None, unassigned: bool) -> bool:
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return False
        if not isinstance(record, dict):
            return False
        who = record.get("owner") or {}
        if unassigned and who:
            return False
        if owner and str(who.get("username") or "") != owner:
            return False
        return True

    def _purge(self, record_id: str) -> None:
        """Borra los artefactos de un registro, incluidos restos de escritura."""
        for suffix in (
            "-original.png",
            "-result.png",
            ".json",
            "-original.png.tmp",
            "-result.png.tmp",
            ".json.tmp",
        ):
            self._path(record_id, suffix).unlink(missing_ok=True)
        self._remove_layers(record_id)

    def _remove_layers(self, record_id: str) -> None:
        for path in self.root.glob(f"{record_id}-layer-*.png*"):
            path.unlink(missing_ok=True)

    def _validate_id(self, record_id: str) -> None:
        if not ID_PATTERN.fullmatch(record_id):
            raise InspectionNotFound(f"Identificador inválido: {record_id!r}.")

    def _path(self, record_id: str, suffix: str) -> Path:
        return self.root / f"{record_id}{suffix}"

    def _atomic_write(self, path: Path, data: bytes) -> None:
        temporary = path.with_name(f"{path.name}.tmp")
        try:
            temporary.write_bytes(data)
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)
